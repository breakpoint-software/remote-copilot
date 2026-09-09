from __future__ import annotations

import json

from projects.discovery import Project, discover_agents


def selection_option_groups(project: Project, supports_agents: bool = True) -> list[dict]:
    groups = [
        {
            "label": {"type": "plain_text", "text": "Modes"},
            "options": [
                {"text": {"type": "plain_text", "text": "Ask"}, "value": "mode:ask"},
                {"text": {"type": "plain_text", "text": "Plan"}, "value": "mode:plan"},
            ],
        }
    ]
    agents = discover_agents(project.path) if supports_agents else []
    if agents:
        groups.append(
            {
                "label": {"type": "plain_text", "text": "Agents / Agent mode"},
                "options": [
                    {"text": {"type": "plain_text", "text": name.replace("-", " ").title()}, "value": f"agent:{name}"}
                    for name in agents
                ],
            }
        )
    return groups


def copilot_modal(
    projects: list[Project],
    channel_id: str,
    selected_name: str | None = None,
    thread_ts: str = "",
    provider_name: str = "copilot",
) -> dict:
    selected = next((p for p in projects if p.name == selected_name), projects[0])
    project_options = [
        {"text": {"type": "plain_text", "text": p.name}, "value": p.name} for p in projects
    ]
    return {
        "type": "modal",
        "callback_id": "copilot_submit",
        "private_metadata": json.dumps({"channel_id": channel_id, "thread_ts": thread_ts}),
        "title": {"type": "plain_text", "text": "🤖 Coding Agent"},
        "submit": {"type": "plain_text", "text": "Send"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "provider_block",
                "label": {"type": "plain_text", "text": "Provider"},
                "dispatch_action": True,
                "element": {
                    "type": "static_select",
                    "action_id": "provider_select",
                    "options": [
                        {"text": {"type": "plain_text", "text": "GitHub Copilot"}, "value": "copilot"},
                        {"text": {"type": "plain_text", "text": "OpenAI Codex"}, "value": "codex"},
                    ],
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "OpenAI Codex" if provider_name == "codex" else "GitHub Copilot"},
                        "value": provider_name,
                    },
                },
            },
            {
                "type": "input",
                "block_id": "project_block",
                "label": {"type": "plain_text", "text": "Project"},
                "dispatch_action": True,
                "element": {
                    "type": "static_select",
                    "action_id": "project_select",
                    "options": project_options,
                    "initial_option": next(o for o in project_options if o["value"] == selected.name),
                },
            },
            {
                "type": "input",
                "block_id": "selection_block",
                "label": {"type": "plain_text", "text": "Mode / Agent"},
                "element": {
                    "type": "static_select",
                    "action_id": "selection_select",
                    "option_groups": selection_option_groups(selected, provider_name in {"copilot", "codex"}),
                    "initial_option": {"text": {"type": "plain_text", "text": "Ask"}, "value": "mode:ask"},
                },
            },
            {
                "type": "input",
                "block_id": "prompt_block",
                "label": {"type": "plain_text", "text": "Prompt"},
                "element": {"type": "plain_text_input", "action_id": "prompt_input", "multiline": True},
            },
        ],
    }
