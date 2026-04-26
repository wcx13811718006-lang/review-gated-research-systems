from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json, write_text
from .assistant import (
    _backend_status,
    _generate_with_backend,
    _read_source_context,
    _utc_stamp,
)
from .config import load_local_ai_config
from .quality import evaluate_local_answer
from .token_compression import maybe_compress_source_context


STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "because",
    "before",
    "being",
    "between",
    "cannot",
    "could",
    "documents",
    "during",
    "does",
    "each",
    "even",
    "from",
    "have",
    "having",
    "into",
    "more",
    "must",
    "never",
    "other",
    "only",
    "outputs",
    "should",
    "source",
    "such",
    "their",
    "that",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "when",
    "where",
    "which",
    "while",
    "without",
    "with",
    "would",
}


def build_source_profile(source_context: str, max_keywords: int = 20) -> dict[str, Any]:
    clean_context = re.sub(r"--- SOURCE: .*? ---\s*", " ", source_context)
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", clean_context)
        if word.casefold() not in STOPWORDS
    ]
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1

    keywords = [
        {"term": term, "count": count}
        for term, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:max_keywords]
    ]
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", clean_context.replace("\n", " "))
        if len(sentence.strip()) > 80
    ][:8]

    return {
        "source_context_characters": len(source_context),
        "keyword_candidates": keywords,
        "evidence_sentence_candidates": sentences,
        "profile_note": (
            "This is a lightweight extraction profile for ideation. "
            "It helps review whether generated ideas are grounded in the supplied source context."
        ),
    }


def _build_ideation_prompt(
    focus: str,
    source_context: str,
    source_profile: dict[str, Any],
    idea_count: int,
) -> str:
    keywords = ", ".join(item["term"] for item in source_profile.get("keyword_candidates", [])[:12])
    return "\n".join(
        [
            "You are a conservative research ideation assistant.",
            "Your job is to generate plausible research starting points from supplied literature or legal documents.",
            "Do not invent facts, sources, legal holdings, data availability, or empirical results.",
            "Every idea must be explicitly anchored to the source context and must identify what still needs verification.",
            "Prefer ideas that are creative but feasible for academic research.",
            "Avoid generic topics. Focus on mechanisms, variables, comparison groups, datasets, identification strategies, and review risks.",
            "",
            "Return exactly these sections:",
            "1. Source Takeaways",
            "2. Research Idea Candidates",
            "3. Data And Method Options",
            "4. Verification Risks",
            "5. Recommended Next Review Step",
            "",
            f"Generate {idea_count} idea candidates.",
            "",
            "FOCUS:",
            focus.strip(),
            "",
            "LIGHTWEIGHT SOURCE PROFILE:",
            f"Keyword candidates: {keywords or 'none'}",
            "",
            "SOURCE CONTEXT:",
            source_context.strip() or "No source context was provided.",
        ]
    )


def _render_theory_scaffold(focus: str, source_profile: dict[str, Any], idea_count: int) -> str:
    keywords = [item["term"] for item in source_profile.get("keyword_candidates", [])[:12]]
    evidence = source_profile.get("evidence_sentence_candidates", [])[:4]
    candidate_count = max(1, min(int(idea_count), 5))

    lines = [
        "# Theory-Grounded Ideation Scaffold",
        "",
        "This scaffold is deterministic. It is not a model-generated answer and should be used only as a review starting point.",
        "",
        "## Focus",
        "",
        focus.strip() or "No focus provided.",
        "",
        "## Extracted Source Cues",
        "",
    ]
    if keywords:
        lines.extend(f"- {keyword}" for keyword in keywords)
    else:
        lines.append("- No keyword candidates extracted.")

    lines.extend(["", "## Evidence Sentence Candidates", ""])
    if evidence:
        lines.extend(f"- {sentence}" for sentence in evidence)
    else:
        lines.append("- No evidence sentence candidates extracted.")

    templates = [
        (
            "Evaluation-production decoupling test",
            "Ask when human reviewers can evaluate AI-produced or machine-assisted research outputs without having produced the underlying artifact themselves.",
            "Useful if source-visible attributes are enough for evaluation; risky if quality depends on hidden process attributes.",
        ),
        (
            "Process-transparency intervention",
            "Ask whether adding source traces, extraction logs, model attempts, and review gates can substitute for some production experience.",
            "Useful when evaluation requires process signals that can be exposed directly in artifacts.",
        ),
        (
            "Review-cost triage design",
            "Ask which fields or document classes can receive lighter review after replay against historically reviewed data.",
            "Useful when benchmark comparison shows stable agreement; risky when candidate outputs are blank or ambiguous.",
        ),
        (
            "Schema-locked creative coding workflow",
            "Ask whether structured legal coding can support creative hypothesis generation while keeping final outputs schema-locked.",
            "Useful when ideas need to flow into downstream datasets without column drift or unsupported claims.",
        ),
        (
            "Failure-preserving research memory",
            "Ask how failed extraction, empty model outputs, and reviewer corrections can become reusable research memory.",
            "Useful when failed branches reveal where the workflow needs stronger evidence or better model routing.",
        ),
    ]
    lines.extend(["", "## Candidate Research Directions", ""])
    for index, (title, question, review_logic) in enumerate(templates[:candidate_count], start=1):
        lines.extend(
            [
                f"### {index}. {title}",
                "",
                f"- Starting question: {question}",
                f"- Why it is grounded: source cues include {', '.join(keywords[:5]) or 'no extracted keywords'}.",
                f"- Review logic: {review_logic}",
                "- Required next step: verify the idea against source text and historical benchmark data before treating it as research direction.",
                "",
            ]
        )

    return "\n".join(lines)


def _evaluate_ideation_output(answer: str, base_gate: dict[str, Any]) -> dict[str, Any]:
    required_markers = [
        "Source Takeaways",
        "Research Idea",
        "Verification",
    ]
    structure_present = all(marker.casefold() in answer.casefold() for marker in required_markers)
    checks = list(base_gate.get("checks", []))
    checks.append(
        {
            "name": "ideation_structure_present",
            "passed": structure_present,
            "detail": "Ideation output should include source takeaways, idea candidates, and verification risks.",
        }
    )

    failed = [str(check["name"]) for check in checks if not check.get("passed")]
    review_required = bool(base_gate.get("review_required", True)) or bool(failed)
    return {
        **base_gate,
        "decision": "needs_human_review" if review_required else "approved_for_analysis",
        "review_required": review_required,
        "can_export_final": False,
        "failed_checks": failed,
        "checks": checks,
        "ideation_policy": (
            "Research ideas are treated as starting points. They require source checking, "
            "feasibility review, and methodological review before use."
        ),
    }


def run_literature_ideation(
    focus: str,
    repo_root: Path,
    config_path: Path | None = None,
    source_paths: list[Path] | None = None,
    output_dir: Path | None = None,
    idea_count: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    config = load_local_ai_config(config_path)
    source_context, source_manifest = _read_source_context(
        source_paths or [],
        int(config.get("max_source_characters_per_file", 4000)),
    )
    source_context, compression_manifest = maybe_compress_source_context(
        source_context,
        config,
        focus,
    )
    preview_limit = int(config.get("source_context_preview_characters", 1000))
    source_profile = build_source_profile(source_context)
    theory_scaffold = _render_theory_scaffold(focus, source_profile, idea_count)
    prompt = _build_ideation_prompt(
        focus=focus,
        source_context=source_context,
        source_profile=source_profile,
        idea_count=max(1, min(int(idea_count), 10)),
    )

    backend_name, backend_status = _backend_status(str(config.get("primary_backend", "ollama")), config)
    generation_attempts: list[dict[str, Any]] = []
    generation_error = ""
    fallback_used = False

    if dry_run:
        model_answer = "Dry run only. No model backend was called."
    elif not backend_status.get("reachable"):
        model_answer = ""
        generation_error = f"{backend_name} backend is not reachable."
    elif backend_status.get("configured_model") and not backend_status.get("effective_model"):
        model_answer = ""
        generation_error = f"{backend_name} configured model is not available."
    else:
        try:
            model_answer = _generate_with_backend(backend_name, prompt, config)
            generation_attempts.append({"backend": backend_name, "ok": True})
        except Exception as exc:
            model_answer = ""
            generation_error = f"{type(exc).__name__}: {exc}"
            generation_attempts.append({"backend": backend_name, "ok": False, "error": generation_error})

    if generation_error and bool(config.get("fallback_to_review_backend", False)):
        fallback_name = str(config.get("review_backend", "lmstudio")).lower()
        if fallback_name and fallback_name != backend_name:
            candidate_name, candidate_status = _backend_status(fallback_name, config)
            if candidate_status.get("reachable"):
                try:
                    model_answer = _generate_with_backend(candidate_name, prompt, config)
                    backend_name = candidate_name
                    backend_status = candidate_status
                    generation_attempts.append({"backend": candidate_name, "ok": True, "fallback": True})
                    generation_error = ""
                    fallback_used = True
                except Exception as exc:
                    fallback_error = f"{type(exc).__name__}: {exc}"
                    generation_attempts.append(
                        {"backend": candidate_name, "ok": False, "fallback": True, "error": fallback_error}
                    )

    base_gate = evaluate_local_answer(
        model_answer,
        source_context,
        backend_status,
        config.get("quality_gate", {}),
    )
    idea_gate = _evaluate_ideation_output(model_answer, base_gate)
    if generation_error:
        idea_gate["generation_error"] = generation_error
        idea_gate["decision"] = "needs_human_review"
        idea_gate["review_required"] = True
        idea_gate["can_export_final"] = False

    run_id = f"ideation_{_utc_stamp()}"
    base_output = output_dir or repo_root / str(config.get("outputs_dir", "outputs/local_ai_runs"))
    run_dir = ensure_directory(base_output / run_id)

    write_json(
        run_dir / "request.json",
        {
            "run_id": run_id,
            "mode": "literature_ideation",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "focus": focus,
            "idea_count": idea_count,
            "backend": backend_name,
            "fallback_used": fallback_used,
            "generation_attempts": generation_attempts,
            "backend_status": backend_status,
            "source_manifest": source_manifest,
            "prompt_compression": compression_manifest,
            "source_context_characters": len(source_context),
            "source_context_preview": source_context[:preview_limit],
        },
    )
    write_json(run_dir / "source_profile.json", source_profile)
    write_text(run_dir / "idea_scaffold.md", theory_scaffold)
    write_text(run_dir / "idea_brief.md", model_answer + "\n")
    write_json(run_dir / "review_gate.json", idea_gate)

    manifest = {
        "run_id": run_id,
        "mode": "literature_ideation",
        "backend": backend_name,
        "fallback_used": fallback_used,
        "generation_attempts": generation_attempts,
        "decision": idea_gate["decision"],
        "review_required": idea_gate["review_required"],
        "can_export_final": idea_gate["can_export_final"],
        "generation_error": generation_error,
        "artifacts": {
            "request": str(run_dir / "request.json"),
            "source_profile": str(run_dir / "source_profile.json"),
            "idea_scaffold": str(run_dir / "idea_scaffold.md"),
            "idea_brief": str(run_dir / "idea_brief.md"),
            "review_gate": str(run_dir / "review_gate.json"),
        },
    }
    write_json(run_dir / "manifest.json", manifest)
    return manifest
