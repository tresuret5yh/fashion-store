"""
Сервис обработки платежей.
Подписывается на события из Kafka и обрабатывает платежи.
"""
from flask import Flask, jsonify
from kafka import KafkaConsumer
import json
import threading
import os

app = Flask(__name__)

# Конфигурация Kafka
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')

def process_payments():
    """Обработка платежных событий из Kafka"""
    consumer = KafkaConsumer(
        'payment-process',
        'payment-compensate',
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='payment-service-group'
    )
    
    for message in consumer:
        event = message.value
        action = event.get('action')
        saga_id = event.get('saga_id')
        
        print(f"Получено платежное событие: {action} для Saga {saga_id}")
        
        if action == 'PROCESS_PAYMENT':
            # Симуляция обработки платежа
            print(f"Обработка платежа для пользователя {event.get('user_id')}")
            
            # В реальном проекте здесь была бы интеграция с платежным шлюзом
            # ...
            
            # Отправка ответа в топик saga-responses
            from kafka import KafkaProducer
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            producer.send('saga-responses', {
                'saga_id': saga_id,
                'service': 'payment-service',
                'status': 'PAYMENT_SUCCESS',
                'message': 'Платеж успешно обработан'
            })
            
        elif action == 'REFUND_PAYMENT':
            # Компенсирующая транзакция - возврат средств
            print(f"Возврат средств для Saga {saga_id}")
            
            # Отправка подтверждения
            from kafka import KafkaProducer
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            producer.send('saga-responses', {
                'saga_id': saga_id,
                'service': 'payment-service',
                'status': 'REFUND_COMPLETED',
                'message': 'Средства возвращены'
            })

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    return jsonify({'status': 'healthy', 'service': 'payment-service'})

if __name__ == '__main__':
    # Запуск обработчика платежей в отдельном потоке
    payment_thread = threading.Thread(target=process_payments, daemon=True)
    payment_thread.start()
    
    app.run(host='0.0.0.0', port=5003, debug=True)