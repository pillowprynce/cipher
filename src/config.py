"""Environment-based configuration for Cipher.

The API key comes ONLY from the CIPHER_API_KEY environment variable.
It is never logged, printed, persisted to files, or written to memory/logs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(Exception):
    """Raised when configuration is invalid or incomplete."""


@dataclass
class Config:
    api_key: str | None
    api_base: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_s: int = 60
    dry_run: bool = False
    max_tool_iterations: int = 12
    default_max_retries: int = 3
    default_max_steps: int = 40
    json_mode: bool = True
    # --- spawn / sub-agent limits ---
    max_spawn_depth: int = 2          # root=0; a depth-2 agent may not spawn
    max_subagents_per_run: int = 8    # total spawn_subagent calls allowed per run
    max_specialist_tool_iters: int = 8  # cap carved out for any single child
    # --- directories (relative to repo root) ---
    memory_dir: str = "memory"
    artifacts_dir: str = "artifacts"
    logs_dir: str = "logs"
    tests_dir: str = "tests"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}")


def load_config() -> Config:
    """Build a Config from the environment.

    Dry-run mode is selected when CIPHER_DRY_RUN=1 OR when no API key is
    present. In dry-run mode the loop uses deterministic stub agents and
    never touches the network.
    """
    api_key = os.environ.get("CIPHER_API_KEY") or None
    explicit_dry = os.environ.get("CIPHER_DRY_RUN") == "1"
    # The gemini-skill backend authenticates via the vault surrogate
    # exchange, so no raw key exists in the environment in that mode.
    skill_backend = os.environ.get("CIPHER_LLM_BACKEND") == "gemini-skill"
    cfg = Config(
        api_key=api_key,
        api_base=os.environ.get("CIPHER_API_BASE", "https://api.openai.com/v1").rstrip("/"),
        model=os.environ.get("CIPHER_MODEL", "gemini-flash-lite-latest"),
        timeout_s=_env_int("CIPHER_TIMEOUT_S", 60),
        dry_run=explicit_dry or (api_key is None and not skill_backend),
        max_tool_iterations=_env_int("CIPHER_MAX_TOOL_ITERS", 12),
        default_max_retries=_env_int("CIPHER_MAX_RETRIES", 3),
        default_max_steps=_env_int("CIPHER_MAX_STEPS", 40),
        json_mode=os.environ.get("CIPHER_JSON_MODE", "1") == "1",
        max_spawn_depth=_env_int("CIPHER_MAX_SPAWN_DEPTH", 2),
        max_subagents_per_run=_env_int("CIPHER_MAX_SUBAGENTS", 8),
        max_specialist_tool_iters=_env_int("CIPHER_MAX_SPECIALIST_ITERS", 8),
    )
    if cfg.max_tool_iterations < 1:
        raise ConfigError("CIPHER_MAX_TOOL_ITERS must be >= 1")
    if cfg.max_spawn_depth < 0:
        raise ConfigError("CIPHER_MAX_SPAWN_DEPTH must be >= 0")
    if cfg.max_subagents_per_run < 0:
        raise ConfigError("CIPHER_MAX_SUBAGENTS must be >= 0")
    return cfg


def require_api_key(cfg: Config) -> str:
    """Return the API key or raise a helpful error. The key value is never
    included in the error message."""
    if not cfg.api_key:
        raise ConfigError(
            "CIPHER_API_KEY is not set. Cipher's agents are real LLM agents and "
            "need an API key for an OpenAI-compatible Chat Completions endpoint.\n"
            "  export CIPHER_API_KEY=...\n"
            "Optional overrides:\n"
            "  CIPHER_API_BASE  (default https://api.openai.com/v1)\n"
            "  CIPHER_MODEL     (default gpt-4o-mini)\n"
            "  CIPHER_MAX_SPAWN_DEPTH / CIPHER_MAX_SUBAGENTS  (spawn limits)\n"
            "Or run without a key in deterministic stub mode:\n"
            "  CIPHER_DRY_RUN=1 python -m src.loop --task tasks/example-hello-task.json"
        )
    return cfg.api_key
