from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json, write_text
from .backends import (
    check_lmstudio,
    check_ollama,
    generate_with_lmstudio,
    generate_with_ollama,
)
from .config import load_local_ai_config
from .quality import evaluate_local_answer


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_source_context(paths: list[Path], max_chars_per_file: int) -> tuple[str, list[dict[str, Any]]]:
    chunks: list[str] = []
    manifest: list[dict[str, Any]] = []
    for path in paths:
        record: dict[str, Any] = {"path": str(path), "included": False, "reason": ""}
        if not path.exists():
            record["reason"] = "missing"
            manifest.append(record)
            continue
        if not path.is_file():
            record["reason"] = "not_a_file"
            manifest.append(record)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            record["reason"] = f"{type(exc).__name__}: {exc}"
            manifest.append(record)
            continue
        snippet = text[:max_chars_per_file]
        chunks.append(f"\n\n--- SOURCE: {path.name} ---\n{snippet}")
        record.update({"included": True, "characters_used": len(snippet)})
        manifest.append(record)
    return "".join(chunks).strip(), manifest


def _build_prompt(user_prompt: str, source_context: str) -> str:
    return "\n".join(
        [
            "You are helping with research work in a review-gated workflow.",
            "Use cautious language. Separate claims from uncertainties.",
            "Do not invent sources, facts, quotes, or results.",
            "If the source context is insufficient, say what is missing.",
            "Return a concise research draft with sections: Answer, Evidence Used, Uncertainties, Suggested Review Steps.",
            "",
            "USER REQUEST:",
            user_prompt.strip(),
            "",
            "SOURCE CONTEXT:",
            source_context.strip() or "No source context was provided.",
        ]
    )


def _select_backend(config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    primary = str(config.get("primary_backend", "ollama")).lower()
    return _backend_status(primary, config)


def _backend_status(name: str, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    normalized_name = name.lower()
    if normalized_name == "lmstudio":
        lmstudio_cfg = config.get("lmstudio", {})
        status = check_lmstudio(
            str(lmstudio_cfg.get("base_url", "")),
            str(lmstudio_cfg.get("model", "")),
        )
        return "lmstudio", status.to_dict()

    ollama_cfg = config.get("ollama", {})
    status = check_ollama(
        str(ollama_cfg.get("base_url", "")),
        str(ollama_cfg.get("model", "")),
    )
    return "ollama", status.to_dict()


def _generate_with_backend(name: str, prompt: str, config: dict[str, Any]) -> str:
    if name == "lmstudio":
        return generate_with_lmstudio(prompt, config)
    return generate_with_ollama(prompt, config)


def run_local_research_prompt(
    user_prompt: str,
    repo_root: Path,
    config_path: Path | None = None,
    source_paths: list[Path] | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    config = load_local_ai_config(config_path)
    source_context, source_manifest = _read_source_context(
        source_paths or [],
        int(config.get("max_source_characters_per_file", 4000)),
    )
    prompt = _build_prompt(user_prompt, source_context)
    backend_name, backend_status = _select_backend(config)

    model_answer = ""
    generation_error = ""
    generation_attempts: list[dict[str, Any]] = []
    if dry_run:
        model_answer = "Dry run only. No model backend was called."
    elif not backend_status.get("reachable"):
        generation_error = f"{backend_name} backend is not reachable."
    elif backend_status.get("configured_model") and not backend_status.get("effective_model"):
        generation_error = f"{backend_name} configured model is not available."
    else:
        try:
            model_answer = _generate_with_backend(backend_name, prompt, config)
            generation_attempts.append({"backend": backend_name, "ok": True})
        except Exception as exc:
            generation_error = f"{type(exc).__name__}: {exc}"
            generation_attempts.append({"backend": backend_name, "ok": False, "error": generation_error})

    fallback_used = False
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

    quality_gate = evaluate_local_answer(
        model_answer,
        source_context,
        backend_status,
        config.get("quality_gate", {}),
    )
    if generation_error:
        quality_gate["decision"] = "needs_human_review"
        quality_gate["review_required"] = True
        quality_gate["can_export_final"] = False
        quality_gate["generation_error"] = generation_error

    run_id = f"local_ai_{_utc_stamp()}"
    base_output = output_dir or repo_root / str(config.get("outputs_dir", "outputs/local_ai_runs"))
    run_dir = ensure_directory(base_output / run_id)

    write_json(
        run_dir / "request.json",
        {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "prompt": user_prompt,
            "backend": backend_name,
            "fallback_used": fallback_used,
            "generation_attempts": generation_attempts,
            "backend_status": backend_status,
            "source_manifest": source_manifest,
        },
    )
    write_text(run_dir / "draft_response.md", model_answer + "\n")
    write_json(run_dir / "review_gate.json", quality_gate)

    manifest = {
        "run_id": run_id,
        "backend": backend_name,
        "fallback_used": fallback_used,
        "generation_attempts": generation_attempts,
        "decision": quality_gate["decision"],
        "review_required": quality_gate["review_required"],
        "can_export_final": quality_gate["can_export_final"],
        "generation_error": generation_error,
        "artifacts": {
            "request": str(run_dir / "request.json"),
            "draft_response": str(run_dir / "draft_response.md"),
            "review_gate": str(run_dir / "review_gate.json"),
        },
    }
    write_json(run_dir / "manifest.json", manifest)
    return manifest
