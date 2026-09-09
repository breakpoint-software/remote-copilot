from pathlib import Path

from projects.discovery import Project
from slack.modals import copilot_modal, selection_option_groups


def test_agent_options_are_namespaced_and_paths_are_not_exposed(tmp_path: Path) -> None:
    project_path = tmp_path / "Repo"
    agents = project_path / ".github" / "agents"
    agents.mkdir(parents=True)
    (agents / "testing.agent.md").write_text("", encoding="utf-8")
    project = Project("Repo", project_path)

    groups = selection_option_groups(project)
    assert groups[0]["options"][0]["value"] == "mode:ask"
    assert groups[1]["options"][0]["value"] == "agent:testing"

    modal = copilot_modal([project], "C123", thread_ts="123.456")
    assert str(project_path) not in str(modal)
    assert "123.456" in modal["private_metadata"]

    codex_modal = copilot_modal([project], "C123", provider_name="codex")
    selection = codex_modal["blocks"][2]["element"]["option_groups"]
    assert selection[1]["label"]["text"] == "Agents / Agent mode"
    assert selection[1]["options"][0]["value"] == "agent:testing"
