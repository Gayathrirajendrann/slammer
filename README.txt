Rajamatha's Family - Ready-to-run Flask project
-----------------------------------------------

How to run:
1. Create and activate a virtual environment:
   python -m venv venv
   # Windows: venv\Scripts\activate
   # Linux/Mac: source venv/bin/activate

2. Install requirements:
   pip install -r requirements.txt

3. Run the app (first run will auto-seed users into SQLite DB):
   python app.py

4. Open in browser:
   http://127.0.0.1:5000/

Notes:
- Default users seeded from data_init.py (63 members).
- First time a user logs in with their email they'll be prompted to set a password.
- PDFs generated use ReportLab.
- If you want the DB pre-created, run the app once then copy the 'rajamathsfamily.db' file.

Enjoy!
