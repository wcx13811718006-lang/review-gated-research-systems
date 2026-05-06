from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assistant import run_local_research_prompt
from .backends import collect_backend_statuses
from .config import load_local_ai_config
from .data_acquisition import acquire_data_sources, render_data_acquisition_summary
from .ideation import run_literature_ideation
from .local_console import run_local_console
from .model_architecture import build_model_execution_plan, render_model_architecture_summary
from .review_memory import (
    append_review_memory,
    collect_review_memory,
    render_review_memory_summary,
    write_review_memory_summary,
)
from .run_memory import collect_run_memory, render_run_memory_summary, write_run_memory_snapshot
from .system_monitor import (
    build_model_routing_advice,
    collect_monitor_snapshot,
    render_model_summary,
    render_monitor_summary,
    write_monitor_snapshot,
)
from .token_compression import compress_file_action
from .verification_audit import build_verification_audit, render_verification_audit_summary, write_verification_audit
from .workflow_templates import (
    build_stage_gated_workflow,
    list_workflow_templates,
    render_workflow_summary,
    write_workflow_artifacts,
)


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

    architecture = subparsers.add_parser(
        "architecture",
        help="Show the conservative model-routing and review-gate architecture plan.",
    )
    architecture.add_argument("--task-type", default="research_draft", help="Task label to include in the plan.")
    architecture.add_argument("--source-count", type=int, default=0, help="Number of explicit source files.")
    architecture.add_argument("--json", action="store_true", help="Print the architecture plan as JSON.")

    memory = subparsers.add_parser(
        "memory",
        help="Summarize recent local AI run artifacts without approving or exporting outputs.",
    )
    memory.add_argument("--limit", type=int, default=20, help="Number of recent run directories to inspect.")
    memory.add_argument("--json", action="store_true", help="Print the run memory snapshot as JSON.")
    memory.add_argument("--write", action="store_true", help="Write the run memory snapshot to outputs/system_monitor.")
    memory.add_argument("--output-dir", type=Path, default=None, help="Optional output directory for memory JSON.")

    acquire = subparsers.add_parser(
        "acquire",
        help="Fetch user-supplied URLs or local files into traceable local intake artifacts.",
    )
    acquire.add_argument("--url", action="append", default=[], help="Explicit URL to acquire. Repeatable.")
    acquire.add_argument("--url-file", type=Path, default=None, help="Text file containing one URL per line.")
    acquire.add_argument("--local-source", type=Path, action="append", default=[], help="Local file to copy into intake.")
    acquire.add_argument("--output-dir", type=Path, default=None, help="Optional output directory for data intake.")
    acquire.add_argument("--max-bytes", type=int, default=None, help="Maximum bytes per source.")
    acquire.add_argument("--dry-run", action="store_true", help="Plan intake without downloading or copying sources.")
    acquire.add_argument("--json", action="store_true", help="Print the intake manifest as JSON.")

    workflow = subparsers.add_parser(
        "workflow",
        help="Show or write a stage-gated workflow template for a social-science material type.",
    )
    workflow.add_argument("--template", default="paper", help="Template id: paper, policy, legal, interview, or web.")
    workflow.add_argument("--project-name", default="", help="Optional project label.")
    workflow.add_argument("--list", action="store_true", help="List available workflow templates.")
    workflow.add_argument("--write", action="store_true", help="Write workflow JSON and Markdown artifacts.")
    workflow.add_argument("--output-dir", type=Path, default=None, help="Optional output directory.")
    workflow.add_argument("--json", action="store_true", help="Print workflow as JSON.")

    audit = subparsers.add_parser(
        "audit",
        help="Run a deterministic verification audit over recent local run artifacts.",
    )
    audit.add_argument("--template", default="", help="Optional workflow template id for high-stakes field context.")
    audit.add_argument("--limit", type=int, default=50, help="Number of recent runs to audit.")
    audit.add_argument("--write", action="store_true", help="Write audit JSON and Markdown artifacts.")
    audit.add_argument("--output-dir", type=Path, default=None, help="Optional output directory.")
    audit.add_argument("--json", action="store_true", help="Print audit as JSON.")

    review_memory = subparsers.add_parser(
        "review-memory",
        help="Append or summarize local human review-memory records.",
    )
    review_memory.add_argument("--add", action="store_true", help="Append a human review-memory record.")
    review_memory.add_argument("--run-id", default="", help="Run ID the record refers to.")
    review_memory.add_argument("--field", default="", help="Field or concept being corrected.")
    review_memory.add_argument("--decision", default="", help="Human decision, e.g. approve, revise, reject.")
    review_memory.add_argument("--correction", default="", help="Corrected value or short note.")
    review_memory.add_argument("--rationale", default="", help="Reason for the correction or decision.")
    review_memory.add_argument("--reviewer", default="", help="Optional reviewer label.")
    review_memory.add_argument("--source-path", default="", help="Optional source or artifact path.")
    review_memory.add_argument("--limit", type=int, default=20, help="Recent records to summarize.")
    review_memory.add_argument("--write", action="store_true", help="Write review-memory summary artifacts.")
    review_memory.add_argument("--output-dir", type=Path, default=None, help="Optional output directory.")
    review_memory.add_argument("--json", action="store_true", help="Print JSON.")

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
    if args.command == "architecture":
        statuses = collect_backend_statuses(config)
        plan = build_model_execution_plan(
            config,
            task_type=args.task_type,
            source_count=args.source_count,
            statuses=statuses,
        )
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(render_model_architecture_summary(plan))
        return
    if args.command == "memory":
        memory = collect_run_memory(repo_root, config, limit=args.limit)
        if args.write:
            output_path = write_run_memory_snapshot(memory, repo_root, config, args.output_dir)
            memory["written_to"] = str(output_path)
        if args.json:
            print(json.dumps(memory, ensure_ascii=False, indent=2))
        else:
            print(render_run_memory_summary(memory))
            if args.write:
                print(f"\nSnapshot written to: {memory['written_to']}")
        return
    if args.command == "acquire":
        manifest = acquire_data_sources(
            repo_root=repo_root,
            config=config,
            urls=args.url,
            url_file=args.url_file,
            local_sources=args.local_source,
            output_dir=args.output_dir,
            max_bytes=args.max_bytes,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
        else:
            print(render_data_acquisition_summary(manifest))
        return
    if args.command == "workflow":
        if args.list:
            templates = {"templates": list_workflow_templates()}
            if args.json:
                print(json.dumps(templates, ensure_ascii=False, indent=2))
            else:
                print("Available Workflow Templates\n")
                for item in templates["templates"]:
                    print(f"- {item['template_id']}: {item['label']} ({item['field_count']} fields)")
            return
        workflow = build_stage_gated_workflow(args.template, project_name=args.project_name)
        if args.write:
            workflow["artifacts"] = write_workflow_artifacts(workflow, repo_root, args.output_dir)
        if args.json:
            print(json.dumps(workflow, ensure_ascii=False, indent=2))
        else:
            print(render_workflow_summary(workflow))
            if args.write:
                print("\nArtifacts:")
                for name, path in workflow["artifacts"].items():
                    print(f"  - {name}: {path}")
        return
    if args.command == "audit":
        audit = build_verification_audit(
            repo_root=repo_root,
            config=config,
            template_id=args.template or None,
            limit=args.limit,
        )
        if args.write:
            audit["artifacts"] = write_verification_audit(audit, repo_root, args.output_dir)
        if args.json:
            print(json.dumps(audit, ensure_ascii=False, indent=2))
        else:
            print(render_verification_audit_summary(audit))
            if args.write:
                print("\nArtifacts:")
                for name, path in audit["artifacts"].items():
                    print(f"  - {name}: {path}")
        return
    if args.command == "review-memory":
        if args.add:
            record = append_review_memory(
                repo_root=repo_root,
                config=config,
                run_id=args.run_id,
                field=args.field,
                decision=args.decision,
                correction=args.correction,
                rationale=args.rationale,
                reviewer=args.reviewer,
                source_path=args.source_path,
            )
            if args.json:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            else:
                print("Review memory record added.")
                print(f"Run ID: {record['run_id']}")
                print(f"Field: {record['field']}")
                print(f"Decision: {record['decision']}")
            return
        memory_summary = collect_review_memory(repo_root, config, limit=args.limit)
        if args.write:
            memory_summary["artifacts"] = write_review_memory_summary(
                memory_summary,
                repo_root,
                config,
                args.output_dir,
            )
        if args.json:
            print(json.dumps(memory_summary, ensure_ascii=False, indent=2))
        else:
            print(render_review_memory_summary(memory_summary))
            if args.write:
                print("\nArtifacts:")
                for name, path in memory_summary["artifacts"].items():
                    print(f"  - {name}: {path}")
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
