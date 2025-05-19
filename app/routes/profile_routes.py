#profile_route.py

from flask import Blueprint, request, jsonify
from app import db
from app.models import User
from app.utils.auth import token_required
from datetime import datetime

profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.route('/me', methods=['GET'])
@token_required
def get_profile(current_user_id):
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'date_of_birth': user.date_of_birth.strftime('%Y-%m-%d') if user.date_of_birth else None
    }), 200

@profile_bp.route('/update', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    data = request.get_json()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if 'username' in data:
        user.username = data['username']
    if 'email' in data:
        user.email = data['email']
    if 'phone' in data:
        user.phone = data['phone']
    if 'date_of_birth' in data:
        try:
            user.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    db.session.commit()
    return jsonify({'message': 'Profile updated successfully'}), 200
