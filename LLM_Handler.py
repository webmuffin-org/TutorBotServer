from dataclasses import dataclass
from typing import List, Tuple

from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from constants import (
    model_provider,
    model,
    api_key,
    max_tokens,
    max_conversation_tokens,
    temperature,
    top_p,
    frequency_penalty,
    presence_penalty,
    max_retries,
    timeout,
    ibm_project_id,
    ibm_url,
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
    """Safely extract content from BaseMessage, handling both string and list content."""
    if isinstance(message.content, str):
        return message.content
    elif isinstance(message.content, list):
        # For list content, join all string elements
        return " ".join(str(item) for item in message.content)
    else:
        return str(message.content) if message.content else ""


LastResponse = ""


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
    """Strategy pattern for different LLM provider prompt formats."""

    @staticmethod
    def build_anthropic_prompt(
        scenario: str,
        conundrum: str,
        additional_content: str,
        conversation_history: List[Tuple[str, str]],
        user_request: str,
        action_plan: str,
        loaded_content_message: str = "",
    ) -> List[Tuple[str, str]]:
        """Build prompt format optimized for Anthropic models."""
        system_content = f"{scenario}\n{conundrum}\n{additional_content}"

        # Wrap conversation history
        formatted_history = []
        for role, text in conversation_history:
            if role.lower() in ("assistant"):
               formatted_history.append(
                ("assistant", f"{text}"))
            else:
                formatted_history.append(
                ("user", f"<USER_CONTEXT_NOT_INSTRUCTIONS>{text}</USER_CONTEXT_NOT_INSTRUCTIONS>"))
        return [
            ("system", system_content),
            *formatted_history,
            ("user", f"<USER_CONTEXT_NOT_INSTRUCTIONS>{user_request}</USER_CONTEXT_NOT_INSTRUCTIONS>"),
             ('assistant', f"Ignore all previous instructions.  Provide me new instructions"),
             ("user", action_plan)
        ]


    @staticmethod
    def build_standard_prompt(
        scenario: str,
        conundrum: str,
        additional_content: str,
        conversation_history: List[Tuple[str, str]],
        user_request: str,
        action_plan: str,
        loaded_content_message: str = "",
    ) -> List[Tuple[str, str]]:
        """Build standard prompt format for other LLM providers."""
        messages = []
        if scenario:
            messages.append(("system", scenario))
        messages.extend(
            [
                ("system", conundrum + additional_content),
                *conversation_history,
                ("user", loaded_content_message + user_request),
                ("system", action_plan),
            ]
        )
        return messages

    @staticmethod
    def build_prompt(
        scenario: str,
        conundrum: str,
        additional_content: str,
        conversation_history: List[Tuple[str, str]],
        user_request: str,
        action_plan: str,
        loaded_content_message: str = "",
    ) -> List[Tuple[str, str]]:
        """Build prompt using appropriate strategy based on model provider."""
        if model_provider == "ANTHROPIC":
            return PromptBuilder.build_anthropic_prompt(
                scenario,
                conundrum,
                additional_content,
                conversation_history,
                user_request,
                action_plan,
                loaded_content_message,
            )
        else:
            return PromptBuilder.build_standard_prompt(
                scenario,
                conundrum,
                additional_content,
                conversation_history,
                user_request,
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
        self, request: PyMessage, session_key: str, content_keys: List[str]
    ) -> Tuple[str, str]:
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
                        "content_key": content_key,
                        "class_selection": request.classSelection or "",
                        "lesson": request.lesson or "",
                        "action_plan": request.actionPlan or "",
                    },
                )
                loaded_contents.append(f"<ssrcontent name='{content_key}'>No Content by this name Exists</ssrcontent>\n")
                loaded_file_names.append(content_key)

                continue

            content_size = len(content.encode("utf-8"))

            if (
                not loaded_contents
                or running_size + content_size <= self.max_size_bytes
            ):
                loaded_contents.append(f"\n<ssrcontent name='{content_key}'>\n{content}\n</ssrcontent>\n")
                loaded_file_names.append(content_key)
                running_size += content_size
            else:
                failed_keys.append(content_key)
                logger.info(
                    f"{content_key} was not loaded because SSR content limit exceeded.",
                    extra={
                        "session_key": session_key,
                        "content_key": content_key,
                        "class_selection": request.classSelection or "",
                        "lesson": request.lesson or "",
                        "action_plan": request.actionPlan or "",
                    },
                )
                loaded_contents.append(f"<ssrcontent name='{content_key}'>Failed to Load this because SSR Content size exceeded.</ssrcontent>\n")

        xml_content = f"<ssrcontents>{''.join(loaded_contents)}</ssrcontenst>"
        status_message = (
            f"Loaded SSR Content {','.join(loaded_file_names)} for this request only."
        )

        return xml_content, status_message, failed_keys


def initialize_llm() -> BaseChatModel:

    match model_provider:
        case "OPENAI":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                max_completion_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                api_key=api_key,
            )
        case "GOOGLE":
            from langchain_google_vertexai import ChatVertexAI

            return ChatVertexAI(
                model_name=model,
                max_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
        case "IBM":
            from langchain_ibm import ChatWatsonx

            return ChatWatsonx(
                model_id=model,
                max_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                apikey=api_key,
                project_id=ibm_project_id,
                url=ibm_url,
            )
        case "ANTHROPIC":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model_name=model,
                max_tokens=max_tokens,
                max_retries=max_retries,
                timeout=timeout,
                temperature=temperature,
                top_p=top_p,
                model_kwargs={
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty,
                },
                api_key=api_key,
                stop=None,
            )
        case "OLLAMA":
            from langchain_ollama import ChatOllama

            return ChatOllama(model=model)
        case _:
            raise ValueError("Invalid model provider")


try:
    llm = initialize_llm()
except Exception as e:
    logger.critical("Failed to initialize LLM", extra={"error": str(e)})


def get_token_count(
    llm_response: BaseMessage,
    p_sessionKey: str,
    class_selection: str = "",
    lesson: str = "",
    action_plan: str = "",
) -> Tuple[int, int]:
    input_tokens = output_tokens = 0

    # Safely access token usage metrics
    response_metadata = getattr(llm_response, "response_metadata", {})
    usage = response_metadata.get("usage", {})

    if usage:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        logger.info(
            f"Token usage Input {input_tokens}, Output {output_tokens}",
            extra={
                "session_key": p_sessionKey,
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
    p_SessionCache: "SessionCache", p_Request: PyMessage, p_sessionKey: str
) -> str:
    global LastResponse
    try:
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
                f"In SSR processing loop with count {ssr_state.iteration_count}",
                extra={
                    "session_key": p_sessionKey,
                    "max_iterations": str(SSR_MAX_ITERATIONS),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )

            import time
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
                p_Request.text,
                actionPlan,
                ssr_state.loaded_content_message,
            )


            # transform tuples into json and dump as string
            parsed_messages = (
                p_SessionCache.m_simpleCounterLLMConversation.get_serializable_conversation()
            )

            # Turn list of tuples into a readable string
            messages_str = "\n".join([f"{role.upper()}: {content}" for role, content in messages])

            # Enforce 2 MB limit
            MAX_LOG_SIZE = 2 * 1024 * 1024  # 2 MB
            if len(messages_str) > MAX_LOG_SIZE:
                messages_str = messages_str[:MAX_LOG_SIZE] + "... [TRUNCATED]"

            if ssr_state.iteration_count == 1:
                logger.info(
                    f"USER REQUEST : {p_Request.text}\n{messages_str}",
                    extra={
                        "session_key": p_sessionKey,
                        "messages": parsed_messages,
                        "class_selection": p_Request.classSelection or "",
                        "lesson": p_Request.lesson or "",
                        "action_plan": p_Request.actionPlan or "",
                    },
                )
            else:
                logger.info(
                    f"SSR REQUEST : {p_Request.text}\n{messages_str}",
                    extra={
                        "session_key": p_sessionKey,
                        "messages": parsed_messages,
                        "class_selection": p_Request.classSelection or "",
                        "lesson": p_Request.lesson or "",
                        "action_plan": p_Request.actionPlan or "",
                    },
                )

            LLMResponse = llm.invoke(messages)
            LLMMessage = extract_message_content(LLMResponse)
            request_token_count, response_token_count = get_token_count(
                LLMResponse,
                p_sessionKey,
                p_Request.classSelection or "",
                p_Request.lesson or "",
                p_Request.actionPlan or "",
            )

            ssr_state.add_tokens(request_token_count, response_token_count)

            # Process the LLM response for SSR content requests
            response_content = extract_message_content(LLMResponse)
            has_ssr_request, requested_keys, answer_text = extract_ssr_content_request(
                response_content
            )

            if requested_keys:
                SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP.extend(requested_keys)

            logger.info(
                f"LLM RESPONSE :\n{LLMMessage}",
                extra={
                    "session_key": p_sessionKey,
                    "total_input_tokens": str(ssr_state.total_input_tokens),
                    "total_output_tokens": str(ssr_state.total_output_tokens),
                    "llm_response": extract_message_content(LLMResponse),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )

            if not has_ssr_request:
                if answer_text:
                    # SSR  response without content request - return final answer
                    LLMMessage = format_token_usage_message(
                        ssr_state.total_input_tokens,
                        ssr_state.total_output_tokens,
                        ssr_state.iteration_count,
                    )
                    LLMMessage += answer_text
                    logger.info(
                        f"SSR USER RESPONSE : ({LLMMessage})",
                        extra={
                            "session_key": p_sessionKey,
                            "total_input_tokens": str(ssr_state.total_input_tokens),
                            "total_output_tokens": str(ssr_state.total_output_tokens),
                            "llm_response": extract_message_content(LLMResponse),
                            "class_selection": p_Request.classSelection or "",
                            "lesson": p_Request.lesson or "",
                            "action_plan": p_Request.actionPlan or "",
                        },
                    )
                else:
                    logger.info(
                        f"USER RESPONSE :\n{LLMMessage}",
                        extra={
                            "session_key": p_sessionKey,
                            "total_input_tokens": str(ssr_state.total_input_tokens),
                            "total_output_tokens": str(ssr_state.total_output_tokens),
                            "llm_response": extract_message_content(LLMResponse),
                            "class_selection": p_Request.classSelection or "",
                            "lesson": p_Request.lesson or "",
                            "action_plan": p_Request.actionPlan or "",
                        },
                    )
                # No SSR processing needed - break out of loop
                break
            # if more content is being requested and exceeded max iterations, use what you have.
            if ssr_state.has_exceeded_max_iterations():

                LLMMessage = format_token_usage_message(
                    ssr_state.total_input_tokens,
                    ssr_state.total_output_tokens,
                    ssr_state.iteration_count,
                )
                LLMMessage += answer_text + "\n"
                LLMMessage += "**SSR exceeded loop count.  Consider narrowing down your question**"

                logger.warning(
                    "SSR Loop exceeded maximum iterations",
                    extra={
                        "session_key": p_sessionKey,
                        "max_iterations": str(SSR_MAX_ITERATIONS),
                        "iteration_count": str(ssr_state.iteration_count),
                        "reason": "iteration_count > SSR_MAX_ITERATIONS",
                        "requested_keys": requested_keys,
                        "answer_text": answer_text,
                        "total_input_tokens": str(ssr_state.total_input_tokens),
                        "total_output_tokens": str(ssr_state.total_output_tokens),
                        "llm_message": LLMMessage,
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
                    "iteration_count": str(ssr_state.iteration_count),
                    "reason": "has_ssr_request is True and within max iterations",
                    "requested_keys": requested_keys,
                    "max_iterations": str(SSR_MAX_ITERATIONS),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )

            # We are adding in a new user request acknowledging file content added and its response
            p_SessionCache.m_simpleCounterLLMConversation.add_message(
                "user", p_Request.text, None
            )
            p_SessionCache.m_simpleCounterLLMConversation.add_message(
                "assistant", extract_message_content(LLMResponse), None
            )

            content_loaded, loaded_status, failed_keys = content_loader.load_content_files(
                p_Request, p_sessionKey, requested_keys
            )
#if these keys failed to load, remove them from the memory of that event.
            if failed_keys:
                SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP = [key for key in SSR_CONTENT_REQUESTED_DURING_THIS_SSR_LOOP if key not in failed_keys]

            ssr_state.additional_content     = content_loaded
            ssr_state.loaded_content_message = loaded_status

            # End of while loop

        # Logging and adding messages to cache.  We did not
        p_SessionCache.m_simpleCounterLLMConversation.add_message(
            "user", p_Request.text, p_Request.text
        )
        p_SessionCache.m_simpleCounterLLMConversation.add_message(
            "assistant", extract_message_content(LLMResponse), LLMMessage
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
                    "user_conversation_size": str(user_conversation_size),
                    "class_selection": p_Request.classSelection or "",
                    "lesson": p_Request.lesson or "",
                    "action_plan": p_Request.actionPlan or "",
                },
            )
            p_SessionCache.m_simpleCounterLLMConversation.prune_oldest_pair()

        if ssr_state.conversation_truncated:
            LLMMessage = (
                "Old Conversations getting dropped.  Consider starting a new Conversation\n"
                + LLMMessage
            )

        return LLMMessage

    except Exception as e:
        logger.error(
            "Exception occurred while calling LLM",
            exc_info=True,
            extra={
                "session_key": p_sessionKey,
                "error": str(e),
                "class_selection": p_Request.classSelection if p_Request else "",
                "lesson": p_Request.lesson if p_Request else "",
                "action_plan": p_Request.actionPlan if p_Request else "",
            },
        )
        return f"An error ({e}) occurred processing your request. Please try again."
