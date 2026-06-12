import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from constants import (
    model_provider,
    default_model,
    max_tokens,
    max_conversation_tokens,
    temperature,
    top_p,
    frequency_penalty,
    presence_penalty,
    max_retries,
    timeout,
    provider_config,
    SSR_MAX_ITERATIONS,
    SSR_CONTENT_SIZE_LIMIT_TOKENS,
    BYTES_PER_TOKEN_ESTIMATE,
    SSR_CONTENT_DIRECTORY,
    SSR_XML_RESPONSE_TAG,
    SSR_REQUEST_TAG,
)
from utils.types import PyMessage
from utils.llm import get_llm_file
from utils.logger import get_logger
from bs4 import BeautifulSoup, Tag

# Import for type annotations only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SessionCache import SessionCache

logger = get_logger()


def extract_message_content(message: BaseMessage) -> str:
    """Safely extract content from BaseMessage, handling both string and list content.

    LangChain content parts can be strings or dicts (e.g. Gemini returns
    {'type': 'text', 'text': '...', 'extras': {...}}). Only the 'text' field
    is user-visible; 'extras' (signatures, thought metadata) must be dropped.
    """
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        parts = []
        for item in message.content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return " ".join(parts)
    return str(message.content) if message.content else ""


def strip_markdown_fencing(text: str) -> str:
    """Strip markdown code fencing from LLM responses.

    Handles two patterns:
    1. Entire response is fenced:
        ```xml
        <content/>
        ```
    2. Preamble text followed by a fenced block:
        Here is the XML:
        ```xml
        <content/>
        ```

    When fencing is present, the structure is always:
        - Opening line: ``` with optional language tag (xml, json, html, etc.)
        - Closing line: ```
        - Exactly 2 backtick lines, no nested fences

    Returns the inner content without fence markers.
    Provider-agnostic: works for any LLM that adds code fencing.
    """
    stripped = text.strip()

    # Case 1: Entire response is a fenced block
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Remove opening fence line (```xml, ```json, ```, etc.)
        if lines[-1].strip() == "```":
            # Clean open/close pair: remove first and last line
            lines = lines[1:-1]
        else:
            # Opening fence but no closing fence: remove only first line
            lines = lines[1:]
        return "\n".join(lines).strip()

    # Case 2: Fenced block after preamble text (anchored to end of string)
    match = re.search(r"```\w*\n(.+?)```\s*$", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()

    return stripped


def calculate_conversation_size_exceeds_limit(
    conversation_size_bytes: int, max_tokens: int
) -> bool:
    """Check if conversation exceeds token limit using byte estimation."""
    return conversation_size_bytes > max_tokens * BYTES_PER_TOKEN_ESTIMATE


def format_token_usage_message(
    input_tokens: int, output_tokens: int, iterations: int
) -> str:
    """Format consistent token usage messages."""
    return f"Total Input Tokens ({input_tokens}), Total Output Tokens ({output_tokens}) over ({iterations}) passes\n"


def extract_ssr_content_request(
    llm_response_content: str,
) -> Tuple[bool, List[str], str]:
    """
    Extract SSR content request from LLM response.
    Returns: (has_ssr_request, requested_keys, answer_text)
    """
    soup = BeautifulSoup(llm_response_content, "lxml-xml")
    ssr_response = soup.find(SSR_XML_RESPONSE_TAG)

    if not isinstance(ssr_response, Tag):
        return False, [], ""

    content_request = ssr_response.find(SSR_REQUEST_TAG)
    if not isinstance(content_request, Tag):
        answer = ssr_response.find("answer")
        answer_text = answer.get_text() if isinstance(answer, Tag) else ""
        return False, [], answer_text

    primary_keys = content_request.find("PrimaryKeys")
    if not isinstance(primary_keys, Tag):
        answer = ssr_response.find("answer")
        answer_text = answer.get_text() if isinstance(answer, Tag) else ""
        return False, [], answer_text

    primary_keys_text = primary_keys.get_text().strip()
    if not primary_keys_text:
        answer = ssr_response.find("answer")
        answer_text = answer.get_text() if isinstance(answer, Tag) else ""
        return False, [], answer_text

    keys = [key.strip() for key in primary_keys_text.split(",")]
    return True, keys, ""


class PromptBuilder:
    """Strategy pattern for different LLM provider prompt formats.

    The standard builder ends with a system message carrying the action plan.
    Anthropic needs its own builder because langchain-anthropic's
    _format_messages (verified against 1.4.1) raises
    "Received multiple non-consecutive system messages" when a system message
    appears after the user/assistant turns, which is exactly the shape the
    standard builder produces (scenario + conundrum system blocks, then
    history, then a trailing action_plan system block).

    The Anthropic variant collapses scenario + conundrum + additional_content
    into a single leading system block and delivers the action plan as the
    final user turn, with a synthetic "How do you want me to respond"
    assistant turn inserted so the user/assistant alternation Anthropic
    requires remains valid.
    """

    @staticmethod
    def build_anthropic_prompt(
        scenario: str,
        conundrum: str,
        additional_content: str,
        conversation_history: List[Tuple[str, str]],
        action_plan: str,
        loaded_content_message: str = "",
    ) -> List[Tuple[str, str]]:
        """Build prompt format optimized for Anthropic models."""
        system_content = f"{scenario}\n{conundrum}\n{additional_content}"

        # Wrap conversation history
        formatted_history = []
        for role, text in conversation_history:
            if role.lower() in ("assistant"):
                formatted_history.append(("assistant", f"{text}"))
            else:
                formatted_history.append(
                    (
                        "user",
                        f"<USER_CONTEXT_NOT_INSTRUCTIONS>{text}</USER_CONTEXT_NOT_INSTRUCTIONS>",
                    )
                )
        return [
            ("system", system_content),
            *formatted_history,
            ("assistant", "How do you want me to respond"),
            ("user", f"{action_plan}"),
        ]

    @staticmethod
    def build_standard_prompt(
        scenario: str,
        conundrum: str,
        additional_content: str,
        conversation_history: List[Tuple[str, str]],
        action_plan: str,
        loaded_content_message: str = "",
    ) -> List[Tuple[str, str]]:
        """Build standard prompt format for other LLM providers."""
        messages = []
        if scenario:
            messages.append(("system", scenario))
        messages.extend(
            [
                ("system", conundrum),
                *conversation_history,
                (
                    "system",
                    f"Use additional content ({loaded_content_message} and Instructions {action_plan}",
                ),
            ]
        )
        return messages

    @staticmethod
    def build_prompt(
        scenario: str,
        conundrum: str,
        additional_content: str,
        conversation_history: List[Tuple[str, str]],
        action_plan: str,
        loaded_content_message: str = "",
        provider: str = model_provider,
    ) -> List[Tuple[str, str]]:
        """Build prompt using appropriate strategy based on model provider."""
        if provider == "ANTHROPIC":
            return PromptBuilder.build_anthropic_prompt(
                scenario,
                conundrum,
                additional_content,
                conversation_history,
                action_plan,
                loaded_content_message,
            )
        else:
            return PromptBuilder.build_standard_prompt(
                scenario,
                conundrum,
                additional_content,
                conversation_history,
                action_plan,
                loaded_content_message,
            )


@dataclass
class SSRIterationState:
    """Track SSR iteration state."""

    iteration_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    additional_content: str = ""
    loaded_content_message: str = ""
    conversation_truncated: bool = False

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts to running totals."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iteration_count += 1

    def has_exceeded_max_iterations(self) -> bool:
        """Check if maximum iterations exceeded."""
        return self.iteration_count > SSR_MAX_ITERATIONS


class SSRContentLoader:
    """Handles loading and size management of SSR content files."""

    def __init__(self, max_size_tokens: int = SSR_CONTENT_SIZE_LIMIT_TOKENS) -> None:
        self.max_size_bytes = max_size_tokens * BYTES_PER_TOKEN_ESTIMATE

    def load_content_files(
        self,
        request: PyMessage,
        session_key: str,
        content_keys: List[str],
        redacted_access_key: str = "",
    ) -> Tuple[str, str, List[str]]:
        """Load content files with size management."""
        loaded_contents = []
        loaded_file_names = []
        running_size = 0
        failed_keys = []

        for content_key in content_keys:
            content = get_llm_file(
                request.classSelection,
                SSR_CONTENT_DIRECTORY,
                f"{content_key}.txt",
                session_key,
                request.classSelection or "",
                request.lesson or "",
                request.actionPlan or "",
            )

            if not content:
                logger.error(
                    "Failed to load SSR content",
                    extra={
                        "session_key": session_key,
                        "redacted_access_key": redacted_access_key,
                        "content_key": content_key,
                        "class_selection": request.classSelection or "",
                        "lesson": request.lesson or "",
                        "action_plan": request.actionPlan or "",
                    },
                )
                loaded_contents.append(
                    f'<SSR_CONTENT name="{content_key}">No Content by this name Exists</SSR_CONTENT>\n'
                )
                loaded_file_names.append(content_key)

                continue

            content_size = len(content.encode("utf-8"))

            if (
                not loaded_contents
                or running_size + content_size <= self.max_size_bytes
            ):
                loaded_contents.append(
                    f'\n<SSR_CONTENT name="{content_key}">\n{content}\n</SSR_CONTENT>\n'
                )
                loaded_file_names.append(content_key)
                running_size += content_size
            else:
                failed_keys.append(content_key)
                logger.info(
                    f"{content_key} was not loaded because SSR content limit exceeded.",
                    extra={
                        "session_key": session_key,
                        "redacted_access_key": redacted_access_key,
                        "content_key": content_key,
                        "class_selection": request.classSelection or "",
                        "lesson": request.lesson or "",
                        "action_plan": request.actionPlan or "",
                    },
                )
                loaded_contents.append(
                    f'<SSR_CONTENT name="{content_key}">Failed to Load this because SSR Content size exceeded.</SSR_CONTENT>\n'
                )

        xml_content = f'<SSR_CONTENTS>{"".join(loaded_contents)}</SSR_CONTENTS>'
        status_message = (
            f'Loaded SSR Content {",".join(loaded_file_names)} for this request only.'
        )

        return xml_content, status_message, failed_keys


def _create_llm_instance(provider: str, model_name: str) -> BaseChatModel:
    """Create a new LLM instance for the given provider and model.

    Uses per-provider credentials from provider_config.
    """
    config: Dict[str, Any] = provider_config.get(provider.upper(), {})
    resolved_key = config.get("api_key")
    if resolved_key is None:
        raise ValueError(f"No API key configured for provider: {provider.upper()}")

    match provider.upper():
        case "OPENAI":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_name,
                max_completion_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                api_key=resolved_key,
                streaming=True,
                stream_usage=True,
                # Possible values: "none", "minimal", "low", "medium", "high",
                # "xhigh". "none" disables reasoning on GPT-5.1+ models; the
                # original GPT-5 only goes down to "minimal"; "xhigh" exists
                # on GPT-5.4+.
                reasoning_effort="none",
            )
        case "GOOGLE":
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model_name,
                max_output_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                temperature=temperature,
                top_p=top_p,
                google_api_key=resolved_key,
                streaming=True,
                # Possible values: "minimal", "low", "medium", "high".
                # Gemini 3+ models cannot fully disable thinking; "low" is the
                # minimum on Pro models ("minimal" exists only on Flash).
                # Defaults to "high" when unset.
                thinking_level="low",
            )
        case "ANTHROPIC":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model_name=model_name,
                max_tokens_to_sample=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                model_kwargs={
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty,
                },
                api_key=resolved_key,
                stop=None,
                streaming=True,
                # Possible values: {"type": "disabled"}, {"type": "adaptive"},
                # and the deprecated {"type": "enabled", "budget_tokens": N}.
                # "disabled" is accepted on Sonnet/Haiku/Opus 4.x; Fable 5
                # rejects an explicit "disabled" (omit the param entirely there).
                thinking={"type": "disabled"},
                # Possible values: "low", "medium", "high", "xhigh", "max".
                # Defaults to "high" when unset. "max" needs Opus 4.6+ or
                # Sonnet 4.6 (not Haiku); "xhigh" needs Opus 4.7+.
                # Typed shorthand for output_config={"effort": ...}; both are
                # sent to the API as output_config.effort.
                effort="low",
            )
        case _:
            raise ValueError(f"Invalid model provider: {provider}")


# LLM instance cache: keyed by (provider, model) tuple
_llm_cache: Dict[tuple, BaseChatModel] = {}


def get_llm() -> BaseChatModel:
    """Get or create the environment-configured LLM instance."""
    resolved_provider = model_provider.upper()
    resolved_model = default_model

    if not isinstance(resolved_model, str) or not resolved_model:
        raise ValueError(f"No model configured for provider: {resolved_provider}")

    key: Tuple[str, str] = (resolved_provider, resolved_model)
    if key not in _llm_cache:
        _llm_cache[key] = _create_llm_instance(resolved_provider, resolved_model)
        logger.info(
            f"Created LLM instance for {resolved_provider}/{resolved_model}",
            extra={
                "provider": resolved_provider,
                "model": resolved_model,
                "session_key": "",
                "class_selection": "",
                "lesson": "",
                "action_plan": "",
            },
        )
    return _llm_cache[key]


# Initialize the default LLM on module load (backward compatible)
try:
    _default_llm = get_llm()
except Exception as e:
    logger.critical("Failed to initialize LLM", extra={"error": str(e)})


def get_token_count(
    llm_response: BaseMessage,
    p_sessionKey: str,
    redacted_access_key: str = "",
    class_selection: str = "",
    lesson: str = "",
    action_plan: str = "",
) -> Tuple[int, int]:
    input_tokens = output_tokens = 0

    # Use LangChain's normalized usage_metadata (provider-agnostic)
    usage_metadata = getattr(llm_response, "usage_metadata", None)
    if usage_metadata:
        input_tokens = usage_metadata.get("input_tokens", 0)
        output_tokens = usage_metadata.get("output_tokens", 0)

    if input_tokens or output_tokens:
        logger.info(
            f"Token usage Input {input_tokens}, Output {output_tokens}",
            extra={
                "session_key": p_sessionKey,
                "redacted_access_key": redacted_access_key,
                "input_tokens": str(input_tokens),
                "output_tokens": str(output_tokens),
                "total_tokens": str(input_tokens + output_tokens),
                "class_selection": class_selection,
                "lesson": lesson,
                "action_plan": action_plan,
            },
        )

    return input_tokens, output_tokens


def invoke_llm_with_ssr(
    p_SessionCache: "SessionCache",
    p_Request: PyMessage,
    p_sessionKey: str,
    redacted_access_key: str,
) -> str:
    resolved_provider = model_provider.upper()
    effective_model = default_model
    try:
        llm_instance = get_llm()

        # Feed in the original request
        RequestText = p_Request.text
        p_SessionCache.m_simpleCounterLLMConversation.add_message(
            "user", RequestText, RequestText
        )

        SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP: List[str] = []

        # start by getting the various prompt components.
        # The p_Request contains the Lesson, Conundrum (Lesson), ActionPlan,
        scenario = (
            get_llm_file(
                p_Request.classSelection,
                "",
                "scenario.txt",
                p_sessionKey,
                p_Request.classSelection or "",
                p_Request.lesson or "",
                p_Request.actionPlan or "",
            )
            or ""
        )

        conundrum = get_llm_file(
            p_Request.classSelection,
            "conundrums",
            p_Request.lesson,
            p_sessionKey,
            p_Request.classSelection or "",
            p_Request.lesson or "",
            p_Request.actionPlan or "",
        )
        if conundrum is None:
            raise HTTPException(status_code=404, detail="Conundrum file not found")

        action_plan = get_llm_file(
            p_Request.classSelection,
            "actionplans",
            p_Request.actionPlan,
            p_sessionKey,
            p_Request.classSelection or "",
            p_Request.lesson or "",
            p_Request.actionPlan or "",
        )
        if action_plan is None:
            raise HTTPException(status_code=404, detail="action_plan file not found")

        actionPlan = action_plan  # + get_result_formatting()  Disabled for now. Not sure why this is here.

        content_loader = SSRContentLoader()
        ssr_state = SSRIterationState()

        while True:

            conversation_history = (
                p_SessionCache.m_simpleCounterLLMConversation.get_all_previous_messages()
            )

            ssr_state.increment_iteration()

            logger.info(
                f"SSR loop count = ({ssr_state.iteration_count})",
                extra={
                    "session_key": p_sessionKey,
                    "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                    "redacted_access_key": redacted_access_key,
                    "max_iterations": str(SSR_MAX_ITERATIONS),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )

            TempAdditionalContent = ssr_state.additional_content
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            temp_additional_content = (
                f"<CURRENT_DATE_TIME>{current_time}</CURRENT_DATE_TIME>\n"
                + TempAdditionalContent
                + "<SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP>"
                + ", ".join(SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP)
                + "</SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP>\n"
            )

            messages = PromptBuilder.build_prompt(
                scenario,
                conundrum,
                temp_additional_content,
                conversation_history,
                actionPlan,
                ssr_state.loaded_content_message,
                provider=resolved_provider,
            )

            # transform tuples into json and dump as string
            parsed_messages = (
                p_SessionCache.m_simpleCounterLLMConversation.get_serializable_conversation()
            )

            # Turn list of tuples into a readable string
            messages_str = "\n".join(
                [f"{role.upper()}: {content}" for role, content in messages]
            )

            # Enforce 2 MB limit
            MAX_LOG_SIZE = 2 * 1024 * 1024  # 2 MB
            if len(messages_str) > MAX_LOG_SIZE:
                messages_str = messages_str[:MAX_LOG_SIZE] + "... [TRUNCATED]"

            if ssr_state.iteration_count == 1:
                clipped_request = (
                    (RequestText[:120] + "...")
                    if len(RequestText) > 120
                    else RequestText
                )

                logger.info(
                    f"USER REQUEST : {clipped_request}\n{messages_str}",
                    extra={
                        "session_key": p_sessionKey,
                        "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                        "redacted_access_key": redacted_access_key,
                        "provider": resolved_provider,
                        "model": effective_model,
                        "messages": parsed_messages,
                        "class_selection": p_Request.classSelection or "",
                        "lesson": p_Request.lesson or "",
                        "action_plan": p_Request.actionPlan or "",
                    },
                )
            else:
                logger.info(
                    f"SSR REQUEST : {RequestText}\n{messages_str}",
                    extra={
                        "session_key": p_sessionKey,
                        "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                        "redacted_access_key": redacted_access_key,
                        "provider": resolved_provider,
                        "model": effective_model,
                        "messages": parsed_messages,
                        "class_selection": p_Request.classSelection or "",
                        "lesson": p_Request.lesson or "",
                        "action_plan": p_Request.actionPlan or "",
                    },
                )

            raw_response = llm_instance.invoke(messages)
            response_text = strip_markdown_fencing(
                extract_message_content(raw_response)
            )
            request_token_count, response_token_count = get_token_count(
                raw_response,
                p_sessionKey,
                redacted_access_key,
                p_Request.classSelection or "",
                p_Request.lesson or "",
                p_Request.actionPlan or "",
            )

            ssr_state.add_tokens(request_token_count, response_token_count)

            # Process the LLM response for SSR content requests
            has_ssr_request, requested_keys, answer_text = extract_ssr_content_request(
                response_text
            )

            if requested_keys:
                SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP.extend(requested_keys)

            logger.info(
                f"LLM RESPONSE :\n{response_text}",
                extra={
                    "session_key": p_sessionKey,
                    "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                    "redacted_access_key": redacted_access_key,
                    "provider": resolved_provider,
                    "model": effective_model,
                    "total_input_tokens": str(ssr_state.total_input_tokens),
                    "total_output_tokens": str(ssr_state.total_output_tokens),
                    "llm_response": response_text,
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )

            if not has_ssr_request:
                if answer_text:
                    # SSR response without content request: return final answer
                    user_facing_message = format_token_usage_message(
                        ssr_state.total_input_tokens,
                        ssr_state.total_output_tokens,
                        ssr_state.iteration_count,
                    )
                    user_facing_message += answer_text
                    logger.info(
                        f"SSR USER RESPONSE : ({user_facing_message})",
                        extra={
                            "session_key": p_sessionKey,
                            "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                            "redacted_access_key": redacted_access_key,
                            "provider": resolved_provider,
                            "model": effective_model,
                            "total_input_tokens": str(ssr_state.total_input_tokens),
                            "total_output_tokens": str(ssr_state.total_output_tokens),
                            "llm_response": response_text,
                            "class_selection": p_Request.classSelection or "",
                            "lesson": p_Request.lesson or "",
                            "action_plan": p_Request.actionPlan or "",
                        },
                    )
                else:
                    user_facing_message = response_text
                    logger.info(
                        f"USER RESPONSE :\n{user_facing_message}",
                        extra={
                            "session_key": p_sessionKey,
                            "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                            "redacted_access_key": redacted_access_key,
                            "provider": resolved_provider,
                            "model": effective_model,
                            "total_input_tokens": str(ssr_state.total_input_tokens),
                            "total_output_tokens": str(ssr_state.total_output_tokens),
                            "llm_response": response_text,
                            "class_selection": p_Request.classSelection or "",
                            "lesson": p_Request.lesson or "",
                            "action_plan": p_Request.actionPlan or "",
                        },
                    )
                # No SSR processing needed: break out of loop
                break

            RequestText = "Here is the requested SSR Content"

            # if more content is being requested and exceeded max iterations, use what you have.
            if ssr_state.has_exceeded_max_iterations():

                user_facing_message = format_token_usage_message(
                    ssr_state.total_input_tokens,
                    ssr_state.total_output_tokens,
                    ssr_state.iteration_count,
                )
                user_facing_message += answer_text + "\n"
                user_facing_message += "**SSR exceeded loop count.  Consider narrowing down your question**"

                logger.warning(
                    "SSR Loop exceeded maximum iterations",
                    extra={
                        "session_key": p_sessionKey,
                        "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                        "redacted_access_key": redacted_access_key,
                        "max_iterations": str(SSR_MAX_ITERATIONS),
                        "iteration_count": str(ssr_state.iteration_count),
                        "reason": "iteration_count > SSR_MAX_ITERATIONS",
                        "requested_keys": requested_keys,
                        "answer_text": answer_text,
                        "total_input_tokens": str(ssr_state.total_input_tokens),
                        "total_output_tokens": str(ssr_state.total_output_tokens),
                        "llm_message": user_facing_message,
                        "class_selection": p_Request.classSelection or "",
                        "lesson": p_Request.lesson or "",
                        "action_plan": p_Request.actionPlan or "",
                    },
                )
                break

            # Log the reason the loop is continuing
            logger.info(
                f"SSR loop continuing because content ({requested_keys}) requested",
                extra={
                    "session_key": p_sessionKey,
                    "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                    "redacted_access_key": redacted_access_key,
                    "iteration_count": str(ssr_state.iteration_count),
                    "reason": "has_ssr_request is True and within max iterations",
                    "requested_keys": requested_keys,
                    "max_iterations": str(SSR_MAX_ITERATIONS),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )

            # LLM requested SSR content.  Record the response in the conversation.
            p_SessionCache.m_simpleCounterLLMConversation.add_message(
                "assistant", response_text, None
            )
            # and indicate user is going to send it in prompt (but not in conversation)
            p_SessionCache.m_simpleCounterLLMConversation.add_message(
                "user", RequestText, None
            )

            content_loaded, loaded_status, failed_keys = (
                content_loader.load_content_files(
                    p_Request, p_sessionKey, requested_keys, redacted_access_key
                )
            )
            # if these keys failed to load, remove them from the memory of that event.
            if failed_keys:
                SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP = [
                    key
                    for key in SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP
                    if key not in failed_keys
                ]

            ssr_state.additional_content = content_loaded
            ssr_state.loaded_content_message = loaded_status

            # End of while loop

        # This is recording the last assistant response in the conversation.  Original Request was put in earlier
        p_SessionCache.m_simpleCounterLLMConversation.add_message(
            "assistant", response_text, user_facing_message
        )

        # Check if conversation size management is needed
        user_conversation_size = (
            p_SessionCache.m_simpleCounterLLMConversation.get_total_conv_content_bytes()
        )
        if calculate_conversation_size_exceeds_limit(
            user_conversation_size, max_conversation_tokens
        ):
            ssr_state.conversation_truncated = True
            logger.info(
                "Conversation exceeded maximum size",
                extra={
                    "session_key": p_sessionKey,
                    "conversation_id": p_SessionCache.m_simpleCounterLLMConversation.conversation_id,
                    "redacted_access_key": redacted_access_key,
                    "provider": resolved_provider,
                    "model": effective_model,
                    "user_conversation_size": str(user_conversation_size),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )
            p_SessionCache.m_simpleCounterLLMConversation.prune_oldest_pair()

        if ssr_state.conversation_truncated:
            user_facing_message = (
                "Old Conversations getting dropped.  Consider starting a new Conversation\n"
                + user_facing_message
            )

        return user_facing_message

    except Exception as e:
        logger.error(
            "Exception occurred while calling LLM",
            exc_info=True,
            extra={
                "session_key": p_sessionKey,
                "conversation_id": (
                    p_SessionCache.m_simpleCounterLLMConversation.conversation_id
                    if p_SessionCache
                    else ""
                ),
                "redacted_access_key": redacted_access_key,
                "provider": resolved_provider,
                "model": effective_model,
                "error": str(e),
                "class_selection": p_Request.classSelection if p_Request else "",
                "lesson": p_Request.lesson if p_Request else "",
                "action_plan": p_Request.actionPlan if p_Request else "",
            },
        )
        return f"An error ({e}) occurred processing your request. Please try again."
