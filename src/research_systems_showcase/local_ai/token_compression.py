from __future__ import annotations

import importlib
import importlib.util
import re
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json, write_text
from .system_monitor import estimate_tokens


DEFAULT_KEEP_TERMS = {
    "addressed",
    "appeal",
    "case",
    "citation",
    "claim",
    "climate",
    "court",
    "decision",
    "defendant",
    "evidence",
    "finaldecision",
    "finding",
    "issue",
    "legal",
    "litigation",
    "metadata",
    "notes",
    "order",
    "party",
    "plaintiff",
    "review",
    "risk",
    "source",
}


def _split_units(text: str) -> list[str]:
    blocks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= 280:
            blocks.append(paragraph)
            continue
        blocks.extend(
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?。！？])\s+", paragraph)
            if sentence.strip()
        )
    return blocks


def _score_unit(unit: str, query_terms: set[str], keep_terms: set[str]) -> float:
    lowered = unit.casefold()
    words = set(re.findall(r"[A-Za-z][A-Za-z\-]{2,}", lowered))
    score = 0.0
    score += 4.0 * len(words & query_terms)
    score += 2.0 * len(words & keep_terms)
    if re.search(r"\b(19|20)\d{2}\b", unit):
        score += 1.5
    if re.search(r"\b[A-Z][A-Za-z]+ v\. [A-Z][A-Za-z]+", unit):
        score += 2.0
    if any(marker in unit for marker in [":", "§", "FinalDecision", "Plaintiff", "Defendant"]):
        score += 1.0
    if len(unit) < 40:
        score -= 0.5
    return score


def builtin_compress_text(
    text: str,
    query: str = "",
    target_tokens: int | None = None,
    ratio: float = 0.65,
) -> dict[str, Any]:
    origin_tokens = estimate_tokens(text)
    if not text.strip() or origin_tokens == 0:
        return {
            "method": "builtin_extractive",
            "compressed_text": "",
            "origin_tokens": 0,
            "compressed_tokens": 0,
            "compression_ratio": 1.0,
            "units_kept": 0,
            "units_total": 0,
        }

    target = target_tokens or max(1, int(origin_tokens * ratio))
    target = max(1, min(target, origin_tokens))
    query_terms = set(re.findall(r"[A-Za-z][A-Za-z\-]{2,}", query.casefold()))
    keep_terms = DEFAULT_KEEP_TERMS | query_terms
    units = _split_units(text)
    scored = [
        {
            "index": index,
            "text": unit,
            "tokens": estimate_tokens(unit),
            "score": _score_unit(unit, query_terms, keep_terms),
        }
        for index, unit in enumerate(units)
    ]
    ranked = sorted(scored, key=lambda item: (-float(item["score"]), int(item["index"])))
    kept: list[dict[str, Any]] = []
    token_total = 0
    for item in ranked:
        item_tokens = int(item["tokens"])
        if kept and token_total + item_tokens > target:
            continue
        kept.append(item)
        token_total += item_tokens
        if token_total >= target:
            break
    kept_sorted = sorted(kept, key=lambda item: int(item["index"]))
    compressed_text = "\n\n".join(str(item["text"]) for item in kept_sorted)
    compressed_tokens = estimate_tokens(compressed_text)
    return {
        "method": "builtin_extractive",
        "compressed_text": compressed_text,
        "origin_tokens": origin_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": round(origin_tokens / compressed_tokens, 2) if compressed_tokens else 1.0,
        "target_tokens": target,
        "units_kept": len(kept_sorted),
        "units_total": len(units),
        "lossy": True,
        "review_note": "Extractive compression is lossy. Use only for draft generation, not final evidence review.",
    }


def _compress_with_llmlingua(
    text: str,
    query: str,
    target_tokens: int | None,
    ratio: float,
) -> dict[str, Any]:
    module = importlib.import_module("llmlingua")
    compressor = module.PromptCompressor()
    kwargs: dict[str, Any] = {"prompt": text, "question": query}
    if target_tokens:
        kwargs["target_token"] = target_tokens
    else:
        kwargs["ratio"] = ratio
    payload = compressor.compress_prompt(**kwargs)
    compressed = str(payload.get("compressed_prompt", ""))
    origin_tokens = int(payload.get("origin_tokens") or estimate_tokens(text))
    compressed_tokens = int(payload.get("compressed_tokens") or estimate_tokens(compressed))
    return {
        "method": "llmlingua",
        "compressed_text": compressed,
        "origin_tokens": origin_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": round(origin_tokens / compressed_tokens, 2) if compressed_tokens else 1.0,
        "plugin_payload": {
            key: value
            for key, value in payload.items()
            if key not in {"compressed_prompt"}
        },
        "lossy": True,
        "review_note": "LLMLingua compression is lossy and must remain review-gated for legal/research use.",
    }


def compress_text(
    text: str,
    query: str = "",
    target_tokens: int | None = None,
    ratio: float = 0.65,
    method: str = "auto",
) -> dict[str, Any]:
    normalized_method = method.casefold()
    if normalized_method not in {"auto", "builtin", "llmlingua"}:
        raise ValueError("Compression method must be one of: auto, builtin, llmlingua.")

    plugin_available = importlib.util.find_spec("llmlingua") is not None
    if normalized_method == "llmlingua" and plugin_available:
        try:
            result = _compress_with_llmlingua(text, query, target_tokens, ratio)
            result["plugin_available"] = True
            return result
        except Exception as exc:
            raise RuntimeError(f"LLMLingua compression failed: {exc}") from exc

    result = builtin_compress_text(text, query=query, target_tokens=target_tokens, ratio=ratio)
    result["plugin_available"] = plugin_available
    if normalized_method == "llmlingua" and not plugin_available:
        result["fallback_reason"] = "llmlingua_not_installed"
    elif normalized_method == "auto":
        result["fallback_reason"] = (
            "safe_auto_uses_builtin; pass --method llmlingua to invoke the optional plugin"
        )
    return result


def maybe_compress_source_context(
    source_context: str,
    config: dict[str, Any],
    query: str,
) -> tuple[str, dict[str, Any]]:
    compression_config = config.get("prompt_compression", {})
    if not bool(compression_config.get("enabled", False)):
        return source_context, {
            "enabled": False,
            "method": "none",
            "origin_tokens": estimate_tokens(source_context),
            "compressed_tokens": estimate_tokens(source_context),
        }

    result = compress_text(
        source_context,
        query=query,
        target_tokens=compression_config.get("target_tokens"),
        ratio=float(compression_config.get("ratio", 0.65)),
        method=str(compression_config.get("method", "auto")),
    )
    return str(result.get("compressed_text", "")), {
        "enabled": True,
        "method": result.get("method"),
        "plugin_available": result.get("plugin_available", False),
        "fallback_reason": result.get("fallback_reason", ""),
        "origin_tokens": result.get("origin_tokens", 0),
        "compressed_tokens": result.get("compressed_tokens", 0),
        "compression_ratio": result.get("compression_ratio", 1.0),
        "lossy": True,
        "review_note": result.get("review_note", ""),
    }


def compress_file_action(
    source_path: Path,
    output_dir: Path,
    query: str = "",
    target_tokens: int | None = None,
    ratio: float = 0.65,
    method: str = "auto",
) -> dict[str, Any]:
    text = source_path.read_text(encoding="utf-8", errors="replace")
    result = compress_text(
        text,
        query=query,
        target_tokens=target_tokens,
        ratio=ratio,
        method=method,
    )
    ensure_directory(output_dir)
    compressed_path = output_dir / f"{source_path.stem}.compressed.txt"
    metadata_path = output_dir / f"{source_path.stem}.compression.json"
    write_text(compressed_path, str(result.get("compressed_text", "")))
    metadata = {key: value for key, value in result.items() if key != "compressed_text"}
    metadata.update({"source_path": str(source_path), "compressed_path": str(compressed_path)})
    write_json(metadata_path, metadata)
    return {
        "compressed_path": str(compressed_path),
        "metadata_path": str(metadata_path),
        **metadata,
    }
