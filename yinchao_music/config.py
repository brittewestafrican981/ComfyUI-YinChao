"""Local API-key configuration for YinChao nodes.

The key is deliberately not a node input. ComfyUI settings are stored in the
user profile and are therefore not serialized into workflow JSON. Environment
variables are a useful headless fallback for servers and CI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


API_KEY_SETTING_ID = "YinChao.apiKey"
API_KEY_ENVIRONMENT = "YINCHAO_API_KEY"
ONBOARDING_URL = "https://platform.yinchaoyongxian.com/"
DEFAULT_API_BASE_URL = "https://open.yinchaoyongxian.com"


def _candidate_user_directories() -> list[Path]:
    candidates: list[Path] = []

    configured = os.environ.get("COMFYUI_USER_DIRECTORY") or os.environ.get(
        "COMFY_USER_DIRECTORY"
    )
    if configured:
        candidates.append(Path(configured).expanduser())

    try:
        import folder_paths  # type: ignore

        get_user_directory = getattr(folder_paths, "get_user_directory", None)
        if callable(get_user_directory):
            candidates.append(Path(get_user_directory()))
    except ImportError:
        pass

    comfy_base = os.environ.get("COMFYUI_BASE_PATH")
    if comfy_base:
        candidates.append(Path(comfy_base).expanduser() / "user")

    # These fallbacks make the package usable from a source checkout without
    # assuming that the repository itself is the ComfyUI installation.
    candidates.extend(
        [
            Path.cwd() / "user",
            Path(__file__).resolve().parents[1] / "user",
        ]
    )

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _key_from_settings(value: dict[str, Any]) -> str | None:
    candidate = value.get(API_KEY_SETTING_ID)
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    # Some ComfyUI versions nest extension settings under an object.
    yinchao = value.get("YinChao")
    if isinstance(yinchao, dict):
        candidate = yinchao.get("apiKey")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def resolve_api_key() -> str:
    """Resolve a key from ComfyUI settings, local node config, then env.

    The settings file is intentionally read-only here. Users configure it in
    the ComfyUI Settings panel; the env fallback is never written back to disk.
    """

    user_directories = _candidate_user_directories()

    # Resolve the source class globally: a ComfyUI setting must win over every
    # local fallback, regardless of which candidate directory was discovered
    # first. This prevents an old local key from silently taking precedence.
    settings_paths: list[Path] = []
    local_config_paths: list[Path] = []
    for user_dir in user_directories:
        for settings_path in (
            user_dir / "default" / "comfy.settings.json",
            user_dir / "comfy.settings.json",
        ):
            settings_paths.append(settings_path)
        local_config_paths.append(user_dir / "default" / "yinchao.json")

    for settings_path in settings_paths:
        settings = _read_json(settings_path)
        if settings:
            key = _key_from_settings(settings)
            if key:
                return key

    for config_path in local_config_paths:
        local_config = _read_json(config_path)
        if local_config:
            candidate = local_config.get("api_key")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    environment_key = os.environ.get(API_KEY_ENVIRONMENT, "").strip()
    if environment_key:
        return environment_key

    raise ConfigurationError(
        "未配置 YinChao API Key。请打开 ComfyUI Settings → YinChao → API Key，"
        f"或设置环境变量 {API_KEY_ENVIRONMENT}。注册、充值并创建 API Key：{ONBOARDING_URL}"
    )


def redact_secret(value: str | None) -> str:
    """Return a short safe representation for diagnostics."""

    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "<redacted>"
    return f"{value[:4]}…{value[-4:]}"
