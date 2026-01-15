"""
Сервис отзывов.
Позволяет пользователям оставлять отзывы и оценки на товары.
"""
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram
import os
import time

app = Flask(__name__)

# Метрики Prometheus
REQUEST_COUNT = Counter('review_requests_total', 'Total review requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('review_request_duration_seconds', 'Request duration')

# База данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql://admin:password@localhost:5432/fashion_store'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1–5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

# Основные эндпоинты (множественное число) - для прямого доступа
@app.route('/api/v1/reviews', methods=['POST'])
def create_review():
    """Создание отзыва (множественное число)"""
    REQUEST_COUNT.labels(method='POST', endpoint='/reviews').inc()
    start = time.time()
    try:
        data = request.json
        if not all(k in data for k in ('product_id', 'user_id', 'rating')):
            return jsonify({'error': 'Требуются: product_id, user_id, rating'}), 400
        if not (1 <= data['rating'] <= 5):
            return jsonify({'error': 'Оценка должна быть от 1 до 5'}), 400

        review = Review(
            product_id=data['product_id'],
            user_id=data['user_id'],
            rating=data['rating'],
            comment=data.get('comment', '')
        )
        db.session.add(review)
        db.session.commit()

        return jsonify({
            'id': review.id,
            'message': 'Отзыв добавлен'
        }), 201
    finally:
        REQUEST_LATENCY.observe(time.time() - start)

@app.route('/api/v1/reviews/product/<int:product_id>', methods=['GET'])
def get_reviews_by_product(product_id):
    """Получение отзывов по товару (множественное число)"""
    REQUEST_COUNT.labels(method='GET', endpoint='/reviews/product').inc()
    start = time.time()
    try:
        reviews = Review.query.filter_by(product_id=product_id).all()
        avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
        return jsonify({
            'product_id': product_id,
            'average_rating': round(avg_rating, 2),
            'total_reviews': len(reviews),
            'reviews': [
                {
                    'id': r.id,
                    'user_id': r.user_id,
                    'rating': r.rating,
                    'comment': r.comment,
                    'created_at': r.created_at.isoformat()
                } for r in reviews
            ]
        }), 200
    finally:
        REQUEST_LATENCY.observe(time.time() - start)

# Эндпоинты для API Gateway (единственное число)
@app.route('/api/v1/review', methods=['POST'])
def create_review_gateway():
    """Создание отзыва через API Gateway (единственное число)"""
    return create_review()

@app.route('/api/v1/review/', methods=['POST'])
def create_review_gateway_with_slash():
    """Создание отзыва через API Gateway (с trailing slash)"""
    return create_review()

@app.route('/api/v1/review/product/<int:product_id>', methods=['GET'])
def get_reviews_by_product_gateway(product_id):
    """Получение отзывов по товару через API Gateway (единственное число)"""
    return get_reviews_by_product(product_id)

@app.route('/api/v1/review/product/<int:product_id>/', methods=['GET'])
def get_reviews_by_product_gateway_with_slash(product_id):
    """Получение отзывов по товару через API Gateway (с trailing slash)"""
    return get_reviews_by_product(product_id)

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    try:
        # Проверка подключения к БД
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    reviews_count = Review.query.count()
    
    return jsonify({
        'status': 'healthy',
        'service': 'review-service',
        'database': db_status,
        'reviews_count': reviews_count,
        'endpoints': {
            'create_review': '/api/v1/review (POST)',
            'get_reviews': '/api/v1/review/product/<id> (GET)'
        }
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Создаем тестовые данные, если таблица пуста
        if Review.query.count() == 0:
            test_reviews = [
                Review(product_id=1, user_id='customer1', rating=5, comment='Отличный товар!'),
                Review(product_id=1, user_id='customer2', rating=4, comment='Хорошее качество'),
                Review(product_id=2, user_id='customer1', rating=3, comment='Нормально'),
                Review(product_id=3, user_id='customer2', rating=5, comment='Супер!'),
            ]
            db.session.add_all(test_reviews)
            db.session.commit()
            print(f"Создано {len(test_reviews)} тестовых отзывов")
    
    print("Review Service запущен")
    print("Доступные эндпоинты:")
    print("- POST /api/v1/reviews - Создать отзыв (прямой доступ)")
    print("- POST /api/v1/review - Создать отзыв (через Gateway)")
    print("- GET /api/v1/reviews/product/<id> - Получить отзывы товара (прямой доступ)")
    print("- GET /api/v1/review/product/<id> - Получить отзывы товара (через Gateway)")
    print("- GET /health - Проверка здоровья")
    print("- GET /metrics - Метрики Prometheus")
    
    app.run(host='0.0.0.0', port=5006, debug=True)