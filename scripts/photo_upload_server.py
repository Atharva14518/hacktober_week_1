#!/usr/bin/env python3
"""Run the offline phone photo receiver on a local hotspot."""

from __future__ import annotations

import argparse
import secrets
import socket
from pathlib import Path

import uvicorn

from wildquest.vision.upload import create_upload_app


ROOT = Path(__file__).resolve().parents[1]


def local_ip() -> str:
    """Best-effort LAN address lookup without sending a packet."""
    host = socket.gethostname()
    try:
        return socket.gethostbyname(host)
    except OSError:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--directory", type=Path, default=ROOT / "artifacts" / "uploads")
    args = parser.parse_args()
    token = secrets.token_urlsafe(18)
    print(f"On the phone hotspot, open http://{local_ip()}:{args.port}/?token={token}")
    print("The one-session upload token is embedded in that private link.")
    print("No internet connection is used. Press Control-C when the upload is done.")
    uvicorn.run(
        create_upload_app(args.directory, token),
        host=args.host,
        port=args.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
