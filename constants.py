import os
import platform
import typing
from typing import Dict, Optional
from urllib.parse import urlparse
from pydantic import SecretStr
from utils.logger import get_logger

logger = get_logger()

# Service configuration
service_name = "tutorbot-server"
env = os.getenv("ENV", "dev")

current_working_path = os.getcwd()
local_assets_path = os.path.normpath(current_working_path)
if not os.path.exists(local_assets_path):
    logger.error(
        "Classes path not found",
        extra={
            "path": str(local_assets_path),
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )


port = int(os.getenv("PORT") or 3000)


cloud_mode_enabled = typing.cast(bool, os.getenv("CLOUD_MODE") == "true")
if not cloud_mode_enabled:
    logger.info(
        "Cloud mode disabled, using local filesystem",
        extra={
            "reason": "CLOUD_MODE environment variable not set",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )

s3_bucket_endpoint = typing.cast(str, os.getenv("S3_BUCKET_ENDPOINT"))
if not s3_bucket_endpoint and cloud_mode_enabled:
    error_message = "Cloud mode is enabled but the required environment variable S3_BUCKET_ENDPOINT is not set."

    logger.error(
        "S3 bucket endpoint not configured",
        extra={
            "cloud_mode": "enabled",
            "missing_var": "S3_BUCKET_ENDPOINT",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

s3_bucket_access_key = typing.cast(SecretStr, os.getenv("S3_BUCKET_ACCESS_KEY"))
if not s3_bucket_access_key and cloud_mode_enabled:
    error_message = "Cloud mode is enabled but the required environment variable S3_BUCKET_ACCESS_KEY is not set."

    logger.error(
        "S3 bucket access key not configured",
        extra={
            "cloud_mode": "enabled",
            "missing_var": "S3_BUCKET_ACCESS_KEY",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

s3_bucket_access_secret = typing.cast(SecretStr, os.getenv("S3_BUCKET_ACCESS_SECRET"))
if not s3_bucket_access_secret and cloud_mode_enabled:
    error_message = "Cloud mode is enabled but the required environment variable S3_BUCKET_ACCESS_SECRET is not set."

    logger.error(
        "S3 bucket access secret not configured",
        extra={
            "cloud_mode": "enabled",
            "missing_var": "S3_BUCKET_ACCESS_SECRET",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

s3_bucket_name = typing.cast(str, os.getenv("S3_BUCKET_NAME"))
if not s3_bucket_name and cloud_mode_enabled:
    error_message = "Cloud mode is enabled but the required environment variable S3_BUCKET_NAME is not set."

    logger.error(
        "S3 bucket name not configured",
        extra={
            "cloud_mode": "enabled",
            "missing_var": "S3_BUCKET_NAME",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

s3_bucket_path = typing.cast(str, os.getenv("S3_BUCKET_PATH"))
if not s3_bucket_path and cloud_mode_enabled:
    error_message = "Cloud mode is enabled but the required environment variable S3_BUCKET_PATH is not set."

    logger.error(
        "S3 bucket path not configured",
        extra={
            "cloud_mode": "enabled",
            "missing_var": "S3_BUCKET_PATH",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

# Pyppeteer removed - now using HTML export instead of PDF

mailgun_enabled = typing.cast(bool, os.getenv("MAILGUN_ENABLED") == "true")
if not mailgun_enabled:
    logger.info(
        "Mailgun disabled, email functionality unavailable",
        extra={
            "reason": "MAILGUN_ENABLED environment variable not set",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )

mailgun_api_url = typing.cast(str, os.getenv("MAILGUN_API_URL"))
if not mailgun_api_url and mailgun_enabled:
    error_message = "Mailgun is enabled but the required environment variable MAILGUN_API_URL is not set."

    logger.error(
        "Mailgun API URL not configured",
        extra={
            "mailgun_enabled": "true",
            "missing_var": "MAILGUN_API_URL",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

mailgun_api_key = typing.cast(str, os.getenv("MAILGUN_API_KEY"))
if not mailgun_api_key and mailgun_enabled:
    error_message = "Mailgun is enabled but the required environment variable MAILGUN_API_KEY is not set."

    logger.error(
        "Mailgun API key not configured",
        extra={
            "mailgun_enabled": "true",
            "missing_var": "MAILGUN_API_KEY",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

mailgun_from_address = typing.cast(str, os.getenv("MAILGUN_FROM_ADDRESS"))
if not mailgun_from_address and mailgun_enabled:
    error_message = "Mailgun is enabled but the required environment variable MAILGUN_FROM_ADDRESS is not set."

    logger.error(
        "Mailgun from address not configured",
        extra={
            "mailgun_enabled": "true",
            "missing_var": "MAILGUN_FROM_ADDRESS",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)


# =============================================================================
# Model Configuration
# =============================================================================
# Each provider has its own API key (required) and an optional comma-separated
# PROVIDER_MODELS list (first entry is that provider's default model). At
# least one provider API key must be configured or the server refuses to
# start. The first provider in PROVIDER_PRIORITY that has an API key becomes
# the server-side default for requests that don't specify a provider.

PROVIDER_PRIORITY: tuple[str, ...] = ("ANTHROPIC", "OPENAI", "GOOGLE")

DEFAULT_PROVIDER_MODELS: Dict[str, list[str]] = {
    "ANTHROPIC": [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    ],
    "OPENAI": [
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
    ],
    "GOOGLE": [
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
    ],
}


def _parse_models_list(env_var: str, fallback_models: list[str]) -> list:
    """Parse a provider model list from PROVIDER_MODELS, falling back to the built-in list."""
    models_str = os.getenv(env_var)
    if models_str:
        return [m.strip() for m in models_str.split(",") if m.strip()]
    return list(fallback_models)


def _load_provider_config() -> Dict[str, Dict]:
    """Load per-provider credentials from environment variables."""
    config: Dict[str, Dict] = {}
    for provider in PROVIDER_PRIORITY:
        key = os.getenv(f"{provider}_API_KEY")
        models = _parse_models_list(
            f"{provider}_MODELS",
            list(DEFAULT_PROVIDER_MODELS[provider]),
        )
        config[provider] = {
            "api_key": SecretStr(key) if key else None,
            "models": models,
            "default_model": models[0],
            "available": bool(key),
        }
    return config


provider_config: Dict[str, Dict] = _load_provider_config()

_available = [p for p, c in provider_config.items() if c["available"]]
if not _available:
    logger.error(
        "No provider API keys configured",
        extra={
            "required": "At least one provider key must be configured",
            "supported_providers": str(list(provider_config.keys())),
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError("At least one provider API key must be configured")

# First provider in priority order with an API key becomes the server default.
model_provider = next(p for p in PROVIDER_PRIORITY if p in _available)
default_model = provider_config[model_provider]["default_model"]

logger.info(
    "Provider configuration loaded",
    extra={
        "available_providers": str(_available),
        "default_provider": str(model_provider),
        "default_model": str(default_model),
        "session_key": "",
        "class_selection": "",
        "lesson": "",
        "action_plan": "",
    },
)

max_tokens = int(os.getenv("MAX_TOKENS") or 10000)

max_conversation_tokens = int(os.getenv("MAX_CONVERSATION_TOKENS") or 20000)

# SSR (Structured Semantic Retrieval) Configuration Constants
SSR_MAX_ITERATIONS = 4
SSR_CONTENT_SIZE_LIMIT_TOKENS = 50000
BYTES_PER_TOKEN_ESTIMATE = 4
SSR_CONTENT_DIRECTORY = "ssrcontent"
SSR_XML_RESPONSE_TAG = "SSR_response"
SSR_REQUEST_TAG = "SSR_requesting_content"


def validate_ssr_configuration():
    """Validate SSR-related configuration on startup."""
    if max_conversation_tokens <= 0:
        raise ValueError("MAX_CONVERSATION_TOKENS must be positive")

    if SSR_CONTENT_SIZE_LIMIT_TOKENS > max_conversation_tokens:
        logger.warning(
            "SSR content limit exceeds conversation limit",
            extra={
                "ssr_limit": str(SSR_CONTENT_SIZE_LIMIT_TOKENS),
                "conversation_limit": str(max_conversation_tokens),
                "session_key": "",
                "class_selection": "",
                "lesson": "",
                "action_plan": "",
            },
        )

    if SSR_MAX_ITERATIONS <= 0:
        raise ValueError("SSR_MAX_ITERATIONS must be positive")

    if BYTES_PER_TOKEN_ESTIMATE <= 0:
        raise ValueError("BYTES_PER_TOKEN_ESTIMATE must be positive")


max_retries = int(os.getenv("MAX_RETRIES") or "2")

timeout = int(os.getenv("TIMEOUT") or "300")

temperature = float(os.getenv("TEMPERATURE") or "0.7")

top_p = None
if os.getenv("TOP_P"):
    top_p = float(os.getenv("TOP_P"))  # type: ignore

frequency_penalty = None
if os.getenv("FREQUENCY_PENALTY"):
    frequency_penalty = float(os.getenv("FREQUENCY_PENALTY"))  # type: ignore

presence_penalty = None
if os.getenv("PRESENCE_PENALTY"):
    presence_penalty = float(os.getenv("PRESENCE_PENALTY"))  # type: ignore

system_encoding = (
    "utf-8" if platform.system() == "Windows" else None
)  # None uses the default system_encoding in Linux

# Loki logging configuration (required)
loki_url = typing.cast(str, os.getenv("LOKI_URL"))
if not loki_url:
    error_message = "LOKI_URL environment variable is required"
    logger.error(
        "Loki URL not configured",
        extra={
            "missing_var": "LOKI_URL",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

loki_user = typing.cast(str, os.getenv("LOKI_USER"))
if not loki_user:
    error_message = "LOKI_USER environment variable is required"
    logger.error(
        "Loki user not configured",
        extra={
            "missing_var": "LOKI_USER",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

loki_password = typing.cast(str, os.getenv("LOKI_PASSWORD"))
if not loki_password:
    error_message = "LOKI_PASSWORD environment variable is required"
    logger.error(
        "Loki password not configured",
        extra={
            "missing_var": "LOKI_PASSWORD",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

loki_org_id = typing.cast(str, os.getenv("LOKI_ORG_ID"))
if not loki_org_id:
    error_message = "LOKI_ORG_ID environment variable is required"
    logger.error(
        "Loki organization ID not configured",
        extra={
            "missing_var": "LOKI_ORG_ID",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError(error_message)

# Loki labels (optional)
loki_labels = typing.cast(str, os.getenv("LOKI_LABELS", ""))

logger.info(
    "Loki logging configured",
    extra={
        "loki_url": str(loki_url),
        "session_key": "",
        "classSelection": "",
        "lesson": "",
        "actionPlan": "",
    },
)
logger.info(
    "Loki organization ID configured",
    extra={
        "loki_org_id": str(loki_org_id),
        "session_key": "",
        "classSelection": "",
        "lesson": "",
        "actionPlan": "",
    },
)
if loki_labels:
    logger.info(
        "Loki additional labels configured",
        extra={
            "loki_labels": str(loki_labels),
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )

# =============================================================================
# Status Indicator Configuration
# =============================================================================

status_page_url: Optional[str] = os.getenv("STATUS_PAGE_URL")


def _parse_status_page_url() -> tuple[Optional[str], Optional[str]]:
    """
    Derive base URL and slug from STATUS_PAGE_URL.

    Handles URL patterns:
    - https://status.example.com/status/{slug}
    - https://status.example.com/{slug}

    Example:
        "https://status.example.com/status/tutorbot"
        -> base_url: "https://status.example.com"
        -> slug: "tutorbot"
    """
    if not status_page_url:
        return None, None

    parsed = urlparse(status_page_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    path = parsed.path.rstrip('/')
    segments = [s for s in path.split('/') if s]

    if not segments:
        return base_url, None

    slug = segments[-1]
    return base_url, slug


uptime_kuma_base_url, uptime_kuma_slug = _parse_status_page_url()

# Cache-Control header timing (seconds)
STATUS_CACHE_MAX_AGE: int = 30
STATUS_CACHE_STALE_WHILE_REVALIDATE: int = 60

# Status polling interval in seconds (client-side)
STATUS_POLL_INTERVAL_SECONDS: int = 60

# Group criticality mapping for status calculation
# Essential: Any monitor down = overall status "down"
# Non-essential: Any monitor down = overall status "degraded"
STATUS_GROUP_CRITICALITY: Dict[str, str] = {
    "Application": "essential",
    "Dependencies": "essential",
    "Observability": "non-essential",
}

# Uptime Kuma status codes
UPTIME_KUMA_STATUS_UP: int = 1
UPTIME_KUMA_STATUS_DOWN: int = 0


def is_status_indicator_enabled() -> bool:
    """Check if status indicator is properly configured."""
    return bool(uptime_kuma_base_url and uptime_kuma_slug)
