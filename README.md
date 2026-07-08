# Article Keyword Search API

A minimal FastAPI app for uploading PDF articles, auto-generating keywords
from their content, and browsing/searching/deleting them.

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/docs for interactive Swagger UI.

## How it works

- **Upload**: `POST /articles/upload` accepts a PDF + a `user_id` (the
  uploader) + optional `title`. The PDF text is extracted with `pypdf`, and
  keywords are generated automatically with **YAKE** (unsupervised keyword
  extraction — no training data or external API needed).
- **Storage**: PDFs are saved to `./uploads/`, metadata to a local SQLite
  database (`articles.db`), via SQLAlchemy.
- **Search**: Keywords are stored per article, so searching a keyword
  surfaces every article it was extracted from.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/articles/upload` | Upload a PDF (`file`, `user_id`, optional `title`) |
| GET | `/articles` | List all articles. Filters: `owner`, `keyword`, `title`, `skip`, `limit` |
| GET | `/articles/search?q=...` | Search by keyword or title |
| GET | `/articles/{id}` | Get a single article's metadata + content preview |
| GET | `/articles/{id}/download` | Download the original PDF |
| DELETE | `/articles/{id}?user_id=...` | Delete an article — only works if `user_id` matches the original uploader |

## Auth note

There's no real login system here — `user_id` is just a plain string passed
by the client, and the app checks it against the stored `owner` field before
allowing deletion. This is fine for a demo/prototype, but swap it for real
authentication (sessions, JWT, OAuth, etc.) before using this for anything
that needs actual security.

## Example usage (curl)

```bash
# Upload
curl -X POST http://127.0.0.1:8000/articles/upload \
  -F "file=@paper.pdf" \
  -F "user_id=alice" \
  -F "title=My Paper"

# List / filter
curl "http://127.0.0.1:8000/articles?keyword=climate"

# Search
curl "http://127.0.0.1:8000/articles/search?q=climate"

# Get by id
curl "http://127.0.0.1:8000/articles/1"

# Delete (only works if user_id matches the uploader)
curl -X DELETE "http://127.0.0.1:8000/articles/1?user_id=alice"
```
