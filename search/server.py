"""Read-only search API and static interface; bind to loopback or a Tailscale address."""
import argparse
import json
import re
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent


def expression(query):
    words = re.findall(r'[^\W_]+', query, re.UNICODE)[:12]
    return ' AND '.join('"' + w + '"' + ('*' if i == len(words)-1 else '') for i, w in enumerate(words))


def connect(path):
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def search(db, query):
    term = expression(query)
    if not term:
        return []
    # Stop pathological broad searches so a new query can get through promptly.
    deadline = time.perf_counter() + 1
    db.set_progress_handler(lambda: time.perf_counter() > deadline, 1000)
    try:
        return [dict(r) for r in db.execute("""
          SELECT rowid AS id, title,
                 snippet(search, 1, char(1), char(2), '…', 30) AS snippet
          FROM search WHERE search MATCH ? AND rank MATCH 'bm25(12.0, 1.0)'
          ORDER BY rank LIMIT 30
        """, (term,))]
    finally:
        db.set_progress_handler(None, 0)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def send(self, value, status=200, mime='application/json; charset=utf-8'):
        body = json.dumps(value, ensure_ascii=False).encode() if mime.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path in ('/', '/app.js', '/style.css'):
            name, mime = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}[url.path]
            return self.send((ROOT / name).read_bytes(), mime=mime + '; charset=utf-8')
        started = time.perf_counter()
        db = connect(self.server.database)
        try:
            if url.path == '/api/stats':
                return self.send(json.loads(db.execute('SELECT value FROM metadata').fetchone()[0]))
            if url.path == '/api/search':
                q = parse_qs(url.query).get('q', [''])[0][:200]
                return self.send(dict(query=q, results=search(db, q), server_ms=round((time.perf_counter()-started)*1000, 1)))
            if url.path.startswith('/api/article/'):
                id = url.path.rsplit('/', 1)[-1]
                if not id.isdigit():
                    return self.send({'error': 'Invalid article'}, 400)
                row = db.execute('SELECT * FROM articles WHERE id=?', (id,)).fetchone()
                return self.send(dict(row) if row else {'error': 'Article not found'}, 200 if row else 404)
            return self.send({'error': 'Not found'}, 404)
        except sqlite3.OperationalError:
            return self.send({'error': 'That search took too long. Try a more specific phrase.'}, 503)
        finally:
            db.close()

    def log_message(self, format, *args):
        pass  # Search terms do not belong in access logs.


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--database', type=Path, required=True)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8765)
    a = p.parse_args()
    with connect(a.database.resolve()) as db:
        db.execute('SELECT value FROM metadata').fetchone()
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    server.database = a.database.resolve()
    print(f'Search listening on port {a.port}', flush=True)
    server.serve_forever()
