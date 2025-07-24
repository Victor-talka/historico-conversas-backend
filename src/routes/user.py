import os
from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from src.models.user import User, ChatHistory, db

user_bp = Blueprint('user', __name__)

def admin_required(f):
    """Decorator para verificar se o usuário é admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        if not user or not user.is_admin:
            return jsonify({'error': 'Acesso negado. Apenas administradores podem acessar este recurso.'}), 403
        return f(*args, **kwargs)
    return decorated_function

@user_bp.route('/', methods=['GET'])
@jwt_required()
@admin_required
def get_users():
    """Listar todos os usuários (apenas admin)"""
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/', methods=['POST'])
@jwt_required()
@admin_required
def create_user():
    """Criar novo usuário (apenas admin)"""
    try:
        data = request.form
        file = request.files.get('csv_file')
        
        if not data.get('phone_number') or not data.get('password'):
            return jsonify({'error': 'Número de telefone e senha são obrigatórios'}), 400
        
        if not file or file.filename == '':
            return jsonify({'error': 'Arquivo CSV é obrigatório'}), 400
        
        # Verificar se usuário já existe
        existing_user = User.query.filter_by(phone_number=data['phone_number']).first()
        if existing_user:
            return jsonify({'error': 'Usuário com este número de telefone já existe'}), 400
        
        # Criar usuário
        user = User(
            phone_number=data['phone_number'],
            is_admin=data.get('is_admin', 'false').lower() == 'true'
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # Para obter o ID do usuário
        
        # Salvar arquivo CSV
        filename = secure_filename(f"user_{user.id}_{file.filename}")
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Criar registro de histórico
        history = ChatHistory(
            user_id=user.id,
            csv_filename=filename
        )
        
        db.session.add(history)
        db.session.commit()
        
        return jsonify(user.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_user(user_id):
    """Obter usuário específico (apenas admin)"""
    try:
        user = User.query.get_or_404(user_id)
        return jsonify(user.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user(user_id):
    """Atualizar usuário (apenas admin)"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        if 'phone_number' in data:
            # Verificar se o novo número não está em uso por outro usuário
            existing_user = User.query.filter_by(phone_number=data['phone_number']).first()
            if existing_user and existing_user.id != user_id:
                return jsonify({'error': 'Número de telefone já está em uso'}), 400
            user.phone_number = data['phone_number']
        
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
        
        db.session.commit()
        return jsonify(user.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    """Deletar usuário (apenas admin)"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Deletar arquivos CSV associados
        for history in user.histories:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], history.csv_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(user)
        db.session.commit()
        
        return '', 204
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/<int:user_id>/upload-csv', methods=['POST'])
@jwt_required()
@admin_required
def upload_csv(user_id):
    """Upload de novo arquivo CSV para usuário (apenas admin)"""
    try:
        user = User.query.get_or_404(user_id)
        file = request.files.get('csv_file')
        
        if not file or file.filename == '':
            return jsonify({'error': 'Arquivo CSV é obrigatório'}), 400
        
        # Deletar histórico anterior se existir
        old_history = ChatHistory.query.filter_by(user_id=user_id).first()
        if old_history:
            old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_history.csv_filename)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
            db.session.delete(old_history)
        
        # Salvar novo arquivo
        filename = secure_filename(f"user_{user_id}_{file.filename}")
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Criar novo registro de histórico
        history = ChatHistory(
            user_id=user_id,
            csv_filename=filename
        )
        
        db.session.add(history)
        db.session.commit()
        
        return jsonify({'message': 'Arquivo CSV atualizado com sucesso'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
