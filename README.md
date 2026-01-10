# Магазин одежды и обуви - Микросервисная архитектура

## Описание проекта
Система интернет-магазина одежды и обуви, построенная на микросервисной архитектуре.

## Архитектура
- **9 микросервисов**: API Gateway, Auth, Catalog, Order, Payment, Inventory, Notification
- **Паттерны**: Saga, CQRS, API Gateway, Circuit Breaker
- **Коммуникация**: HTTP/REST (синхронная), Kafka (асинхронная)
- **Мониторинг**: Prometheus + Grafana

## Запуск проекта

1. Клонировать репозиторий:
```bash
git clone <repository-url>
cd fashion-store