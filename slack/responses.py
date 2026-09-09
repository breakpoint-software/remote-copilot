from __future__ import annotations

from typing import Any


SLACK_MESSAGE_LIMIT = 3_000


def post_thread_response(
    client: Any,
    channel_id: str,
    thread_ts: str,
    text: str,
    *,
    filename: str = "coding-agent-response.md",
) -> None:
    """Post short text directly and attach long text as a UTF-8 Slack file."""
    if len(text) <= SLACK_MESSAGE_LIMIT:
        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)
        return

    client.files_upload_v2(
        channel=channel_id,
        thread_ts=thread_ts,
        filename=filename,
        title="Coding agent response",
        content=text.encode("utf-8"),
        initial_comment="🤖 The response exceeded 3,000 characters and is attached as a file.",
    )
