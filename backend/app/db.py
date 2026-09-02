"""
SQLAlchemy engine, session factory, and ORM models.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import settings

try:
    from pgvector.sqlalchemy import Vector
except Exception:
    Vector = None

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String, nullable=True)
    chunk_text = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True)

    # keep pgvector column only if package exists
    if Vector is not None:
        embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=True)

    document = relationship("Document", back_populates="chunks")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    document_filename = Column(String, nullable=False)
    schema_name = Column(String, nullable=False)
    schema_hash = Column(String, nullable=False)
    schema_json = Column(Text, nullable=False)
    extracted_json = Column(Text, nullable=False)
    # pending -> completed | failed. New rows start "pending" and are filled
    # in by a background task so the request thread never blocks on the LLM
    # call. See app/services/extraction.py:perform_extraction_and_store.
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)



def ensure_pgvector_and_columns() -> None:
    """
    Ensure pgvector extension exists and add vector column if missing.

    Each statement runs in its own transaction. On a fresh database,
    ALTER TABLE document_chunks fails because the table doesn't exist
    yet — and if that ran in the same transaction as CREATE EXTENSION,
    Postgres would abort the whole transaction and silently roll back
    the extension creation too. Separate transactions keep one expected
    failure from undoing an earlier success.
    """
    if Vector is None:
        return

    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass

    with engine.begin() as conn:
        try:
            conn.execute(text(f"ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector({settings.EMBEDDING_DIM})"))
        except Exception:
            pass

    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_json TEXT"))
        except Exception:
            pass

def ensure_extraction_run_columns() -> None:
    """
    Add the status/error_message columns for deployments created before
    background extraction was introduced. New installs get them for free
    from Base.metadata.create_all.
    """
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE extraction_runs ADD COLUMN IF NOT EXISTS status VARCHAR NOT NULL DEFAULT 'completed'"
            ))
        except Exception:
            pass

        try:
            conn.execute(text("ALTER TABLE extraction_runs ADD COLUMN IF NOT EXISTS error_message TEXT"))
        except Exception:
            pass
