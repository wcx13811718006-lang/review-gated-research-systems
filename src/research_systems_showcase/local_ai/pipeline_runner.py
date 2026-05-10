from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json
from .assistant import run_local_research_prompt
from .config import load_local_ai_config
from .data_acquisition import acquire_data_sources
from .ideation import run_literature_ideation
from .verification_audit import build_verification_audit, write_verification_audit
from .workflow_templates import build_stage_gated_workflow, write_workflow_artifacts


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _pipeline_root(repo_root: Path, config: dict[str, Any], output_dir: Path | None) -> Path:
    if output_dir is not None:
        return output_dir
    local_ai_config = config.get("local_pipeline", {})
    return repo_root / str(local_ai_config.get("outputs_dir", "outputs/pipeline_runs"))


def _extracted_source_paths(acquisition_manifest: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for record in acquisition_manifest.get("records", []):
        if not isinstance(record, dict):
            continue
        text_path = str(record.get("extracted_text_path") or "")
        raw_path = str(record.get("raw_path") or "")
        candidate = Path(text_path or raw_path).expanduser() if (text_path or raw_path) else None
        if candidate and candidate.exists() and candidate.is_file():
            paths.append(candidate)
    return paths


def _stage(stage_id: str, status: str, detail: str, artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "status": status,
        "detail": detail,
        "artifacts": artifacts or {},
    }


def run_review_gated_pipeline(
    *,
    task: str,
    repo_root: Path,
    config_path: Path | None = None,
    source_paths: list[Path] | None = None,
    urls: list[str] | None = None,
    template_id: str = "paper",
    mode: str = "ask",
    idea_count: int = 5,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the public-safe local workflow as one inspectable, review-gated sequence.

    This is a convenience wrapper around existing components. It does not approve,
    finalize, or export model outputs.
    """

    config = load_local_ai_config(config_path)
    pipeline_dir = ensure_directory(_pipeline_root(repo_root, config, output_dir) / f"pipeline_{_utc_stamp()}")
    task_text = task.strip() or "Draft a review-gated research note from the supplied source."
    mode_normalized = mode.strip().casefold() or "ask"
    if mode_normalized not in {"ask", "ideate"}:
        raise ValueError("mode must be ask or ideate")

    stages: list[dict[str, Any]] = []
    workflow = build_stage_gated_workflow(template_id, project_name=pipeline_dir.name)
    workflow_artifacts = write_workflow_artifacts(workflow, repo_root, pipeline_dir / "workflow")
    routing_stage = _stage(
        "routing",
        "completed",
        f"Selected workflow template: {workflow['template_id']}",
        workflow_artifacts,
    )

    local_sources = list(source_paths or [])
    source_urls = list(urls or [])
    acquisition_manifest: dict[str, Any] = {}
    generation_sources = local_sources
    if local_sources or source_urls:
        acquisition_manifest = acquire_data_sources(
            repo_root=repo_root,
            config=config,
            urls=source_urls,
            local_sources=local_sources,
            output_dir=pipeline_dir / "intake",
            dry_run=dry_run,
        )
        generation_sources = _extracted_source_paths(acquisition_manifest) or local_sources
        counts = acquisition_manifest.get("counts", {})
        stages.append(
            _stage(
                "ingestion",
                "completed" if not counts.get("failed") else "needs_review",
                (
                    f"requested={counts.get('requested', 0)}; "
                    f"acquired={counts.get('acquired', 0)}; "
                    f"text_extracted={counts.get('text_extracted', 0)}; "
                    f"failed={counts.get('failed', 0)}; "
                    f"dry_run={counts.get('dry_run', 0)}"
                ),
                {"intake_manifest": str(acquisition_manifest.get("manifest_path", ""))},
            )
        )
    else:
        stages.append(_stage("ingestion", "skipped", "No explicit source was supplied."))
    stages.append(routing_stage)

    if mode_normalized == "ideate":
        model_manifest = run_literature_ideation(
            focus=task_text,
            repo_root=repo_root,
            config_path=config_path,
            source_paths=generation_sources,
            idea_count=idea_count,
            dry_run=dry_run,
        )
    else:
        model_manifest = run_local_research_prompt(
            user_prompt=task_text,
            repo_root=repo_root,
            config_path=config_path,
            source_paths=generation_sources,
            dry_run=dry_run,
        )
    stages.append(
        _stage(
            "validation",
            "needs_review" if model_manifest.get("review_required", True) else "completed",
            (
                f"decision={model_manifest.get('decision', 'unknown')}; "
                f"review_required={model_manifest.get('review_required', True)}; "
                f"can_export_final={model_manifest.get('can_export_final', False)}"
            ),
            model_manifest.get("artifacts", {}),
        )
    )

    audit = build_verification_audit(
        repo_root=repo_root,
        config=config,
        template_id=workflow["template_id"],
        limit=20,
    )
    audit_artifacts = write_verification_audit(audit, repo_root, pipeline_dir / "audit")
    stages.append(
        _stage(
            "review",
            "needs_review" if audit.get("counts", {}).get("risk_levels", {}).get("high") else "completed",
            f"runs_audited={audit.get('runs_audited', 0)}",
            audit_artifacts,
        )
    )
    stages.append(
        _stage(
            "export",
            "blocked",
            "Final export remains blocked until human review approves or revises records.",
        )
    )

    manifest = {
        "pipeline_id": pipeline_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pipeline_directory": str(pipeline_dir),
        "mode": mode_normalized,
        "template_id": workflow["template_id"],
        "task": task_text,
        "source_count": len(generation_sources),
        "dry_run": dry_run,
        "review_required": True,
        "can_export_final": False,
        "decision": model_manifest.get("decision", "needs_human_review"),
        "workflow": workflow,
        "acquisition_manifest": acquisition_manifest,
        "model_manifest": model_manifest,
        "verification_audit": audit,
        "stages": stages,
        "policy": (
            "This pipeline is a convenience orchestration layer only. It preserves review gates, "
            "keeps failed or uncertain branches inspectable, and does not auto-finalize outputs."
        ),
    }
    manifest_path = pipeline_dir / "pipeline_manifest.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def render_pipeline_summary(manifest: dict[str, Any]) -> str:
    lines = [
        "Review-Gated Local Pipeline",
        "",
        f"Pipeline directory: {manifest.get('pipeline_directory', '')}",
        f"Manifest: {manifest.get('manifest_path', '')}",
        f"Mode: {manifest.get('mode', '')}",
        f"Template: {manifest.get('template_id', '')}",
        f"Decision: {manifest.get('decision', 'needs_human_review')}",
        f"Review required: {manifest.get('review_required', True)}",
        f"Can export final: {manifest.get('can_export_final', False)}",
        "",
        "Architecture stages:",
    ]
    for stage in manifest.get("stages", []):
        if not isinstance(stage, dict):
            continue
        lines.append(
            "- {stage_id}: {status} | {detail}".format(
                stage_id=stage.get("stage_id", "unknown"),
                status=stage.get("status", "unknown"),
                detail=stage.get("detail", ""),
            )
        )
        artifacts = stage.get("artifacts", {})
        if isinstance(artifacts, dict):
            for name, path in artifacts.items():
                if path:
                    lines.append(f"  - {name}: {path}")

    model_manifest = manifest.get("model_manifest", {})
    if isinstance(model_manifest, dict) and model_manifest.get("generation_error"):
        lines.extend(["", f"Generation error: {model_manifest['generation_error']}"])

    lines.extend(["", str(manifest.get("policy", ""))])
    return "\n".join(lines)
