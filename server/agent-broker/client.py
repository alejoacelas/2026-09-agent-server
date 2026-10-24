#!/usr/bin/env python3
"""gh and gog for the agent user: forwards the command to the credential broker (see broker.py).
Install as ~/.local/bin/gh and ~/.local/bin/gog for agent; the file name picks the command."""
import json
import os
import socket
import sys

argv = [os.path.basename(sys.argv[0]), *sys.argv[1:]]
stdin = "" if sys.stdin.isatty() else sys.stdin.read()
with socket.socket(socket.AF_UNIX) as s:
    s.connect("/srv/agent-broker/broker.sock")
    s.sendall((json.dumps({"argv": argv, "stdin": stdin}) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
reply = json.loads(data)
sys.stdout.write(reply["stdout"])
sys.stderr.write(reply["stderr"])
sys.exit(reply["code"])
