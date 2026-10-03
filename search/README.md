# Find

A Raycast-style search prototype over a local copy of Simple English Wikipedia.
The index and service run on Hetzner; the browser sends queries over Tailscale.
Open **http://agent-server/** while connected to Tailscale.

Type to search, use ↑/↓ to select a result, and Enter to focus the full article.
Escape returns to search or clears the query; ⌘K focuses search. On small screens,
tap a result to read it and use Results to return. The footer measures request time
(including response parsing) and server search time separately. The 80 ms typing
pause and rendering time are not included in that footer measurement.

## Data and behavior

The corpus is Wikimedia's [2023-11-01 Simple English Wikipedia export](https://huggingface.co/datasets/wikimedia/wikipedia/tree/3e1f92c331f318af862b87e2319ed5dc26d80f5d/20231101.simple).
It contains real article text; searches and article previews use the local database,
with no upstream requests. Article source links provide contributor history.
Text is licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
and GFDL; the UI displays attribution. No personal files are imported.

SQLite FTS5 indexes titles and bodies, weights title matches more heavily, and
matches the final word as a prefix. Exact titles come first, followed by other
title matches, then body matches. Single-character queries search titles only.
All words must match. It returns up to 30
ranked results; this is keyword search, without semantic embeddings or typo
correction. Superseded browser requests are cancelled and stale responses ignored.
Server queries stop after one second. Aborting a browser request does not itself
cancel a query already running on the server.

## Rebuild

The source lives in this repository. Deployment files and data live in
`~/.local/share/agent-server-search/` on the server, with a user systemd service.
The server needs Python 3 with SQLite FTS5; only indexing needs PyArrow.

```sh
runtime="$HOME/.local/share/agent-server-search"
mkdir -p "$runtime/data" "$HOME/.config/systemd/user"
~/.local/bin/uv venv "$runtime/.venv"
~/.local/bin/uv pip install --python "$runtime/.venv/bin/python" pyarrow==23.0.1
curl -fL --retry 3 \
  https://huggingface.co/datasets/wikimedia/wikipedia/resolve/3e1f92c331f318af862b87e2319ed5dc26d80f5d/20231101.simple/train-00000-of-00001.parquet \
  -o "$runtime/data/wikipedia.parquet"
# From the repository root on the server:
cp search/{index.py,server.py,index.html,app.js,style.css} "$runtime/"
"$runtime/.venv/bin/python" "$runtime/index.py" \
  "$runtime/data/wikipedia.parquet" "$runtime/data/search.sqlite"
cp search/search.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
sudo loginctl enable-linger "$USER"
systemctl --user enable --now search.service
sudo tailscale serve --bg --http=80 http://127.0.0.1:8765
```

The builder refuses to overwrite an existing database. Build to a new filename to
preserve an existing index. The service binds only to loopback; Tailscale Serve
exposes it within the tailnet (HTTP inside the encrypted Tailscale connection).
There is no public listener, Funnel, or additional application login. Tailnet
access rules determine who can read the corpus. No credentials are needed.

```sh
python3 -m unittest discover -s search -v
node --check search/app.js
curl 'http://agent-server/api/search?q=quantum%20mec'
systemctl --user status search.service
```
