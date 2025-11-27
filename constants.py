import os
import platform
import typing
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


model_provider = typing.cast(str, os.getenv("MODEL_PROVIDER"))
if not model_provider:
    logger.error(
        "No model provider selected, using default",
        extra={
            "default_provider": "OPENAI",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    model_provider = "OPENAI"

model = typing.cast(str, os.getenv("MODEL"))
if not model:
    logger.error(
        "No model selected, using default",
        extra={
            "default_model": "atgpt-4o-latest",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    model = "chatgpt-4o-latest"
logger.info(
    "Model configured",
    extra={
        "model": str(model),
        "session_key": "",
        "classSelection": "",
        "lesson": "",
        "actionPlan": "",
    },
)

api_key = typing.cast(SecretStr, os.getenv("API_KEY"))
if not api_key and model_provider != "GOOGLE":
    logger.error(
        "API key not configured",
        extra={
            "missing_var": "API_KEY",
            "model_provider": str(model_provider),
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError("API_KEY environment variable not set")

max_tokens = int(os.getenv("MAX_TOKENS") or 10000)

max_conversation_tokens = int(os.getenv("MAX_CONVERSATION_TOKENS") or 20000)

# SSR (Structured Semantic Retrieval) Configuration Constants
SSR_MAX_ITERATIONS = 4
SSR_CONTENT_SIZE_LIMIT_TOKENS = 30000
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

timeout = int(os.getenv("TIMEOUT") or "60")

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

ibm_url = typing.cast(SecretStr, os.getenv("IBM_URL"))
if not ibm_url:
    ibm_url = "https://us-south.ml.cloud.ibm.com"

ibm_project_id = typing.cast(str, os.getenv("IBM_PROJECT_ID"))
if not ibm_project_id and model_provider == "IBM":
    logger.error(
        "IBM project ID not configured",
        extra={
            "missing_var": "IBM_PROJECT_ID",
            "model_provider": "IBM",
            "session_key": "",
            "class_selection": "",
            "lesson": "",
            "action_plan": "",
        },
    )
    raise ValueError("IBM_PROJECT_ID environment variable not set")

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
