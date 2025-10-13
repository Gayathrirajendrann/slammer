# app.py
from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import os

# -------------------- FLASK APP & DATABASE --------------------
app = Flask(__name__)

# Secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'replace-with-a-better-secret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# PostgreSQL Database URL (must be set as environment variable)
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("❌ DATABASE_URL environment variable not set! Example: postgresql://user:pass@localhost:5432/dbname")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

db = SQLAlchemy(app)
print("Using database:", app.config['SQLALCHEMY_DATABASE_URI'])


# -------------------- MODELS --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='given_feedbacks')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_feedbacks')


# -------------------- HELPERS --------------------
def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)


# -------------------- DATABASE INIT & SEED --------------------
def init_db():
    from data_init import seed_users
    with app.app_context():
        db.create_all()
        if User.query.count() == 0:
            seed_users(db, User)
            print("✅ Database initialized and users seeded.")


# Initialize DB on startup
init_db()


# -------------------- ROUTES --------------------
@app.route('/')
def splash():
    return render_template('splash.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# -------------------- AUTH --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email not recognized. Please use an email from the class list.", "danger")
            return redirect(url_for('login'))

        if not user.password_hash:
            session['pre_user_id'] = user.id
            return redirect(url_for('set_password'))

        password = request.form.get('password', '')
        if user.check_password(password):
            session['user_id'] = user.id
            flash(f"Welcome, {user.name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Incorrect password.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/set-password', methods=['GET', 'POST'])
def set_password():
    pre_id = session.get('pre_user_id')
    if not pre_id:
        flash("No email selected. Start from login.", "warning")
        return redirect(url_for('login'))

    user = User.query.get(pre_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        p1 = request.form.get('password')
        p2 = request.form.get('confirm_password')
        if not p1 or p1 != p2:
            flash("Passwords empty or don't match.", "danger")
            return redirect(url_for('set_password'))

        user.set_password(p1)
        db.session.commit()
        session.pop('pre_user_id', None)
        session['user_id'] = user.id
        flash("Password set! Logged in.", "success")
        return redirect(url_for('dashboard'))

    return render_template('set_password.html', user=user)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Logged out.", "info")
    return redirect(url_for('login'))


# -------------------- DASHBOARD --------------------
@app.route('/dashboard')
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=user)


# -------------------- FEEDBACK --------------------
@app.route('/give-feedback', methods=['GET', 'POST'])
def give_feedback():
    user = current_user()
    if not user:
        return redirect(url_for('login'))

    users = User.query.order_by(User.name).all()
    recipients = [u for u in users if u.id != user.id]

    if request.method == 'POST':
        recipient_id = int(request.form.get('recipient_id'))
        content = request.form.get('content', '').strip()
        visible = bool(request.form.get('visible'))

        if not content:
            flash("Feedback cannot be empty.", "danger")
            return redirect(url_for('give_feedback'))

        existing = Feedback.query.filter_by(sender_id=user.id, recipient_id=recipient_id).first()
        if existing:
            existing.content = content
            existing.visible = visible
            flash("Feedback updated!", "success")
        else:
            f = Feedback(sender_id=user.id, recipient_id=recipient_id, content=content, visible=visible)
            db.session.add(f)
            flash("Feedback sent!", "success")

        db.session.commit()
        return redirect(url_for('give_feedback'))

    feedback_map = {f.recipient_id: f for f in user.given_feedbacks}

    return render_template(
        'give_feedback.html',
        user=user,
        recipients=recipients,
        feedback_map=feedback_map
    )


@app.route('/view-feedback')
def view_feedback():
    user = current_user()
    if not user:
        return redirect(url_for('login'))

    given = Feedback.query.filter_by(sender_id=user.id).order_by(Feedback.created_at.desc()).all()
    received = Feedback.query.filter_by(recipient_id=user.id).order_by(Feedback.created_at.desc()).all()
    return render_template('view_feedback.html', user=user, given=given, received=received)



#------------------------------------
@app.route('/download-given-pdf')  # The URL for this route
def download_given_pdf():           # The function name is also the endpoint name
    user = current_user()           # Get the logged-in user
    if not user:
        return redirect(url_for('login'))

    # Get all feedbacks the user gave
    given = Feedback.query.filter_by(sender_id=user.id).order_by(Feedback.created_at.desc()).all()

    # Create a PDF in memory
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"Feedbacks Given by {user.name}")
    y -= 40

    c.setFont("Helvetica", 12)
    for f in given:
        recipient_name = f.recipient.name
        content = f.content
        created_at = f.created_at.strftime("%Y-%m-%d %H:%M")
        line = f"To {recipient_name} ({created_at}): {content}"
        c.drawString(50, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            y = height - 50

    c.save()
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="given_feedbacks.pdf",
        mimetype="application/pdf"
    )

#-------------------------------
@app.route('/download-received-pdf')
def download_received_pdf():
    user = current_user()
    if not user:
        return redirect(url_for('login'))

    # Get all feedbacks received
    received = Feedback.query.filter_by(recipient_id=user.id).order_by(Feedback.created_at.desc()).all()

    # Create a PDF in memory
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"Feedbacks Received by {user.name}")
    y -= 40

    c.setFont("Helvetica", 12)
    for f in received:
        sender_name = f.sender.name if f.sender else "Unknown"
        content = f.content
        created_at = f.created_at.strftime("%Y-%m-%d %H:%M")
        line = f"From {sender_name} ({created_at}): {content}"
        c.drawString(50, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            y = height - 50

    c.save()
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="received_feedbacks.pdf",
        mimetype="application/pdf"
    )
#--------------------------------------
@app.route('/add-sridevi-final')
def add_sridevi_final():
    # Check if Sridevi already exists
    user = User.query.filter_by(email="sridevi-aid@saranathan.ac.in").first()
    if user:
        return f"✅ Sridevi already exists: {user.id} - {user.name}"

    # Add Sridevi
    new_user = User(
        name="A.SRIDEVI MAM (RAJAMATHA)",
        email="sridevi-aid@saranathan.ac.in"
    )
    db.session.add(new_user)
    db.session.commit()
    return f"✅ Added Sridevi: {new_user.id} - {new_user.name}"
#-----------------------------------------------
@app.route('/all-users')
def all_users():
    users = User.query.order_by(User.name).all()
    return "<br>".join(f"{u.id} - {u.name} ({u.email})" for u in users)



# -------------------- MAIN --------------------
if __name__ == '__main__':
    app.run(debug=True)
