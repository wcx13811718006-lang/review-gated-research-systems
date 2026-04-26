from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assistant import run_local_research_prompt
from .backends import collect_backend_statuses
from .config import load_local_ai_config
from .ideation import run_literature_ideation
from .local_console import run_local_console
from .system_monitor import (
    build_model_routing_advice,
    collect_monitor_snapshot,
    render_model_summary,
    render_monitor_summary,
    write_monitor_snapshot,
)
from .token_compression import compress_file_action


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local review-gated AI helper.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to local AI config JSON. Defaults to built-in conservative settings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Check local Ollama and LM Studio availability.")
    subparsers.add_parser("models", help="Show configured, available, and effective local models.")

    monitor = subparsers.add_parser("monitor", help="Show local system, model, and token-usage status.")
    monitor.add_argument("--json", action="store_true", help="Print the full monitor snapshot as JSON.")
    monitor.add_argument("--write", action="store_true", help="Write the monitor snapshot to outputs/system_monitor.")
    monitor.add_argument("--output-dir", type=Path, default=None, help="Optional output directory for monitor JSON.")

    console = subparsers.add_parser("console", help="Start a minimal local operations console.")
    console.add_argument("--host", default="127.0.0.1", help="Local bind host. Defaults to 127.0.0.1.")
    console.add_argument("--port", type=int, default=8765, help="Local console port. Defaults to 8765.")

    ask = subparsers.add_parser("ask", help="Run a local model prompt and write review-gated artifacts.")
    ask.add_argument("prompt", help="Research or work request.")
    ask.add_argument("--source", type=Path, action="append", default=[], help="Optional text source file.")
    ask.add_argument("--output-dir", type=Path, default=None, help="Optional output directory for run artifacts.")
    ask.add_argument("--dry-run", action="store_true", help="Write artifacts without calling a model backend.")

    ideate = subparsers.add_parser(
        "ideate",
        help="Generate review-gated research idea candidates from supplied literature or legal sources.",
    )
    ideate.add_argument("focus", help="Research focus, question, or domain for ideation.")
    ideate.add_argument("--source", type=Path, action="append", default=[], help="Literature or legal source file.")
    ideate.add_argument("--ideas", type=int, default=5, help="Number of idea candidates to request, capped at 10.")
    ideate.add_argument("--output-dir", type=Path, default=None, help="Optional output directory for run artifacts.")
    ideate.add_argument("--dry-run", action="store_true", help="Write artifacts without calling a model backend.")

    compress = subparsers.add_parser("compress", help="Compress a text source for lower-cost draft prompts.")
    compress.add_argument("--source", type=Path, required=True, help="Text source file to compress.")
    compress.add_argument("--query", default="", help="Research question or focus used for query-aware compression.")
    compress.add_argument("--target-tokens", type=int, default=None, help="Optional target token budget.")
    compress.add_argument("--ratio", type=float, default=0.65, help="Fallback compression ratio. Defaults to 0.65.")
    compress.add_argument(
        "--method",
        choices=["auto", "builtin", "llmlingua"],
        default="auto",
        help="Compression method. Auto uses the safe builtin path; llmlingua must be requested explicitly.",
    )
    compress.add_argument("--output-dir", type=Path, default=Path("outputs/compressed_prompts"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = _repo_root()
    config = load_local_ai_config(args.config)

    if args.command == "status":
        print(json.dumps(collect_backend_statuses(config), ensure_ascii=False, indent=2))
        return
    if args.command == "models":
        statuses = collect_backend_statuses(config)
        print(render_model_summary(build_model_routing_advice(statuses, config)))
        return
    if args.command == "monitor":
        snapshot = collect_monitor_snapshot(repo_root, config)
        if args.write:
            output_path = write_monitor_snapshot(snapshot, repo_root, config, args.output_dir)
            snapshot["written_to"] = str(output_path)
        if args.json:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        else:
            print(render_monitor_summary(snapshot))
            if args.write:
                print(f"\nSnapshot written to: {snapshot['written_to']}")
        return
    if args.command == "console":
        run_local_console(repo_root=repo_root, config=config, config_path=args.config, host=args.host, port=args.port)
        return
    if args.command == "compress":
        result = compress_file_action(
            source_path=args.source,
            output_dir=args.output_dir,
            query=args.query,
            target_tokens=args.target_tokens,
            ratio=args.ratio,
            method=args.method,
        )
        print("Compression completed.")
        print(f"Method: {result.get('method')}")
        print(f"Plugin available: {result.get('plugin_available')}")
        if result.get("fallback_reason"):
            print(f"Fallback reason: {result.get('fallback_reason')}")
        print(f"Origin tokens: {result.get('origin_tokens')}")
        print(f"Compressed tokens: {result.get('compressed_tokens')}")
        print(f"Compression ratio: {result.get('compression_ratio')}")
        print(f"Compressed text: {result['compressed_path']}")
        print(f"Metadata: {result['metadata_path']}")
        print("Policy: compressed prompts remain draft-only and review-gated.")
        return

    if args.command == "ideate":
        manifest = run_literature_ideation(
            focus=args.focus,
            repo_root=repo_root,
            config_path=args.config,
            source_paths=args.source,
            output_dir=args.output_dir,
            idea_count=args.ideas,
            dry_run=args.dry_run,
        )
    else:
        manifest = run_local_research_prompt(
            user_prompt=args.prompt,
            repo_root=repo_root,
            config_path=args.config,
            source_paths=args.source,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
        )
    print("Local AI run completed.")
    print(f"Backend: {manifest['backend']}")
    print(f"Fallback used: {manifest['fallback_used']}")
    print(f"Decision: {manifest['decision']}")
    print(f"Review required: {manifest['review_required']}")
    print(f"Can export final: {manifest['can_export_final']}")
    if manifest.get("generation_error"):
        print(f"Generation error: {manifest['generation_error']}")
    print("Artifacts:")
    for name, path in manifest["artifacts"].items():
        print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
