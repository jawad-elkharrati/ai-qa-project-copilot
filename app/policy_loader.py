from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.config import get_settings
from app.policy_models import PolicySet


class PolicyConfigurationError(ValueError):
    """Raised when the versioned QA policy file cannot be loaded safely."""


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parents[1] / candidate


def load_policy_set(path: str | Path) -> PolicySet:
    policy_path = _resolve_path(path)
    try:
        content = policy_path.read_bytes()
    except OSError as exc:
        raise PolicyConfigurationError(f"unable to read policy file: {policy_path}") from exc
    try:
        policy_set = PolicySet.model_validate_json(content)
    except ValidationError as exc:
        raise PolicyConfigurationError(f"invalid policy file: {policy_path}: {exc}") from exc
    return policy_set.model_copy(update={"content_hash": hashlib.sha256(content).hexdigest()})


@lru_cache
def get_policy_set() -> PolicySet:
    return load_policy_set(get_settings().policy_path)
