from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assistant import run_local_research_prompt
from .backends import collect_backend_statuses
from .config import load_local_ai_config
from .ideation import run_literature_ideation


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = _repo_root()
    config = load_local_ai_config(args.config)

    if args.command == "status":
        print(json.dumps(collect_backend_statuses(config), ensure_ascii=False, indent=2))
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
