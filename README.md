# Smart Insight Desk MVP

Минимальный backend для приема тикетов, простого AI-анализа и просмотра агрегированной аналитики.

## Стек

- FastAPI
- SQLite
- Docker / Docker Compose

## Запуск

### Через Docker Compose

```bash
docker compose up --build
```

После запуска:

- Swagger UI: `http://127.0.0.1:8000/doc`
- API root: `http://127.0.0.1:8000/`

### Локально без Docker

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger UI будет доступен по адресу:

```text
http://127.0.0.1:8000/doc
```

## Эндпоинты

- `POST /submit-ticket` - прием жалобы
- `GET /analytics` - выдача результатов анализа

## Хранение данных

SQLite база сохраняется в `./data/smart_insight.db` через bind-mount в Docker Compose.
