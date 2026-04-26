from __future__ import annotations

import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .system_monitor import collect_monitor_snapshot, render_monitor_summary


def render_console_html(snapshot: dict[str, Any]) -> str:
    monitor_summary = escape(render_monitor_summary(snapshot))
    commands = [
        "research-ai-local --config local_ai.config.json monitor",
        "research-ai-local --config local_ai.config.json models",
        'research-ai-local --config local_ai.config.json compress --source README.md --query "review-gated workflow"',
        'research-ai-local --config local_ai.config.json ask "Draft a review-gated answer." --source README.md',
        'research-ai-local --config local_ai.config.json ideate "Generate research ideas." --source /path/to/source.pdf',
    ]
    command_items = "\n".join(f"<li><code>{escape(command)}</code></li>" for command in commands)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local Research AI Console</title>
  <style>
    :root {{
      --bg: #f6f3ed;
      --ink: #1f2933;
      --muted: #5c6670;
      --card: #fffdf8;
      --line: #d8d0c2;
      --accent: #234f42;
    }}
    body {{
      margin: 0;
      background: linear-gradient(135deg, #f8f4ec, #edf3ef);
      color: var(--ink);
      font: 16px/1.5 ui-serif, Georgia, "Times New Roman", serif;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      letter-spacing: -0.02em;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 19px;
    }}
    p {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 20px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
      box-shadow: 0 10px 30px rgba(35, 79, 66, 0.08);
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #17211d;
      color: #eff7f1;
      border-radius: 12px;
      padding: 16px;
      overflow: auto;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    .pill {{
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      background: #dfe8df;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
    }}
    li {{
      margin-bottom: 8px;
    }}
  </style>
</head>
<body>
  <main>
    <span class="pill">local only · review-gated · no auto-finalization</span>
    <h1>Local Research AI Console</h1>
    <p>A compact operations surface for model status, system load, token estimates, and safe research commands.</p>
    <div class="grid">
      <section class="card">
        <h2>Live Status</h2>
        <pre id="status">{monitor_summary}</pre>
      </section>
      <section class="card">
        <h2>Safe Commands</h2>
        <ul>{command_items}</ul>
        <p>Run commands from the repository root. Outputs remain draft or review-gated unless explicitly validated.</p>
      </section>
      <section class="card">
        <h2>Model Switching Rule</h2>
        <p>If the primary local model is weak or unstable, switch the configured model or rely on the review backend fallback. Switching models changes draft generation only; it does not bypass human review.</p>
      </section>
      <section class="card">
        <h2>Research Design Pattern</h2>
        <p>Borrowed from systems such as AI co-scientist, Hermes, OpenClaw, and DeepScientist: generate, reflect, rank, preserve failures, and keep review memory. This console keeps those patterns local and conservative.</p>
      </section>
    </div>
  </main>
  <script>
    async function refreshStatus() {{
      try {{
        const response = await fetch('/api/monitor');
        const payload = await response.json();
        document.getElementById('status').textContent = payload.summary_text;
      }} catch (error) {{
        document.getElementById('status').textContent = 'Status refresh failed: ' + error;
      }}
    }}
    setInterval(refreshStatus, 10000);
  </script>
</body>
</html>
"""


class LocalConsoleServer:
    def __init__(self, repo_root: Path, config: dict[str, Any]) -> None:
        self.repo_root = repo_root
        self.config = config

    def handler_class(self) -> type[BaseHTTPRequestHandler]:
        console = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

            def _send(self, status: int, body: str, content_type: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:
                if self.path in {"/", "/index.html"}:
                    snapshot = collect_monitor_snapshot(console.repo_root, console.config)
                    self._send(200, render_console_html(snapshot), "text/html")
                    return
                if self.path == "/api/monitor":
                    snapshot = collect_monitor_snapshot(console.repo_root, console.config)
                    payload = {
                        "snapshot": snapshot,
                        "summary_text": render_monitor_summary(snapshot),
                    }
                    self._send(200, json.dumps(payload, ensure_ascii=False), "application/json")
                    return
                self._send(404, "Not found", "text/plain")

        return Handler


def run_local_console(
    repo_root: Path,
    config: dict[str, Any],
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Local console is restricted to 127.0.0.1 / localhost.")
    console = LocalConsoleServer(repo_root=repo_root, config=config)
    server = ThreadingHTTPServer((host, port), console.handler_class())
    print(f"Local Research AI Console: http://{host}:{port}")
    print("Press Ctrl+C to stop. The console is status-only and review-gated.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nConsole stopped.")
    finally:
        server.server_close()
