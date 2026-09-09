from __future__ import annotations

from typing import Any


class CopilotUnavailableError(RuntimeError):
    pass


def load_sdk() -> tuple[type[Any], type[Any], type[Any]]:
    try:
        from copilot import CopilotClient, PermissionHandler
        from copilot.session_events import AssistantMessageData
    except ImportError as exc:
        raise CopilotUnavailableError("GitHub Copilot SDK is not installed.") from exc
    return CopilotClient, AssistantMessageData, PermissionHandler


class CopilotService:
    """Thin adapter around github-copilot-sdk's current async API."""

    def __init__(self, timeout_seconds: float = 600) -> None:
        self.timeout_seconds = timeout_seconds
        self._client: Any | None = None

    async def create_session(self, working_directory: str, agent: str | None = None) -> Any:
        client_type, _, permission_handler = load_sdk()
        if self._client is None:
            self._client = client_type()
            await self._client.start()
        return await self._client.create_session(
            working_directory=working_directory,
            agent=agent,
            streaming=False,
            on_permission_request=permission_handler.approve_all,
        )

    async def send(self, session: Any, prompt: str, mode: str) -> str:
        _, message_type, _ = load_sdk()
        event = await session.send_and_wait(
            prompt,
            agent_mode="plan" if mode == "plan" else "interactive",
            timeout=self.timeout_seconds,
        )
        if event is None or not isinstance(event.data, message_type):
            return "Copilot completed without a text response."
        return event.data.content

    async def close(self) -> None:
        if self._client is not None:
            await self._client.stop()
            self._client = None
