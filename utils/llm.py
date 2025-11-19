import markdown
import nh3
from copy import deepcopy
from typing import List, Tuple

from utils.filesystem import open_text_file
from utils.logger import get_logger

logger = get_logger()


def redact_access_key(key: str) -> str:
    """
    Redact access key for safe logging using partial masking.
    Shows first 4 and last 4 characters with ... in between.

    Examples:
        "sk-abc123456789xyz" -> "sk-a...9xyz"
        "short" -> "s...t"
        "" -> "no_key"
    """
    if not key:
        return "no_key"
    if len(key) <= 8:
        # For very short keys, show first and last char only
        return f"{key[0]}...{key[-1]}" if len(key) >= 2 else "***"
    return f"{key[:4]}...{key[-4:]}"


def validate_access_key(
    access_key: str,
    session_key: str,
    class_selection: str = "",
    lesson: str = "",
    action_plan: str = "",
) -> bool:

    available_keys = open_text_file("config/access_keys.txt")

    if available_keys is None:
        logger.error(
            "Access key file not found",
            extra={
                "session_key": session_key,
                "class_selection": class_selection,
                "lesson": lesson,
                "action_plan": action_plan,
            },
        )
        return False

    if access_key not in available_keys.splitlines():
        logger.warning(
            "Invalid access key",
            extra={
                "session_key": session_key,
                "access_key": access_key,
                "class_selection": class_selection,
                "lesson": lesson,
                "action_plan": action_plan,
            },
        )
        return False

    return True


def get_llm_file(
    class_directory: str,
    type: str,
    file_name: str,
    session_key: str,
    class_selection: str = "",
    lesson: str = "",
    action_plan: str = "",
) -> str:

    temp_name = ""

    if type:
        content = open_text_file(f"classes/{class_directory}/{type}/{file_name}")
        temp_name              = f"classes/{class_directory}/{type}/{file_name}"
    else:
        content = open_text_file(f"classes/{class_directory}/{file_name}")
        temp_name              = f"classes/{class_directory}/{file_name}"

    if content is None:
        logger.warning(
            f"Failed to locate file ({temp_name})",
            extra={
                "session_key": session_key,
                "file_name": file_name,
                "class_selection": class_selection or class_directory,
                "lesson": lesson,
                "action_plan": action_plan,
            },
        )
        return ""

    if len(content) == 0:
        logger.warning(
            f"File ({temp_name}) is empty",
            extra={
                "session_key": session_key,
                "type": type,
                "file_name": file_name,
                "class_selection": class_selection or class_directory,
                "lesson": lesson,
                "action_plan": action_plan,
            },
        )
    else:
        logger.info(
            f"Loaded file ({temp_name})",
            extra={
                "session_key": session_key,
                "type": type,
                "file_name": file_name,
                "class_selection": class_selection or class_directory,
                "lesson": lesson,
                "action_plan": action_plan,
            },
        )

    return content


def format_conversation(conversation: List[Tuple[str, str]]) -> List[str]:
    user_message = """<div class="user-message"><h2 class="message-text">User: </h2><p>{user_input}</p></div>"""
    assistant_message = """<div class="bot-message"><h2 class="message-text">Bot:</h2>{assistant_response}</div>"""

    messages = []

    for message in conversation:
        role = message[0]
        content = message[1]

        if role == "user":
            messages.append(user_message.format(user_input=content))
        elif role == "assistant":
            html = markdown.markdown(content)

            attributes = deepcopy(nh3.ALLOWED_ATTRIBUTES)
            attributes["div"] = set()
            attributes["div"].add("class")

            clean_html = nh3.clean(html, attributes=attributes)
            messages.append(assistant_message.format(assistant_response=clean_html))

    return messages
