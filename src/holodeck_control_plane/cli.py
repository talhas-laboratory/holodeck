from __future__ import annotations

import argparse

from .service import serve
from .project import initialize_project, policy_decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Holodeck")
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
    policy_parser = commands.add_parser(
        "policy-check",
        help="Look up an advisory project action policy",
        description="Look up an advisory policy decision; this command does not enforce or block actions.",
    )
    policy_parser.add_argument("action")
    policy_parser.add_argument("--path", default=".")
    mcp_parser = commands.add_parser("mcp", help="Run the Holodeck MCP adapter over a local HTTP runtime")
    mcp_parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8787",
        help="Base URL of a running Holodeck HTTP runtime",
    )
    args = parser.parse_args()
    if args.command == "init":
        result = initialize_project(args.path, force=args.force)
        print(f"initialized {result['manifest']}")
        return
    if args.command == "policy-check":
        print(policy_decision(args.path, args.action))
        return
    if args.command == "mcp":
        from holodeck_control_plane.mcp_server import run_mcp

        run_mcp(base_url=args.base_url)
        return
    serve(database=args.database, host=args.host, port=args.port, insecure_bind=args.insecure_bind)
