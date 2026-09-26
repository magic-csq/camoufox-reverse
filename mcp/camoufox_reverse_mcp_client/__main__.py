"""Command line entrypoint for the dependency-free MCP client."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

from .client import MCPError, MCPStdioClient


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Camoufox Reverse MCP stdio client")
    parser.add_argument("--command", required=True, help="MCP server executable")
    parser.add_argument("--project-dir", help="Absolute project directory forwarded to the server")
    parser.add_argument("--proxy", help="Proxy URL forwarded to the server")
    parser.add_argument("--cwd", type=Path, help="MCP server working directory")
    parser.add_argument("--env", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--start-retries",
        type=int,
        default=2,
        help="Transparent respawn attempts when the server process dies during "
        "the initialize handshake (default: 2; 0 disables)",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list-tools", help="List MCP tools")
    call = subparsers.add_parser("call", help="Call one MCP tool")
    call.add_argument("name")
    call.add_argument("--arguments", default="{}", help="JSON object passed as tool arguments")
    batch = subparsers.add_parser(
        "batch",
        help="Run a sequence of tool calls within ONE server session "
        "(JSON-lines file or '-' for stdin; keeps the browser alive across calls)",
    )
    batch.add_argument("file", help="JSON-lines file of {\"tool\": name, \"arguments\": {...}}, or '-' for stdin")
    batch.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Abort the batch on the first failed call (default: report and continue)",
    )
    return parser


def _parse_env(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, content = value.partition("=")
        if not separator or not name:
            raise ValueError("--env must use NAME=VALUE")
        result[name] = content
    return result


def _server_args(namespace: argparse.Namespace) -> list[str]:
    args: list[str] = []
    if namespace.project_dir is not None:
        args.extend(["--project-dir", namespace.project_dir])
    if namespace.proxy is not None:
        args.extend(["--proxy", namespace.proxy])
    return args


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        namespace = parser.parse_args(argv)
        supplied_env = _parse_env(namespace.env)
        env = {**os.environ, **supplied_env} if supplied_env else None
        client = MCPStdioClient(
            command=namespace.command,
            args=_server_args(namespace),
            env=env,
            cwd=namespace.cwd,
            timeout=namespace.timeout,
            start_retries=namespace.start_retries,
        )
        try:
            client.initialize()
            if namespace.action == "list-tools":
                result: dict[str, Any] = client.list_tools()
                print(json.dumps(result, ensure_ascii=False, sort_keys=True))
                return 0
            if namespace.action == "batch":
                exit_code = 0

                def run_line(lineno: int, raw: str) -> tuple[dict[str, Any] | None, bool]:
                    """Process one batch line; returns (entry, shutdown)."""
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        return None, False
                    tool_name: str | None = None
                    try:
                        spec = json.loads(line)
                        if not isinstance(spec, dict) or not isinstance(spec.get("tool"), str):
                            raise ValueError("each batch line must be {\"tool\": name, \"arguments\": {...}}")
                        tool_name = spec["tool"]
                        if tool_name == "__shutdown__":
                            return {"tool": tool_name, "ok": True, "result": {"status": "shutdown"}}, True
                        arguments = spec.get("arguments", {})
                        if not isinstance(arguments, dict):
                            raise ValueError("batch line arguments must be a JSON object")
                        result = client.call_tool(tool_name, arguments)
                        return {"tool": tool_name, "ok": True, "result": result}, False
                    except MCPError:
                        return {
                            "tool": tool_name,
                            "ok": False,
                            "error": "MCP request failed; details omitted to protect sensitive values.",
                        }, False
                    except (json.JSONDecodeError, ValueError) as error:
                        return {"tool": None, "ok": False, "error": f"line {lineno}: {error}"}, False

                def emit(entry: dict[str, Any]) -> bool:
                    nonlocal exit_code
                    print(json.dumps(entry, ensure_ascii=False), flush=True)
                    if not entry["ok"]:
                        exit_code = 1
                        return namespace.stop_on_error
                    return False

                is_fifo = False
                if namespace.file != "-":
                    try:
                        is_fifo = stat.S_ISFIFO(os.stat(namespace.file).st_mode)
                    except OSError:
                        is_fifo = False
                if is_fifo:
                    # Long-session mode: reopen the FIFO after each writer's EOF so
                    # one server process (and its browser) serves many one-shot
                    # `echo '{"tool": ...}' > fifo` commands. Terminates on
                    # {"tool": "__shutdown__"}.
                    while True:
                        with open(namespace.file, encoding="utf-8") as lines:
                            for lineno, raw in enumerate(lines, start=1):
                                entry, shutdown = run_line(lineno, raw)
                                if entry is None:
                                    continue
                                if emit(entry) or shutdown:
                                    return exit_code
                    # unreachable
                source = sys.stdin if namespace.file == "-" else open(namespace.file, encoding="utf-8")
                with source as lines:
                    for lineno, raw in enumerate(lines, start=1):
                        entry, shutdown = run_line(lineno, raw)
                        if entry is None:
                            continue
                        if emit(entry) or shutdown:
                            return exit_code
                return exit_code
            else:
                try:
                    arguments = json.loads(namespace.arguments)
                except json.JSONDecodeError as error:
                    raise ValueError("--arguments must be a JSON object") from error
                if not isinstance(arguments, dict):
                    raise ValueError("--arguments must be a JSON object")
                result = client.call_tool(namespace.name, arguments)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        finally:
            client.close()
    except (MCPError, OSError, ValueError) as error:
        message = (
            "MCP request failed; details omitted to protect sensitive values."
            if isinstance(error, MCPError)
            else str(error)
        )
        print(json.dumps({"status": "error", "error": {"message": message}}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
