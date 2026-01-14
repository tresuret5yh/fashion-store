"""
API Gateway для магазина одежды и обуви.
Обеспечивает единую точку входа, маршрутизацию и сбор метрик.
"""
from flask import Flask, request, jsonify
import requests
import os
import time
from functools import wraps
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram

app = Flask(__name__)

# === Метрики Prometheus ===
REQUEST_COUNT = Counter(
    'gateway_requests_total',
    'Total requests to API Gateway',
    ['service', 'method', 'status']
)
REQUEST_LATENCY = Histogram(
    'gateway_request_duration_seconds',
    'Request latency in seconds',
    ['service']
)
UPSTREAM_LATENCY = Histogram(
    'gateway_upstream_duration_seconds',
    'Upstream service response time',
    ['service']
)

# Конфигурация сервисов
SERVICES = {
    'auth': os.getenv('AUTH_SERVICE_URL', 'http://auth-service:5000'),
    'catalog': os.getenv('CATALOG_SERVICE_URL', 'http://catalog-service:5001'),
    'order': os.getenv('ORDER_SERVICE_URL', 'http://order-service:5002'),
    'inventory': os.getenv('INVENTORY_SERVICE_URL', 'http://inventory-service:5004'), 
    'review': os.getenv('REVIEW_SERVICE_URL', 'http://review-service:5006'),
    'user': os.getenv('USER_SERVICE_URL', 'http://user-service:5007'),
    'notification': os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:5005'),  
}

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            REQUEST_COUNT.labels(service='gateway', method=request.method, status='401').inc()
            return jsonify({'error': 'Требуется аутентификация'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/metrics')
def metrics():
    """Эндпоинт для сбора метрик Prometheus"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health')
def health_check():
    """Проверка здоровья шлюза"""
    return jsonify({'status': 'healthy', 'service': 'api-gateway'})

@app.route('/api/v1/<service>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@require_auth
def proxy(service, path):
    if service not in SERVICES:
        REQUEST_COUNT.labels(service='gateway', method=request.method, status='404').inc()
        return jsonify({'error': 'Сервис не найден'}), 404

    service_url = SERVICES[service]

    # Преобразование путей
    if service == 'user':
        target_path = f"api/v1/users/{path}"
    elif service == 'review':
        target_path = f"api/v1/{path}"
    else:
        # Для auth, catalog, order, notification — стандартный путь: /api/v1/...
        target_path = f"api/v1/{path}"

    url = f"{service_url}/{target_path}"
    start_time = time.time()

    try:
        upstream_start = time.time()
        response = requests.request(
            method=request.method,
            url=url,
            headers={key: value for key, value in request.headers if key != 'Host'},
            data=request.get_data(),
            params=request.args,
            cookies=request.cookies,
            allow_redirects=False,
            timeout=10
        )
        upstream_duration = time.time() - upstream_start
        UPSTREAM_LATENCY.labels(service=service).observe(upstream_duration)

        status = str(response.status_code)
        REQUEST_COUNT.labels(service=service, method=request.method, status=status).inc()
        REQUEST_LATENCY.labels(service=service).observe(time.time() - start_time)

        return (response.content, response.status_code, dict(response.headers))

    except requests.exceptions.Timeout:
        REQUEST_COUNT.labels(service=service, method=request.method, status='504').inc()
        return jsonify({'error': f'Таймаут к {service}'}), 504
    except requests.exceptions.ConnectionError:
        REQUEST_COUNT.labels(service=service, method=request.method, status='502').inc()
        return jsonify({'error': f'Нет соединения с {service}'}), 502
    except Exception as e:
        REQUEST_COUNT.labels(service=service, method=request.method, status='500').inc()
        return jsonify({'error': 'Внутренняя ошибка шлюза'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)