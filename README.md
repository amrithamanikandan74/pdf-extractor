# PDF Extractor

A tool that reads PDF documents and pulls out structured data from them using AI — you define what fields you want (like "policy number", "coverage amount", "effective date"), upload a PDF, and it returns clean JSON with those fields filled in, along with the exact page and text each answer came from.

Built with **FastAPI** (Python) on the backend and **React** on the frontend.

---

## Live demo

| What | Where |
|---|---|
| **App (frontend)** | https://pdfextractor-eta.vercel.app |
| **API (backend)** | https://pdf-extractor-4n88.onrender.com |
| **API docs (Swagger)** | https://pdf-extractor-4n88.onrender.com/docs |

> Hosted on free tiers — the backend spins down after inactivity, so the first request after a while may take 30–60 seconds to wake up.

---

## What it does

1. **Upload a PDF** — the app extracts and indexes its text.
2. **Define a schema (template)** — a list of fields you want extracted, each with a short description.
3. **Run extraction** — an LLM (via Groq) reads the relevant parts of the PDF and fills in your schema.
4. **Review the result** — every field shows which part of the document it came from, plus a confidence score.
5. **Compare runs** — re-run the same schema later, or compare two runs side by side, including a pgvector-vs-Elasticsearch retrieval comparison (Elasticsearch runs locally only — see below).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, PostgreSQL + pgvector |
| AI | Groq (LLM extraction), fastembed (ONNX-based embeddings) |
| Frontend | React, Vite |
| Database | PostgreSQL with the pgvector extension, hosted on [Neon](https://neon.tech) |
| Deployment | Backend on [Render](https://render.com), frontend on [Vercel](https://vercel.com) |
| Local dev | Docker, Docker Compose (adds an Elasticsearch container for the alternate search backend) |
| Security | API-key auth, rate limiting, upload validation |

**Why fastembed instead of sentence-transformers/torch:** the original embedding step used `sentence-transformers`, which pulls in PyTorch — importing it and loading a model alone uses 400–600MB of RAM, more than free-tier hosting (like Render's 512MB cap) allows. `fastembed` runs the same MiniLM-family model on ONNX Runtime with a much smaller memory footprint, so the backend fits comfortably on a free instance.

**Why Elasticsearch is local-only:** the app supports two interchangeable retrieval backends — pgvector (default, used in the live deployment via Neon) and Elasticsearch (for comparing vector search vs. traditional BM25 full-text search). Hosting a dedicated Elasticsearch cluster isn't free anywhere reliable, so it's wired up for local development via Docker Compose only; the Compare page's Elasticsearch option is demoed locally rather than in the hosted version.

---

## Project structure

```
pdf-extractor/
├── docker-compose.yaml      # Local dev: db, Elasticsearch, backend, frontend
├── .env.example
│
├── backend/
│   ├── app/
│   │   ├── main.py           # App entry point
│   │   ├── config.py         # Settings & environment variables
│   │   ├── db.py              # Database models
│   │   ├── routes/            # API endpoints
│   │   └── services/           # Core logic (PDF parsing, extraction, retrieval)
│   ├── requirements.txt
│   └── Dockerfile
│
└── frontend/
    ├── src/
    │   ├── pages/             # App screens (Upload, Templates, Extraction, History...)
    │   └── lib/                # API client
    ├── package.json
    └── Dockerfile
```

## Running it locally

You need **Docker Desktop** installed. That's it — Docker handles Python, Node, and the database for you.

### 1. Clone the repo

```bash
git clone https://github.com/amrithamanikandan74/pdf-extractor.git
cd pdf-extractor
```

Everything below runs from this root folder — you don't need to `cd` into `backend/` or `frontend/` at all.

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

This starts four containers — database, Elasticsearch, backend API, and frontend — all in one command, from the project root. Locally you can set `SEARCH_BACKEND=elasticsearch` to try the alternate retrieval backend.

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
