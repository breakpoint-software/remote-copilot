import asyncio
from pathlib import Path

from copilot_controller.session_manager import SessionManager


class FakeSession:
    def __init__(self) -> None:
        self.disconnected = False

    async def disconnect(self) -> None:
        self.disconnected = True


class FakeService:
    name = "fake"
    display_name = "Fake"
    supports_agents = True

    def __init__(self) -> None:
        self.created: list[tuple[str, str | None, FakeSession]] = []

    async def create_session(self, path: str, agent: str | None = None) -> FakeSession:
        session = FakeSession()
        self.created.append((path, agent, session))
        return session

    async def send(self, session: FakeSession, prompt: str, mode: str) -> str:
        return f"{prompt}:{mode}"

    async def close_session(self, session: FakeSession) -> None:
        await session.disconnect()

    async def close(self) -> None:
        return None


def test_reuses_session_and_replaces_it_when_selection_changes(tmp_path: Path) -> None:
    async def scenario() -> None:
        service = FakeService()
        manager = SessionManager({"fake": service})  # type: ignore[dict-item]
        result = await manager.send("fake", "U1", "Repo", tmp_path, "mode", "ask", "hello")
        await manager.send("fake", "U1", "Repo", tmp_path, "mode", "ask", "again")
        first = service.created[0][2]
        await manager.send("fake", "U1", "Repo", tmp_path, "agent", "backend", "build")

        assert result == "hello:ask"
        assert len(service.created) == 2
        assert first.disconnected
        assert service.created[1][1] == "backend"

    asyncio.run(scenario())
