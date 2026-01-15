# Магазин одежды и обуви - Микросервисная архитектура

## Обновленная архитектура
- **9 микросервисов**: API Gateway, Auth, Catalog, Order, Payment, Inventory, Notification, User Profile, Analytics
- **Service Discovery**: Consul для динамического обнаружения сервисов
- **Оркестрация**: Kubernetes для production окружения
- **Паттерны**: Saga, CQRS, API Gateway, Circuit Breaker, Event-Driven
- **Коммуникация**: HTTP/REST, Kafka (асинхронная), Consul DNS
- **Мониторинг**: Prometheus + Grafana + Consul Health Checks

## Новые сервисы

### 1. User Profile Service (порт 5006)
- Управление профилями пользователей
- Адреса доставки и предпочтения
- История активности пользователей
- Интеграция с Auth Service через Consul

### 2. Analytics Service (порт 5007)
- Сбор и анализ данных из Kafka
- Генерация отчетов и дашбордов
- Прогнозирование продаж
- Экспорт данных в CSV

## Service Discovery - Consul
Все микросервисы автоматически регистрируются в Consul при запуске:
- Health checks каждые 10 секунд
- DNS-адресация: `service-name.fashion-store.svc.cluster.local`
- Веб-интерфейс: http://localhost:8500

## Kubernetes Deployment

### Требования:
- Minikube или Kubernetes кластер
- Helm (опционально)
- kubectl

### Установка:
```bash
# Создание namespace
kubectl apply -f k8s/namespace.yaml

# Установка секретов и конфигураций
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml

# Установка Consul
kubectl apply -f k8s/deployments/consul.yaml

# Установка микросервисов
kubectl apply -f k8s/deployments/

# Установка Ingress
kubectl apply -f k8s/ingress/