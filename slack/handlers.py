from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import logging
import threading
from typing import Any

from config import Settings
from copilot_controller.session_manager import SessionManager
from providers.base import AgentProvider, ProviderAuthenticationError, ProviderUnavailableError
from projects.discovery import discover_agents, discover_projects, resolve_project
from slack.modals import copilot_modal
from slack.responses import post_thread_response

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThreadContext:
    owner_user_id: str
    provider_name: str
    project_name: str
    selection_type: str
    selection_value: str


class AsyncRunner:
    """Keep Copilot's async client and sessions on one persistent event loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True, name="copilot-sdk").start()

    def run(self, coroutine: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result()


def register_handlers(app: Any, settings: Settings, sessions: SessionManager, providers: dict[str, AgentProvider]) -> None:
    runner = AsyncRunner()
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="copilot-request")
    thread_contexts: dict[tuple[str, str], ThreadContext] = {}
    contexts_lock = threading.Lock()

    @app.middleware
    def log_slack_inbound(body: dict, next: Any) -> Any:
        """Log Slack routing metadata without message contents or credentials."""
        event = body.get("event") or {}
        logger.warning(
            "[SLACK-INBOUND] envelope=%s event=%s subtype=%s channel=%s "
            "thread_ts=%s user=%s",
            body.get("type", "interactive_or_command"),
            event.get("type"),
            event.get("subtype"),
            event.get("channel"),
            event.get("thread_ts"),
            event.get("user"),
        )
        return next()

    def post_error(client: Any, channel_id: str, thread_ts: str, message: str) -> None:
        try:
            post_thread_response(client, channel_id, thread_ts, message)
        except Exception:
            logger.exception("Failed to post a coding-agent error to Slack")

    def execute_prompt(
        client: Any,
        channel_id: str,
        thread_ts: str,
        provider_name: str,
        user_id: str,
        project_name: str,
        selection_type: str,
        selection_value: str,
        prompt: str,
        show_heading: bool,
    ) -> None:
        project = resolve_project(settings.projects_root, project_name)
        if project is None:
            post_error(client, channel_id, thread_ts, "❌ Project not found. The selected project is no longer available.")
            return
        provider = providers.get(provider_name)
        if provider is None:
            post_error(client, channel_id, thread_ts, "❌ The selected provider is unavailable.")
            return
        if selection_type == "agent" and (not provider.supports_agents or selection_value not in discover_agents(project.path)):
            post_error(client, channel_id, thread_ts, "❌ The selected agent is no longer available.")
            return
        try:
            response = runner.run(sessions.send(
                provider_name, user_id, project.name, project.path, selection_type, selection_value, prompt
            ))
            if show_heading:
                label = "Agent" if selection_type == "agent" else "Mode"
                text = (
                    f"🤖 *{provider.display_name}*\n\n*Project:* {project.name}\n"
                    f"*{label}:* {selection_value.replace('-', ' ').title()}\n\n{response}"
                )
            else:
                text = f"🤖 *{provider.display_name}:* {response}"
        except ProviderAuthenticationError:
            logger.exception("Coding-agent provider authentication failed")
            text = f"❌ {provider.display_name} is not authenticated. Run `codex login` on the backend machine."
        except ProviderUnavailableError:
            logger.exception("Coding-agent provider unavailable")
            text = f"❌ {provider.display_name} is unavailable on this machine."
        except Exception:
            logger.exception("Provider %s failed for project %s", provider_name, project.name)
            text = f"❌ {provider.display_name} could not complete the request. Check the application logs."
        try:
            post_thread_response(
                client,
                channel_id,
                thread_ts,
                text,
                filename=f"{provider_name}-response.md",
            )
        except Exception:
            logger.exception("Failed to post Copilot response to Slack")

    @app.command("/copilot")
    def open_copilot(ack: Any, body: dict, client: Any) -> None:
        ack()
        projects = discover_projects(settings.projects_root)
        if not projects:
            client.chat_postEphemeral(
                channel=body["channel_id"], user=body["user_id"],
                text=f"❌ No Git repositories found directly under {settings.projects_root}.",
            )
            return
        try:
            parent = client.chat_postMessage(
                channel=body["channel_id"],
                text=f"🤖 Coding-agent session started by <@{body['user_id']}>. Configure it in the modal, then continue in this thread.",
            )
            client.views_open(
                trigger_id=body["trigger_id"],
                view=copilot_modal(projects, body["channel_id"], thread_ts=parent["ts"]),
            )
        except Exception:
            logger.exception("Failed to open Copilot modal")

    @app.action("project_select")
    def update_project(ack: Any, body: dict, client: Any) -> None:
        ack()
        selected_name = body["actions"][0]["selected_option"]["value"]
        projects = discover_projects(settings.projects_root)
        if not any(p.name == selected_name for p in projects):
            return
        try:
            metadata = json.loads(body["view"]["private_metadata"])
            view = copilot_modal(
                projects,
                metadata["channel_id"],
                selected_name,
                thread_ts=metadata["thread_ts"],
                provider_name=body["view"]["state"]["values"]["provider_block"]["provider_select"]["selected_option"]["value"],
            )
            client.views_update(view_id=body["view"]["id"], hash=body["view"]["hash"], view=view)
        except Exception:
            logger.exception("Failed to update Copilot modal")

    @app.action("provider_select")
    def update_provider(ack: Any, body: dict, client: Any) -> None:
        ack()
        provider_name = body["actions"][0]["selected_option"]["value"]
        if provider_name not in providers:
            return
        metadata = json.loads(body["view"]["private_metadata"])
        project_name = body["view"]["state"]["values"]["project_block"]["project_select"]["selected_option"]["value"]
        projects = discover_projects(settings.projects_root)
        try:
            client.views_update(
                view_id=body["view"]["id"],
                hash=body["view"]["hash"],
                view=copilot_modal(projects, metadata["channel_id"], project_name, metadata["thread_ts"], provider_name),
            )
        except Exception:
            logger.exception("Failed to update provider in coding-agent modal")

    @app.view("copilot_submit")
    def submit_copilot(ack: Any, body: dict, client: Any, view: dict) -> None:
        values = view["state"]["values"]
        provider_name = values["provider_block"]["provider_select"]["selected_option"]["value"]
        project_name = values["project_block"]["project_select"]["selected_option"]["value"]
        raw_selection = values["selection_block"]["selection_select"]["selected_option"]["value"]
        prompt = values["prompt_block"]["prompt_input"].get("value", "").strip()
        project = resolve_project(settings.projects_root, project_name)
        errors: dict[str, str] = {}
        if not prompt:
            errors["prompt_block"] = "Enter a prompt."
        if project is None:
            errors["project_block"] = "The selected project is no longer available."
        try:
            selection_type, selection_value = raw_selection.split(":", 1)
        except ValueError:
            selection_type, selection_value = "", ""
        provider = providers.get(provider_name)
        if provider is None:
            errors["provider_block"] = "Select a valid provider."
        if selection_type not in {"mode", "agent"} or (
            selection_type == "mode" and selection_value not in {"ask", "plan"}
        ):
            errors["selection_block"] = "Select a valid mode or agent."
        elif project and selection_type == "agent" and (
            provider is None or not provider.supports_agents or selection_value not in discover_agents(project.path)
        ):
            errors["selection_block"] = "The selected agent is no longer available."
        if errors:
            ack(response_action="errors", errors=errors)
            return
        ack()
        metadata = json.loads(view["private_metadata"])
        channel_id = metadata["channel_id"]
        thread_ts = metadata["thread_ts"]
        user_id = body["user"]["id"]
        assert project is not None
        with contexts_lock:
            thread_contexts[(channel_id, thread_ts)] = ThreadContext(
                user_id, provider_name, project.name, selection_type, selection_value
            )
        logger.info(
            "Registered coding-agent Slack thread: channel=%s thread_ts=%s provider=%s owner=%s project=%s",
            channel_id,
            thread_ts,
            provider_name,
            user_id,
            project.name,
        )
        executor.submit(
            execute_prompt,
            client,
            channel_id,
            thread_ts,
            provider_name,
            user_id,
            project.name,
            selection_type,
            selection_value,
            prompt,
            True,
        )

    @app.event("message")
    def continue_copilot_thread(event: dict, client: Any) -> None:
        logger.warning(
            "[COPILOT-THREAD] message received channel=%s thread_ts=%s user=%s subtype=%s bot=%s",
            event.get("channel"),
            event.get("thread_ts"),
            event.get("user"),
            event.get("subtype"),
            bool(event.get("bot_id")),
        )
        # Ignore bot messages, edits/deletions, and top-level messages. Slack uses
        # thread_broadcast when the author also sends the reply to the channel.
        if (
            event.get("bot_id")
            or event.get("subtype") not in (None, "thread_broadcast")
            or not event.get("thread_ts")
        ):
            return
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        user_id = event.get("user")
        prompt = event.get("text", "").strip()
        if not channel_id or not thread_ts or not user_id or not prompt:
            return
        with contexts_lock:
            context = thread_contexts.get((channel_id, thread_ts))
        if context is None:
            logger.warning(
                "[COPILOT-THREAD] ignored unknown thread channel=%s thread_ts=%s active_threads=%d",
                channel_id,
                thread_ts,
                len(thread_contexts),
            )
            return
        if user_id != context.owner_user_id:
            post_error(client, channel_id, thread_ts, "Only the user who started this Copilot session can send prompts to it.")
            return
        logger.warning(
            "[COPILOT-THREAD] routing reply channel=%s thread_ts=%s project=%s",
            channel_id,
            thread_ts,
            context.project_name,
        )
        executor.submit(
            execute_prompt,
            client,
            channel_id,
            thread_ts,
            context.provider_name,
            user_id,
            context.project_name,
            context.selection_type,
            context.selection_value,
            prompt,
            False,
        )
