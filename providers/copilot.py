from __future__ import annotations

from typing import Any

from copilot_controller.client import CopilotService, CopilotUnavailableError

from .base import ProviderUnavailableError


class CopilotProvider:
    name = "copilot"
    display_name = "GitHub Copilot"
    supports_agents = True

    def __init__(self, timeout_seconds: float = 600) -> None:
        self._service = CopilotService(timeout_seconds)

    async def create_session(self, working_directory: str, agent: str | None = None) -> Any:
        try:
            return await self._service.create_session(working_directory, agent)
        except CopilotUnavailableError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    async def send(self, session: Any, prompt: str, mode: str) -> str:
        return await self._service.send(session, prompt, mode)

    async def close_session(self, session: Any) -> None:
        await session.disconnect()

    async def close(self) -> None:
        await self._service.close()
