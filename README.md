# Marginalia

**Organise every article by its keywords.**

Marginalia is a minimal [FastAPI](https://fastapi.tiangolo.com/) application for uploading PDF articles, automatically generating keywords from their content, and then browsing, searching, downloading, and deleting them. No training data, no external APIs, no manual tagging: drop in a PDF and Marginalia works out what it's about.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Example Usage](#example-usage)
- [Data Model](#data-model)
- [Authentication Note](#authentication-note)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **PDF upload**: upload any text-based PDF along with the uploader's `user_id` and an optional title.
- **Automatic keyword extraction**: keywords are generated from the article's text using [YAKE](https://github.com/LIAAD/yake), an unsupervised, language-independent method.
- **Keyword and title search**: find every article that matches a keyword or a title fragment.
- **Filtering and pagination**: filter the article list by owner, keyword, or title, and page through results with `skip` and `limit`.
- **Download originals**: retrieve the original PDF at any time.
- **Owner-only deletion**: only the user who uploaded an article can delete it.
- **Interactive docs**: Swagger UI is available out of the box at `/docs`.
- **Zero-config storage**: SQLite for metadata, the local filesystem for PDFs. Nothing to install or provision.

## Tech Stack

| Layer              | Technology                                   |
| ------------------ | -------------------------------------------- |
| Web framework      | [FastAPI](https://fastapi.tiangolo.com/)     |
| Server             | [Uvicorn](https://www.uvicorn.org/)          |
| PDF text extraction| [pypdf](https://pypdf.readthedocs.io/)       |
| Keyword extraction | [YAKE](https://github.com/LIAAD/yake)        |
| Database / ORM     | SQLite via [SQLAlchemy](https://www.sqlalchemy.org/) |
| Language           | Python 3                                     |

## How It Works

1. **Upload.** A client sends a PDF to `POST /articles/upload` together with a `user_id` (the uploader) and an optional `title`.
2. **Extract text.** The PDF's text is read with `pypdf`.
3. **Generate keywords.** YAKE analyses the text and produces a ranked set of keywords, with no training data or API key required.
4. **Store.** The PDF is saved to `./uploads/`, and the article's metadata (owner, title, keywords, content preview) is written to the local SQLite database, `articles.db`, through SQLAlchemy.
5. **Search.** Keywords are stored per article, so searching for a keyword surfaces every article it was extracted from.

## Project Structure

```
.
├── main.py            # FastAPI app: routes, models, keyword extraction
├── requirements.txt   # Python dependencies
├── articles.db        # SQLite database (created/used at runtime)
├── uploads/           # Uploaded PDF files
├── static/            # Static assets served by the app
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.9 or newer
- `pip`

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/NostalgicWinters/Marginalia---Organise-every-article-by-it-s-keywords-.git
cd Marginalia---Organise-every-article-by-it-s-keywords-

# 2. (Recommended) create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Run the server

```bash
uvicorn main:app --reload
```

The API is now running at <http://127.0.0.1:8000>.

Open <http://127.0.0.1:8000/docs> for the interactive Swagger UI, where you can try every endpoint from the browser. FastAPI also serves an alternative ReDoc view at <http://127.0.0.1:8000/redoc>.

## API Reference

| Method | Path                         | Description                                                              |
| ------ | ---------------------------- | ------------------------------------------------------------------------ |
| POST   | `/articles/upload`           | Upload a PDF (`file`, `user_id`, optional `title`)                       |
| GET    | `/articles`                  | List all articles. Filters: `owner`, `keyword`, `title`, `skip`, `limit` |
| GET    | `/articles/search?q=...`     | Search by keyword or title                                               |
| GET    | `/articles/{id}`             | Get a single article's metadata and content preview                      |
| GET    | `/articles/{id}/download`    | Download the original PDF                                                |
| DELETE | `/articles/{id}?user_id=...` | Delete an article. Only works if `user_id` matches the original uploader |

### Upload parameters

| Field     | Type   | Required | Description                         |
| --------- | ------ | -------- | ----------------------------------- |
| `file`    | file   | Yes      | The PDF to upload                   |
| `user_id` | string | Yes      | Identifier of the uploading user    |
| `title`   | string | No       | A human-friendly title for the article |

### List filters (`GET /articles`)

| Query param | Description                                  |
| ----------- | -------------------------------------------- |
| `owner`     | Only return articles uploaded by this user   |
| `keyword`   | Only return articles with this keyword       |
| `title`     | Only return articles matching this title     |
| `skip`      | Number of results to skip (for pagination)   |
| `limit`     | Maximum number of results to return          |

## Example Usage

```bash
# Upload a PDF
curl -X POST http://127.0.0.1:8000/articles/upload \
  -F "file=@paper.pdf" \
  -F "user_id=alice" \
  -F "title=My Paper"

# List articles, filtered by keyword
curl "http://127.0.0.1:8000/articles?keyword=climate"

# Search by keyword or title
curl "http://127.0.0.1:8000/articles/search?q=climate"

# Get one article by id
curl "http://127.0.0.1:8000/articles/1"

# Download the original PDF
curl -OJ "http://127.0.0.1:8000/articles/1/download"

# Delete (only works if user_id matches the uploader)
curl -X DELETE "http://127.0.0.1:8000/articles/1?user_id=alice"
```

### Using Python

```python
import requests

BASE = "http://127.0.0.1:8000"

# Upload
with open("paper.pdf", "rb") as f:
    r = requests.post(
        f"{BASE}/articles/upload",
        files={"file": f},
        data={"user_id": "alice", "title": "My Paper"},
    )
print(r.json())

# Search
print(requests.get(f"{BASE}/articles/search", params={"q": "climate"}).json())
```

## Data Model

Each uploaded article is stored with its metadata in `articles.db`. Conceptually, an article record holds:

- an **id** (assigned automatically)
- the **owner** (the `user_id` supplied at upload time)
- a **title** (provided, or derived when omitted)
- the generated **keywords**
- a **content preview** extracted from the PDF
- a reference to the **stored PDF file** in `uploads/`

## Authentication Note

There is no real login system here. `user_id` is just a plain string passed by the client, and the app compares it against the stored `owner` field before allowing deletion.

This is fine for a demo or prototype, but **swap it for real authentication** (sessions, JWT, OAuth, etc.) before using this for anything that needs actual security. As it stands, anyone who knows or guesses a `user_id` can act as that user.

## Limitations

- **Text-based PDFs only.** Scanned or image-only PDFs have no extractable text, so keyword generation will return little or nothing unless you add an OCR step.
- **Single-node storage.** SQLite and the local `uploads/` folder are ideal for a prototype but not for horizontally scaled deployments.
- **No authentication.** See the [note above](#authentication-note).
- **Keyword quality varies.** YAKE is unsupervised, so results depend on the length and quality of the source text.

## Roadmap

Ideas for taking Marginalia further:

- [ ] Real authentication and per-user access control
- [ ] OCR support for scanned PDFs
- [ ] Manual keyword editing and tagging
- [ ] Ranked, full-text search across article content
- [ ] A browsable web UI for exploring articles by keyword
- [ ] Docker setup for one-command deployment
- [ ] Automated tests and CI

## Contributing

Contributions, issues, and feature requests are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a pull request

## License
 
Distributed under the [MIT License](https://choosealicense.com/licenses/mit/). See the [`LICENSE`](LICENSE) file for details.
