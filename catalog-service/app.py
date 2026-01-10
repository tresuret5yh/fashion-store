"""
Сервис каталога товаров для магазина одежды и обуви.
Реализует CQRS для разделения операций чтения и записи.
"""
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://admin:password@localhost:5433/catalog_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Модель товара
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))  # одежда, обувь, аксессуары
    size = db.Column(db.String(10))  # S, M, L, XL, 42, 43, etc.
    color = db.Column(db.String(30))
    stock_quantity = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

# Команды (CQRS - Write operations)
@app.route('/api/v1/products', methods=['POST'])
def create_product():
    """Создание нового товара"""
    data = request.json
    product = Product(
        name=data['name'],
        description=data.get('description'),
        price=data['price'],
        category=data.get('category', 'clothing'),
        size=data.get('size'),
        color=data.get('color'),
        stock_quantity=data.get('stock_quantity', 0)
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({'id': product.id, 'message': 'Товар создан'}), 201

@app.route('/api/v1/products/<int:product_id>/stock', methods=['PUT'])
def update_stock(product_id):
    """Обновление количества товара на складе"""
    data = request.json
    product = Product.query.get_or_404(product_id)
    product.stock_quantity = data['quantity']
    db.session.commit()
    return jsonify({'message': 'Количество обновлено'}), 200

# Запросы (CQRS - Read operations)
@app.route('/api/v1/products', methods=['GET'])
def get_products():
    """Получение списка товаров с фильтрацией"""
    category = request.args.get('category')
    size = request.args.get('size')
    color = request.args.get('color')
    
    query = Product.query.filter_by(is_active=True)
    
    if category:
        query = query.filter_by(category=category)
    if size:
        query = query.filter_by(size=size)
    if color:
        query = query.filter_by(color=color)
    
    products = query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'category': p.category,
        'size': p.size,
        'color': p.color,
        'stock_quantity': p.stock_quantity
    } for p in products]), 200

@app.route('/api/v1/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Получение информации о конкретном товаре"""
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': product.price,
        'category': product.category,
        'size': product.size,
        'color': product.color,
        'stock_quantity': product.stock_quantity
    }), 200

# Circuit Breaker эндпоинт
@app.route('/api/v1/products/circuit-breaker', methods=['GET'])
def circuit_breaker_test():
    """
    Эндпоинт для демонстрации Circuit Breaker
    В реальном проекте здесь была бы интеграция с Hystrix или аналогичной библиотекой
    """
    import random
    import time
    
    # Симуляция случайных сбоев
    if random.random() < 0.3:  # 30% вероятность сбоя
        time.sleep(2)  # Имитация таймаута
        return jsonify({'error': 'Сервис временно недоступен'}), 503
    
    return jsonify({'status': 'OK', 'message': 'Circuit Breaker работает'}), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    return jsonify({'status': 'healthy', 'service': 'catalog-service'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)