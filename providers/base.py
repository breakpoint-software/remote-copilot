from __future__ import annotations

from typing import Any, Protocol


class ProviderError(RuntimeError):
    """A coding-agent provider failed to execute a request."""


class ProviderUnavailableError(ProviderError):
    """A provider executable or SDK is unavailable."""


class ProviderAuthenticationError(ProviderError):
    """A provider is installed but is not authenticated."""


class AgentProvider(Protocol):
    name: str
    display_name: str
    supports_agents: bool

    async def create_session(self, working_directory: str, agent: str | None = None) -> Any: ...

    async def send(self, session: Any, prompt: str, mode: str) -> str: ...

    async def close_session(self, session: Any) -> None: ...

    async def close(self) -> None: ...
