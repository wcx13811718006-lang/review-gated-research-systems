from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


DEFAULT_LOCAL_AI_CONFIG: dict[str, Any] = {
    "primary_backend": "ollama",
    "review_backend": "lmstudio",
    "fallback_to_review_backend": True,
    "outputs_dir": "outputs/local_ai_runs",
    "max_source_characters_per_file": 4000,
    "source_context_preview_characters": 1000,
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen2.5:7b",
        "timeout_seconds": 90,
        "num_predict": 512,
        "temperature": 0.1,
    },
    "lmstudio": {
        "base_url": "http://127.0.0.1:1234",
        "model": "",
        "timeout_seconds": 90,
        "max_tokens": 512,
        "temperature": 0.1,
        "disable_thinking": True,
    },
    "quality_gate": {
        "allow_final_without_review": False,
        "require_human_review": True,
        "minimum_source_context_characters": 200,
        "minimum_answer_characters": 120,
    },
    "model_architecture": {
        "mode": "review_gated_local",
        "allow_auto_finalize": False,
        "borrowed_patterns": [
            "stateful_workflow",
            "role_separated_generation_review",
            "durable_artifact_memory",
            "failed_branch_preservation",
            "local_observability",
        ],
    },
    "monitor": {
        "outputs_dir": "outputs/system_monitor",
        "token_artifact_dir": "outputs/local_ai_runs",
        "token_recent_run_limit": 20,
        "disk_paths": [".", "outputs/local_ai_runs", "/tmp"],
        "high_load_ratio": 0.85,
        "low_disk_free_fraction": 0.1,
    },
    "prompt_compression": {
        "enabled": False,
        "method": "auto",
        "ratio": 0.65,
        "target_tokens": None,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_local_ai_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        return copy.deepcopy(DEFAULT_LOCAL_AI_CONFIG)
    if not path.exists():
        raise FileNotFoundError(f"Local AI config not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Local AI config must be a JSON object.")
    return _deep_merge(DEFAULT_LOCAL_AI_CONFIG, payload)
