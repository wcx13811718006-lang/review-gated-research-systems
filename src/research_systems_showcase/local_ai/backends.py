from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class BackendStatus:
    name: str
    base_url: str
    reachable: bool
    configured_model: str
    available_models: list[str]
    effective_model: str
    status_label: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(url: str, timeout: float) -> tuple[bool, dict[str, Any], str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
            return 200 <= int(getattr(response, "status", 200)) < 300, payload, ""
    except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
        return False, {}, f"{type(exc).__name__}: {exc}"


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body.strip() or str(exc)
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    parsed = json.loads(body or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("Model backend returned a non-object JSON payload.")
    return parsed


def check_ollama(base_url: str, configured_model: str, timeout: float = 2.0) -> BackendStatus:
    normalized = base_url.rstrip("/")
    reachable, payload, detail = _read_json(f"{normalized}/api/tags", timeout)
    available = [
        str(item.get("name"))
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]
    effective = configured_model if configured_model and configured_model in available else ""
    label = "reachable" if reachable else "unreachable"
    if reachable and configured_model and not effective:
        label = "model_unavailable"
        detail = f"Configured model is not listed by Ollama: {configured_model}"
    return BackendStatus("ollama", normalized, reachable, configured_model, available, effective, label, detail)


def check_lmstudio(base_url: str, configured_model: str, timeout: float = 2.0) -> BackendStatus:
    normalized = base_url.rstrip("/")
    reachable, payload, detail = _read_json(f"{normalized}/v1/models", timeout)
    available = [
        str(item.get("id"))
        for item in payload.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    effective = configured_model if configured_model and configured_model in available else ""
    if reachable and not effective and available and not configured_model:
        effective = available[0]
    label = "reachable" if reachable else "unreachable"
    if reachable and configured_model and not effective:
        label = "model_unavailable"
        detail = f"Configured model is not listed by LM Studio: {configured_model}"
    return BackendStatus("lmstudio", normalized, reachable, configured_model, available, effective, label, detail)


def collect_backend_statuses(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ollama_cfg = config.get("ollama", {})
    lmstudio_cfg = config.get("lmstudio", {})
    return {
        "ollama": check_ollama(
            str(ollama_cfg.get("base_url", "")),
            str(ollama_cfg.get("model", "")),
        ).to_dict(),
        "lmstudio": check_lmstudio(
            str(lmstudio_cfg.get("base_url", "")),
            str(lmstudio_cfg.get("model", "")),
        ).to_dict(),
    }


def generate_with_ollama(prompt: str, config: dict[str, Any]) -> str:
    backend = config["ollama"]
    base_url = str(backend["base_url"]).rstrip("/")
    model = str(backend["model"])
    timeout = float(backend.get("timeout_seconds", 90))
    payload = _post_json(
        f"{base_url}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": int(backend.get("num_predict", 512)),
                "temperature": float(backend.get("temperature", 0.1)),
            },
        },
        timeout,
    )
    return str(payload.get("response", "")).strip()


def generate_with_lmstudio(prompt: str, config: dict[str, Any]) -> str:
    backend = config["lmstudio"]
    base_url = str(backend["base_url"]).rstrip("/")
    model = str(backend.get("model") or "")
    timeout = float(backend.get("timeout_seconds", 90))
    max_tokens = int(backend.get("max_tokens", 512))
    temperature = float(backend.get("temperature", 0.1))
    user_prompt = prompt
    if bool(backend.get("disable_thinking", True)):
        user_prompt = "/no_think\n" + prompt
    status = check_lmstudio(base_url, model, timeout=2.0)
    selected_model = status.effective_model or model
    if not selected_model:
        raise RuntimeError("LM Studio is reachable but no model is available for generation.")

    payload = _post_json(
        f"{base_url}/v1/chat/completions",
        {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": "You are a cautious research assistant."},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout,
    )
    choices = payload.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        if isinstance(message, dict):
            content = str(message.get("content", "")).strip()
            if content:
                return content
            reasoning = str(message.get("reasoning_content", "")).strip()
            if reasoning:
                return (
                    "LM Studio returned reasoning content without a final answer. "
                    "This draft requires review.\n\n"
                    + reasoning
                )
    return ""
