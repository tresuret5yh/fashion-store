"""
Сервис обработки заказов с использованием паттерна Saga.
Координирует распределенную транзакцию между несколькими сервисами.
"""
from flask import Flask, request, jsonify
import json
import uuid
from kafka import KafkaProducer
import threading
import os
import time

app = Flask(__name__)

# Конфигурация Kafka с меньшим размером сообщений
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')

# Инициализация продюсера Kafka с правильной конфигурацией
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    max_request_size=10485760,  # 10MB вместо 100MB
    batch_size=16384,  # Уменьшаем размер батча
    linger_ms=0  # Отправляем сразу
)

# Состояния Saga
SAGA_STATES = {
    'PENDING': 'ожидание',
    'INVENTORY_CHECKED': 'проверен запас',
    'PAYMENT_PROCESSED': 'оплата обработана',
    'COMPLETED': 'завершено',
    'FAILED': 'ошибка',
    'COMPENSATING': 'компенсация'
}

# Хранилище заказов (в памяти для упрощения)
orders = {}

# Saga шаги
class OrderSaga:
    def __init__(self, order_id, user_id, items):
        self.order_id = order_id
        self.user_id = user_id
        self.items = items
        self.state = 'PENDING'
        self.compensation_steps = []
        
    def execute(self):
        """Выполнение Saga"""
        try:
            # Шаг 1: Проверка наличия товара
            self._check_inventory()
            time.sleep(1)  # Небольшая задержка
            
            # Шаг 2: Обработка платежа
            self._process_payment()
            time.sleep(1)
            
            # Шаг 3: Завершение заказа
            self._complete_order()
            
        except Exception as e:
            print(f"Ошибка в Saga {self.order_id}: {e}")
            # Запуск компенсирующих транзакций
            self._compensate()
    
    def _check_inventory(self):
        """Проверка наличия товаров на складе"""
        print(f"Проверка запасов для заказа {self.order_id}")
        
        # Отправка сообщения в inventory-service
        producer.send('inventory-check', {
            'saga_id': self.order_id,
            'action': 'CHECK_INVENTORY',
            'items': self.items,
            'timestamp': time.time()
        })
        
        self.state = 'INVENTORY_CHECKED'
        self.compensation_steps.append('compensate_inventory')
        orders[self.order_id] = self.__dict__
    
    def _process_payment(self):
        """Обработка платежа"""
        print(f"Обработка платежа для заказа {self.order_id}")
        
        # Отправка сообщения в payment-service
        producer.send('payment-process', {
            'saga_id': self.order_id,
            'action': 'PROCESS_PAYMENT',
            'user_id': self.user_id,
            'amount': sum(item.get('price', 0) * item.get('quantity', 1) for item in self.items),
            'timestamp': time.time()
        })
        
        self.state = 'PAYMENT_PROCESSED'
        self.compensation_steps.append('compensate_payment')
        orders[self.order_id] = self.__dict__
    
    def _complete_order(self):
        """Завершение заказа"""
        print(f"Завершение заказа {self.order_id}")
        
        # Отправка уведомления
        producer.send('notifications', {
            'saga_id': self.order_id,
            'action': 'ORDER_COMPLETED',
            'user_id': self.user_id,
            'message': f'Ваш заказ {self.order_id} успешно оформлен',
            'timestamp': time.time()
        })
        
        self.state = 'COMPLETED'
        orders[self.order_id] = self.__dict__
    
    def _compensate(self):
        """Выполнение компенсирующих транзакций"""
        print(f"Запуск компенсации для заказа {self.order_id}")
        self.state = 'COMPENSATING'
        
        # Выполнение компенсирующих действий в обратном порядке
        for step in reversed(self.compensation_steps):
            if step == 'compensate_payment':
                producer.send('payment-compensate', {
                    'saga_id': self.order_id,
                    'action': 'REFUND_PAYMENT',
                    'user_id': self.user_id,
                    'timestamp': time.time()
                })
            elif step == 'compensate_inventory':
                producer.send('inventory-compensate', {
                    'saga_id': self.order_id,
                    'action': 'RESTORE_INVENTORY',
                    'items': self.items,
                    'timestamp': time.time()
                })
        
        self.state = 'FAILED'
        orders[self.order_id] = self.__dict__

# API endpoints
@app.route('/api/v1/orders', methods=['POST'])
def create_order():
    """Создание нового заказа с использованием Saga"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Требуется JSON тело запроса'}), 400
        
        order_id = str(uuid.uuid4())[:8]  # Более короткий ID
        
        # Создание и выполнение Saga
        saga = OrderSaga(
            order_id=order_id,
            user_id=data.get('user_id', 'anonymous'),
            items=data.get('items', [])
        )
        
        # Запуск Saga в отдельном потоке
        thread = threading.Thread(target=saga.execute)
        thread.start()
        
        return jsonify({
            'order_id': order_id,
            'status': 'Заказ в обработке',
            'saga_state': saga.state,
            'message': 'Saga запущена успешно'
        }), 202
        
    except Exception as e:
        return jsonify({'error': f'Ошибка создания заказа: {str(e)}'}), 500

@app.route('/api/v1/orders/<string:order_id>', methods=['GET'])
def get_order_status(order_id):
    """Получение статуса заказа"""
    if order_id not in orders:
        return jsonify({'error': 'Заказ не найден'}), 404
    
    order = orders[order_id]
    return jsonify({
        'order_id': order_id,
        'state': order['state'],
        'state_description': SAGA_STATES.get(order['state'], 'неизвестно'),
        'user_id': order.get('user_id'),
        'items': order.get('items', [])
    }), 200

@app.route('/api/v1/orders', methods=['GET'])
def list_orders():
    """Получение списка всех заказов"""
    return jsonify({
        'total': len(orders),
        'orders': [
            {
                'order_id': order_id,
                'state': data['state'],
                'user_id': data.get('user_id')
            }
            for order_id, data in orders.items()
        ]
    }), 200

# Эндпоинт для тестирования Kafka
@app.route('/api/v1/test/kafka', methods=['POST'])
def test_kafka():
    """Тестирование подключения к Kafka"""
    try:
        test_message = {
            'test': 'message',
            'timestamp': time.time(),
            'service': 'order-service'
        }
        
        producer.send('test-topic', test_message)
        producer.flush()
        
        return jsonify({
            'status': 'success',
            'message': 'Тестовое сообщение отправлено в Kafka'
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Ошибка подключения к Kafka: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    return jsonify({
        'status': 'healthy',
        'service': 'order-service',
        'orders_count': len(orders),
        'kafka_connected': True
    }), 200

if __name__ == '__main__':
    print(f"Order Service запущен. Kafka broker: {KAFKA_BROKER}")
    print("Доступные эндпоинты:")
    print("- POST /api/v1/orders - Создать заказ")
    print("- GET /api/v1/orders/<order_id> - Получить статус заказа")
    print("- GET /api/v1/orders - Список всех заказов")
    print("- POST /api/v1/test/kafka - Тест Kafka")
    print("- GET /health - Проверка здоровья")
    
    app.run(host='0.0.0.0', port=5002, debug=True)