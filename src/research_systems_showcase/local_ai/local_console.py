from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
            "action": "monitor",
            "when": "先确认电脑负载、模型是否在线、token 使用情况。",
            "command": "research-ai-local --config local_ai.config.json monitor",
        },
        {
            "title": "查看模型",
            "action": "models",
            "when": "需要判断 Ollama / LM Studio 当前可用模型时使用。",
            "command": "research-ai-local --config local_ai.config.json models",
        },
        {
            "title": "压缩材料",
            "action": "compress",
            "when": "长文献先压缩，降低草稿生成 token 成本。压缩结果仍需复核。",
            "command": 'research-ai-local --config local_ai.config.json compress --source README.md --query "review-gated workflow"',
        },
        {
            "title": "研究问答草稿",
            "action": "ask",
            "when": "围绕一份材料生成可复核草稿，不作为最终结论。",
            "command": 'research-ai-local --config local_ai.config.json ask "Draft a review-gated answer." --source README.md',
        },
        {
            "title": "文献创意起点",
            "action": "ideate",
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


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _output_run_dir(repo_root: Path, config: dict[str, Any]) -> Path:
    monitor_config = config.get("monitor", {})
    path_text = str(monitor_config.get("token_artifact_dir") or config.get("outputs_dir", "outputs/local_ai_runs"))
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else repo_root / path


def collect_recent_runs(repo_root: Path, config: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    run_root = _output_run_dir(repo_root, config)
    if not run_root.exists():
        return []
    run_dirs = sorted(
        [path for path in run_root.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    records: list[dict[str, Any]] = []
    for run_dir in run_dirs[:limit]:
        request = _load_json(run_dir / "request.json")
        review_gate = _load_json(run_dir / "review_gate.json")
        if not request and not review_gate:
            continue
        records.append(
            {
                "run_id": request.get("run_id") or run_dir.name,
                "created_at": request.get("created_at", ""),
                "backend": request.get("backend", ""),
                "decision": review_gate.get("decision", "unknown"),
                "review_required": bool(review_gate.get("review_required", True)),
                "failed_checks": review_gate.get("failed_checks", []),
                "path": str(run_dir),
            }
        )
    return records


def _run_items(recent_runs: list[dict[str, Any]]) -> str:
    if not recent_runs:
        return """
        <div class="empty-state">
          <strong>还没有本地运行记录</strong>
          <span>运行 ask / ideate / compress 后，这里会显示最近的审阅状态。</span>
        </div>
        """
    return "\n".join(
        f"""
        <article class="run-row">
          <div>
            <strong>{escape(str(item.get('run_id', 'unknown')))}</strong>
            <span>{escape(str(item.get('decision', 'unknown')))} · backend {escape(str(item.get('backend', '')))}</span>
          </div>
          <small>{escape(_short_path(str(item.get('path', ''))))}</small>
        </article>
        """
        for item in recent_runs
    )


def _runs_payload(recent_runs: list[dict[str, Any]]) -> str:
    return json.dumps({"recent_runs": recent_runs}, ensure_ascii=False)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _effective_config_path(repo_root: Path, config_path: Path | None) -> Path | None:
    if config_path is not None:
        path = config_path.expanduser()
        return path if path.is_absolute() else repo_root / path
    local_config = repo_root / "local_ai.config.json"
    if local_config.exists():
        return local_config
    example_config = repo_root / "configs" / "local_ai.example.json"
    return example_config if example_config.exists() else None


@dataclass
class ConsoleJob:
    job_id: str
    action: str
    title: str
    command_display: str
    argv: list[str]
    status: str = "queued"
    stage: str = "queued"
    created_at: str = field(default_factory=_utc_now)
    started_at: str = ""
    completed_at: str = ""
    started_monotonic: float = 0.0
    completed_monotonic: float = 0.0
    return_code: int | None = None
    pid: int | None = None
    error: str = ""
    log_lines: list[str] = field(default_factory=list)
    backend_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        duration = 0.0
        if self.started_monotonic:
            end = time.monotonic() if self.status == "running" else self.completed_monotonic
            duration = max(0.0, end - self.started_monotonic)
        return {
            "job_id": self.job_id,
            "action": self.action,
            "title": self.title,
            "command_display": self.command_display,
            "status": self.status,
            "stage": self.stage,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(duration, 1),
            "return_code": self.return_code,
            "pid": self.pid,
            "error": self.error,
            "log_tail": "\n".join(self.log_lines[-120:]),
            "backend_snapshot": self.backend_snapshot,
            "result_summary": self._result_summary(),
        }

    def _result_summary(self) -> dict[str, Any]:
        labels = {
            "Backend": "backend",
            "Fallback used": "fallback_used",
            "Decision": "decision",
            "Review required": "review_required",
            "Can export final": "can_export_final",
            "Generation error": "generation_error",
        }
        summary: dict[str, Any] = {"artifacts": []}
        for line in self.log_lines:
            for label, key in labels.items():
                prefix = f"{label}:"
                if line.startswith(prefix):
                    summary[key] = line.removeprefix(prefix).strip()
            if line.startswith("  - ") and ":" in line:
                name, path = line[4:].split(":", 1)
                summary["artifacts"].append({"name": name.strip(), "path": path.strip()})
        return summary


class LocalConsoleJobManager:
    allowed_actions = {"monitor", "models", "compress", "ask", "ideate"}

    def __init__(self, repo_root: Path, config: dict[str, Any], config_path: Path | None = None) -> None:
        self.repo_root = repo_root
        self.config = config
        self.config_path = _effective_config_path(repo_root, config_path)
        self.jobs: dict[str, ConsoleJob] = {}
        self.lock = threading.Lock()

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.lock:
            jobs = list(self.jobs.values())[-limit:]
            return [job.to_dict() for job in reversed(jobs)]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return job.to_dict() if job else None

    def start_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        job = self._build_job(payload)
        with self.lock:
            self.jobs[job.job_id] = job
        thread = threading.Thread(target=self._run_job, args=(job.job_id,), daemon=True)
        thread.start()
        return job.to_dict()

    def _build_job(self, payload: dict[str, Any]) -> ConsoleJob:
        action = str(payload.get("action") or "").strip().casefold()
        if action not in self.allowed_actions:
            raise ValueError("Unsupported action. Only safe local console actions are allowed.")
        prompt = str(payload.get("prompt") or "").strip()
        source = str(payload.get("source") or "").strip()

        argv = [
            sys.executable,
            "-m",
            "src.research_systems_showcase.local_ai.cli",
        ]
        if self.config_path is not None:
            argv.extend(["--config", str(self.config_path)])

        title = action
        if action == "monitor":
            title = "查看状态"
            argv.append("monitor")
        elif action == "models":
            title = "查看模型"
            argv.append("models")
        elif action == "compress":
            title = "压缩材料"
            source_path = self._resolve_source_path(source or "README.md")
            query = prompt or "review-gated workflow"
            argv.extend(["compress", "--source", str(source_path), "--query", query])
        elif action == "ask":
            title = "研究问答草稿"
            source_path = self._resolve_source_path(source or "README.md")
            question = prompt or "Draft a review-gated answer."
            argv.extend(["ask", question, "--source", str(source_path)])
        elif action == "ideate":
            title = "文献创意起点"
            source_path = self._resolve_source_path(source or "README.md")
            focus = prompt or "Generate research ideas."
            argv.extend(["ideate", focus, "--source", str(source_path)])

        return ConsoleJob(
            job_id=uuid.uuid4().hex[:12],
            action=action,
            title=title,
            command_display=" ".join(shlex.quote(part) for part in argv),
            argv=argv,
        )

    def _resolve_source_path(self, source: str) -> Path:
        path = Path(source).expanduser()
        if not path.is_absolute():
            path = self.repo_root / path
        if not path.exists():
            raise ValueError(f"Source path does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Source path is not a file: {path}")
        return path

    def _run_job(self, job_id: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.status = "running"
            job.stage = "starting local process"
            job.started_at = _utc_now()
            job.started_monotonic = time.monotonic()
            job.backend_snapshot = collect_monitor_snapshot(self.repo_root, self.config).get("backends", {})

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env.setdefault("PYTHONPYCACHEPREFIX", str(Path(os.environ.get("TMPDIR", "/tmp")) / "research_ai_pycache"))
        try:
            process = subprocess.Popen(
                job.argv,
                cwd=self.repo_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self._fail_job(job_id, f"Failed to start process: {exc}")
            return

        with self.lock:
            job = self.jobs[job_id]
            job.pid = process.pid
            job.stage = "running local model/helper command"
            job.log_lines.append(f"Started PID {process.pid}: {job.command_display}")

        assert process.stdout is not None
        for line in process.stdout:
            clean = line.rstrip()
            if not clean:
                continue
            self._append_log(job_id, clean)
            self._infer_stage(job_id, clean)

        return_code = process.wait()
        with self.lock:
            job = self.jobs[job_id]
            job.return_code = return_code
            job.completed_at = _utc_now()
            job.completed_monotonic = time.monotonic()
            job.status = "completed" if return_code == 0 else "failed"
            job.stage = "completed" if return_code == 0 else "failed"
            if return_code != 0 and not job.error:
                job.error = f"Process exited with code {return_code}"

    def _append_log(self, job_id: str, line: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.log_lines.append(line)
            if len(job.log_lines) > 240:
                job.log_lines = job.log_lines[-240:]

    def _infer_stage(self, job_id: str, line: str) -> None:
        normalized = line.casefold()
        stage = ""
        if "local ai run completed" in normalized:
            stage = "writing review-gated artifacts"
        elif "backend:" in normalized:
            stage = "model backend reported"
        elif "decision:" in normalized or "review required:" in normalized:
            stage = "review gate evaluated"
        elif "artifacts:" in normalized:
            stage = "artifact paths available"
        elif "compression completed" in normalized:
            stage = "compression completed"
        elif "local research ai monitor" in normalized:
            stage = "monitor snapshot ready"
        elif "model routing status" in normalized:
            stage = "model routing checked"
        if stage:
            with self.lock:
                self.jobs[job_id].stage = stage

    def _fail_job(self, job_id: str, error: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.status = "failed"
            job.stage = "failed"
            job.error = error
            job.completed_at = _utc_now()
            job.completed_monotonic = time.monotonic()
            job.log_lines.append(error)


def _jobs_payload(jobs: list[dict[str, Any]]) -> str:
    return json.dumps({"jobs": jobs}, ensure_ascii=False)


def render_workbench_html(snapshot: dict[str, Any], recent_runs: list[dict[str, Any]]) -> str:
    monitor_summary = escape(render_monitor_summary(snapshot))
    summary = snapshot.get("summary", {})
    cpu = snapshot.get("cpu", {})
    memory = snapshot.get("memory", {})
    token_usage = snapshot.get("token_usage", {})
    backends = snapshot.get("backends", {})
    disk = snapshot.get("disk", [])
    overall_status = str(summary.get("status", "unknown"))
    memory_text = (
        f"{memory.get('available_gb')} GB"
        if memory.get("available_gb") is not None
        else f"{memory.get('free_or_inactive_gb', 'n/a')} GB"
    )
    disk_text = f"{disk[0].get('free_gb', 'n/a')} GB" if disk else "n/a"
    command_json = json.dumps(_command_cards(), ensure_ascii=False)
    model_rows = "\n".join(
        f"""
        <div class="status-line">
          <span>{escape(name)}</span>
          <strong class="{_badge_class(str(status.get('status_label', 'unknown')))}">{escape(str(status.get('status_label', 'unknown')))}</strong>
          <small>{escape(str(status.get('effective_model') or 'no model'))}</small>
        </div>
        """
        for name, status in backends.items()
    )
    run_items = _run_items(recent_runs)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local Research AI Console | 研究 AI 工作台</title>
  <style>
    :root {{
      --paper: #f3efe6;
      --panel: #fffaf0;
      --ink: #17202a;
      --muted: #66717d;
      --line: #d7cbb8;
      --green: #1f5a45;
      --amber: #a76318;
      --blue: #1d4f73;
      --black: #111a16;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      height: 100svh;
      overflow: hidden;
      color: var(--ink);
      background: linear-gradient(135deg, #f7f2e8 0%, #edf4ef 100%);
      font: 15px/1.45 Avenir Next, ui-sans-serif, system-ui, sans-serif;
    }}
    .shell {{
      display: grid;
      grid-template-columns: 244px minmax(460px, 1fr) 330px;
      height: 100svh;
    }}
    aside, main {{
      min-height: 0;
      overflow: auto;
    }}
    .rail {{
      padding: 22px 16px;
      border-right: 1px solid var(--line);
      background: rgba(255, 250, 240, 0.72);
    }}
    .brand {{
      display: grid;
      gap: 5px;
      margin-bottom: 22px;
    }}
    .brand strong {{
      font-size: 22px;
      letter-spacing: -0.03em;
    }}
    .brand span, .muted {{
      color: var(--muted);
    }}
    .nav {{
      display: grid;
      gap: 8px;
    }}
    .nav button, .copy-btn, .primary-btn, .secondary-btn {{
      border: 0;
      border-radius: 12px;
      cursor: pointer;
      font-weight: 750;
    }}
    .nav button {{
      width: 100%;
      text-align: left;
      padding: 12px;
      background: transparent;
      color: var(--ink);
    }}
    .nav button.active, .nav button:hover {{
      background: #e6eee6;
      color: var(--green);
    }}
    .workspace {{
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) minmax(170px, 250px) auto;
      min-width: 0;
      padding: 22px;
      gap: 14px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 46px);
      letter-spacing: -0.04em;
      line-height: 0.98;
    }}
    .health {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .pill {{
      padding: 6px 10px;
      border-radius: 999px;
      background: #e5e0d6;
      color: var(--muted);
      font-weight: 800;
      font-size: 12px;
    }}
    .pill.good, .good {{ color: var(--green); }}
    .pill.warn, .warn {{ color: var(--amber); }}
    .conversation {{
      min-height: 0;
      overflow: auto;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: rgba(255, 250, 240, 0.78);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.4);
    }}
    .bubble {{
      max-width: 780px;
      padding: 15px 16px;
      margin-bottom: 12px;
      border-radius: 18px;
      background: white;
      border: 1px solid #e4d9c9;
    }}
    .bubble.assistant {{
      background: #14231d;
      color: #f2f7f1;
      border-color: #14231d;
    }}
    .bubble.assistant p, .bubble.assistant li {{
      color: #dce8df;
    }}
    .composer {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 150px;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: var(--panel);
    }}
    .composer textarea, .composer input {{
      width: 100%;
      border: 1px solid #d8cbb9;
      border-radius: 12px;
      background: #fffdf7;
      padding: 11px 12px;
      font: inherit;
    }}
    .composer textarea {{
      min-height: 78px;
      resize: vertical;
    }}
    .primary-btn {{
      background: var(--green);
      color: white;
      padding: 12px 14px;
    }}
    .secondary-btn {{
      background: #e6eee6;
      color: var(--green);
      padding: 12px 14px;
    }}
    .button-stack {{
      display: grid;
      gap: 9px;
      align-content: stretch;
    }}
    .feedback-dock {{
      max-width: 960px;
      min-height: 0;
      overflow: hidden;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: #fffdf7;
      color: var(--ink);
    }}
    .feedback-dock header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }}
    .feedback-dock pre {{
      max-height: 120px;
      margin: 8px 0 0;
    }}
    .result-summary {{
      display: grid;
      gap: 6px;
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .result-summary strong {{
      color: var(--ink);
    }}
    .result-summary code {{
      margin-top: 4px;
      white-space: normal;
      word-break: break-word;
    }}
    .job-meta {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 8px 0;
    }}
    .job-chip {{
      padding: 5px 9px;
      border-radius: 999px;
      background: #e8e1d5;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }}
    .job-chip.running {{
      background: #dfeee5;
      color: var(--green);
    }}
    .job-chip.failed {{
      background: #fff0d6;
      color: var(--amber);
    }}
    .job-row {{
      display: grid;
      gap: 4px;
      padding: 10px 0;
      border-top: 1px solid #eadfce;
      cursor: pointer;
    }}
    .job-row.active {{
      background: #eef5ee;
      margin: 0 -8px;
      padding: 10px 8px;
      border-radius: 12px;
    }}
    .job-row:first-child {{
      border-top: 0;
    }}
    .job-row strong {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
    }}
    .inspector {{
      display: grid;
      align-content: start;
      gap: 14px;
      padding: 22px 18px;
      border-left: 1px solid var(--line);
      background: rgba(255, 250, 240, 0.68);
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 15px;
      background: rgba(255, 253, 247, 0.9);
    }}
    .panel h2 {{
      margin: 0 0 10px;
      font-size: 17px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 9px;
    }}
    .metric {{
      padding: 10px;
      border-radius: 13px;
      background: #f1eadf;
    }}
    .metric span, .status-line span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }}
    .metric strong {{
      display: block;
      margin-top: 4px;
      font-size: 18px;
    }}
    .status-line, .run-row {{
      display: grid;
      gap: 4px;
      padding: 10px 0;
      border-top: 1px solid #eadfce;
    }}
    .run-row:first-child, .status-line:first-child {{
      border-top: 0;
    }}
    code {{
      display: block;
      margin-top: 8px;
      padding: 10px;
      border-radius: 12px;
      background: #efe6d8;
      overflow-x: auto;
      white-space: nowrap;
      font: 13px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .copy-btn {{
      margin-top: 10px;
      padding: 9px 12px;
      color: white;
      background: var(--blue);
    }}
    .empty-state {{
      display: grid;
      gap: 6px;
      color: var(--muted);
    }}
    details {{
      margin-top: 10px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 800;
      color: var(--green);
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 260px;
      overflow: auto;
      padding: 12px;
      border-radius: 12px;
      color: #eef7f1;
      background: var(--black);
    }}
    .toast {{
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translate(-50%, 12px);
      opacity: 0;
      padding: 10px 14px;
      border-radius: 999px;
      color: white;
      background: var(--black);
      transition: 180ms ease;
      pointer-events: none;
    }}
    .toast.show {{
      opacity: 1;
      transform: translate(-50%, 0);
    }}
    @media (max-width: 980px) {{
      body {{ overflow: auto; height: auto; }}
      .shell {{ display: block; height: auto; }}
      .rail, .inspector {{ border: 0; }}
      .workspace {{ min-height: 720px; }}
      .composer {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="rail">
      <div class="brand">
        <strong>Research AI</strong>
        <span>本地 · 审阅门控 · 可追踪</span>
      </div>
      <div class="nav" id="taskNav"></div>
      <p class="muted">命令固定在左侧；工作区只显示当前任务和下一步。</p>
    </aside>
    <main class="workspace">
      <div class="topbar">
        <div>
          <h1>研究者工作台</h1>
          <p class="muted">对话式准备任务，同时查看审阅结果和电脑状态。</p>
        </div>
        <div class="health">
          <span class="pill {_badge_class(overall_status)}">status {escape(overall_status)}</span>
          <span class="pill">CPU {escape(str(cpu.get('load_ratio_1m', 'n/a')))}</span>
          <span class="pill">tokens {escape(str(token_usage.get('estimated_total_tokens', 0)))}</span>
        </div>
      </div>
      <section class="conversation" id="conversation">
        <div class="bubble assistant">
          <strong>怎么开始</strong>
          <p>从左侧选择任务。可以只生成命令，也可以点击“运行并看反馈”让本地白名单任务在后台执行。所有模型结果仍然需要 review gate 和人工判断。</p>
        </div>
      </section>
      <section class="feedback-dock" id="liveJob">
        <header>
          <strong id="liveJobTitle">任务反馈</strong>
          <span class="muted">固定显示当前任务，不需要翻聊天记录</span>
        </header>
        <div class="job-meta" id="liveJobMeta">
          <span class="job-chip">等待任务</span>
        </div>
        <div class="result-summary" id="liveJobSummary">
          运行后这里会显示模型后端、Decision、Review required 和 artifact 路径。
        </div>
        <pre id="liveJobLog">等待任务启动。</pre>
      </section>
      <section class="composer">
        <div>
          <textarea id="researchPrompt" placeholder="输入研究问题、文献任务或审阅目标。例如：根据这篇论文提出三个可验证研究思路。"></textarea>
          <input id="sourcePath" placeholder="材料路径，可选。例如：/path/to/source.pdf 或 README.md">
        </div>
        <div class="button-stack">
          <button class="primary-btn" type="button" onclick="runSelected()">运行并看反馈</button>
          <button class="secondary-btn" type="button" onclick="composeSelected()">只生成命令</button>
        </div>
      </section>
    </main>
    <aside class="inspector">
      <section class="panel">
        <h2>电脑状态</h2>
        <div class="metric-grid">
          <div class="metric"><span>内存</span><strong>{escape(memory_text)}</strong></div>
          <div class="metric"><span>温度</span><strong>{escape(str(snapshot.get('thermal', {}).get('thermal_pressure', 'n/a')))}</strong></div>
          <div class="metric"><span>磁盘</span><strong>{escape(disk_text)}</strong></div>
          <div class="metric"><span>运行记录</span><strong>{escape(str(token_usage.get('runs_counted', 0)))}</strong></div>
        </div>
      </section>
      <section class="panel">
        <h2>模型状态</h2>
        {model_rows}
      </section>
      <section class="panel">
        <h2>审阅结果 / 最近运行</h2>
        <div id="runList">{run_items}</div>
      </section>
      <section class="panel">
        <h2>任务进度</h2>
        <div id="jobList">
          <div class="empty-state">
            <strong>暂无后台任务</strong>
            <span>点击“运行并看反馈”后，这里会显示进度、PID、状态和耗时。</span>
          </div>
        </div>
      </section>
      <section class="panel">
        <h2>原始诊断</h2>
        <details>
          <summary>展开日志</summary>
          <pre id="rawStatus">{monitor_summary}</pre>
        </details>
      </section>
    </aside>
  </div>
  <div class="toast" id="toast">已复制</div>
  <script>
    const TASKS = {command_json};
    let selectedTask = TASKS[3];
    let activeJobId = null;

    function renderNav() {{
      const nav = document.getElementById('taskNav');
      nav.innerHTML = '';
      TASKS.forEach((task, index) => {{
        const button = document.createElement('button');
        button.textContent = task.title;
        button.className = task.title === selectedTask.title ? 'active' : '';
        button.onclick = () => {{
          selectedTask = task;
          renderNav();
          addAssistant('已选择：' + task.title + '。' + task.when);
        }};
        nav.appendChild(button);
      }});
    }}

    function addAssistant(text, command) {{
      const conversation = document.getElementById('conversation');
      const bubble = document.createElement('div');
      bubble.className = 'bubble assistant';
      const safeText = document.createElement('p');
      safeText.textContent = text;
      bubble.appendChild(safeText);
      if (command) {{
        const code = document.createElement('code');
        code.textContent = command;
        bubble.appendChild(code);
        const button = document.createElement('button');
        button.className = 'copy-btn';
        button.textContent = '复制命令';
        button.onclick = () => copyText(command);
        bubble.appendChild(button);
      }}
      conversation.appendChild(bubble);
      conversation.scrollTop = conversation.scrollHeight;
    }}

    function buildCommand() {{
      const prompt = document.getElementById('researchPrompt').value.trim();
      const source = document.getElementById('sourcePath').value.trim();
      const defaultSource = source || 'README.md';
      let command = selectedTask.command;
      if (prompt) {{
        command = command.replace(/"Draft a review-gated answer\\."|"Generate research ideas\\."|"review-gated workflow"/, JSON.stringify(prompt));
      }}
      if (selectedTask.action === 'compress' || selectedTask.action === 'ask' || selectedTask.action === 'ideate') {{
        command = command.replace('README.md', defaultSource).replace('/path/to/source.pdf', defaultSource);
      }}
      return command;
    }}

    function composeSelected() {{
      const command = buildCommand();
      addAssistant('下面是当前任务的安全运行命令。运行后请查看右侧最近运行和 review_gate。', command);
      copyText(command);
    }}

    async function runSelected() {{
      const prompt = document.getElementById('researchPrompt').value.trim();
      const source = document.getElementById('sourcePath').value.trim();
      const command = buildCommand();
      addAssistant('正在启动本地白名单任务。这里不会绕过 review gate，也不会自动最终化输出。', command);
      try {{
        const response = await fetch('/api/jobs', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            action: selectedTask.action,
            prompt: prompt,
            source: source
          }})
        }});
        const payload = await response.json();
        if (!response.ok) {{
          addAssistant('任务未启动：' + (payload.error || response.statusText));
          return;
        }}
        activeJobId = payload.job.job_id;
        renderActiveJob(payload.job);
        addAssistant('任务已启动：' + payload.job.title + '。右侧“任务进度”和中间“任务反馈”会自动刷新。');
        refreshJobs();
      }} catch (error) {{
        addAssistant('任务启动失败：' + error);
      }}
    }}

    function copyText(text) {{
      navigator.clipboard.writeText(text).then(() => {{
        const toast = document.getElementById('toast');
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 1400);
      }});
    }}

    async function refreshStatus() {{
      try {{
        const response = await fetch('/api/monitor');
        const payload = await response.json();
        document.getElementById('rawStatus').textContent = payload.summary_text;
        if (payload.recent_runs) {{
          renderRuns(payload.recent_runs);
        }}
      }} catch (error) {{
        document.getElementById('rawStatus').textContent = 'Status refresh failed: ' + error;
      }}
    }}

    async function refreshJobs() {{
      try {{
        const response = await fetch('/api/jobs');
        const payload = await response.json();
        const jobs = payload.jobs || [];
        if (!activeJobId && jobs.length > 0) {{
          activeJobId = jobs[0].job_id;
        }}
        renderJobs(jobs);
        if (activeJobId) {{
          const active = jobs.find((job) => job.job_id === activeJobId);
          if (active) {{
            renderActiveJob(active);
            if (active.status === 'completed' || active.status === 'failed') {{
              refreshStatus();
            }}
          }}
        }}
      }} catch (error) {{
        const jobList = document.getElementById('jobList');
        jobList.innerHTML = '<div class="empty-state"><strong>任务状态刷新失败</strong><span>' + escapeHtml(String(error)) + '</span></div>';
      }}
    }}

    function renderRuns(runs) {{
      const runList = document.getElementById('runList');
      if (!runs || runs.length === 0) {{
        runList.innerHTML = '<div class="empty-state"><strong>还没有本地运行记录</strong><span>运行 ask / ideate / compress 后，这里会显示最近的审阅状态。</span></div>';
        return;
      }}
      runList.innerHTML = '';
      runs.forEach((run) => {{
        const row = document.createElement('article');
        row.className = 'run-row';
        const detail = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = run.run_id || 'unknown';
        const meta = document.createElement('span');
        meta.textContent = (run.decision || 'unknown') + ' · backend ' + (run.backend || '');
        detail.appendChild(title);
        detail.appendChild(meta);
        const path = document.createElement('small');
        path.textContent = run.path || '';
        row.appendChild(detail);
        row.appendChild(path);
        runList.appendChild(row);
      }});
    }}

    function renderJobs(jobs) {{
      const jobList = document.getElementById('jobList');
      if (!jobs || jobs.length === 0) {{
        jobList.innerHTML = '<div class="empty-state"><strong>暂无后台任务</strong><span>点击“运行并看反馈”后，这里会显示进度、PID、状态和耗时。</span></div>';
        return;
      }}
      jobList.innerHTML = '';
      jobs.slice(0, 8).forEach((job) => {{
        const row = document.createElement('article');
        row.className = 'job-row' + (job.job_id === activeJobId ? ' active' : '');
        const title = document.createElement('strong');
        title.innerHTML = '<span>' + escapeHtml(job.title || job.action || 'job') + '</span><span class="job-chip ' + escapeHtml(job.status || '') + '">' + escapeHtml(job.status || 'unknown') + '</span>';
        const stage = document.createElement('span');
        stage.textContent = job.stage || '';
        const meta = document.createElement('small');
        meta.textContent = 'id ' + (job.job_id || '') + ' · pid ' + (job.pid || 'n/a') + ' · ' + (job.duration_seconds || 0) + 's';
        row.onclick = () => {{
          activeJobId = job.job_id;
          renderActiveJob(job);
        }};
        row.appendChild(title);
        row.appendChild(stage);
        row.appendChild(meta);
        jobList.appendChild(row);
      }});
    }}

    function renderActiveJob(job) {{
      const live = document.getElementById('liveJob');
      const title = document.getElementById('liveJobTitle');
      const meta = document.getElementById('liveJobMeta');
      const summary = document.getElementById('liveJobSummary');
      const log = document.getElementById('liveJobLog');
      title.textContent = '任务反馈：' + (job.title || job.action || '本地任务');
      meta.innerHTML = '';
      [
        '状态 ' + (job.status || 'unknown'),
        '阶段 ' + (job.stage || 'unknown'),
        'PID ' + (job.pid || 'n/a'),
        '耗时 ' + (job.duration_seconds || 0) + 's'
      ].forEach((item) => {{
        const chip = document.createElement('span');
        chip.className = 'job-chip ' + (job.status || '');
        chip.textContent = item;
        meta.appendChild(chip);
      }});
      if (job.backend_snapshot) {{
        Object.keys(job.backend_snapshot).forEach((name) => {{
          const backend = job.backend_snapshot[name] || {{}};
          const chip = document.createElement('span');
          chip.className = 'job-chip';
          chip.textContent = name + ' ' + (backend.status_label || 'unknown') + ' · ' + (backend.effective_model || 'no model');
          meta.appendChild(chip);
        }});
      }}
      renderResultSummary(summary, job);
      const lines = [];
      lines.push(job.command_display || '');
      if (job.error) {{
        lines.push('');
        lines.push('ERROR: ' + job.error);
      }}
      if (job.log_tail) {{
        lines.push('');
        lines.push(job.log_tail);
      }} else {{
        lines.push('');
        lines.push('任务已创建，等待第一条输出。模型调用时可能有一段时间没有新日志。');
      }}
      log.textContent = lines.join('\\n');
      log.scrollTop = log.scrollHeight;
    }}

    function renderResultSummary(container, job) {{
      const result = job.result_summary || {{}};
      const hasResult = Boolean(result.backend || result.decision || result.review_required || result.can_export_final || result.generation_error || (result.artifacts && result.artifacts.length));
      if (!hasResult) {{
        container.innerHTML = '<span><strong>当前阶段：</strong>' + escapeHtml(job.stage || '等待输出') + '</span><span>模型运行中可能几十秒没有新日志；右侧仍会更新 PID 和耗时。</span>';
        return;
      }}
      const parts = [];
      if (result.backend) parts.push('<span><strong>Backend:</strong> ' + escapeHtml(result.backend) + '</span>');
      if (result.decision) parts.push('<span><strong>Decision:</strong> ' + escapeHtml(result.decision) + '</span>');
      if (result.review_required) parts.push('<span><strong>Review required:</strong> ' + escapeHtml(result.review_required) + '</span>');
      if (result.can_export_final) parts.push('<span><strong>Can export final:</strong> ' + escapeHtml(result.can_export_final) + '</span>');
      if (result.generation_error) parts.push('<span><strong>Generation error:</strong> ' + escapeHtml(result.generation_error) + '</span>');
      if (result.artifacts && result.artifacts.length) {{
        result.artifacts.forEach((artifact) => {{
          parts.push('<span><strong>' + escapeHtml(artifact.name || 'artifact') + ':</strong><code>' + escapeHtml(artifact.path || '') + '</code></span>');
        }});
      }}
      container.innerHTML = parts.join('');
    }}

    function escapeHtml(text) {{
      return text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }}

    renderNav();
    refreshJobs();
    setInterval(refreshStatus, 10000);
    setInterval(refreshJobs, 2000);
  </script>
</body>
</html>
"""


class LocalConsoleServer:
    def __init__(self, repo_root: Path, config: dict[str, Any], config_path: Path | None = None) -> None:
        self.repo_root = repo_root
        self.config = config
        self.job_manager = LocalConsoleJobManager(repo_root=repo_root, config=config, config_path=config_path)

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

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                self._send(status, json.dumps(payload, ensure_ascii=False), "application/json")

            def _read_json_body(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length > 65536:
                    raise ValueError("Request body is too large.")
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Request body must be a JSON object.")
                return payload

            def do_GET(self) -> None:
                if self.path in {"/", "/index.html"}:
                    snapshot = collect_monitor_snapshot(console.repo_root, console.config)
                    recent_runs = collect_recent_runs(console.repo_root, console.config)
                    self._send(200, render_workbench_html(snapshot, recent_runs), "text/html")
                    return
                if self.path == "/api/monitor":
                    snapshot = collect_monitor_snapshot(console.repo_root, console.config)
                    recent_runs = collect_recent_runs(console.repo_root, console.config)
                    payload = {
                        "snapshot": snapshot,
                        "summary_text": render_monitor_summary(snapshot),
                        "recent_runs": recent_runs,
                    }
                    self._send(200, json.dumps(payload, ensure_ascii=False), "application/json")
                    return
                if self.path == "/api/runs":
                    recent_runs = collect_recent_runs(console.repo_root, console.config)
                    self._send(200, _runs_payload(recent_runs), "application/json")
                    return
                if self.path == "/api/jobs":
                    self._send(200, _jobs_payload(console.job_manager.list_jobs()), "application/json")
                    return
                if self.path.startswith("/api/jobs/"):
                    job_id = self.path.removeprefix("/api/jobs/")
                    job = console.job_manager.get_job(job_id)
                    if job is None:
                        self._send_json(404, {"error": "Job not found."})
                    else:
                        self._send_json(200, {"job": job})
                    return
                self._send(404, "Not found", "text/plain")

            def do_POST(self) -> None:
                if self.path == "/api/jobs":
                    try:
                        payload = self._read_json_body()
                        job = console.job_manager.start_job(payload)
                    except (ValueError, json.JSONDecodeError) as exc:
                        self._send_json(400, {"error": str(exc)})
                        return
                    self._send_json(202, {"job": job})
                    return
                self._send(404, "Not found", "text/plain")

        return Handler


def run_local_console(
    repo_root: Path,
    config: dict[str, Any],
    config_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Local console is restricted to 127.0.0.1 / localhost.")
    console = LocalConsoleServer(repo_root=repo_root, config=config, config_path=config_path)
    server = ThreadingHTTPServer((host, port), console.handler_class())
    print(f"Local Research AI Console: http://{host}:{port}")
    print("Press Ctrl+C to stop. The console runs only whitelisted local actions and remains review-gated.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nConsole stopped.")
    finally:
        server.server_close()
