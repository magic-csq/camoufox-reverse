#!/usr/bin/env python3
"""crb — camoufox-reverse-browser one-command CLI.

Wraps the FIFO long-session batch mode of mcp/run-client.sh so an agent never
has to manage mkfifo/echo/tail itself:

    crb.py --project-dir /abs/evidence launch [--headless]
    crb.py --project-dir /abs/evidence navigate https://target.example/
    crb.py --project-dir /abs/evidence click 'button:has-text("Next")'
    crb.py --project-dir /abs/evidence type 'input[type="email"]' 'user@x.com'
    crb.py --project-dir /abs/evidence snapshot
    crb.py --project-dir /abs/evidence eval 'document.title'
    crb.py --project-dir /abs/evidence call <tool> --arguments '<json>'
    crb.py --project-dir /abs/evidence stop

The first command auto-starts a resident MCP server (browser survives across
commands); `stop` closes the browser and shuts the server down. Every command
prints the tool's real JSON result to stdout and exits non-zero on failure.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

TOOLKIT_ROOT = Path(os.environ.get("CAMOUFOX_REVERSE_ROOT") or Path(__file__).resolve().parent.parent)
DEFAULT_PROXY = "http://127.0.0.1:7890"


def _state_dir(project_dir: Path) -> Path:
    state = project_dir / ".crb"
    state.mkdir(parents=True, exist_ok=True)
    return state


def _server_alive(state: Path) -> bool:
    pidfile = state / "server.pid"
    if not pidfile.exists():
        return False
    try:
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError):
        return False


def _start_server(project_dir: Path, proxy: str, timeout: float) -> None:
    state = _state_dir(project_dir)
    fifo = state / "mcp.fifo"
    results = state / "results.jsonl"
    if fifo.exists() and not _is_fifo(fifo):
        fifo.unlink()
    if not fifo.exists():
        os.mkfifo(fifo)
    runner = TOOLKIT_ROOT / "mcp" / "run-client.sh"
    if not runner.exists():
        raise SystemExit(f"crb: missing {runner} — is CAMOUFOX_REVERSE_ROOT correct?")
    out = open(results, "ab", buffering=0)
    proc = subprocess.Popen(
        [
            "bash", str(runner),
            "--browser-project-dir", str(TOOLKIT_ROOT),
            "--project-dir", str(project_dir),
            "--proxy", proxy,
            "--timeout", str(int(timeout)),
            "batch", str(fifo),
        ],
        stdout=out,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    (state / "server.pid").write_text(str(proc.pid))
    # Give the server a moment to come up; calls also tolerate slow starts.
    time.sleep(2)


def _is_fifo(path: Path) -> bool:
    import stat as stat_mod
    try:
        return stat_mod.S_ISFIFO(path.stat().st_mode)
    except OSError:
        return False


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "rb") as fh:
        return sum(1 for _ in fh)


def call_tool(project_dir: Path, tool: str, arguments: dict, timeout: float,
              proxy: str) -> tuple[dict, int]:
    """Send one tool call over the resident FIFO session; return (entry, exit_code)."""
    state = _state_dir(project_dir)
    results = state / "results.jsonl"
    lock = open(state / "lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        if not _server_alive(state):
            _start_server(project_dir, proxy, timeout)
        fifo = state / "mcp.fifo"
        before = _count_lines(results)
        line = json.dumps({"tool": tool, "arguments": arguments}, ensure_ascii=False)
        deadline = time.time() + timeout
        # Opening a FIFO for writing blocks until the server opens it for reading.
        with open(fifo, "w", encoding="utf-8") as fh:
            fh.write(line + "\n")
        while time.time() < deadline:
            if _count_lines(results) > before:
                with open(results, encoding="utf-8") as fh:
                    entry = json.loads(fh.readlines()[-1])
                ok = bool(entry.get("ok")) and not _is_tool_error(entry)
                return entry, 0 if ok else 1
            if not _server_alive(state):
                return {"tool": tool, "ok": False, "error": "server died; see results.jsonl"}, 1
            time.sleep(0.5)
        return {"tool": tool, "ok": False, "error": f"timeout after {timeout}s"}, 1
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _is_tool_error(entry: dict) -> bool:
    try:
        content = entry["result"]["content"][0]
        if content.get("isError"):
            return True
        text = content.get("text", "")
        parsed = json.loads(text)
        return "error" in parsed
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return False


def stop_session(project_dir: Path, timeout: float, proxy: str) -> int:
    state = _state_dir(project_dir)
    if not _server_alive(state):
        print(json.dumps({"status": "not_running"}, ensure_ascii=False))
        return 0
    entry, _ = call_tool(project_dir, "close_browser", {"project_dir": str(project_dir)}, timeout, proxy)
    print(json.dumps(entry, ensure_ascii=False))
    entry, code = call_tool(project_dir, "__shutdown__", {}, 30, proxy)
    print(json.dumps(entry, ensure_ascii=False))
    pidfile = state / "server.pid"
    try:
        pid = int(pidfile.read_text().strip())
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.5)
        else:
            os.kill(pid, signal.SIGTERM)
    except (ValueError, OSError):
        pass
    pidfile.unlink(missing_ok=True)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="camoufox-reverse-browser one-command CLI")
    parser.add_argument("--project-dir", required=True, type=Path, help="absolute evidence project dir")
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--timeout", type=float, default=180.0, help="per-call timeout seconds")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("launch", help="launch browser (start session if needed)").add_argument(
        "--headless", action=argparse.BooleanOptionalAction, default=True)
    sub.add_parser("navigate").add_argument("url")
    sub.add_parser("click").add_argument("selector")
    type_p = sub.add_parser("type")
    type_p.add_argument("selector")
    type_p.add_argument("text")
    sub.add_parser("snapshot", help="take an aria snapshot of the page")
    sub.add_parser("screenshot", help="take a screenshot (prints base64 JSON)")
    eval_p = sub.add_parser("eval", help="evaluate a JS expression")
    eval_p.add_argument("expression")
    sub.add_parser("requests", help="list captured network requests")
    sub.add_parser("page-info")
    call_p = sub.add_parser("call", help="call any MCP tool by name")
    call_p.add_argument("tool")
    call_p.add_argument("--arguments", default="{}", help="JSON object")
    sub.add_parser("stop", help="close browser and shut down the resident server")
    sub.add_parser("status", help="show whether the resident server is alive")

    ns = parser.parse_args(argv)
    project_dir = ns.project_dir.expanduser().resolve()

    if ns.cmd == "status":
        alive = _server_alive(_state_dir(project_dir))
        print(json.dumps({"server_alive": alive, "project_dir": str(project_dir)}, ensure_ascii=False))
        return 0 if alive else 1
    if ns.cmd == "stop":
        return stop_session(project_dir, ns.timeout, ns.proxy)

    if ns.cmd == "call":
        try:
            arguments = json.loads(ns.arguments)
            if not isinstance(arguments, dict):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            print("crb: --arguments must be a JSON object", file=sys.stderr)
            return 2
        tool = ns.tool
    elif ns.cmd == "launch":
        tool, arguments = "launch_browser", {"headless": ns.headless}
    elif ns.cmd == "navigate":
        tool, arguments = "navigate", {"url": ns.url}
    elif ns.cmd == "click":
        tool, arguments = "click", {"selector": ns.selector}
    elif ns.cmd == "type":
        tool, arguments = "type_text", {"selector": ns.selector, "text": ns.text}
    elif ns.cmd == "snapshot":
        tool, arguments = "take_snapshot", {}
    elif ns.cmd == "screenshot":
        tool, arguments = "take_screenshot", {}
    elif ns.cmd == "eval":
        tool, arguments = "evaluate_js", {"expression": ns.expression}
    elif ns.cmd == "requests":
        tool, arguments = "list_network_requests", {}
    elif ns.cmd == "page-info":
        tool, arguments = "get_page_info", {}
    else:
        parser.error(f"unknown command {ns.cmd}")
    arguments.setdefault("project_dir", str(project_dir))

    entry, code = call_tool(project_dir, tool, arguments, ns.timeout, ns.proxy)
    print(json.dumps(entry, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
