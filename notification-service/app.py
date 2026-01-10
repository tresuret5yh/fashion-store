"""
Сервис уведомлений.
Отправляет уведомления пользователям через различные каналы.
"""
from flask import Flask, jsonify
from kafka import KafkaConsumer
import json
import threading
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = Flask(__name__)

# Конфигурация Kafka
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')

# Конфигурация email (для демонстрации)
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'notifications@fashionstore.com',
    'sender_password': 'password'  # В реальном проекте использовать переменные окружения
}

# Хранилище уведомлений (в памяти для упрощения)
notifications_log = []

def process_notifications():
    """Обработка событий уведомлений из Kafka"""
    consumer = KafkaConsumer(
        'notifications',
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='notification-service-group'
    )
    
    for message in consumer:
        event = message.value
        action = event.get('action')
        saga_id = event.get('saga_id')
        
        print(f"Получено событие уведомления: {action} для Saga {saga_id}")
        
        if action == 'ORDER_COMPLETED':
            # Отправка уведомления о завершении заказа
            send_order_confirmation(
                user_id=event.get('user_id'),
                order_id=saga_id,
                message=event.get('message', 'Ваш заказ успешно оформлен')
            )
        
        elif action == 'ORDER_FAILED':
            # Отправка уведомления об ошибке заказа
            send_order_failure(
                user_id=event.get('user_id'),
                order_id=saga_id,
                message=event.get('message', 'При обработке заказа произошла ошибка')
            )
        
        elif action == 'SHIPMENT_SENT':
            # Отправка уведомления об отправке заказа
            send_shipment_notification(
                user_id=event.get('user_id'),
                order_id=saga_id,
                tracking_number=event.get('tracking_number')
            )
        
        # Логируем уведомление
        log_notification({
            'type': action,
            'saga_id': saga_id,
            'user_id': event.get('user_id'),
            'message': event.get('message'),
            'timestamp': datetime.now().isoformat(),
            'status': 'sent'
        })

def send_order_confirmation(user_id, order_id, message):
    """Отправка подтверждения заказа"""
    # В реальном проекте здесь была бы отправка email/SMS
    
    print(f"Отправка подтверждения заказа пользователю {user_id}")
    print(f"Заказ: {order_id}")
    print(f"Сообщение: {message}")
    
    # Имитация отправки email
    try:
        # Здесь был бы реальный код отправки email
        # send_email(user_id, "Подтверждение заказа", message)
        pass
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
    
    # Также можно отправлять уведомления в мессенджеры
    send_telegram_notification(user_id, message)
    
    return True

def send_order_failure(user_id, order_id, message):
    """Отправка уведомления об ошибке заказа"""
    print(f"Отправка уведомления об ошибке пользователю {user_id}")
    print(f"Заказ: {order_id}")
    print(f"Сообщение: {message}")
    
    # Имитация отправки уведомления
    send_telegram_notification(user_id, f"⚠️ {message}")
    
    return True

def send_shipment_notification(user_id, order_id, tracking_number):
    """Отправка уведомления об отправке заказа"""
    message = f"Ваш заказ {order_id} отправлен. Трек-номер: {tracking_number}"
    
    print(f"Отправка уведомления об отправке пользователю {user_id}")
    print(f"Сообщение: {message}")
    
    send_telegram_notification(user_id, f"🚚 {message}")
    
    return True

def send_telegram_notification(user_id, message):
    """Имитация отправки уведомления в Telegram"""
    # В реальном проекте здесь была бы интеграция с Telegram Bot API
    print(f"[TELEGRAM] Для пользователя {user_id}: {message}")
    return True

def send_email(to_email, subject, body):
    """Отправка email (упрощенная версия для демонстрации)"""
    try:
        # Создание сообщения
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Добавление текста
        msg.attach(MIMEText(body, 'plain'))
        
        # Отправка через SMTP
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False

def log_notification(notification_data):
    """Логирование отправленных уведомлений"""
    notifications_log.append(notification_data)
    
    # Ограничиваем лог последними 100 записями
    if len(notifications_log) > 100:
        notifications_log.pop(0)

# REST API для управления уведомлениями
@app.route('/api/v1/notifications', methods=['GET'])
def get_notifications():
    """Получение лога уведомлений"""
    # Фильтрация по параметрам запроса
    user_id = request.args.get('user_id')
    notification_type = request.args.get('type')
    limit = int(request.args.get('limit', 50))
    
    filtered_log = notifications_log.copy()
    
    if user_id:
        filtered_log = [n for n in filtered_log if n.get('user_id') == user_id]
    
    if notification_type:
        filtered_log = [n for n in filtered_log if n.get('type') == notification_type]
    
    # Применяем лимит
    filtered_log = filtered_log[-limit:]
    
    return jsonify({
        'total': len(filtered_log),
        'notifications': filtered_log
    }), 200

@app.route('/api/v1/notifications/send', methods=['POST'])
def send_custom_notification():
    """Отправка кастомного уведомления"""
    data = request.json
    
    required_fields = ['user_id', 'message', 'type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Отсутствует поле: {field}'}), 400
    
    # Отправка уведомления
    success = send_telegram_notification(data['user_id'], data['message'])
    
    if success:
        # Логируем уведомление
        log_notification({
            'type': data['type'],
            'user_id': data['user_id'],
            'message': data['message'],
            'timestamp': datetime.now().isoformat(),
            'status': 'sent',
            'custom': True
        })
        
        return jsonify({
            'status': 'success',
            'message': 'Уведомление отправлено',
            'notification_id': len(notifications_log) - 1
        }), 200
    
    return jsonify({
        'status': 'error',
        'message': 'Не удалось отправить уведомление'
    }), 500

@app.route('/api/v1/notifications/stats', methods=['GET'])
def get_notification_stats():
    """Получение статистики уведомлений"""
    if not notifications_log:
        return jsonify({
            'total_sent': 0,
            'by_type': {},
            'by_day': {}
        }), 200
    
    # Статистика по типам
    by_type = {}
    for notification in notifications_log:
        n_type = notification.get('type', 'unknown')
        by_type[n_type] = by_type.get(n_type, 0) + 1
    
    # Статистика по дням
    by_day = {}
    for notification in notifications_log:
        timestamp = notification.get('timestamp')
        if timestamp:
            # Извлекаем дату из timestamp
            date_part = timestamp.split('T')[0]
            by_day[date_part] = by_day.get(date_part, 0) + 1
    
    return jsonify({
        'total_sent': len(notifications_log),
        'by_type': by_type,
        'by_day': by_day,
        'last_24_hours': sum(1 for n in notifications_log 
                           if is_recent(n.get('timestamp', ''), hours=24))
    }), 200

def is_recent(timestamp, hours=24):
    """Проверка, является ли timestamp не старше указанного количества часов"""
    try:
        from datetime import datetime, timedelta
        notification_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_difference = datetime.now() - notification_time
        return time_difference <= timedelta(hours=hours)
    except:
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья сервиса"""
    return jsonify({
        'status': 'healthy',
        'service': 'notification-service',
        'notifications_sent': len(notifications_log),
        'kafka_connected': True
    }), 200

@app.route('/api/v1/notifications/test/email', methods=['POST'])
def test_email():
    """Тестовый эндпоинт для проверки отправки email"""
    data = request.json
    
    if 'email' not in data or 'message' not in data:
        return jsonify({'error': 'Требуется поля email и message'}), 400
    
    success = send_email(
        to_email=data['email'],
        subject='Тестовое уведомление от Fashion Store',
        body=data['message']
    )
    
    if success:
        return jsonify({
            'status': 'success',
            'message': 'Тестовое email отправлено'
        }), 200
    
    return jsonify({
        'status': 'error',
        'message': 'Не удалось отправить email'
    }), 500

if __name__ == '__main__':
    # Запуск обработчика уведомлений Kafka в отдельном потоке
    kafka_thread = threading.Thread(target=process_notifications, daemon=True)
    kafka_thread.start()
    
    app.run(host='0.0.0.0', port=5005, debug=True)