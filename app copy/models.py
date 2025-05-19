from app import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')

    # ➕ Tambahan untuk profile
    phone = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)

    # Relasi ke tabel Deteksi
    deteksi = db.relationship('Deteksi', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.username} - {self.role}>"

class Deteksi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    apnea_status = db.Column(db.String(20))  # Menyimpan status "apnea" atau "normal"

    def __repr__(self):
        return f"<Deteksi User:{self.user_id} Status:{self.apnea_status}>"
