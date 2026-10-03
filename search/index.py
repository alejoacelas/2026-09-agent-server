"""Build a local full-text index from Wikimedia's plain-text Parquet export."""
import argparse
import json
import sqlite3
import time
from pathlib import Path
import pyarrow.parquet as pq


def build(source, destination):
    if destination.exists():
        raise SystemExit('Destination exists; choose a new filename to preserve the old index.')
    started = time.perf_counter()
    db = sqlite3.connect(destination)
    db.executescript("""
      CREATE TABLE articles(id INTEGER PRIMARY KEY, title TEXT, url TEXT, text TEXT);
      CREATE VIRTUAL TABLE search USING fts5(title, text, content='articles', content_rowid='id', prefix='2 3 4', tokenize='unicode61 remove_diacritics 2');
      CREATE TABLE metadata(value TEXT);
    """)
    count = size = 0
    for batch in pq.ParquetFile(source).iter_batches(batch_size=2000):
        rows = batch.to_pylist()
        db.executemany('INSERT INTO articles VALUES(?,?,?,?)', [(int(r['id']), r['title'], r['url'], r['text']) for r in rows])
        count += len(rows)
        size += sum(len(r['text'].encode()) for r in rows)
    db.execute("INSERT INTO search(search) VALUES('rebuild')")
    db.execute("INSERT INTO search(search) VALUES('optimize')")
    db.execute('INSERT INTO metadata VALUES(?)', (json.dumps(dict(articles=count, text_bytes=size, corpus='Simple English Wikipedia', snapshot='2023-11-01')),))
    db.commit()
    db.close()
    print(json.dumps(dict(articles=count, text_bytes=size, index_bytes=destination.stat().st_size, build_seconds=round(time.perf_counter()-started, 1))), flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    a = p.parse_args()
    build(a.source, a.destination)
