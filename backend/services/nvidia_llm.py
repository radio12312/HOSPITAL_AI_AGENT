"""NVIDIA API catalog (NIM) client shared by every agent.

Provides chat completion, structured JSON responses validated with Pydantic, model probing
with automatic fallback, retry with exponential backoff, an on-disk response cache and call
counting. Thinking/reasoning mode is disabled for Nemotron models to keep responses fast.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from core.config import settings
from core.logging import get_logger

log = get_logger("llm")

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The LLM could not be used (missing key, no working model, or repeated failures)."""


@dataclass
class LLMResult:
    text: str
    api_calls: int  # real HTTP requests made (retries included; 0 on a cache hit)
    model: str
    cache_hit: bool = False


# ---------------------------------------------------------------- client & model resolution

@lru_cache(maxsize=8)
def _client(model: str, temperature: float, max_tokens: int):
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    kwargs = {}
    if settings.nvidia_disable_thinking and "nemotron" in model:
        kwargs["model_kwargs"] = {"chat_template_kwargs": {"enable_thinking": False}}
    return ChatNVIDIA(model=model, api_key=settings.nvidia_api_key, temperature=temperature,
                      max_completion_tokens=max_tokens, **kwargs)


def _status_code(err: Exception) -> int | None:
    code = getattr(getattr(err, "response", None), "status_code", None)
    if code is None:
        m = re.search(r"\[(\d{3})\]", str(err)) or re.search(r"\b(40[48]|410|429|50[0234])\b", str(err))
        code = int(m.group(1)) if m else None
    return code


@lru_cache(maxsize=4)
def _probe(model: str) -> str | None:
    """One tiny request. None if the model answers, else a reason.

    The catalog still lists retired models that answer every request with HTTP 410, so the
    model list alone can't be trusted.
    """
    from langchain_core.messages import HumanMessage

    try:
        _client(model, 0.0, 8).invoke([HumanMessage(content="ping")])
        return None
    except Exception as e:  # noqa: BLE001 - any failure means "not usable"
        return f"HTTP {_status_code(e)}: {str(e).splitlines()[0][:120]}"


_resolved: str | None = None


def resolve_model() -> str:
    """Return the configured model, else the fallback, else raise LLMError."""
    global _resolved
    if _resolved:
        return _resolved
    if not settings.nvidia_api_key:
        raise LLMError("NVIDIA_API_KEY is not set. Add your key from https://build.nvidia.com to .env.")
    problems = []
    for model in (settings.nvidia_model, settings.nvidia_fallback_model):
        reason = _probe(model)
        if reason is None:
            if problems:
                log.warning("Primary model unavailable (%s); using fallback %s", problems[0], model)
            _resolved = model
            return model
        problems.append(f"{model}: {reason}")
    raise LLMError("No usable NVIDIA model. " + "; ".join(problems))


def model_name() -> str:
    try:
        return resolve_model()
    except LLMError:
        return "unavailable"


# ---------------------------------------------------------------- completion

def _cache_file(model: str, system: str, user: str):
    key = hashlib.sha256(json.dumps([model, system, user, settings.llm_temperature,
                                     settings.llm_max_tokens]).encode()).hexdigest()
    return settings.cache_path / f"{key}.json"


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def chat(system: str, user: str, *, label: str = "llm") -> LLMResult:
    """Chat completion with cache, retry/backoff on transient errors, and call counting."""
    from langchain_core.messages import HumanMessage, SystemMessage

    model = resolve_model()
    path = _cache_file(model, system, user)
    if settings.llm_cache_enabled and path.exists():
        log.info("LLM cache hit (%s)", label)
        return LLMResult(json.loads(path.read_text(encoding="utf-8"))["text"], 0, model, True)

    client = _client(model, settings.llm_temperature, settings.llm_max_tokens)
    attempts = 0
    while True:
        attempts += 1
        try:
            t0 = time.perf_counter()
            msg = client.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            text = _THINK.sub("", str(msg.content)).strip()
            log.info("LLM call ok (%s) model=%s attempt=%d %.1fs", label, model, attempts, time.perf_counter() - t0)
            break
        except Exception as e:  # noqa: BLE001
            status = _status_code(e)
            transient = status in TRANSIENT_STATUS or type(e).__name__ in {"ConnectionError", "Timeout", "ReadTimeout"}
            if attempts > settings.llm_max_retries or not transient:
                raise LLMError(f"LLM request failed after {attempts} attempt(s) (HTTP {status})") from e
            delay = min(2 ** attempts, 30) + random.uniform(0, 1)
            log.warning("Transient LLM error (HTTP %s), retry %d in %.1fs", status, attempts, delay)
            time.sleep(delay)

    if settings.llm_cache_enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"label": label, "model": model, "text": text}), encoding="utf-8")
    return LLMResult(text, attempts, model)


def extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    if not candidate:
        raise ValueError("no JSON object in model output")
    return json.loads(candidate)


def chat_json(system: str, user: str, schema: type[T], *, label: str = "llm") -> tuple[T, int]:
    """Structured JSON response validated against `schema`; one corrective retry on bad JSON.

    Returns (parsed_object, api_calls). Raises LLMError if both attempts fail.
    """
    calls, prompt = 0, user
    for attempt in (1, 2):
        res = chat(system, prompt, label=label)
        calls += res.api_calls
        try:
            return schema.model_validate(extract_json(res.text)), calls
        except (ValidationError, ValueError) as e:
            err = str(e).splitlines()[0][:300]
            log.warning("Invalid JSON from LLM (%s, attempt %d): %s", label, attempt, err)
            prompt = f"{user}\n\nYour previous reply was invalid ({err}). Reply with ONLY the JSON object."
    raise LLMError(f"LLM returned invalid JSON twice ({label})")
