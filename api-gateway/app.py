"""
API Gateway для магазина одежды и обуви.
Обеспечивает единую точку входа и маршрутизацию запросов.
"""
from flask import Flask, request, jsonify
import requests
import os
from functools import wraps
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

app = Flask(__name__)

# Конфигурация сервисов
SERVICES = {
    'auth': os.getenv('AUTH_SERVICE_URL', 'http://auth-service:5000'),
    'catalog': os.getenv('CATALOG_SERVICE_URL', 'http://catalog-service:5001'),
    'order': os.getenv('ORDER_SERVICE_URL', 'http://order-service:5002'),
}

# Простая проверка аутентификации (для демонстрации)
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Требуется аутентификация'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/v1/<service>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@require_auth
def proxy(service, path):
    """Проксирование запросов к соответствующим сервисам"""
    if service not in SERVICES:
        return jsonify({'error': 'Сервис не найден'}), 404
    
    service_url = SERVICES[service]
    url = f"{service_url}/{path}"
    
    try:
        # Проксирование запроса
        response = requests.request(
            method=request.method,
            url=url,
            headers={key: value for key, value in request.headers 
                    if key != 'Host'},
            data=request.get_data(),
            params=request.args,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        # Возврат ответа от сервиса
        return (response.content, response.status_code, response.headers.items())
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Ошибка соединения с сервисом {service}', 'details': str(e)}), 502

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка здоровья API Gateway"""
    return jsonify({'status': 'healthy', 'service': 'api-gateway'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)