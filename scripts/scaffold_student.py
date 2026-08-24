#!/usr/bin/env python3
"""Generate a runnable frontend + backend/API + database trio for one student.

Used to lay down the Release 0 skeleton for students 2-5 so the integrated
application comes up end to end from day one. Each generated service is a
working CRUD microservice over a generic `records` table; the owning student
replaces the schema, seed data, and routes with their own feature.

    python3 scripts/scaffold_student.py 3 "Attractions & Dining" "Kevin Kim" attraction
"""

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DB_DOCKERFILE = """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY init_db.py .
COPY app.py .

RUN python init_db.py

EXPOSE {db_port}

CMD ["python", "app.py"]
"""

DB_INIT = '''"""Create and seed the {feature} database (student-{n}, {owner}).

TODO ({owner}): replace `records` with the real schema for {feature}.
The project specification requires at least ten records per table, so keep the
seed at ten or more when you change it.
"""

import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "student{n}.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS records (
    record_id   INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    created_on  TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM records")

records = [
    (i, "{noun} {{}}".format(i), "{noun}", "Placeholder {feature} record {{}}".format(i),
     "2026-08-{{:02d}}".format(i))
    for i in range(1, 13)
]

cursor.executemany(
    """
    INSERT INTO records (record_id, title, category, detail, created_on)
    VALUES (?, ?, ?, ?, ?)
    """,
    records,
)

conn.commit()
conn.close()

print(f"student-{n}-db initialised with {{len(records)}} records.")
'''

DB_APP = '''"""{feature} database API (student-{n}, {owner}).

This service exclusively owns student{n}.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.

TODO ({owner}): replace the generic `records` resource with the real {feature}
resources.
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/student{n}.db"
FIELDS = ("title", "category", "detail", "created_on")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health")
def health():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()["n"]
    conn.close()
    return jsonify({{"service": "student-{n}-db", "status": "running", "records": count}})


@app.get("/records")
def list_records():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM records ORDER BY record_id").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.get("/records/<int:record_id>")
def get_record(record_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({{"error": "Record not found"}}), 404

    return jsonify(dict(row))


@app.post("/records")
def create_record():
    payload = request.get_json(silent=True) or {{}}
    missing = [f for f in FIELDS if payload.get(f) in (None, "")]

    if missing:
        return jsonify({{"error": f"Missing fields: {{', '.join(missing)}}"}}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        f"INSERT INTO records ({{', '.join(FIELDS)}}) VALUES (?, ?, ?, ?)",
        tuple(payload[f] for f in FIELDS),
    )
    conn.commit()
    record_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.put("/records/<int:record_id>")
def update_record(record_id):
    payload = request.get_json(silent=True) or {{}}
    updates = {{f: payload[f] for f in FIELDS if f in payload}}

    if not updates:
        return jsonify({{"error": "No updatable fields supplied"}}), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return jsonify({{"error": "Record not found"}}), 404

    conn.execute(
        f"UPDATE records SET {{', '.join(f'{{f}} = ?' for f in updates)}} WHERE record_id = ?",
        (*updates.values(), record_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM records WHERE record_id = ?", (record_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({{"error": "Record not found"}}), 404

    return jsonify({{"deleted": record_id}})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port={db_port})
'''

API_DOCKERFILE = """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE {api_port}

CMD ["python", "app.py"]
"""

API_REQUIREMENTS = """flask==3.0.3
flask-cors==4.0.1
requests==2.32.3
"""

API_APP = '''"""{feature} backend/API (student-{n}, {owner}).

Serves HTMX fragments to the student-{n} frontend, reads and writes through
student-{n}-db only, and reaches the LLM only through the shared AI-Mode
service.

TODO ({owner}): replace the generic record routes with the real {feature}
routes. student-1/api shows the fuller structure (routes/, services/, views/)
once a feature outgrows a single module.
"""

import os
from html import escape

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://student-{n}-db:{db_port}")
AI_MODE_URL = os.getenv("AI_MODE_URL", "http://ai-mode:5300")

DB_DOWN = "Could not reach the {feature} database service."


def error_fragment(message, detail=""):
    body = f"<div class='notice notice-error'>{{escape(message)}}</div>"
    if detail:
        body += f"<pre>{{escape(str(detail)[:600])}}</pre>"
    return body


def records_table(records):
    if not records:
        return "<p class='muted'>No records yet.</p>"

    rows = "".join(
        "<tr>"
        f"<td>{{record['record_id']}}</td>"
        f"<td>{{escape(record['title'])}}</td>"
        f"<td>{{escape(record['category'])}}</td>"
        f"<td style='white-space:normal'>{{escape(record['detail'])}}</td>"
        f"<td>{{escape(record['created_on'])}}</td>"
        "<td>"
        f"<button class='btn-sm btn-danger' hx-delete='/api/student-{n}/records/{{record['record_id']}}' "
        "hx-target='#records-panel' hx-swap='innerHTML'>Delete</button>"
        "</td></tr>"
        for record in records
    )
    return (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Detail</th>"
        "<th>Created</th><th></th></tr></thead>"
        f"<tbody>{{rows}}</tbody></table></div>"
        f"<p class='muted'>{{len(records)}} record(s).</p>"
    )


def fetch_records():
    response = requests.get(f"{{DB_SERVICE_URL}}/records", timeout=5)
    response.raise_for_status()
    return response.json()


@app.get("/health")
def health():
    return jsonify({{"service": "student-{n}-api", "status": "running"}})


@app.get("/records")
def list_records():
    try:
        return records_table(fetch_records()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@app.post("/records")
def create_record():
    payload = {{key: value.strip() for key, value in request.form.items()}}
    try:
        response = requests.post(f"{{DB_SERVICE_URL}}/records", json=payload, timeout=5)
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid record.")), 400
        response.raise_for_status()
        return records_table(fetch_records()), 201
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    try:
        response = requests.delete(
            f"{{DB_SERVICE_URL}}/records/{{record_id}}", timeout=5
        )
        if response.status_code == 404:
            return error_fragment("Record not found."), 404
        response.raise_for_status()
        return records_table(fetch_records()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@app.post("/ai/chat")
def ai_chat():
    """AI-Mode integration. Flow: Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM."""
    question = request.form.get("question", "").strip()

    if not question:
        return error_fragment("Ask a question first."), 400

    try:
        records = fetch_records()
        context = "\\n".join(
            f"  {{r['title']}} ({{r['category']}}): {{r['detail']}}" for r in records[:10]
        )
    except requests.RequestException:
        context = ""

    try:
        response = requests.post(
            f"{{AI_MODE_URL}}/chat",
            json={{"question": question, "context": context}},
            timeout=180,
        )
        response.raise_for_status()
        answer = response.json()["answer"]
        return (
            "<div class='chat-msg user'><div class='who'>You</div>"
            f"<div class='bubble'>{{escape(question)}}</div></div>"
            "<div class='chat-msg bot'><div class='who'>Wander AI</div>"
            f"<div class='bubble'>{{escape(answer)}}</div></div>"
        ), 200
    except requests.RequestException as exc:
        return error_fragment("Could not reach the AI-Mode service.", exc), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port={api_port})
'''

FRONTEND_DOCKERFILE = """FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY templates/index.html /usr/share/nginx/html/index.html

EXPOSE 80
"""

FRONTEND_NGINX = """# student-{n} frontend microservice ({feature}, {owner}).
# Resolves the shared theme and this feature's API so the page works both
# standalone (localhost:80{n}8) and behind the unified home page.

server {{
    listen 80;
    server_name _;

    resolver 127.0.0.11 valid=10s;

    location / {{
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }}

    location /shared/ {{
        proxy_pass http://shared-frontend:80/shared/;
        proxy_set_header Host $host;
    }}

    location /api/student-{n}/ {{
        proxy_pass http://student-{n}-api:{api_port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }}
}}
"""

FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{feature} - Wander</title>
    <link rel="stylesheet" href="/shared/css/theme.css">
    <script src="/shared/js/htmx.min.js"></script>
</head>
<body>
<main class="app-shell">
    <header class="app-header card">
        <h1>{feature}</h1>
        <p>Student {n} &middot; {owner} &middot; <a href="/" style="color:var(--accent)">back to all features</a></p>
    </header>

    <div class="notice notice-error">
        Release 0 scaffold. {owner}: replace the generic records below with the
        real {feature} feature. The wiring (frontend to API to database to
        AI-Mode) already works, so start by changing the schema in
        <code>student-{n}/db/init_db.py</code>.
    </div>

    <nav class="tab-nav">
        <button class="tab-btn is-active" data-tab="records" type="button">Records</button>
        <button class="tab-btn" data-tab="ai" type="button">AI mode</button>
    </nav>

    <section class="tab-panel is-active card" id="panel-records">
        <div id="records-panel"
             hx-get="/api/student-{n}/records"
             hx-trigger="load"
             hx-swap="innerHTML"></div>

        <form hx-post="/api/student-{n}/records"
              hx-target="#records-panel"
              hx-swap="innerHTML"
              hx-on::after-request="this.reset()"
              style="margin-top:1.5rem">
            <h3 style="margin-top:0">Add a record</h3>
            <div class="form-grid">
                <div><label>Title</label><input name="title" required></div>
                <div><label>Category</label><input name="category" required></div>
                <div><label>Detail</label><input name="detail"></div>
                <div><label>Created on</label><input type="date" name="created_on" required></div>
            </div>
            <button type="submit">Create</button>
            <span class="spinner">saving...</span>
        </form>
    </section>

    <section class="tab-panel card" id="panel-ai">
        <h3 style="margin-top:0">Wander AI</h3>
        <p class="muted">Runs locally through AI-Mode and Ollama.</p>

        <div class="chat-log" id="chat-log">
            <p class="muted">Ask a question about this feature's data.</p>
        </div>

        <form hx-post="/api/student-{n}/ai/chat"
              hx-target="#chat-log"
              hx-swap="beforeend"
              hx-on::after-request="this.reset()">
            <div class="form-grid">
                <div style="grid-column:1/-1">
                    <label>Question</label>
                    <input name="question" required>
                </div>
            </div>
            <button type="submit">Ask</button>
            <span class="spinner">thinking...</span>
        </form>
    </section>
</main>

<script>
const buttons = Array.from(document.querySelectorAll(".tab-btn"));
const panels = {{
    records: document.getElementById("panel-records"),
    ai: document.getElementById("panel-ai"),
}};

function activate(name) {{
    buttons.forEach((b) => b.classList.toggle("is-active", b.dataset.tab === name));
    Object.entries(panels).forEach(([key, panel]) =>
        panel.classList.toggle("is-active", key === name)
    );
}}

buttons.forEach((b) => b.addEventListener("click", () => activate(b.dataset.tab)));
</script>
</body>
</html>
"""


TESTS_README = """# student-{n} tests

Release 0 validates this feature through `scripts/smoke_test.py {n}`, which the
`student-{n}` GitHub Actions workflow runs against the live services:

```bash
python3 scripts/smoke_test.py {n}
```

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing (project specification, section 7.3). Unit tests for this feature
belong in this directory.
"""


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path.relative_to(REPO_ROOT)}")


def scaffold(n, feature, owner, noun):
    api_port = 5100 + n
    db_port = 5200 + n
    root = REPO_ROOT / f"student-{n}"
    fields = dict(n=n, feature=feature, owner=owner, noun=noun,
                  api_port=api_port, db_port=db_port)

    print(f"student-{n}: {feature} ({owner})")

    write(root / "db" / "Dockerfile", DB_DOCKERFILE.format(**fields))
    write(root / "db" / "requirements.txt", "flask==3.0.3\n")
    write(root / "db" / "init_db.py", DB_INIT.format(**fields))
    write(root / "db" / "app.py", DB_APP.format(**fields))

    write(root / "api" / "Dockerfile", API_DOCKERFILE.format(**fields))
    write(root / "api" / "requirements.txt", API_REQUIREMENTS)
    write(root / "api" / "app.py", API_APP.format(**fields))

    write(root / "frontend" / "Dockerfile", FRONTEND_DOCKERFILE)
    write(root / "frontend" / "nginx.conf", FRONTEND_NGINX.format(**fields))
    write(root / "frontend" / "templates" / "index.html", FRONTEND_HTML.format(**fields))

    write(root / "tests" / "README.md", TESTS_README.format(**fields))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", type=int, choices=range(1, 6))
    parser.add_argument("feature")
    parser.add_argument("owner")
    parser.add_argument("noun", help="singular noun for the seeded placeholder rows")
    args = parser.parse_args()

    scaffold(args.number, args.feature, args.owner, args.noun)


if __name__ == "__main__":
    main()
