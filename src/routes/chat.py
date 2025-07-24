import os
import pandas as pd
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, ChatHistory

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Endpoint para obter lista de conversas do usuário"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        
        # Buscar histórico do usuário
        history = ChatHistory.query.filter_by(user_id=current_user_id).first()
        
        if not history:
            return jsonify({'conversations': []}), 200
        
        # Ler arquivo CSV
        csv_path = os.path.join(current_app.config['UPLOAD_FOLDER'], history.csv_filename)
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Arquivo de histórico não encontrado'}), 404
        
        df = pd.read_csv(csv_path)
        
        # Agrupar por número de telefone para obter lista de conversas
        conversations = []
        for mobile_number in df['mobile_number'].unique():
            if pd.isna(mobile_number):
                continue
                
            contact_messages = df[df['mobile_number'] == mobile_number]
            last_message = contact_messages.iloc[-1]
            
            conversations.append({
                'mobile_number': mobile_number,
                'last_message': last_message['text'] if pd.notna(last_message['text']) else '',
                'last_message_date': last_message['message_created'],
                'message_count': len(contact_messages)
            })
        
        # Ordenar por data da última mensagem
        conversations.sort(key=lambda x: x['last_message_date'], reverse=True)
        
        return jsonify({'conversations': conversations}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/messages/<mobile_number>', methods=['GET'])
@jwt_required()
def get_messages(mobile_number):
    """Endpoint para obter mensagens de uma conversa específica"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        
        # Buscar histórico do usuário
        history = ChatHistory.query.filter_by(user_id=current_user_id).first()
        
        if not history:
            return jsonify({'messages': []}), 200
        
        # Ler arquivo CSV
        csv_path = os.path.join(current_app.config['UPLOAD_FOLDER'], history.csv_filename)
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Arquivo de histórico não encontrado'}), 404
        
        df = pd.read_csv(csv_path)
        
        # Filtrar mensagens do contato específico
        contact_messages = df[df['mobile_number'] == mobile_number]
        
        # Parâmetros de paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Calcular offset
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Aplicar paginação
        paginated_messages = contact_messages.iloc[start_idx:end_idx]
        
        messages = []
        for _, row in paginated_messages.iterrows():
            message = {
                'message_id': row['message_id'] if pd.notna(row['message_id']) else None,
                'fromMe': bool(row['fromMe']) if pd.notna(row['fromMe']) else False,
                'type': row['type'] if pd.notna(row['type']) else 'text',
                'direction': row['direction'] if pd.notna(row['direction']) else 'INCOMING',
                'text': row['text'] if pd.notna(row['text']) else '',
                'media': row['media'] if pd.notna(row['media']) else None,
                'message_created': row['message_created'] if pd.notna(row['message_created']) else None
            }
            messages.append(message)
        
        return jsonify({
            'messages': messages,
            'total_messages': len(contact_messages),
            'page': page,
            'per_page': per_page,
            'has_next': end_idx < len(contact_messages),
            'has_prev': page > 1
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/search', methods=['GET'])
@jwt_required()
def search_messages():
    """Endpoint para pesquisar mensagens"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'error': 'Termo de pesquisa é obrigatório'}), 400
        
        # Buscar histórico do usuário
        history = ChatHistory.query.filter_by(user_id=current_user_id).first()
        
        if not history:
            return jsonify({'results': []}), 200
        
        # Ler arquivo CSV
        csv_path = os.path.join(current_app.config['UPLOAD_FOLDER'], history.csv_filename)
        
        if not os.path.exists(csv_path):
            return jsonify({'error': 'Arquivo de histórico não encontrado'}), 404
        
        df = pd.read_csv(csv_path)
        
        # Pesquisar nas mensagens de texto
        text_matches = df[df['text'].str.contains(query, case=False, na=False)]
        
        # Pesquisar nos números de telefone
        phone_matches = df[df['mobile_number'].str.contains(query, case=False, na=False)]
        
        # Combinar resultados
        all_matches = pd.concat([text_matches, phone_matches]).drop_duplicates()
        
        results = []
        for _, row in all_matches.iterrows():
            result = {
                'mobile_number': row['mobile_number'] if pd.notna(row['mobile_number']) else '',
                'message_id': row['message_id'] if pd.notna(row['message_id']) else None,
                'text': row['text'] if pd.notna(row['text']) else '',
                'message_created': row['message_created'] if pd.notna(row['message_created']) else None,
                'fromMe': bool(row['fromMe']) if pd.notna(row['fromMe']) else False
            }
            results.append(result)
        
        # Ordenar por data
        results.sort(key=lambda x: x['message_created'] or '', reverse=True)
        
        return jsonify({'results': results[:100]}), 200  # Limitar a 100 resultados
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

