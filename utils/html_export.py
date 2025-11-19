from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import html
import re

# Markdown will be rendered client-side with JavaScript

from SessionCache import SessionCache
from constants import system_encoding


class TimestampUtils:
    """Shared timestamp utilities for HTML export"""

    @staticmethod
    def format_timestamp(dt: Optional[datetime] = None) -> str:
        """Generate a formatted timestamp for display"""
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%I:%M %p")

    @staticmethod
    def format_full_datetime(dt: Optional[datetime] = None) -> str:
        """Generate a full datetime string for HTML export"""
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%b %d, %Y %I:%M %p")

    @staticmethod
    def format_iso(dt: Optional[datetime] = None) -> str:
        """Generate ISO string for data attributes"""
        if dt is None:
            dt = datetime.now()
        return dt.isoformat()

    @staticmethod
    def create_export_timestamp(
        dt: Optional[datetime] = None, message_type: str = "bot"
    ) -> str:
        """Create a timestamp element for HTML export"""
        if dt is None:
            dt = datetime.now()

        timestamp = TimestampUtils.format_timestamp(dt)
        full_datetime = TimestampUtils.format_full_datetime(dt)

        return f"""<div class="message-timestamp {message_type}-timestamp" 
                        title="{html.escape(full_datetime)}">
                    {html.escape(timestamp)}
                </div>"""


class HTMLTemplateRenderer:
    """Handles HTML template rendering for conversation exports."""

    def __init__(self):
        """Initialize the template renderer and load templates."""
        self._html_template: Optional[str] = None
        self._css_content: Optional[str] = None

    def _load_templates(self) -> None:
        """Load HTML template and CSS content from files."""
        if self._html_template is None:
            with open("static/export.html", "r", encoding="utf-8") as f:
                self._html_template = f.read()

        # Always reload CSS to pick up changes (remove caching for CSS)
        with open("static/conversation.css", "r", encoding="utf-8") as f:
            conversation_css = f.read()
        with open("static/export.css", "r", encoding="utf-8") as f:
            export_css = f.read()
        self._css_content = conversation_css + "\n\n" + export_css

    def render_template(
        self,
        conversation_html: str,
        class_name: str,
        lesson: str,
        action_plan: str,
        timestamp: str,
    ) -> str:
        """Render the complete HTML template with conversation content."""
        # Load templates if not already loaded
        self._load_templates()

        # Replace placeholders in the template
        if not self._html_template or not self._css_content:
            raise ValueError("Failed to load template files")

        html_content = self._html_template.replace("{{css_content}}", self._css_content)
        html_content = html_content.replace("{{conversation_html}}", conversation_html)
        html_content = html_content.replace("{{class_name}}", html.escape(class_name))
        html_content = html_content.replace("{{lesson}}", html.escape(lesson))
        html_content = html_content.replace("{{action_plan}}", html.escape(action_plan))
        html_content = html_content.replace("{{timestamp}}", html.escape(timestamp))

        return html_content


class ConversationFormatter:
    """Formats conversation messages for HTML export with markdown rendering."""

    @staticmethod
    def parse_bot_response(content: str) -> Tuple[Optional[str], str]:
        """Parse bot response to extract token usage and actual answer."""
        # Pattern to match token usage line, potentially followed by SSR status messages
        token_pattern = r"^Total Input Tokens \((\d+)\), Total Output Tokens \((\d+)\) over \((\d+)\) passes?\s*\n"
        match = re.match(token_pattern, content)

        if match:
            input_tokens = match.group(1)
            output_tokens = match.group(2)
            iterations = match.group(3)
            token_info = f"Input: {input_tokens} | Output: {output_tokens} | Iterations: {iterations}"

            # Get the remaining content after token info
            remaining_content = content[match.end() :]

            # Check for SSR status messages and skip them
            ssr_messages = [
                "SSR exceeded loop count.  Answer may not have considered all information\n",
                "Old Conversations getting dropped.  Consider starting a new Conversation\n",
            ]

            answer = remaining_content
            for ssr_msg in ssr_messages:
                if answer.startswith(ssr_msg):
                    answer = answer[len(ssr_msg) :]

        else:
            token_info = None
            answer = content

        # Remove any leading/trailing whitespace
        answer = answer.strip()

        # Clean up indentation in the HTML export only (not affecting the live web interface)
        # Handle case where first line has no indentation but subsequent lines do
        lines = answer.split("\n")
        if len(lines) > 1:
            # Find the most common indentation among non-empty lines (excluding the first line)
            indentations = []
            for line in lines[1:]:  # Skip first line
                if line.strip():  # Only non-empty lines
                    indent = len(line) - len(line.lstrip())
                    if indent > 0:
                        indentations.append(indent)

            # If we found indented lines, remove the most common indentation
            if indentations:
                from collections import Counter

                most_common_indent = Counter(indentations).most_common(1)[0][0]

                # Only remove if it's substantial (4+ spaces)
                if most_common_indent >= 4:
                    cleaned_lines = [lines[0]]  # Keep first line as-is
                    for line in lines[1:]:
                        if (
                            line.strip()
                            and len(line) >= most_common_indent
                            and line[:most_common_indent].isspace()
                        ):
                            cleaned_lines.append(line[most_common_indent:])
                        elif line.strip():
                            cleaned_lines.append(line.lstrip())
                        else:
                            cleaned_lines.append("")
                    answer = "\n".join(cleaned_lines)

        return token_info, answer

    @staticmethod
    def format_message(
        role: str,
        content: str,
        message_id: int,
        message_time: Optional[datetime] = None,
    ) -> str:
        """Format a single message based on role."""
        if message_time is None:
            message_time = datetime.now()

        if role == "user":
            escaped_content = html.escape(content)
            timestamp = TimestampUtils.create_export_timestamp(message_time, "user")
            return f"""
            <div class="message user">
                <div class="message-content">
                    <div class="message-header">You</div>
                    <p class="message-text">{escaped_content}</p>
                    {timestamp}
                </div>
            </div>"""
        elif role == "assistant":
            token_info, answer = ConversationFormatter.parse_bot_response(content)

            # Keep the raw markdown for client-side rendering and copying
            raw_markdown = answer

            # Escape for HTML display in the hidden textarea
            escaped_raw = html.escape(raw_markdown)

            # Escape for safe insertion into data attribute
            escaped_for_data = html.escape(raw_markdown).replace('"', "&quot;")

            # Build the message HTML
            token_html = ""
            if token_info:
                token_html = f'<div class="token-info">{html.escape(token_info)}</div>'

            timestamp = TimestampUtils.create_export_timestamp(message_time, "bot")

            return f"""
            <div class="message bot">
                <div class="message-content">
                    <div class="message-header">
                        TutorBot
                        <button class="copy-button" onclick="copyRawMarkdown('raw-{message_id}')" title="Copy raw markdown">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M4 2a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H4zm0 1h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>
                                <path d="M2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1H2z"/>
                            </svg>
                            Copy MD
                        </button>
                    </div>
                    {token_html}
                    <div class="message-text rendered-markdown" data-markdown="{escaped_for_data}">
                        <!-- Markdown will be rendered here by JavaScript -->
                    </div>
                    <textarea id="raw-{message_id}" class="raw-markdown-content" readonly style="display: none;">{escaped_raw}</textarea>
                    {timestamp}
                </div>
            </div>"""

        return ""

    @staticmethod
    def format_conversation(conversation: List[Tuple[str, str]]) -> str:
        """Format entire conversation for HTML export."""
        formatted_messages = []
        message_id = 0
        base_time = datetime.now()

        for i, (role, content) in enumerate(conversation):
            if role in ["user", "assistant"]:
                # Simulate message times with 1 minute intervals
                minutes_offset = (len(conversation) - i) * 1
                message_time = base_time - timedelta(minutes=minutes_offset)

                formatted_messages.append(
                    ConversationFormatter.format_message(
                        role, content, message_id, message_time
                    )
                )
                message_id += 1

        return "\n".join(formatted_messages)


class HTMLConversationExporter:
    """Main class for exporting conversations to HTML format."""

    def __init__(self):
        self.template_renderer = HTMLTemplateRenderer()
        self.formatter = ConversationFormatter()

    async def generate_conversation_html(
        self,
        session_key: Optional[str],
        class_name: Optional[str],
        lesson: Optional[str],
        action_plan: Optional[str],
        session_cache: SessionCache,
    ) -> bytes:
        """Generate HTML file content for a conversation."""
        if session_key is None:
            raise ValueError("Session Key not found")

        if session_cache is None:
            raise ValueError("Could not locate Session Key")

        # Get conversation messages
        conversation = (
            session_cache.m_simpleCounterLLMConversation.get_user_conversation_messages()
        )

        # Format conversation
        formatted_conversation = self.formatter.format_conversation(conversation)

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Render complete HTML
        html_content = self.template_renderer.render_template(
            conversation_html=formatted_conversation,
            class_name=class_name or "Unknown",
            lesson=lesson or "Unknown",
            action_plan=action_plan or "Unknown",
            timestamp=timestamp,
        )

        # Convert to bytes with proper encoding
        encoding = system_encoding or "utf-8"
        return html_content.encode(encoding)

    def get_filename(self) -> str:
        """Generate filename for the HTML export."""
        date_string = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{date_string}_TutorBot_Conversation.html"
