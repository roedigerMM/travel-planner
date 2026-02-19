# app/models.py
from datetime import datetime
from .extensions import db


class Search(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    travel_month = db.Column(db.String(7), nullable=True)  # "YYYY-MM"
