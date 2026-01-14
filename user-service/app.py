"""
Сервис управления профилями пользователей.
Хранит и управляет персональными данными: имя, email, адрес, телефон и т.д.
Не отвечает за аутентификацию — только за данные профиля.
"""
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram
import os
import time

app = Flask(__name__)

# === Метрики Prometheus ===
REQUEST_COUNT = Counter('user_requests_total', 'Total user service requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('user_request_duration_seconds', 'Request duration')

# === База данных ===
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql://admin:password@localhost:5432/fashion_store'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === Модель пользователя ===
class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    user_id = db.Column(db.String(50), primary_key=True)  # совпадает с username из auth-service
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

# === Эндпоинты ===

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/api/v1/users/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    REQUEST_COUNT.labels(method='GET', endpoint='/users/<id>').inc()
    start = time.time()
    try:
        profile = UserProfile.query.get(user_id)
        if not profile:
            return jsonify({'error': 'Профиль не найден'}), 404
        return jsonify({
            'user_id': profile.user_id,
            'full_name': profile.full_name,
            'email': profile.email,
            'phone': profile.phone,
            'address': profile.address,
            'city': profile.city,
            'country': profile.country,
            'postal_code': profile.postal_code,
            'created_at': profile.created_at.isoformat(),
            'updated_at': profile.updated_at.isoformat()
        }), 200
    finally:
        REQUEST_LATENCY.observe(time.time() - start)

@app.route('/api/v1/users/<user_id>', methods=['PUT'])
def update_user_profile(user_id):
    REQUEST_COUNT.labels(method='PUT', endpoint='/users/<id>').inc()
    start = time.time()
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Требуется JSON тело запроса'}), 400

        profile = UserProfile.query.get(user_id)
        if not profile:
            # Создаём профиль, если его нет (например, после регистрации в auth-service)
            profile = UserProfile(user_id=user_id)

        # Обновляем поля
        profile.full_name = data.get('full_name', profile.full_name)
        profile.email = data.get('email', profile.email)
        profile.phone = data.get('phone', profile.phone)
        profile.address = data.get('address', profile.address)
        profile.city = data.get('city', profile.city)
        profile.country = data.get('country', profile.country)
        profile.postal_code = data.get('postal_code', profile.postal_code)

        db.session.add(profile)
        db.session.commit()

        return jsonify({
            'message': 'Профиль обновлён',
            'user_id': profile.user_id
        }), 200
    finally:
        REQUEST_LATENCY.observe(time.time() - start)

@app.route('/api/v1/users/<user_id>', methods=['POST'])
def create_user_profile(user_id):
    """Создание профиля (альтернативный способ, например, при миграции)"""
    REQUEST_COUNT.labels(method='POST', endpoint='/users/<id>').inc()
    start = time.time()
    try:
        data = request.json
        required_fields = ['full_name', 'email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Обязательное поле: {field}'}), 400

        if UserProfile.query.get(user_id):
            return jsonify({'error': 'Профиль уже существует'}), 409

        profile = UserProfile(
            user_id=user_id,
            full_name=data['full_name'],
            email=data['email'],
            phone=data.get('phone'),
            address=data.get('address'),
            city=data.get('city'),
            country=data.get('country'),
            postal_code=data.get('postal_code')
        )
        db.session.add(profile)
        db.session.commit()

        return jsonify({
            'message': 'Профиль создан',
            'user_id': profile.user_id
        }), 201
    finally:
        REQUEST_LATENCY.observe(time.time() - start)

@app.route('/health', methods=['GET'])
def health_check():
    # Проверка подключения к БД
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'ok'
    except Exception as e:
        db_status = f'error: {str(e)}'

    return jsonify({
        'status': 'healthy',
        'service': 'user-service',
        'database': db_status,
        'profiles_count': UserProfile.query.count()
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5007, debug=True)