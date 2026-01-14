# Магазин одежды и обуви - Микросервисная архитектура

## Обновленная архитектура
- **9 микросервисов**: API Gateway, Auth, Catalog, Order, Payment, Inventory, Notification, User Profile, Analytics
- **Service Discovery**: Consul для динамического обнаружения сервисов
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

