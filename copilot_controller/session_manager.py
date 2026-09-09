from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from providers.base import AgentProvider


@dataclass
class ActiveSession:
    session: Any
    provider_name: str
    selection_type: str
    selection_value: str


class SessionManager:
    """Own one active SDK session per Slack user and project."""

    def __init__(self, providers: dict[str, AgentProvider]) -> None:
        self._providers = providers
        self._sessions: dict[tuple[str, str, str], ActiveSession] = {}
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}

    async def send(
        self,
        provider_name: str,
        user_id: str,
        project_name: str,
        project_path: Path,
        selection_type: str,
        selection_value: str,
        prompt: str,
    ) -> str:
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_name}")
        key = (provider_name, user_id, project_name)
        async with self._locks.setdefault(key, asyncio.Lock()):
            active = self._sessions.get(key)
            if active and (active.selection_type, active.selection_value) != (
                selection_type,
                selection_value,
            ):
                await provider.close_session(active.session)
                active = None
            if active is None:
                session = await provider.create_session(
                    str(project_path), selection_value if selection_type == "agent" else None
                )
                active = ActiveSession(session, provider_name, selection_type, selection_value)
                self._sessions[key] = active
            mode = selection_value if selection_type == "mode" else "ask"
            return await provider.send(active.session, prompt, mode)
