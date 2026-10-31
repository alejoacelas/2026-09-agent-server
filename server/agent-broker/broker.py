"""Credential broker: lets the `agent` user act with Alejo's credentials without reading them.

Runs as alejo. Two front doors:

1. A Unix socket (/srv/agent-broker/broker.sock, group agent) that runs `gh` and `gog` for the
   agent. Commands that print or change credentials are refused, commands run from an empty folder,
   and file paths must be inside /srv/agent-share, so the agent can't make them read or write
   Alejo's files.
2. An HTTP proxy on 127.0.0.1:8790 that forwards /<route>/... to an upstream and adds that route's
   headers, so tools such as git can push to GitHub without holding a token. Routes are in
   routes.json. A header value may embed 1Password references as {op://vault/item/field}; they are
   read with `op-agent read` and re-read after SECRET_TTL seconds, so rotating a key needs only a
   vault update. A route with "allow" forwards only those first path segments (API methods).
"""

import json
import os
import re
import time
import shutil
import socket
import socketserver
import stat
import subprocess
import tempfile
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


def share_parts(value: str):
    """The share path that value, or its part after "=" or "@", names (always a suffix of value),
    and its components below the share; None if it names none."""
    for v in (value, value.split("=", 1)[-1]):
        v = v.lstrip("@")
        if v.startswith(str(SHARE)):
            rel = os.path.relpath(os.path.normpath(v), SHARE)
            if rel == "." or not rel.startswith(".."):
                return v, [] if rel == "." else rel.split("/")
    return None


def open_share_dir(parts, create=False):
    """A descriptor for SHARE/parts, opened one component at a time without following symlinks."""
    fd = os.open(SHARE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o2770, dir_fd=fd)
                except FileExistsError:
                    pass
            fd, old = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd), fd
            os.close(old)
    except BaseException:
        os.close(fd)
        raise
    return fd


def copy_in(dir_fd, name, dest: Path):
    """Copy dir_fd/name (a file or folder; symlinks and other kinds are skipped) to dest."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except FileNotFoundError:
        return
    except OSError:  # a symlink (ELOOP) or something we can't open
        return
    try:
        st = os.fstat(fd)
        if stat.S_ISREG(st.st_mode):
            with open(fd, "rb", closefd=False) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
        elif stat.S_ISDIR(st.st_mode):
            dest.mkdir(exist_ok=True)
            for entry in os.listdir(fd):
                copy_in(fd, entry, dest / entry)
    finally:
        os.close(fd)


def copy_back(staged: Path, parts, before):
    """Write files under staged that are new or changed since staging back to SHARE/parts."""
    paths = [staged] if staged.is_file() else sorted(p for p in staged.rglob("*") if p.is_file()) if staged.is_dir() else []
    for p in paths:
        st = p.stat()
        if before.get(p) == (st.st_size, st.st_mtime_ns):
            continue
        rel = parts + list(p.relative_to(staged).parts) if p != staged else parts
        dir_fd = open_share_dir(rel[:-1], create=True)
        try:
            fd = os.open(rel[-1], os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o660, dir_fd=dir_fd)
            with open(fd, "wb") as dst, open(p, "rb") as src:
                shutil.copyfileobj(src, dst)
        finally:
            os.close(dir_fd)


def stage(argv, tmp: Path):
    """Point share paths in argv at copies in tmp, a folder only alejo can open. check() resolves
    symlinks, but agent could swap a checked path for a symlink to Alejo's files before gh or gog
    opens it; the copies can't be swapped. Returns the new argv and what to copy back."""
    out, staged = [], []
    for i, a in enumerate(argv):
        found = share_parts(a) if i else None
        if not found:
            out.append(a)
            continue
        v, parts = found
        dest = tmp / str(i) / "share"
        dest.mkdir(parents=True)
        if parts:
            dest = dest.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dir_fd = open_share_dir(parts[:-1])
            except FileNotFoundError:  # an output path in a folder the command will create
                dir_fd = None
            if dir_fd is not None:
                try:
                    copy_in(dir_fd, parts[-1], dest)
                finally:
                    os.close(dir_fd)
        else:
            dir_fd = open_share_dir([])
            try:
                for entry in os.listdir(dir_fd):
                    copy_in(dir_fd, entry, dest / entry)
            finally:
                os.close(dir_fd)
        files = [dest] if dest.is_file() else dest.rglob("*") if dest.is_dir() else []
        before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in files if p.is_file()}
        staged.append((dest, parts, before, v))
        out.append(a[: len(a) - len(v)] + str(dest))
    return out, staged


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
                with tempfile.TemporaryDirectory(prefix="agent-broker-") as tmp:
                    staged_argv, staged = stage(argv, Path(tmp))
                    out = subprocess.run([BIN[argv[0]], *staged_argv[1:]], input=req.get("stdin", ""), cwd=EMPTY,
                                         env=env, capture_output=True, text=True, timeout=600)
                    for dest, parts, before, _ in staged:
                        copy_back(dest, parts, before)
                    stdout, stderr = out.stdout, out.stderr
                    for dest, _, _, v in staged:  # show the agent its own paths
                        stdout, stderr = stdout.replace(str(dest), v), stderr.replace(str(dest), v)
                reply = {"code": out.returncode, "stdout": stdout, "stderr": stderr}
        except Exception as e:  # report, don't crash the broker
            reply = {"code": 1, "stdout": "", "stderr": f"agent-broker: {e}\n"}
        self.wfile.write((json.dumps(reply) + "\n").encode())


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


SECRET_TTL = 300
OP_REF = re.compile(r"\{(op://[^{}]+)\}")
_secrets = {}  # reference -> (value, read at)
_secrets_lock = threading.Lock()


def secret(ref):
    """The value of a 1Password reference or "gh", cached for SECRET_TTL seconds."""
    with _secrets_lock:
        value, at = _secrets.get(ref, (None, 0))
        if value is None or time.time() - at > SECRET_TTL:
            if ref == "gh":
                cmd = ["/usr/bin/gh", "auth", "token"]
            else:
                cmd = [str(HOME / ".local/bin/op-agent"), "read", ref]
            value = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
            _secrets[ref] = (value, time.time())
        return value


def route_headers(route):
    """The headers a route adds, with secrets filled in."""
    if "secret" in route:  # the original single-header form, used by the github route
        value = secret(route["secret"])
        if route.get("basic"):
            value = "Basic " + b64encode(f"x-access-token:{value}".encode()).decode()
        return {route["header"]: route.get("prefix", "") + value}
    return {k: OP_REF.sub(lambda m: secret(m.group(1)), v) for k, v in route["headers"].items()}


def load_routes():
    routes = json.loads((HERE / "routes.json").read_text())
    for r in routes.values():
        route_headers(r)  # fail at start-up, not on first use, if a secret can't be read
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
        # A web page that rebinds its own domain to 127.0.0.1 would arrive under its own name.
        if self.headers.get("Host") not in ("127.0.0.1:8790", "localhost:8790"):
            self.send_error(403, "unknown host")
            return
        name, _, rest = self.path.lstrip("/").partition("/")
        route = ROUTES.get(name)
        if not route:
            self.send_error(404, "unknown route")
            return
        if "allow" in route and rest.split("?", 1)[0].split("/", 1)[0] not in route["allow"]:
            self.send_error(403, "method not allowed on this route")
            return
        body = self.read_body() if self.command in ("POST", "PUT", "PATCH") else None
        req = urllib.request.Request(route["upstream"].rstrip("/") + "/" + rest, data=body, method=self.command)
        added = route_headers(route)
        for k, v in self.headers.items():
            if k.lower() not in HOP and k.lower() not in {h.lower() for h in added}:
                req.add_header(k, v)
        for k, v in added.items():
            req.add_header(k, v)
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
