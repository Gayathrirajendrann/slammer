import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'replace-with-a-better-secret'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
