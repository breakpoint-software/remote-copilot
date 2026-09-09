from pathlib import Path

from projects.discovery import discover_agents, discover_projects, resolve_project


def test_discovers_only_immediate_git_repositories(tmp_path: Path) -> None:
    repo = tmp_path / "MyRepo"
    (repo / ".git").mkdir(parents=True)
    (tmp_path / "ordinary").mkdir()
    nested = tmp_path / "group" / "nested"
    (nested / ".git").mkdir(parents=True)

    assert [p.name for p in discover_projects(tmp_path)] == ["MyRepo"]
    assert resolve_project(tmp_path, "MyRepo") is not None
    assert resolve_project(tmp_path, "../MyRepo") is None


def test_discovers_agent_names(tmp_path: Path) -> None:
    agents = tmp_path / ".github" / "agents"
    agents.mkdir(parents=True)
    (agents / "backend.agent.md").write_text("agent", encoding="utf-8")
    (agents / "ignore.md").write_text("no", encoding="utf-8")

    assert discover_agents(tmp_path) == ["backend"]
