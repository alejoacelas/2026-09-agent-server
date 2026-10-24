"""Credential broker: lets the `agent` user act with Alejo's credentials without reading them.

Runs as alejo. Two front doors:

1. A Unix socket (/srv/agent-broker/broker.sock, group agent) that runs `gh` and `gog` for the
   agent. Commands that print or change credentials are refused, commands run from an empty folder,
   and file paths must be inside /srv/agent-share, so the agent can't make them read or write
   Alejo's files.
2. An HTTP proxy on 127.0.0.1:8790 that forwards /<route>/... to an upstream and adds that route's
   secret, so tools such as git can push to GitHub without holding a token. Routes are in
   routes.json; secrets come from `gh auth token` or 1Password (`op-agent read`) at start-up.
"""

import json
import os
import socket
import socketserver
import subprocess
import threading
import urllib.error
import urllib.request
from base64 import b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
SOCKET = Path("/srv/agent-broker/broker.sock")
SHARE = Path("/srv/agent-share")
EMPTY = Path("/srv/agent-broker/empty")  # owned by alejo, not writable by agent
HERE = Path(__file__).parent
BIN = {"gh": "/usr/bin/gh", "gog": str(HOME / ".local/bin/gog")}
# First words that print, export or change credentials, run arbitrary code, or add account keys.
REFUSED = {
    "gh": {"auth", "extension", "ext", "alias", "config", "ssh-key", "gpg-key", "codespace", "cs"},
    "gog": {"auth", "config", "login", "logout"},
}
REFUSED_FLAGS = {"--access-token", "--home"}


def outside_share(value: str) -> bool:
    """True if value, or the part after "=" or "@", names a file outside the share.
    Words such as owner/repo stay relative to EMPTY, which nobody can write to."""
    for v in {value, value.split("=", 1)[-1]}:
        v = v.lstrip("@")
        if v.startswith(("/", "~", "./", "../")) or v == ".." or "/../" in v or v.endswith("/.."):
            p = Path(os.path.expanduser(v))
            real = (p if p.is_absolute() else EMPTY / p).resolve()
            if real != SHARE and SHARE not in real.parents:
                return True
    return False


def check(argv):
    if not argv or argv[0] not in BIN:
        return "only gh and gog are available through the broker"
    # Any bare word counts, so a flag value placed before the subcommand can't hide it.
    refused = [a for a in argv[1:] if a in REFUSED[argv[0]]]
    if refused:
        return f"`{argv[0]} {refused[0]}` is not available to agents"
    for a in argv[1:]:
        if a.split("=", 1)[0] in REFUSED_FLAGS:
            return f"{a.split('=', 1)[0]} is not available to agents"
        if outside_share(a):
            return f"file paths must be inside {SHARE}: {a}"
    return None


class Commands(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            req = json.loads(self.rfile.readline())
            argv = [str(a) for a in req.get("argv", [])]
            problem = check(argv)
            if problem:
                reply = {"code": 2, "stdout": "", "stderr": f"agent-broker: {problem}\n"}
            else:
                env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(HOME), "LANG": "C.UTF-8",
                       "GIT_CEILING_DIRECTORIES": str(EMPTY.parent), "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"}
                out = subprocess.run([BIN[argv[0]], *argv[1:]], input=req.get("stdin", ""), cwd=EMPTY, env=env,
                                     capture_output=True, text=True, timeout=600)
                reply = {"code": out.returncode, "stdout": out.stdout, "stderr": out.stderr}
        except Exception as e:  # report, don't crash the broker
            reply = {"code": 1, "stdout": "", "stderr": f"agent-broker: {e}\n"}
        self.wfile.write((json.dumps(reply) + "\n").encode())


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def load_routes():
    routes = json.loads((HERE / "routes.json").read_text())
    for name, r in routes.items():
        if r["secret"] == "gh":
            value = subprocess.run(["/usr/bin/gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
        else:
            value = subprocess.run([str(HOME / ".local/bin/op-agent"), "read", r["secret"]],
                                   capture_output=True, text=True, check=True).stdout.strip()
        r["value"] = ("Basic " + b64encode(f"x-access-token:{value}".encode()).decode()) if r.get("basic") else (r.get("prefix", "") + value)
    return routes


ROUTES = {}
HOP = {"host", "connection", "keep-alive", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "content-length"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # pass redirects to the client instead of sending the secret elsewhere


OPENER = urllib.request.build_opener(NoRedirect)


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def forward(self):
        name, _, rest = self.path.lstrip("/").partition("/")
        route = ROUTES.get(name)
        if not route:
            self.send_error(404, "unknown route")
            return
        body = self.read_body() if self.command in ("POST", "PUT", "PATCH") else None
        req = urllib.request.Request(route["upstream"].rstrip("/") + "/" + rest, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in HOP and k.lower() != route["header"].lower():
                req.add_header(k, v)
        req.add_header(route["header"], route["value"])
        try:
            resp = OPENER.open(req, timeout=600)
        except urllib.error.HTTPError as e:
            resp = e
        data = resp.read()
        self.send_response(resp.status if hasattr(resp, "status") else resp.code)
        for k, v in resp.headers.items():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def read_body(self):
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():  # git sends large pushes chunked
            parts = []
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if not size:
                    while self.rfile.readline().strip():
                        pass
                    return b"".join(parts)
                parts.append(self.rfile.read(size))
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = forward


if __name__ == "__main__":
    ROUTES.update(load_routes())
    SOCKET.unlink(missing_ok=True)
    commands = UnixServer(str(SOCKET), Commands)
    os.chmod(SOCKET, 0o660)  # the folder is setgid agent, so the socket is group agent
    threading.Thread(target=commands.serve_forever, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", 8790), Proxy).serve_forever()
