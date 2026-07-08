"""
Minimal FastAPI app: upload PDF articles, auto-extract keywords from their
content, and browse/search/delete them.

Run with:
    uvicorn main:app --reload

NOTE ON "USERS":
This is a minimal demo, so there's no real auth/login system. Every request
that needs to identify a person just passes a `user_id` string (form field
or query param). Whoever uploaded an article with a given user_id is the
only one who can delete it. Swap this out for real auth (JWT/session/etc.)
before using this anywhere near production.
"""

import os
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
import yake

# --------------------------------------------------------------------------
# Setup: storage dir + database
# --------------------------------------------------------------------------

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DATABASE_URL = "sqlite:///./articles.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    filename = Column(String)
    filepath = Column(String)
    owner = Column(String, index=True)
    keywords = Column(String, default="")  # comma-separated
    content_preview = Column(Text, default="")
    uploaded_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Article Keyword Search API",
    description="Upload PDF articles, auto-tag them with keywords, and search/browse/delete them.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------------
# PDF text extraction + keyword generation
# --------------------------------------------------------------------------


def extract_text_from_pdf(filepath: str) -> str:
    reader = PdfReader(filepath)
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts).strip()


def generate_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Unsupervised keyword extraction using YAKE (no training data needed,
    works decently out of the box on article-length text)."""
    if not text:
        return []
    kw_extractor = yake.KeywordExtractor(lan="en", n=2, top=max_keywords, dedupLim=0.9)
    scored = kw_extractor.extract_keywords(text)
    # YAKE: lower score = more relevant
    scored.sort(key=lambda pair: pair[1])
    return [kw for kw, _score in scored]


def serialize_article(article: Article, include_preview: bool = False) -> dict:
    data = {
        "id": article.id,
        "title": article.title,
        "filename": article.filename,
        "owner": article.owner,
        "keywords": article.keywords.split(",") if article.keywords else [],
        "uploaded_at": article.uploaded_at,
    }
    if include_preview:
        data["content_preview"] = article.content_preview
    return data


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.post("/articles/upload", tags=["articles"])
def upload_article(
    file: UploadFile = File(..., description="PDF file to upload"),
    user_id: str = Form(..., description="Identifier of the uploading user"),
    title: Optional[str] = Form(None, description="Optional custom title; defaults to filename"),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    safe_filename = f"{datetime.utcnow().timestamp()}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, safe_filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        text = extract_text_from_pdf(filepath)
    except Exception as exc:
        os.remove(filepath)
        raise HTTPException(status_code=400, detail=f"Failed to read PDF: {exc}")

    keywords = generate_keywords(text)

    article = Article(
        title=title or file.filename,
        filename=file.filename,
        filepath=filepath,
        owner=user_id,
        keywords=",".join(keywords),
        content_preview=text[:1000],
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    return serialize_article(article)


@app.get("/articles", tags=["articles"])
def list_articles(
    owner: Optional[str] = Query(None, description="Filter by uploader"),
    keyword: Optional[str] = Query(None, description="Filter by keyword (substring match)"),
    title: Optional[str] = Query(None, description="Filter by title (substring match)"),
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List all articles, with optional filters."""
    query = db.query(Article)
    if owner:
        query = query.filter(Article.owner == owner)
    if title:
        query = query.filter(Article.title.ilike(f"%{title}%"))
    if keyword:
        query = query.filter(Article.keywords.ilike(f"%{keyword}%"))

    total = query.count()
    articles = query.order_by(Article.uploaded_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "results": [serialize_article(a) for a in articles],
    }


@app.get("/articles/search", tags=["articles"])
def search_articles(
    q: str = Query(..., description="Search term matched against title and keywords"),
    db: Session = Depends(get_db),
):
    """Search articles by a free-text term against title + keywords —
    this is what powers 'search by keyword and find the matching articles'."""
    articles = (
        db.query(Article)
        .filter((Article.keywords.ilike(f"%{q}%")) | (Article.title.ilike(f"%{q}%")))
        .order_by(Article.uploaded_at.desc())
        .all()
    )
    return {"query": q, "count": len(articles), "results": [serialize_article(a) for a in articles]}


@app.get("/articles/{article_id}", tags=["articles"])
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Look up a single article by its id."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return serialize_article(article, include_preview=True)


@app.get("/articles/{article_id}/download", tags=["articles"])
def download_article(article_id: int, db: Session = Depends(get_db)):
    """Download the original PDF file."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if not os.path.exists(article.filepath):
        raise HTTPException(status_code=410, detail="File missing from storage")
    return FileResponse(article.filepath, filename=article.filename, media_type="application/pdf")


@app.delete("/articles/{article_id}", tags=["articles"])
def delete_article(
    article_id: int,
    user_id: str = Query(..., description="Must match the article's uploader to authorize deletion"),
    db: Session = Depends(get_db),
):
    """Delete an article — only allowed if user_id matches the original uploader."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.owner != user_id:
        raise HTTPException(status_code=403, detail="You are not allowed to delete this article.")

    if os.path.exists(article.filepath):
        os.remove(article.filepath)

    db.delete(article)
    db.commit()
    return {"detail": f"Article {article_id} deleted successfully."}


@app.get("/api", tags=["meta"])
def api_info():
    return {
        "message": "Article Keyword Search API",
        "docs": "/docs",
        "endpoints": [
            "POST /articles/upload",
            "GET /articles",
            "GET /articles/search?q=...",
            "GET /articles/{id}",
            "GET /articles/{id}/download",
            "DELETE /articles/{id}?user_id=...",
        ],
    }


# Serve the frontend (static/index.html + assets) at "/".
# Mounted last so it doesn't shadow the API routes defined above.
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
