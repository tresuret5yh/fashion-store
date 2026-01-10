"""
Сервис аутентификации и авторизации.
Управляет пользователями, JWT токенами и правами доступа.
"""
from flask import Flask, request, jsonify
import jwt
import datetime
from functools import wraps
import hashlib
import os

app = Flask(__name__)

# Конфигурация
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fashion-store-secret-key-2024')
app.config['TOKEN_EXPIRATION_HOURS'] = 24

# Хранилище пользователей (в памяти для упрощения)
# В реальном проекте использовалась бы база данных
users = {
    'admin': {
        'password': hashlib.sha256('admin123'.encode()).hexdigest(),  # Хешированный пароль
        'role': 'admin',
        'email': 'admin@fashionstore.com',
        'full_name': 'Администратор Системы'
    },
    'customer1': {
        'password': hashlib.sha256('customer123'.encode()).hexdigest(),
        'role': 'customer',
        'email': 'customer@example.com',
        'full_name': 'Иван Петров'
    }
}

# Декоратор для проверки JWT токена
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Проверяем заголовок Authorization
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'error': 'Токен отсутствует'}), 401
        
        try:
            # Декодируем токен
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Срок действия токена истек'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Неверный токен'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# Декоратор для проверки ролей
def roles_required(*required_roles):
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            user_role = users.get(current_user, {}).get('role')
            if user_role not in required_roles:
                return jsonify({'error': 'Недостаточно прав'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return decorator

@app.route('/api/v1/auth/register', methods=['POST'])
def register():
    """Регистрация нового пользователя"""
    data = request.json
    
    required_fields = ['username', 'password', 'email', 'full_name']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Отсутствует поле: {field}'}), 400
    
    username = data['username']
    if username in users:
        return jsonify({'error': 'Пользователь уже существует'}), 409
    
    # Хеширование пароля
    hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()
    
    # Создание пользователя
    users[username] = {
        'password': hashed_password,
        'role': data.get('role', 'customer'),
        'email': data['email'],
        'full_name': data['full_name']
    }
    
    return jsonify({
        'message': 'Пользователь успешно зарегистрирован',
        'username': username
    }), 201

@app.route('/api/v1/auth/login', methods=['POST'])
def login():
    """Аутентификация пользователя и выдача JWT токена"""
    data = request.json
    
    if 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Требуется имя пользователя и пароль'}), 400
    
    username = data['username']
    password = data['password']
    
    # Проверка существования пользователя
    if username not in users:
        return jsonify({'error': 'Неверные учетные данные'}), 401
    
    # Проверка пароля
    hashed_input_password = hashlib.sha256(password.encode()).hexdigest()
    if users[username]['password'] != hashed_input_password:
        return jsonify({'error': 'Неверные учетные данные'}), 401
    
    # Создание JWT токена
    token_payload = {
        'username': username,
        'role': users[username]['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(
            hours=app.config['TOKEN_EXPIRATION_HOURS']
        )
    }
    
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
    
    # Возврат информации о пользователе без пароля
    user_info = {
        'username': username,
        'role': users[username]['role'],
        'email': users[username]['email'],
        'full_name': users[username]['full_name']
    }
    
    return jsonify({
        'token': token,
        'user': user_info,
        'expires_in': app.config['TOKEN_EXPIRATION_HOURS'] * 3600  # в секундах
    }), 200

@app.route('/api/v1/auth/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    """Проверка валидности токена"""
    user_info = {
        'username': current_user,
        'role': users[current_user]['role'],
        'email': users[current_user]['email'],
        'full_name': users[current_user]['full_name']
    }
    
    return jsonify({
        'valid': True,
        'user': user_info
    }), 200

@app.route('/api/v1/auth/users/<username>', methods=['GET'])
@token_required
@roles_required('admin')
def get_user(current_user, username):
    """Получение информации о пользователе (только для администраторов)"""
    if username not in users:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    user_info = {
        'username': username,
        'role': users[username]['role'],
        'email': users[username]['email'],
        'full_name': users[username]['full_name']
    }
    
    return jsonify(user_info), 200

@app.route('/api/v1/auth/users', methods=['GET'])
@token_required
@roles_required('admin')
def list_users(current_user):
    """Получение списка всех пользователей (только для администраторов)"""
    users_list = []
    for username, user_data in users.items():
        users_list.append({
            'username': username,
            'role': user_data['role'],
            'email': user_data['email'],
            'full_name': user_data['full_name']
        })
    
    return jsonify({
        'total': len(users_list),
        'users': users_list
    }), 200

@app.route('/api/v1/auth/users/<username>/role', methods=['PUT'])
@token_required
@roles_required('admin')
def update_user_role(current_user, username):
    """Обновление роли пользователя (только для администраторов)"""
    if username not in users:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.json
    if 'role' not in data:
        return jsonify({'error': 'Требуется поле role'}), 400
    
    allowed_roles = ['admin', 'customer', 'manager']
    if data['role'] not in allowed_roles:
        return jsonify({'error': f'Роль должна быть одной из: {allowed_roles}'}), 400
    
    users[username]['role'] = data['role']
    
    return jsonify({
        'message': 'Роль пользователя обновлена',
        'username': username,
        'new_role': data['role']
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    return jsonify({
        'status': 'healthy',
        'service': 'auth-service',
        'users_count': len(users)
    }), 200

@app.route('/api/v1/auth/circuit-breaker', methods=['GET'])
def circuit_breaker_test():
    """
    Эндпоинт для демонстрации Circuit Breaker.
    Имитирует сбои для тестирования устойчивости системы.
    """
    import random
    import time
    
    # Симуляция случайных сбоев (20% вероятность)
    if random.random() < 0.2:
        # Имитация задержки
        time.sleep(3)
        return jsonify({
            'status': 'error',
            'message': 'Сервис временно недоступен',
            'circuit_breaker': 'OPEN'
        }), 503
    
    # Нормальная работа
    return jsonify({
        'status': 'ok',
        'message': 'Сервис работает нормально',
        'circuit_breaker': 'CLOSED'
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)