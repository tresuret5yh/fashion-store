"""
Сервис управления запасами товаров.
Отвечает за контроль остатков на складе и резервирование товаров.
"""
from flask import Flask, request, jsonify
from kafka import KafkaProducer, KafkaConsumer
import json
import threading
import os
from datetime import datetime

app = Flask(__name__)

# Конфигурация Kafka
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')

# Инициализация продюсера Kafka
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Хранилище запасов (в памяти для упрощения)
# Формат: {product_id: {'quantity': 100, 'reserved': 0}}
inventory = {
    1: {'quantity': 50, 'reserved': 0, 'name': 'Джинсы Levi\'s'},
    2: {'quantity': 30, 'reserved': 0, 'name': 'Футболка Nike'},
    3: {'quantity': 25, 'reserved': 0, 'name': 'Кроссовки Adidas'},
    4: {'quantity': 40, 'reserved': 0, 'name': 'Куртка зимняя'},
    5: {'quantity': 60, 'reserved': 0, 'name': 'Рубашка офисная'}
}

# Блокировка для потокобезопасности
from threading import Lock
inventory_lock = Lock()

def process_inventory_events():
    """Обработка событий инвентаря из Kafka"""
    consumer = KafkaConsumer(
        'inventory-check',
        'inventory-compensate',
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='inventory-service-group'
    )
    
    for message in consumer:
        event = message.value
        action = event.get('action')
        saga_id = event.get('saga_id')
        
        print(f"Получено событие инвентаря: {action} для Saga {saga_id}")
        
        if action == 'CHECK_INVENTORY':
            # Проверка и резервирование товаров
            result = check_and_reserve_inventory(event.get('items', []), saga_id)
            
            # Отправка ответа
            producer.send('saga-responses', {
                'saga_id': saga_id,
                'service': 'inventory-service',
                'status': result['status'],
                'message': result['message'],
                'details': result.get('details')
            })
            
        elif action == 'RESTORE_INVENTORY':
            # Компенсирующая транзакция - отмена резервирования
            result = restore_inventory(event.get('items', []), saga_id)
            
            producer.send('saga-responses', {
                'saga_id': saga_id,
                'service': 'inventory-service',
                'status': result['status'],
                'message': result['message']
            })

def check_and_reserve_inventory(items, saga_id):
    """
    Проверка наличия и резервирование товаров.
    Возвращает результат операции.
    """
    with inventory_lock:
        # Проверяем наличие всех товаров
        unavailable_items = []
        
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            
            if product_id not in inventory:
                unavailable_items.append({
                    'product_id': product_id,
                    'reason': 'Товар не найден'
                })
            elif inventory[product_id]['quantity'] - inventory[product_id]['reserved'] < quantity:
                unavailable_items.append({
                    'product_id': product_id,
                    'available': inventory[product_id]['quantity'] - inventory[product_id]['reserved'],
                    'requested': quantity,
                    'reason': 'Недостаточно товара на складе'
                })
        
        if unavailable_items:
            return {
                'status': 'INVENTORY_INSUFFICIENT',
                'message': 'Недостаточно товаров на складе',
                'details': {'unavailable_items': unavailable_items}
            }
        
        # Резервируем товары
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            inventory[product_id]['reserved'] += quantity
        
        print(f"Товары зарезервированы для Saga {saga_id}")
        
        return {
            'status': 'INVENTORY_RESERVED',
            'message': 'Товары успешно зарезервированы',
            'details': {
                'saga_id': saga_id,
                'reserved_at': datetime.now().isoformat()
            }
        }

def restore_inventory(items, saga_id):
    """Отмена резервирования товаров (компенсирующая транзакция)"""
    with inventory_lock:
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            
            if product_id in inventory:
                inventory[product_id]['reserved'] = max(
                    0, inventory[product_id]['reserved'] - quantity
                )
        
        print(f"Резервирование отменено для Saga {saga_id}")
        
        return {
            'status': 'INVENTORY_RESTORED',
            'message': 'Резервирование товаров отменено'
        }

# REST API для ручного управления запасами
@app.route('/api/v1/inventory', methods=['GET'])
def get_inventory():
    """Получение информации о всех запасах"""
    inventory_list = []
    for product_id, data in inventory.items():
        inventory_list.append({
            'product_id': product_id,
            'name': data.get('name', 'Неизвестный товар'),
            'total_quantity': data['quantity'],
            'reserved': data['reserved'],
            'available': data['quantity'] - data['reserved']
        })
    
    return jsonify({
        'total_items': len(inventory_list),
        'inventory': inventory_list
    }), 200

@app.route('/api/v1/inventory/<int:product_id>', methods=['GET'])
def get_product_inventory(product_id):
    """Получение информации о запасах конкретного товара"""
    if product_id not in inventory:
        return jsonify({'error': 'Товар не найден'}), 404
    
    data = inventory[product_id]
    return jsonify({
        'product_id': product_id,
        'name': data.get('name', 'Неизвестный товар'),
        'total_quantity': data['quantity'],
        'reserved': data['reserved'],
        'available': data['quantity'] - data['reserved']
    }), 200

@app.route('/api/v1/inventory/<int:product_id>/stock', methods=['PUT'])
def update_stock(product_id):
    """Обновление количества товара на складе"""
    data = request.json
    
    if 'quantity' not in data:
        return jsonify({'error': 'Требуется поле quantity'}), 400
    
    with inventory_lock:
        if product_id not in inventory:
            # Создаем новый товар
            inventory[product_id] = {
                'quantity': data['quantity'],
                'reserved': 0,
                'name': data.get('name', f'Товар {product_id}')
            }
        else:
            inventory[product_id]['quantity'] = data['quantity']
    
    return jsonify({
        'message': 'Запас товара обновлен',
        'product_id': product_id,
        'new_quantity': data['quantity']
    }), 200

@app.route('/api/v1/inventory/check', methods=['POST'])
def check_availability():
    """Проверка доступности товаров (синхронный эндпоинт)"""
    data = request.json
    
    if 'items' not in data:
        return jsonify({'error': 'Требуется поле items'}), 400
    
    result = check_and_reserve_inventory(data['items'], 'direct-api-call')
    
    return jsonify(result), 200

@app.route('/api/v1/inventory/reserve', methods=['POST'])
def reserve_items():
    """Резервирование товаров (синхронный эндпоинт)"""
    data = request.json
    
    if 'items' not in data or 'reservation_id' not in data:
        return jsonify({'error': 'Требуется поля items и reservation_id'}), 400
    
    with inventory_lock:
        # Проверяем доступность
        unavailable_items = []
        
        for item in data['items']:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            
            if product_id not in inventory:
                unavailable_items.append({
                    'product_id': product_id,
                    'reason': 'Товар не найден'
                })
            elif inventory[product_id]['quantity'] - inventory[product_id]['reserved'] < quantity:
                unavailable_items.append({
                    'product_id': product_id,
                    'available': inventory[product_id]['quantity'] - inventory[product_id]['reserved'],
                    'requested': quantity,
                    'reason': 'Недостаточно товара'
                })
        
        if unavailable_items:
            return jsonify({
                'status': 'failed',
                'message': 'Недостаточно товаров',
                'unavailable_items': unavailable_items
            }), 400
        
        # Резервируем
        for item in data['items']:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            inventory[product_id]['reserved'] += quantity
    
    return jsonify({
        'status': 'success',
        'message': 'Товары зарезервированы',
        'reservation_id': data['reservation_id'],
        'reserved_at': datetime.now().isoformat()
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    total_items = sum(data['quantity'] for data in inventory.values())
    reserved_items = sum(data['reserved'] for data in inventory.values())
    
    return jsonify({
        'status': 'healthy',
        'service': 'inventory-service',
        'total_products': len(inventory),
        'total_items': total_items,
        'reserved_items': reserved_items,
        'available_items': total_items - reserved_items
    }), 200

if __name__ == '__main__':
    # Запуск обработчика событий Kafka в отдельном потоке
    kafka_thread = threading.Thread(target=process_inventory_events, daemon=True)
    kafka_thread.start()
    
    app.run(host='0.0.0.0', port=5004, debug=True)