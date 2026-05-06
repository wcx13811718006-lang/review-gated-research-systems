from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json, write_text


WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "paper": {
        "label": "Academic Paper",
        "fields": [
            "research_question",
            "theory_or_mechanism",
            "research_design",
            "identification_strategy",
            "data_sources",
            "measurement_decisions",
            "main_findings",
            "limitations",
            "verification_questions",
        ],
        "high_stakes_fields": [
            "identification_strategy",
            "measurement_decisions",
            "main_findings",
        ],
        "validation_checks": [
            "requires explicit source support for findings",
            "flags causal claims without design evidence",
            "separates author claims from reviewer interpretation",
        ],
    },
    "policy": {
        "label": "Policy Report",
        "fields": [
            "policy_problem",
            "institutional_context",
            "actors",
            "timeline",
            "claims",
            "evidence_used",
            "policy_recommendations",
            "implementation_constraints",
            "verification_questions",
        ],
        "high_stakes_fields": [
            "claims",
            "evidence_used",
            "policy_recommendations",
        ],
        "validation_checks": [
            "checks whether recommendations are source-supported",
            "flags missing institutional context",
            "distinguishes descriptive claims from normative claims",
        ],
    },
    "legal": {
        "label": "Legal Or Administrative Document",
        "fields": [
            "document_type",
            "actors",
            "claims_or_issues",
            "institutional_context",
            "timeline",
            "outcome_or_decision",
            "coding_relevant_evidence",
            "uncertainties",
            "verification_questions",
        ],
        "high_stakes_fields": [
            "document_type",
            "outcome_or_decision",
            "coding_relevant_evidence",
        ],
        "validation_checks": [
            "does not infer final decision from title alone",
            "flags missing parties or outcome fields",
            "preserves uncertainty for coding-relevant evidence",
        ],
    },
    "interview": {
        "label": "Interview Transcript",
        "fields": [
            "speaker_roles",
            "themes",
            "institutional_context",
            "claims",
            "examples_or_episodes",
            "contradictions",
            "privacy_or_sensitivity_flags",
            "verification_questions",
        ],
        "high_stakes_fields": [
            "claims",
            "privacy_or_sensitivity_flags",
            "speaker_roles",
        ],
        "validation_checks": [
            "flags personally sensitive information",
            "distinguishes quoted claims from analyst summaries",
            "does not treat one interview as population evidence",
        ],
    },
    "web": {
        "label": "Web-Based Source",
        "fields": [
            "source_url",
            "publisher_or_author",
            "retrieval_date",
            "claim_summary",
            "evidence_or_links",
            "update_or_version_signals",
            "credibility_notes",
            "verification_questions",
        ],
        "high_stakes_fields": [
            "claim_summary",
            "publisher_or_author",
            "credibility_notes",
        ],
        "validation_checks": [
            "preserves retrieval date",
            "flags unsupported claims and missing authorship",
            "does not treat web text as validated fact without review",
        ],
    },
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def list_workflow_templates() -> list[dict[str, Any]]:
    return [
        {
            "template_id": template_id,
            "label": template["label"],
            "field_count": len(template["fields"]),
            "high_stakes_fields": template["high_stakes_fields"],
        }
        for template_id, template in sorted(WORKFLOW_TEMPLATES.items())
    ]


def build_stage_gated_workflow(template_id: str, project_name: str = "") -> dict[str, Any]:
    normalized = template_id.strip().casefold()
    if normalized not in WORKFLOW_TEMPLATES:
        available = ", ".join(sorted(WORKFLOW_TEMPLATES))
        raise ValueError(f"Unknown workflow template '{template_id}'. Available templates: {available}.")

    template = WORKFLOW_TEMPLATES[normalized]
    stages = [
        {
            "stage_id": "intake",
            "owner": "system",
            "purpose": "Collect user-supplied files or URLs into traceable intake artifacts.",
            "output": "intake_manifest.json plus raw/extracted text artifacts",
            "gate": "source must be traceable; failed intake remains inspectable",
        },
        {
            "stage_id": "first_pass_extraction",
            "owner": "primary_model",
            "purpose": "Draft structured fields from the selected template.",
            "output": "draft structured extraction",
            "gate": "draft-only; no final claims",
        },
        {
            "stage_id": "schema_validation",
            "owner": "deterministic_local",
            "purpose": "Check required fields, missingness, and high-stakes field completeness.",
            "output": "validation flags",
            "gate": "missing high-stakes fields route to review",
        },
        {
            "stage_id": "second_model_audit",
            "owner": "review_backend",
            "purpose": "Audit for unsupported claims, schema inconsistencies, and recurring error patterns.",
            "output": "audit packet",
            "gate": "auditor can escalate but cannot approve final use",
        },
        {
            "stage_id": "human_review",
            "owner": "human_reviewer",
            "purpose": "Approve, revise, reject, or record correction examples.",
            "output": "review decision and correction memory",
            "gate": "final use requires human responsibility",
        },
        {
            "stage_id": "analysis_ready_export",
            "owner": "system",
            "purpose": "Export only reviewed or explicitly validated records.",
            "output": "downstream-safe export",
            "gate": "no auto-finalization",
        },
    ]
    return {
        "template_id": normalized,
        "project_name": project_name,
        "label": template["label"],
        "fields": template["fields"],
        "high_stakes_fields": template["high_stakes_fields"],
        "validation_checks": template["validation_checks"],
        "stages": stages,
        "policy": (
            "This workflow is verification-centered. Model output is a draft until "
            "schema checks, audit, and human review determine downstream readiness."
        ),
    }


def render_workflow_summary(workflow: dict[str, Any]) -> str:
    lines = [
        "Stage-Gated Research Workflow",
        "",
        f"Template: {workflow.get('template_id')} ({workflow.get('label')})",
        f"Project: {workflow.get('project_name') or 'unspecified'}",
        "",
        "Structured fields:",
    ]
    lines.extend(f"- {field}" for field in workflow.get("fields", []))
    lines.extend(["", "High-stakes fields:"])
    lines.extend(f"- {field}" for field in workflow.get("high_stakes_fields", []))
    lines.extend(["", "Validation checks:"])
    lines.extend(f"- {check}" for check in workflow.get("validation_checks", []))
    lines.extend(["", "Stages:"])
    for stage in workflow.get("stages", []):
        lines.append(
            "- {stage_id}: {purpose} | gate: {gate}".format(
                stage_id=stage.get("stage_id", ""),
                purpose=stage.get("purpose", ""),
                gate=stage.get("gate", ""),
            )
        )
    lines.extend(["", str(workflow.get("policy", ""))])
    return "\n".join(lines)


def write_workflow_artifacts(
    workflow: dict[str, Any],
    repo_root: Path,
    output_dir: Path | None = None,
) -> dict[str, str]:
    base_dir = output_dir or repo_root / "outputs" / "workflow_templates"
    run_dir = ensure_directory(base_dir / f"workflow_{workflow['template_id']}_{_utc_stamp()}")
    json_path = run_dir / "workflow.json"
    markdown_path = run_dir / "workflow.md"
    write_json(json_path, workflow)
    write_text(markdown_path, render_workflow_summary(workflow) + "\n")
    return {"workflow_json": str(json_path), "workflow_markdown": str(markdown_path)}
