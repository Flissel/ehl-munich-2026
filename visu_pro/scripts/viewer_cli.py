"""Tiny CLI for talking to the viewer's control port directly (debugging / smoke tests).

    python scripts/viewer_cli.py get_viewer_status
    python scripts/viewer_cli.py set_paint paint_id=racing_red
    python scripts/viewer_cli.py set_wheel_style style_id=sport
"""
import json
import os
import socket
import sys


def send(command, args=None, port=None, token=None, timeout=10.0):
    port = port or int(os.environ.get("VIEWER_CONTROL_PORT", "30777"))
    token = token if token is not None else os.environ.get("VIEWER_TOKEN", "")
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall((json.dumps({"id": 1, "token": token, "command": command, "args": args or {}}) + "\n").encode())
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.decode())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "get_viewer_status"
    kv = dict(a.split("=", 1) for a in sys.argv[2:])
    print(json.dumps(send(cmd, kv), indent=2))
