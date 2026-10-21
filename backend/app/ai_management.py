"""
Central AI provider management.

This module is the SINGLE SOURCE OF TRUTH for external AI API calls.

Architecture
------------
Feature modules own:
    - prompts
    - business logic
    - feature-specific validation

This module owns:
    - AI provider selection
    - Gemini API-key discovery
    - round-robin key rotation
    - key failover
    - Gemini client creation
    - model/configuration management
    - provider-specific API calls
    - response extraction
    - provider/API error handling

Feature modules should ONLY call:

    from app.ai_management import generate_ai_text

Environment variables
---------------------
Required:

    AI_PROVIDER=gemini
    GEMINI_MODEL=gemini-3.5-flash-lite

Gemini keys:

    GEMINI_API_KEY_1=...
    GEMINI_API_KEY_2=...
    GEMINI_API_KEY_3=...
    ...
    GEMINI_API_KEY_N=...

Only numbered Gemini keys are supported.

The legacy variable GEMINI_API_KEY is intentionally NOT supported.
This prevents an old single-key environment variable from silently
bypassing the multi-key rotation system.

Key rotation
------------
Independent requests rotate round-robin:

    Request 1 -> KEY_1
    Request 2 -> KEY_2
    Request 3 -> KEY_3
    Request 4 -> KEY_1

If a selected key fails, the next available key is tried automatically.

A failed key is temporarily cooled down. Quota/rate-limit failures use
the configured cooldown. Other failures receive a shorter cooldown.

The rotation state is process-local. In a multi-worker deployment,
each worker has its own rotation state. Global coordination can later
be implemented with Redis or another shared state store.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv
from google import genai


# ============================================================
# ENVIRONMENT
# ============================================================

# Locate the backend .env from the current working directory.
# This is particularly useful when Uvicorn is started from the
# backend/project directory.
_DOTENV_PATH = find_dotenv(usecwd=True)

if _DOTENV_PATH:
    load_dotenv(_DOTENV_PATH)
else:
    load_dotenv()


# ============================================================
# AI CONFIGURATION
# ============================================================

DEFAULT_AI_PROVIDER = "gemini"

AI_PROVIDER = os.getenv(
    "AI_PROVIDER",
    DEFAULT_AI_PROVIDER,
).strip().lower()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite",
).strip()

DEFAULT_TEMPERATURE = float(
    os.getenv(
        "AI_TEMPERATURE",
        "0.9",
    )
)

DEFAULT_MAX_OUTPUT_TOKENS = int(
    os.getenv(
        "AI_MAX_OUTPUT_TOKENS",
        "12000",
    )
)

# Cooldown applied after quota/rate-limit related failures.
GEMINI_KEY_COOLDOWN_SECONDS = float(
    os.getenv(
        "GEMINI_KEY_COOLDOWN_SECONDS",
        "60",
    )
)

# Safety limit for automatically discovered numbered keys.
MAX_GEMINI_KEYS = int(
    os.getenv(
        "MAX_GEMINI_KEYS",
        "100",
    )
)


# ============================================================
# PROVIDER-NEUTRAL GENERATION CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class AIGenerationConfig:
    """Provider-neutral settings passed to the active AI provider."""

    temperature: float = DEFAULT_TEMPERATURE
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS


# ============================================================
# GEMINI KEY RUNTIME STATE
# ============================================================


@dataclass
class _GeminiKeyState:
    """
    Runtime state for one configured Gemini API key.

    The actual API secret is never returned by diagnostic functions.
    """

    index: int
    key: str
    cooldown_until: float = 0.0
    consecutive_failures: int = 0


_GEMINI_KEY_PATTERN = re.compile(
    r"^GEMINI_API_KEY_(\d+)$"
)

_key_lock = threading.RLock()

# Key pool is initialized lazily.
_gemini_keys: list[_GeminiKeyState] = []

# Points to the next key position for independent requests.
_next_key_position = 0


# ============================================================
# GEMINI KEY DISCOVERY
# ============================================================


def _discover_gemini_keys() -> list[_GeminiKeyState]:
    """
    Discover all numbered Gemini API keys from the environment.

    Accepted:
        GEMINI_API_KEY_1
        GEMINI_API_KEY_2
        GEMINI_API_KEY_3
        ...

    Keys are sorted numerically.

    Example:
        GEMINI_API_KEY_2
        GEMINI_API_KEY_10

    becomes:
        KEY_2
        KEY_10

    rather than alphabetical ordering.

    The legacy GEMINI_API_KEY variable is intentionally ignored.
    """

    discovered: list[tuple[int, str]] = []

    for environment_name, value in os.environ.items():
        match = _GEMINI_KEY_PATTERN.fullmatch(environment_name)

        if not match:
            continue

        if not value or not value.strip():
            continue

        try:
            key_index = int(match.group(1))
        except ValueError:
            continue

        if key_index <= 0:
            continue

        if key_index > MAX_GEMINI_KEYS:
            continue

        discovered.append(
            (
                key_index,
                value.strip(),
            )
        )

    # Protect against duplicate indices.
    unique_by_index: dict[int, str] = {}

    for key_index, key in discovered:
        unique_by_index[key_index] = key

    return [
        _GeminiKeyState(
            index=key_index,
            key=key,
        )
        for key_index, key in sorted(
            unique_by_index.items(),
            key=lambda item: item[0],
        )
    ]


def _get_gemini_key_pool() -> list[_GeminiKeyState]:
    """
    Return the process-local Gemini key pool.

    The environment is read once per backend process. Restart the
    backend after changing .env values.
    """

    global _gemini_keys

    with _key_lock:
        if _gemini_keys:
            return _gemini_keys

        discovered_keys = _discover_gemini_keys()

        if discovered_keys:
            _gemini_keys = discovered_keys

        return _gemini_keys


# ============================================================
# SAFE API-KEY REPRESENTATION
# ============================================================


def _mask_api_key(key: str) -> str:
    """
    Return a safe representation of an API key for logs.

    The complete credential is never logged.
    """

    if not key:
        return "<empty>"

    if len(key) <= 8:
        return "****"

    return f"{key[:4]}...{key[-4:]}"


# ============================================================
# KEY AVAILABILITY / ROTATION
# ============================================================


def _is_key_available(
    state: _GeminiKeyState,
    now: float,
) -> bool:
    """Return True when the key is not currently cooling down."""

    return state.cooldown_until <= now


def _select_next_gemini_key(
    *,
    excluded_indices: set[int] | None = None,
) -> _GeminiKeyState | None:
    """
    Select the next available Gemini key using round-robin rotation.

    A key in excluded_indices cannot be selected for this request.

    The global rotation pointer advances immediately after selection,
    ensuring independent requests do not repeatedly select the same key.
    """

    global _next_key_position

    excluded_indices = excluded_indices or set()

    with _key_lock:
        key_pool = _get_gemini_key_pool()

        if not key_pool:
            return None

        now = time.monotonic()
        pool_size = len(key_pool)

        for offset in range(pool_size):
            position = (
                _next_key_position + offset
            ) % pool_size

            state = key_pool[position]

            if state.index in excluded_indices:
                continue

            if not _is_key_available(state, now):
                continue

            _next_key_position = (
                position + 1
            ) % pool_size

            return state

        return None


def _mark_key_success(
    state: _GeminiKeyState,
) -> None:
    """Reset the key's runtime failure state after success."""

    with _key_lock:
        state.consecutive_failures = 0
        state.cooldown_until = 0.0


def _mark_key_failure(
    state: _GeminiKeyState,
    error: Exception,
) -> None:
    """
    Record a failed request and temporarily cool down the key.

    Quota/rate-limit errors use the full configured cooldown.
    Other errors receive a shorter progressive cooldown.
    """

    error_text = str(error).lower()

    quota_related_terms = (
        "quota",
        "rate limit",
        "ratelimit",
        "resource exhausted",
        "too many requests",
        "429",
        "exceeded",
        "limit",
    )

    is_quota_related = any(
        term in error_text
        for term in quota_related_terms
    )

    with _key_lock:
        state.consecutive_failures += 1

        if is_quota_related:
            cooldown = GEMINI_KEY_COOLDOWN_SECONDS
        else:
            cooldown = min(
                10.0 * state.consecutive_failures,
                GEMINI_KEY_COOLDOWN_SECONDS,
            )

        state.cooldown_until = (
            time.monotonic() + cooldown
        )


# ============================================================
# PROVIDER CLIENT MANAGEMENT
# ============================================================


def _get_gemini_client(
    api_key: str,
) -> genai.Client:
    """Create a Gemini client for one specific API key."""

    if not api_key:
        raise RuntimeError(
            "Gemini API key is empty."
        )

    return genai.Client(
        api_key=api_key,
    )


def _get_provider_client(
    *,
    api_key: str | None = None,
) -> Any:
    """
    Create the client for the configured AI provider.

    Provider-specific implementation is intentionally isolated here.
    """

    if AI_PROVIDER == "gemini":
        if not api_key:
            raise RuntimeError(
                "No Gemini API key is available."
            )

        return _get_gemini_client(api_key)

    raise RuntimeError(
        f"Unsupported AI provider: '{AI_PROVIDER}'. "
        "Configure a supported provider in AI_PROVIDER."
    )


# ============================================================
# GEMINI GENERATION
# ============================================================


def _generate_with_gemini(
    *,
    prompt: str,
    system_instruction: str | None,
    config: AIGenerationConfig,
) -> str:
    """
    Generate text with automatic Gemini key rotation and failover.

    One logical request:
        1. Select the next available key.
        2. Call Gemini.
        3. Return immediately on non-empty success.
        4. Mark failed key and cool it down.
        5. Try another available key.
        6. Never retry the same key within the request.
        7. Raise one final error if all available keys fail.
    """

    key_pool = _get_gemini_key_pool()

    if not key_pool:
        raise RuntimeError(
            "No Gemini API keys are configured. "
            "Add GEMINI_API_KEY_1, GEMINI_API_KEY_2, etc. "
            "to the backend .env file and restart the backend."
        )

    request_kwargs: dict[str, Any] = {
        "model": GEMINI_MODEL,
        "input": prompt,
        "generation_config": {
            "temperature": config.temperature,
            "max_output_tokens": config.max_output_tokens,
        },
    }

    if system_instruction:
        request_kwargs["system_instruction"] = system_instruction

    attempted_indices: set[int] = set()
    errors: list[str] = []

    # A logical request attempts each configured key at most once.
    max_attempts = len(key_pool)

    for _ in range(max_attempts):
        state = _select_next_gemini_key(
            excluded_indices=attempted_indices,
        )

        if state is None:
            break

        attempted_indices.add(state.index)

        masked_key = _mask_api_key(state.key)

        try:
            client = _get_provider_client(
                api_key=state.key,
            )

            interaction = client.interactions.create(
                **request_kwargs,
            )

            output = (
                getattr(
                    interaction,
                    "output_text",
                    None,
                )
                or ""
            ).strip()

            if not output:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            _mark_key_success(state)

            print(
                "AI request succeeded "
                f"(provider=gemini, model={GEMINI_MODEL}, "
                f"key=GEMINI_API_KEY_{state.index})"
            )

            return output

        except Exception as error:
            _mark_key_failure(
                state,
                error,
            )

            error_message = (
                str(error).strip()
                or error.__class__.__name__
            )

            errors.append(
                f"GEMINI_API_KEY_{state.index}: {error_message}"
            )

            print(
                "Gemini API key failed; rotating to the next key. "
                f"(key=GEMINI_API_KEY_{state.index}, "
                f"masked={masked_key}, "
                f"model={GEMINI_MODEL}, "
                f"error={error_message})"
            )

    attempted_key_names = ", ".join(
        f"GEMINI_API_KEY_{index}"
        for index in sorted(attempted_indices)
    )

    details = " | ".join(errors)

    raise RuntimeError(
        "All available Gemini API keys failed for this request. "
        f"Attempted: {attempted_key_names or 'none'}. "
        f"Details: {details or 'No additional error details available.'}"
    )


# ============================================================
# PUBLIC APPLICATION AI API
# ============================================================


def generate_ai_text(
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> str:
    """
    Generate text through the configured AI provider.

    This is the public application-level AI interface.

    Feature modules should NOT:
        - import google.genai
        - create AI clients
        - read API keys
        - select models
        - implement provider failover

    They should only call this function.
    """

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(
            "AI prompt cannot be empty."
        )

    if system_instruction is not None:
        if not isinstance(system_instruction, str):
            raise ValueError(
                "system_instruction must be a string or None."
            )

        system_instruction = (
            system_instruction.strip()
            or None
        )

    try:
        resolved_temperature = (
            DEFAULT_TEMPERATURE
            if temperature is None
            else float(temperature)
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "AI temperature must be a valid number."
        ) from error

    try:
        resolved_max_output_tokens = (
            DEFAULT_MAX_OUTPUT_TOKENS
            if max_output_tokens is None
            else int(max_output_tokens)
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "AI max_output_tokens must be a valid integer."
        ) from error

    config = AIGenerationConfig(
        temperature=resolved_temperature,
        max_output_tokens=resolved_max_output_tokens,
    )

    if config.temperature < 0:
        raise ValueError(
            "AI temperature cannot be negative."
        )

    if config.max_output_tokens <= 0:
        raise ValueError(
            "AI max_output_tokens must be greater than zero."
        )

    if AI_PROVIDER == "gemini":
        return _generate_with_gemini(
            prompt=prompt.strip(),
            system_instruction=system_instruction,
            config=config,
        )

    raise RuntimeError(
        f"Unsupported AI provider: '{AI_PROVIDER}'."
    )


# ============================================================
# SAFE DIAGNOSTICS
# ============================================================


def get_ai_provider_info() -> dict[str, Any]:
    """
    Return safe AI configuration information.

    API secrets are never returned.
    """

    key_pool = _get_gemini_key_pool()
    now = time.monotonic()

    available_keys = sum(
        1
        for state in key_pool
        if _is_key_available(
            state,
            now,
        )
    )

    configured_key_names = [
        f"GEMINI_API_KEY_{state.index}"
        for state in key_pool
    ]

    # This is diagnostic only. The legacy variable is never used.
    legacy_key_present = bool(
        os.getenv(
            "GEMINI_API_KEY",
            "",
        ).strip()
    )

    return {
        "provider": AI_PROVIDER,
        "model": (
            GEMINI_MODEL
            if AI_PROVIDER == "gemini"
            else None
        ),
        "configured_gemini_keys": len(key_pool),
        "configured_key_names": configured_key_names,
        "available_gemini_keys": available_keys,
        "key_rotation": "round_robin",
        "key_failover": True,
        "legacy_gemini_key_present": legacy_key_present,
        "legacy_gemini_key_used": False,
        "dotenv_path": _DOTENV_PATH or None,
        "default_temperature": DEFAULT_TEMPERATURE,
        "default_max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        "cooldown_seconds": GEMINI_KEY_COOLDOWN_SECONDS,
    }


def get_gemini_key_status() -> list[dict[str, Any]]:
    """
    Return safe runtime status for each configured Gemini key.

    The actual API key is never returned.
    """

    key_pool = _get_gemini_key_pool()
    now = time.monotonic()

    with _key_lock:
        return [
            {
                "key_name": (
                    f"GEMINI_API_KEY_{state.index}"
                ),
                "masked_key": _mask_api_key(
                    state.key,
                ),
                "available": _is_key_available(
                    state,
                    now,
                ),
                "consecutive_failures": (
                    state.consecutive_failures
                ),
                "cooldown_remaining_seconds": round(
                    max(
                        0.0,
                        state.cooldown_until - now,
                    ),
                    2,
                ),
            }
            for state in key_pool
        ]


__all__ = [
    "AIGenerationConfig",
    "generate_ai_text",
    "get_ai_provider_info",
    "get_gemini_key_status",
]
