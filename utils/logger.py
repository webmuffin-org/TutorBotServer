import json
import logging
import os
import time
import requests
from typing import Optional, Tuple


class LokiHandler(logging.Handler):
    """Push to Loki /loki/api/v1/push with authentication."""

    def __init__(
        self,
        service_name: str,
        url: str,
        model_provider: str,
        model: str,
        env: str = "dev",
        loki_labels: str = "",
        auth: Optional[Tuple[str, str]] = None,
        org_id: Optional[str] = None,
        timeout: float = 3.0,
    ):
        super().__init__()
        self.endpoint = url.rstrip("/") + "/loki/api/v1/push"
        self.timeout = timeout
        self.auth = auth
        self.org_id = org_id
        self.labels = self._get_labels(
            service_name, model_provider, model, env, loki_labels
        )

    # ---------- helpers --------------------------------------------------

    def _get_labels(
        self,
        service_name: str,
        model_provider: str,
        model: str,
        env: str,
        loki_labels: str = "",
    ):
        """Get labels from constants."""
        lbl = {
            "service_name": service_name,
            "model_provider": model_provider,
            "model": model,
            "env": env,
        }

        # Parse additional labels from loki_labels string
        if loki_labels:
            for pair in loki_labels.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    lbl[k.strip()] = v.strip()

        # Individual environment labels (still allow for flexibility)
        for k, v in os.environ.items():
            if k.startswith("LOKI_LABEL_"):
                lbl[k[11:].lower()] = v

        return lbl

    @staticmethod
    def _now_ns() -> str:
        return str(int(time.time() * 1_000_000_000))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 1) Extract fields that should be labels
            label_fields = ["class_selection", "lesson", "action_plan", "redacted_access_key"]
            stream_labels = self.labels.copy()

            # Add dynamic labels from record
            for field in label_fields:
                value = getattr(record, field, "")
                # Ensure value is a string
                if value:
                    # Convert to string and limit length
                    str_value = str(value)
                    stream_labels[field] = str_value[:1024] if len(str_value) > 1024 else str_value
                else:
                    stream_labels[field] = ""  # Empty string for missing values

            # 2) Build details dictionary for JSON log message
            ignored = {
                "msg",
                "args",
                "exc_info",
                "exc_text",
                "stack_info",
                "levelname",
                "levelno",
                "name",
                "taskName",
                # Exclude fields that are now labels
                "class_selection",
                "lesson",
                "action_plan",
                "redacted_access_key",
            }
            detail = {}
            for k, v in record.__dict__.items():
                if k not in ignored and not k.startswith("_"):
                    if v is None:
                        continue
                    
                    # Keep original field names and values for JSON
                    if isinstance(v, (str, int, float, bool)):
                        # Keep primitive types as-is for JSON
                        detail[k] = v
                    else:
                        # Complex objects remain as-is for JSON serialization
                        detail[k] = v

            # 3) automatically add metadata fields
            detail["level"] = record.levelname.lower()
            detail["message"] = record.getMessage()
            
            # 4) ensure session_key and conversation_id are always present
            if "session_key" not in detail:
                detail["session_key"] = ""
            if "conversation_id" not in detail:
                detail["conversation_id"] = ""

            # 5) Create JSON log message with all details
            log_json = json.dumps(detail)
            
            # 6) Loki value format: [timestamp, log_message]
            value = [self._now_ns(), log_json]

            payload = {"streams": [{"stream": stream_labels, "values": [value]}]}


            # Prepare request parameters
            kwargs = {"json": payload, "timeout": self.timeout}

            # Add authentication if provided
            if self.auth:
                kwargs["auth"] = self.auth

            # Add headers if org_id is provided
            if self.org_id:
                kwargs["headers"] = {"X-Scope-OrgID": self.org_id}

            response = requests.post(self.endpoint, **kwargs)
            response.raise_for_status()

        except Exception:
            # swallow failures: logging must never crash the app
            self.handleError(record)


_logger_instance = None


def setup_logger(
    name="tutorbot-server",
    level=logging.INFO,
    model_provider="unknown",
    model="unknown",
    env="dev",
    loki_url="",
    loki_user="",
    loki_password="",
    loki_org_id="",
    loki_labels="",
) -> logging.Logger:
    """Set up and return the centralized logger instance."""
    global _logger_instance

    if _logger_instance is not None:
        return _logger_instance

    lg = logging.getLogger(name)
    lg.setLevel(level)
    lg.handlers.clear()  # Clear any existing handlers

    # Set up Loki handler if URL is provided
    if loki_url:
        auth = (loki_user, loki_password) if loki_user and loki_password else None

        h = LokiHandler(
            service_name=name,
            url=loki_url,
            model_provider=model_provider,
            model=model,
            env=env,
            loki_labels=loki_labels,
            auth=auth,
            org_id=loki_org_id,
        )
        h.setFormatter(logging.Formatter("%(levelname)s — %(message)s"))
        lg.addHandler(h)

    # Also add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s — %(name)s — %(levelname)s — %(message)s")
    )
    lg.addHandler(console_handler)

    _logger_instance = lg
    return lg


def get_logger() -> logging.Logger:
    """Get the centralized logger instance. Returns basic logger if not initialized."""
    global _logger_instance

    if _logger_instance is None:
        # Return a basic logger for early initialization stages
        return logging.getLogger("tutorbot-server")

    return _logger_instance
