from __future__ import annotations

import argparse

from .service import serve
from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(description="Holodeck Runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve", help="Run the local coordination API")
    serve_parser.add_argument("--database", default="holodeck.db")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    init_parser = commands.add_parser("init", help="Initialize a local SQLite store")
    init_parser.add_argument("--database", default="holodeck.db")
    args = parser.parse_args()
    if args.command == "init":
        Store(args.database)
        print(f"initialized {args.database}")
        return
    serve(database=args.database, host=args.host, port=args.port)
