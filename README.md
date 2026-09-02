# PDF Extractor

A tool that reads PDF documents and pulls out structured data from them using AI — you define what fields you want (like "policy number", "coverage amount", "effective date"), upload a PDF, and it returns clean JSON with those fields filled in, along with the exact page and text each answer came from.

Built with **FastAPI** (Python) on the backend and **React** on the frontend, running fully containerized with **Docker**.

---

## What it does

1. **Upload a PDF** — the app extracts and indexes its text.
2. **Define a schema (template)** — a list of fields you want extracted, each with a short description.
3. **Run extraction** — an LLM (via Groq) reads the relevant parts of the PDF and fills in your schema.
4. **Review the result** — every field shows which part of the document it came from, plus a confidence score.
5. **Compare runs** — re-run the same schema later, or compare two runs side by side.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, PostgreSQL + pgvector |
| AI | Groq (LLM extraction), sentence-transformers (embeddings) |
| Frontend | React, Vite |
| Infra | Docker, Docker Compose |
| Security | API-key auth, rate limiting, upload validation |

---

## Project structure

```
pdf-extractor/
├── backend/
│   ├── app/
│   │   ├── main.py           # App entry point
│   │   ├── config.py         # Settings & environment variables
│   │   ├── db.py              # Database models
│   │   ├── routes/            # API endpoints
│   │   └── services/           # Core logic (PDF parsing, extraction, retrieval)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── frontend/
    ├── src/
    │   ├── pages/             # App screens (Upload, Templates, Extraction, History...)
    │   └── lib/                # API client
    ├── package.json
    └── Dockerfile
```

---

## Getting started

You need **Docker Desktop** installed. That's it — Docker handles Python, Node, and the database for you.

### 1. Clone the repo

```bash
git clone https://github.com/amrithamanikandan74/pdf-extractor.git
cd pdf-extractor/backend
```

### 2. Set up your environment file

```bash
cp .env.example .env
```

Open `.env` and fill in three things:

| Variable | What it is |
|---|---|
| `GROQ_API_KEY` | Get one free at [console.groq.com](https://console.groq.com) |
| `API_KEY` | Any random secret string — this protects your API |
| `POSTGRES_PASSWORD` | Any password for the database |

To generate a secure `API_KEY`, run:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Build and run everything

```bash
docker compose up -d --build
```

This starts three containers: the database, the backend API, and the frontend — all in one command.

### 4. Open the app

| What | Where |
|---|---|
| **Frontend (the app)** | http://localhost |
| **Backend health check** | http://localhost:8000/status |
| **Backend API docs** | http://localhost:8000/docs |

That's it — upload a PDF, create a template, and run your first extraction.

---

## Stopping the project

```bash
docker compose down
```

To also wipe the database and start completely fresh:
```bash
docker compose down -v
```

---
