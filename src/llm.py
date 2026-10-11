"""Minimal stdlib-only client for OpenAI-compatible Chat Completions.

Uses urllib only. The API key is sent as a Bearer header and is NEVER
logged, printed, persisted, or included in exception messages.

When CIPHER_LLM_BACKEND=gemini-skill, requests are routed through the
Gemini skill CLI (~/workspace/skills/gemini/bin/chat.py), which holds
the credential via the secure vault surrogate exchange. In that mode no
raw key ever exists in this process's environment.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from .config import Config


class LLMError(Exception):
    """Raised when the LLM call fails. Never carries the API key."""


def _redacted_url(url: str) -> str:
    # The key is only ever in a header, but be defensive anyway.
    return url


def _via_skill_cli(payload: dict, timeout_s: int) -> str:
    """Route a chat request through the Gemini skill CLI.

    The CLI authenticates via the vault surrogate exchange; no raw key
    is present in this process. Raises LLMError on failure.
    """
    cli = os.path.expanduser("~/workspace/skills/gemini/bin/chat.py")
    try:
        proc = subprocess.run(
            [sys.executable, cli],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            timeout=timeout_s + 120,
        )
    except subprocess.TimeoutExpired:
        raise LLMError("gemini skill CLI timed out")
    except OSError as e:
        raise LLMError(f"gemini skill CLI could not start: {e}")
    if proc.returncode != 0:
        raw = (proc.stdout or b"").decode("utf-8", "replace") or (
            proc.stderr or b""
        ).decode("utf-8", "replace")
        try:
            msg = json.loads(raw).get("error", "skill CLI failed")
        except Exception:
            msg = raw[:300] or "skill CLI failed"
        raise LLMError(f"gemini skill: {msg[:300]}")
    try:
        out = json.loads(proc.stdout.decode("utf-8"))
    except Exception:
        raise LLMError("gemini skill: unreadable output")
    if out.get("error"):
        raise LLMError(f"gemini skill: {str(out['error'])[:300]}")
    content = out.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise LLMError("gemini skill: empty content")
    return content


def chat_complete(
    cfg: Config,
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int = 2500,
) -> str:
    """Send a chat completion request and return the assistant's text content.

    Raises LLMError on transport errors, non-2xx status, or malformed
    responses. Raises ConfigError (via require_api_key) when no key is set
    and the skill backend is not selected.
    """
    if os.environ.get("CIPHER_LLM_BACKEND") == "gemini-skill":
        return _via_skill_cli(
            {
                "model": cfg.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "json_mode": cfg.json_mode,
            },
            cfg.timeout_s,
        )

    from .config import require_api_key

    api_key = require_api_key(cfg)
    url = f"{cfg.api_base}/chat/completions"
    body: dict = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if cfg.json_mode:
        # OpenAI-compatible JSON mode; every role prompt demands a strict
        # JSON object, so this tightens compliance.
        body["response_format"] = {"type": "json_object"}

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        _redacted_url(url),
        data=data,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            detail = ""
        raise LLMError(f"LLM HTTP {e.code} from {cfg.api_base}: {detail}")
    except urllib.error.URLError as e:
        raise LLMError(f"LLM request failed ({cfg.api_base}): {e.reason}")
    except (TimeoutError, json.JSONDecodeError) as e:
        raise LLMError(f"LLM response unreadable: {type(e).__name__}")

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LLMError("LLM response missing choices[0].message.content")
    # Some OpenAI-compatible endpoints return content as a list of parts.
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM returned empty content")
    return content
