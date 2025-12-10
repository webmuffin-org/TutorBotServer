from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Optional, Iterator, TypedDict
import uuid


# Type definitions for messages
class Message(TypedDict):
    id: int
    timestamp: str
    role: str  # 'user' or 'assistant'
    content: str
    conv_content: Optional[str]


class SessionData(TypedDict, total=False):
    initial: str
    # Add other session data fields as they are discovered


class MessageSummary(TypedDict):
    id: int
    timestamp: str
    role: str
    content_preview: str
    has_conv_content: bool


class ConversationSummaryDict(TypedDict):
    total_messages: int
    user_messages_count: int
    assistant_messages_count: int
    conversation_start: Optional[str]
    conversation_latest: Optional[str]
    messages: List[MessageSummary]


ConversationHistory = List[Message]
RoleContentTuple = Tuple[str, str]


class ConversationState(TypedDict):
    """State for a single conversation stored in history."""
    messages: ConversationHistory
    message_id_counter: int


class SimpleCounterLLMConversation:
    """
    Manages conversations stored in a shared conversation history dictionary.
    All conversations are stored in the history - there is no separate "current" conversation.
    """

    def __init__(self, conversation_history: Dict[str, ConversationState]) -> None:
        """
        Initialize with a reference to the shared conversation history.
        :param conversation_history: Shared dict storing all conversations by ID
        """
        self._conversation_history = conversation_history
        self._current_conversation_id: str = self._generate_conversation_id()
        # Initialize the current conversation in history
        self._conversation_history[self._current_conversation_id] = {
            "messages": [],
            "message_id_counter": 1
        }

    @staticmethod
    def _generate_conversation_id() -> str:
        """Generate a unique conversation ID."""
        return str(uuid.uuid4())

    @property
    def conversation_id(self) -> str:
        """Get the current conversation ID."""
        return self._current_conversation_id

    @property
    def conversation(self) -> ConversationHistory:
        """Get the current conversation's messages."""
        state = self._conversation_history.get(self._current_conversation_id)
        if state is None:
            return []
        return state["messages"]

    @property
    def message_id_counter(self) -> int:
        """Get the current conversation's message ID counter."""
        state = self._conversation_history.get(self._current_conversation_id)
        if state is None:
            return 1
        return state["message_id_counter"]

    def _increment_counter(self) -> int:
        """Increment and return the message ID counter."""
        state = self._conversation_history.get(self._current_conversation_id)
        if state is None:
            return 1
        counter = state["message_id_counter"]
        state["message_id_counter"] = counter + 1
        # Reset counter if it's too high
        if state["message_id_counter"] > 1e9:
            state["message_id_counter"] = 1
        return counter

    def add_message(self, role: str, content: str, conv_content: Optional[str]) -> None:
        """
        Adds a message to the conversation with a timestamp and a simple incremental ID.
        :param role: The role of the message sender ('user' or 'assistant').
        :param content: The content of the message.
        :param conv_content: if not null, then add to download for user facing conversation
        """
        state = self._conversation_history.get(self._current_conversation_id)
        if state is None:
            # Re-initialize if somehow missing
            self._conversation_history[self._current_conversation_id] = {
                "messages": [],
                "message_id_counter": 1
            }
            state = self._conversation_history[self._current_conversation_id]

        message: Message = {
            "id": self._increment_counter(),
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "conv_content": conv_content,
        }
        state["messages"].append(message)

    def clear(self) -> None:
        """
        Starts a new conversation. The old conversation remains in history.
        Generates a new conversation ID and initializes empty state.
        """
        # Generate new conversation ID (old one stays in history)
        self._current_conversation_id = self._generate_conversation_id()
        # Initialize the new conversation in history
        self._conversation_history[self._current_conversation_id] = {
            "messages": [],
            "message_id_counter": 1
        }

    def switch_to_conversation(self, conversation_id: str) -> bool:
        """
        Switch to an existing conversation by ID.
        :param conversation_id: The ID of the conversation to switch to
        :return: True if switch was successful, False if conversation doesn't exist
        """
        if conversation_id in self._conversation_history:
            self._current_conversation_id = conversation_id
            return True
        return False

    def to_string(self) -> str:
        """
        Converts the conversation to a string in a format suitable for the LLM.
        """
        return json.dumps({"messages": self.conversation})

    def to_conversation(self) -> str:
        """
        Outputs the conversation in a simplified format, focusing on 'role' and 'content'.
        """
        return json.dumps(
            [
                {"role": msg["role"], "content": msg["content"]}
                for msg in self.conversation
            ]
        )

    def get_history(self) -> ConversationHistory:
        """
        Retrieves the conversation history.
        :return: A copy of the conversation history.
        """
        return list(self.conversation)

    def __str__(self) -> str:
        """
        String representation of the conversation history.
        """
        return self.to_string()

    def __repr__(self) -> str:
        """
        Provides a detailed representation of the conversation for debugging.
        """
        conversation_preview = ", ".join(
            f"{msg['role']}: {msg['content'][:30]}..." for msg in self.conversation[:5]
        )
        return (
            f"<SimpleCounterLLMConversation (Last 5 Messages): {conversation_preview}>"
        )

    def get_all_previous_messages(self) -> List[RoleContentTuple]:
        """
        Retrieves all messages from the conversation.
        Returns:
            A list of tuples, each containing the role and content of each message in the conversation.
        """
        return [(message["role"], message["content"]) for message in self.conversation]

    def get_user_conversation_messages(self) -> List[Tuple[str, Optional[str]]]:
        """
        Retrieves all messages from the conversation where conv_content is not None.
        Returns:
            A list of tuples, each containing the role and conv_content of each message.
        """
        return [
            (message["role"], message["conv_content"])
            for message in self.conversation
            if message.get("conv_content") is not None
        ]

    def get_total_conv_content_bytes(self) -> int:
        """
        Calculates the total byte size of all conv_content fields in the conversation
        where conv_content is not None.

        Returns:
            The total number of bytes used by conv_content strings.
        """
        return sum(
            len(message["conv_content"].encode("utf-8"))
            for message in self.conversation
            if message.get("conv_content") is not None
            and message["conv_content"] is not None
        )

    def __iter__(self) -> Iterator[Message]:
        """
        Returns an iterator over a snapshot of the conversation list.
        """
        return iter(list(self.conversation))

    def get_user_questions_as_string(self) -> str:
        """
        Retrieves all user questions and concatenates them into a single string.
        Returns:
            A string containing all user questions separated by a space.
        """
        # Filter for messages where the role is 'user' and concatenate the content
        user_questions = " ".join(
            msg["content"] for msg in self.conversation if msg["role"] == "user"
        )
        return user_questions

    def get_last_assistance_response(self) -> Optional[str]:
        """
        Returns the content of the last message in the conversation where the role is 'assistant'.
        Returns None if there are no assistant messages in the conversation.
        """
        # Iterate backwards through the conversation to find the last 'assistant' message and return only its content
        for message in reversed(self.conversation):
            if message["role"] == "assistant":
                return message[
                    "content"
                ]  # Return only the content of the last assistant message
        return None  # Return None if no 'assistant' messages are found

    def prune_oldest_pair(self) -> None:
        """
        Removes the oldest pair of user and assistant messages from the conversation.
        This helps conserve space while keeping the conversation balanced.
        """
        messages = self.conversation
        user_index: Optional[int] = None
        assistant_index: Optional[int] = None

        # Find the indices of the oldest 'user' and 'assistant' messages
        for i, message in enumerate(messages):
            if message["role"] == "user" and user_index is None:
                user_index = i
            elif message["role"] == "assistant" and assistant_index is None:
                assistant_index = i
            # Stop the loop if both indices are found
            if user_index is not None and assistant_index is not None:
                break

        # Remove the oldest pair if both exist
        if user_index is not None and assistant_index is not None:
            # Remove the assistant message first if it comes before the user in the list
            if assistant_index < user_index:
                messages.pop(assistant_index)
                messages.pop(user_index - 1)  # Adjust for shifted index
            else:
                messages.pop(user_index)
                messages.pop(assistant_index - 1)  # Adjust for shifted index

    def get_serializable_conversation(self) -> List[Message]:
        """
        Returns the entire conversation in a JSON-friendly format.

        This function returns all conversation data as JSON-serializable dictionaries,
        avoiding any tuples or classes in favor of plain Python data structures.

        Returns:
            A dictionary containing the complete conversation with all fields.
        """
        return [
            {
                "id": msg["id"],
                "timestamp": msg["timestamp"],
                "role": msg["role"],
                "content": msg["content"],
                "conv_content": msg["conv_content"],
            }
            for msg in self.conversation
        ]

    def get_serializable_conversation_summary(self) -> ConversationSummaryDict:
        """
        Returns a summary of the conversation in JSON-serializable format.

        This includes metadata about the conversation and simplified message data.

        Returns:
            A dictionary with conversation summary information.
        """
        messages = self.conversation
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assistant_messages = [
            msg for msg in messages if msg["role"] == "assistant"
        ]

        return {
            "total_messages": len(messages),
            "user_messages_count": len(user_messages),
            "assistant_messages_count": len(assistant_messages),
            "conversation_start": (
                messages[0]["timestamp"] if messages else None
            ),
            "conversation_latest": (
                messages[-1]["timestamp"] if messages else None
            ),
            "messages": [
                {
                    "id": msg["id"],
                    "timestamp": msg["timestamp"],
                    "role": msg["role"],
                    "content_preview": (
                        msg["content"][:100] + "..."
                        if len(msg["content"]) > 100
                        else msg["content"]
                    ),
                    "has_conv_content": msg["conv_content"] is not None,
                }
                for msg in messages
            ],
        }


class SessionCache:
    def __init__(self, session_key: str, data: SessionData) -> None:
        self.m_session_key: str = session_key
        self.m_data: SessionData = data
        self.m_last_update: datetime = datetime.utcnow()
        # Single source of truth: all conversations stored here by conversation_id
        self.m_conversation_history: Dict[str, ConversationState] = {}
        # Conversation manager that works with the shared history
        self.m_simpleCounterLLMConversation: SimpleCounterLLMConversation = (
            SimpleCounterLLMConversation(self.m_conversation_history)
        )

    def update(self, data: SessionData) -> None:
        self.m_data.update(data)
        self.m_last_update = datetime.utcnow()

    def get_conversation_by_id(self, conversation_id: str) -> Optional[ConversationHistory]:
        """Retrieve a conversation by its ID from history."""
        state = self.m_conversation_history.get(conversation_id)
        if state is not None:
            return list(state["messages"])
        return None

    def get_all_conversation_ids(self) -> List[str]:
        """Get all conversation IDs stored in history."""
        return list(self.m_conversation_history.keys())


class SessionCacheManager:
    def __init__(self, idle_timeout: timedelta = timedelta(hours=1)) -> None:
        self.sessions: Dict[str, SessionCache] = {}
        self.idle_timeout: timedelta = idle_timeout

    def add_session(self, session_key: str, data: SessionData) -> None:
        session = SessionCache(session_key, data)
        self.sessions[session_key] = session

    def get_session(self, session_key: str) -> SessionCache:
        session = self.sessions.get(session_key)
        if session is None:
            raise KeyError(f"Session with key {session_key} not found")
        return session

    def remove_session(self, session_key: str) -> None:
        if session_key in self.sessions:
            del self.sessions[session_key]

    def cleanup_idle_sessions(self) -> None:
        now = datetime.utcnow()
        idle_sessions: List[str] = [
            key
            for key, session in self.sessions.items()
            if now - session.m_last_update > self.idle_timeout
        ]
        for session_key in idle_sessions:
            self.remove_session(session_key)


session_manager: SessionCacheManager = SessionCacheManager()


global_conversation: SimpleCounterLLMConversation = SimpleCounterLLMConversation({})
