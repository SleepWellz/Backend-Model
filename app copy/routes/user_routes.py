from flask import Blueprint, jsonify
from app.utils.auth import token_required  # Pakai token_required untuk otentikasi
from app import db
from sqlalchemy.sql import func
from app.models import Deteksi

user_routes = Blueprint('user_routes', __name__)

# Endpoint untuk mendapatkan summary user (total deteksi, deteksi terakhir, dan status apnea tertinggi)
@user_routes.route('/summary', methods=['GET'])
@token_required
def get_user_summary(user_id):  # menerima user_id dari decorator
    try:
        # Menghitung jumlah deteksi
        total = db.session.query(func.count(Deteksi.id)).filter_by(user_id=user_id).scalar()

        # Mengambil deteksi terakhir berdasarkan created_at
        terakhir = db.session.query(func.max(Deteksi.created_at)).filter_by(user_id=user_id).scalar()

        # Mengambil status apnea tertinggi (status apnea terakhir)
        tertinggi = db.session.query(func.max(Deteksi.apnea_status)).filter_by(user_id=user_id).scalar()

        # Mengembalikan data summary dalam bentuk JSON
        return jsonify({
            "totalDeteksi": total,
            "terakhir": terakhir.strftime("%d %B %Y") if terakhir else "-",
            "apneaStatus": tertinggi if tertinggi else "-"  # Mengganti skor tertinggi dengan status apnea
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Gagal mengambil ringkasan deteksi"}), 500


# Endpoint untuk mendapatkan riwayat deteksi (semua deteksi yang dilakukan oleh user)
@user_routes.route('/history', methods=['GET'])
@token_required
def get_user_history(user_id):
    try:
        # Mengambil riwayat deteksi berdasarkan user_id
        deteksi_list = Deteksi.query.filter_by(user_id=user_id).all()

        # Menyiapkan list deteksi dengan data yang dibutuhkan
        history = [
            {
                "created_at": deteksi.created_at.strftime("%d %B %Y"),
                "apnea_status": deteksi.apnea_status
            }
            for deteksi in deteksi_list
        ]

        # Mengembalikan history dalam bentuk JSON
        return jsonify({"history": history})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Gagal mengambil riwayat deteksi"}), 500
