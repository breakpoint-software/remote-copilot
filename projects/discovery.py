from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    name: str
    path: Path


def discover_projects(root: Path) -> list[Project]:
    """Return immediate children of root that contain a .git entry."""
    try:
        children = root.iterdir()
        projects = [Project(p.name, p.resolve()) for p in children if p.is_dir() and (p / ".git").exists()]
    except OSError:
        return []
    return sorted(projects, key=lambda project: project.name.casefold())


def resolve_project(root: Path, name: str) -> Project | None:
    """Resolve a project by discovered name, never by a client-supplied path."""
    return next((project for project in discover_projects(root) if project.name == name), None)


def discover_agents(project_path: Path) -> list[str]:
    agents_dir = project_path / ".github" / "agents"
    try:
        agents = [p.name[: -len(".agent.md")] for p in agents_dir.glob("*.agent.md") if p.is_file()]
    except OSError:
        return []
    return sorted(agents, key=str.casefold)
