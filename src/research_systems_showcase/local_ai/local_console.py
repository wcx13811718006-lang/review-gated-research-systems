from __future__ import annotations

import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .system_monitor import collect_monitor_snapshot, render_monitor_summary


def _badge_class(status: str) -> str:
    normalized = status.casefold()
    if normalized in {"ok", "reachable", "nominal"}:
        return "good"
    if normalized in {"attention", "model_unavailable"}:
        return "warn"
    return "muted"


def _short_path(path: str, max_chars: int = 42) -> str:
    if len(path) <= max_chars:
        return path
    return "..." + path[-max_chars:]


def _command_cards() -> list[dict[str, str]]:
    return [
        {
            "title": "查看状态",
            "when": "先确认电脑负载、模型是否在线、token 使用情况。",
            "command": "research-ai-local --config local_ai.config.json monitor",
        },
        {
            "title": "查看模型",
            "when": "需要判断 Ollama / LM Studio 当前可用模型时使用。",
            "command": "research-ai-local --config local_ai.config.json models",
        },
        {
            "title": "压缩材料",
            "when": "长文献先压缩，降低草稿生成 token 成本。压缩结果仍需复核。",
            "command": 'research-ai-local --config local_ai.config.json compress --source README.md --query "review-gated workflow"',
        },
        {
            "title": "研究问答草稿",
            "when": "围绕一份材料生成可复核草稿，不作为最终结论。",
            "command": 'research-ai-local --config local_ai.config.json ask "Draft a review-gated answer." --source README.md',
        },
        {
            "title": "文献创意起点",
            "when": "从论文或法律材料提取研究思路，默认进入人工复核。",
            "command": 'research-ai-local --config local_ai.config.json ideate "Generate research ideas." --source /path/to/source.pdf',
        },
    ]


def render_console_html(snapshot: dict[str, Any]) -> str:
    monitor_summary = escape(render_monitor_summary(snapshot))
    summary = snapshot.get("summary", {})
    cpu = snapshot.get("cpu", {})
    memory = snapshot.get("memory", {})
    thermal = snapshot.get("thermal", {})
    token_usage = snapshot.get("token_usage", {})
    backends = snapshot.get("backends", {})
    model_routing = snapshot.get("model_routing", {})
    disk = snapshot.get("disk", [])

    overall_status = str(summary.get("status", "unknown"))
    ollama = backends.get("ollama", {})
    lmstudio = backends.get("lmstudio", {})
    primary_model = str(ollama.get("effective_model") or "none")
    review_model = str(lmstudio.get("effective_model") or "none")
    memory_text = (
        f"{memory.get('available_gb')} GB available"
        if memory.get("available_gb") is not None
        else f"{memory.get('free_or_inactive_gb', 'n/a')} GB free/inactive"
    )
    disk_text = "n/a"
    if disk:
        disk_text = f"{disk[0].get('free_gb', 'n/a')} GB free"
    advisories = summary.get("advisories") or []
    advisory_items = (
        "\n".join(f"<li>{escape(str(item))}</li>" for item in advisories)
        if advisories
        else "<li>No current advisories. 可以继续做轻量研究操作。</li>"
    )
    model_cards = "\n".join(
        f"""
        <div class="mini-card">
          <span class="label">{escape(name)}</span>
          <span class="badge {_badge_class(str(status.get('status_label', 'unknown')))}">{escape(str(status.get('status_label', 'unknown')))}</span>
          <strong>{escape(str(status.get('effective_model') or 'no effective model'))}</strong>
          <small>available: {escape(', '.join(status.get('available_models', [])) or 'none')}</small>
        </div>
        """
        for name, status in backends.items()
    )
    command_cards = "\n".join(
        f"""
        <article class="action-card">
          <div>
            <h3>{escape(item['title'])}</h3>
            <p>{escape(item['when'])}</p>
            <code>{escape(item['command'])}</code>
          </div>
          <button type="button" data-command="{escape(item['command'], quote=True)}" onclick="copyCommand(this)">复制命令</button>
        </article>
        """
        for item in _command_cards()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local Research AI Console | 研究 AI 本地操作台</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --ink: #18232e;
      --muted: #5c6875;
      --card: #fffdf7;
      --line: #d6cabb;
      --accent: #215846;
      --accent-2: #7a4e20;
      --soft: #e7efe8;
      --dark: #16231d;
      --good: #1e6b4e;
      --warn: #9a5c00;
    }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(33, 88, 70, 0.12), transparent 34rem),
        linear-gradient(135deg, #f8f4ec, #eef4ef);
      color: var(--ink);
      font: 16px/1.5 Avenir Next, ui-sans-serif, system-ui, sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 56px;
    }}
    h1 {{
      margin: 8px 0 10px;
      font-size: clamp(32px, 5vw, 54px);
      line-height: 1;
      letter-spacing: -0.02em;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 21px;
    }}
    h3 {{
      margin: 0 0 6px;
      font-size: 17px;
    }}
    p, small {{
      color: var(--muted);
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.9fr);
      gap: 18px;
      align-items: stretch;
    }}
    .hero-card, .card, .action-card, .mini-card {{
      background: rgba(255, 253, 247, 0.92);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 45px rgba(35, 79, 66, 0.09);
    }}
    .hero-card {{
      padding: 26px;
    }}
    .status-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 18px;
    }}
    .metric {{
      background: #f4efe5;
      border-radius: 14px;
      padding: 12px;
    }}
    .metric span, .label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 5px;
    }}
    .metric strong {{
      font-size: 18px;
    }}
    .workflow {{
      padding: 22px;
    }}
    .steps {{
      counter-reset: step;
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
    }}
    .steps li {{
      list-style: none;
      display: grid;
      grid-template-columns: 34px 1fr;
      gap: 10px;
      align-items: start;
      color: var(--muted);
    }}
    .steps li::before {{
      counter-increment: step;
      content: counter(step);
      display: inline-grid;
      place-items: center;
      width: 28px;
      height: 28px;
      border-radius: 999px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
    }}
    .card {{
      padding: 22px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 18px;
      margin-top: 18px;
    }}
    .actions {{
      display: grid;
      gap: 12px;
    }}
    .action-card {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      padding: 16px;
      align-items: center;
    }}
    .action-card p {{
      margin: 0 0 10px;
    }}
    .action-card code {{
      display: block;
      background: #f3eadc;
      border-radius: 10px;
      padding: 9px 10px;
      white-space: nowrap;
      overflow-x: auto;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{
      background: #174536;
    }}
    .side-stack {{
      display: grid;
      gap: 18px;
    }}
    .mini-list {{
      display: grid;
      gap: 10px;
    }}
    .mini-card {{
      padding: 14px;
    }}
    .mini-card strong, .mini-card small {{
      display: block;
      margin-top: 6px;
      word-break: break-word;
    }}
    .badge, .pill {{
      display: inline-block;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 800;
    }}
    .pill {{
      padding: 5px 11px;
      background: #dfe8df;
      color: var(--accent);
    }}
    .badge {{
      padding: 4px 10px;
      background: #e8e6df;
      color: var(--muted);
    }}
    .badge.good {{
      background: #dceee4;
      color: var(--good);
    }}
    .badge.warn {{
      background: #fff1d6;
      color: var(--warn);
    }}
    .advisories {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    details {{
      margin-top: 18px;
    }}
    summary {{
      cursor: pointer;
      color: var(--accent);
      font-weight: 800;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: var(--dark);
      color: #eff7f1;
      border-radius: 12px;
      padding: 16px;
      overflow: auto;
      max-height: 420px;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.9em;
    }}
    .toast {{
      position: fixed;
      right: 20px;
      bottom: 20px;
      background: var(--dark);
      color: white;
      padding: 11px 14px;
      border-radius: 12px;
      opacity: 0;
      transform: translateY(10px);
      transition: 180ms ease;
      pointer-events: none;
    }}
    .toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
    @media (max-width: 860px) {{
      .hero, .grid {{
        grid-template-columns: 1fr;
      }}
      .action-card {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-card">
        <span class="pill">local only · review-gated · no auto-finalization</span>
        <h1>研究 AI 本地操作台</h1>
        <p>给研究者使用的简洁入口：先看系统是否健康，再复制安全命令运行草稿、文献创意或 token 压缩。网页本身不会自动最终化任何研究输出。</p>
        <div class="status-strip" id="summary-cards">
          <div class="metric">
            <span>总体状态</span>
            <strong><span class="badge {_badge_class(overall_status)}">{escape(overall_status)}</span></strong>
          </div>
          <div class="metric">
            <span>CPU 负载</span>
            <strong>{escape(str(cpu.get('load_ratio_1m', 'n/a')))}</strong>
          </div>
          <div class="metric">
            <span>内存</span>
            <strong>{escape(memory_text)}</strong>
          </div>
          <div class="metric">
            <span>温度/压力</span>
            <strong>{escape(str(thermal.get('thermal_pressure', 'unavailable')))}</strong>
          </div>
          <div class="metric">
            <span>Token 估算</span>
            <strong>{escape(str(token_usage.get('estimated_total_tokens', 0)))}</strong>
          </div>
          <div class="metric">
            <span>磁盘</span>
            <strong>{escape(disk_text)}</strong>
          </div>
        </div>
      </div>
      <aside class="workflow hero-card">
        <h2>怎么操作</h2>
        <ol class="steps">
          <li><strong>先看状态。</strong> 确认总体状态、Ollama、LM Studio 和电脑负载正常。</li>
          <li><strong>选择任务。</strong> 下方选择“查看模型 / 压缩材料 / 研究问答 / 文献创意”。</li>
          <li><strong>复制命令。</strong> 点击复制，在启动脚本打开的终端或新终端里粘贴运行。</li>
          <li><strong>人工复核。</strong> 所有模型输出都是草稿，进入 review-gated 流程后再用于研究。</li>
        </ol>
      </aside>
    </section>

    <div class="grid">
      <section class="card">
        <h2>常用研究操作</h2>
        <div class="actions">{command_cards}</div>
      </section>

      <aside class="side-stack">
        <section class="card">
          <h2>模型状态</h2>
          <div class="mini-list">{model_cards}</div>
          <p>主模型：<strong>{escape(primary_model)}</strong><br>复核/备用模型：<strong>{escape(review_model)}</strong></p>
          <p>{escape(str(model_routing.get('policy', 'Model switching does not bypass review gates.')))}</p>
        </section>

        <section class="card">
          <h2>提醒</h2>
          <ul class="advisories">{advisory_items}</ul>
        </section>

        <section class="card">
          <h2>输出在哪里</h2>
          <p>命令运行后会写入本地 artifact 目录。不要只看模型回答，要同时看 request、review_gate 和 source profile。</p>
          <p><strong>当前 token 统计目录：</strong><br>{escape(_short_path(str(token_usage.get('source', 'outputs/local_ai_runs'))))}</p>
        </section>
      </aside>
    </div>

    <details>
      <summary>展开原始诊断日志</summary>
      <pre id="status">{monitor_summary}</pre>
    </details>
  </main>
  <div class="toast" id="toast">已复制命令</div>
  <script>
    function copyCommand(button) {{
      const command = button.getAttribute('data-command');
      navigator.clipboard.writeText(command).then(() => {{
        const toast = document.getElementById('toast');
        toast.classList.add('show');
        button.textContent = '已复制';
        setTimeout(() => {{
          toast.classList.remove('show');
          button.textContent = '复制命令';
        }}, 1600);
      }});
    }}
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
