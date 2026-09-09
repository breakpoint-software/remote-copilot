import asyncio
from pathlib import Path

from providers.codex import CodexProvider


def test_resolves_an_explicit_codex_executable(tmp_path: Path) -> None:
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"")
    provider = CodexProvider(str(executable))

    assert provider._resolve_executable() == str(executable.resolve())


def test_creates_session_after_resolving_executable(tmp_path: Path) -> None:
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"")
    provider = CodexProvider(str(executable))

    session = asyncio.run(provider.create_session(str(tmp_path)))

    assert session.working_directory == tmp_path
    assert provider.executable == str(executable.resolve())


def test_creates_codex_session_with_discovered_agent(tmp_path: Path) -> None:
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"")
    agents = tmp_path / ".github" / "agents"
    agents.mkdir(parents=True)
    (agents / "backend.agent.md").write_text("Work on backend code.", encoding="utf-8")
    provider = CodexProvider(str(executable))

    session = asyncio.run(provider.create_session(str(tmp_path), "backend"))

    assert session.agent == "backend"
