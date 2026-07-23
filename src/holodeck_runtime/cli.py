from __future__ import annotations

import argparse

from .service import serve
from .project import initialize_project, policy_decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Holodeck Runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve", help="Run the local coordination API")
    serve_parser.add_argument("--database", default="holodeck.db")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.add_argument(
        "--insecure-bind",
        action="store_true",
        help="Allow binding to non-loopback interfaces",
    )
    init_parser = commands.add_parser("init", help="Initialize a project-local Holodeck policy")
    init_parser.add_argument("--path", default=".")
    init_parser.add_argument("--force", action="store_true")
    policy_parser = commands.add_parser("policy-check", help="Read a project action policy")
    policy_parser.add_argument("action")
    policy_parser.add_argument("--path", default=".")
    args = parser.parse_args()
    if args.command == "init":
        result = initialize_project(args.path, force=args.force)
        print(f"initialized {result['manifest']}")
        return
    if args.command == "policy-check":
        print(policy_decision(args.path, args.action))
        return
    serve(database=args.database, host=args.host, port=args.port, insecure_bind=args.insecure_bind)
