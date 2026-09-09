from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import shutil

from .base import ProviderAuthenticationError, ProviderError, ProviderUnavailableError

logger = logging.getLogger(__name__)


@dataclass
class CodexSession:
    working_directory: Path
    agent: str | None = None
    thread_id: str | None = None
    agent_instructions_sent: bool = False


class CodexProvider:
    """Adapter for the official Codex CLI non-interactive JSONL interface."""

    name = "codex"
    display_name = "OpenAI Codex"
    supports_agents = True

    def __init__(
        self,
        executable: str = "codex",
        timeout_seconds: float = 600,
        sandbox: str = "workspace-write",
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.sandbox = sandbox

    def _resolve_executable(self) -> str | None:
        resolved = shutil.which(self.executable)
        if resolved:
            return resolved
        configured = Path(self.executable)
        if configured.is_file():
            return str(configured.resolve())
        if self.executable != "codex":
            return None
        # The Codex VS Code extension bundles the CLI but VS Code does not always
        # propagate that temporary bin directory to child/backend processes.
        extension_root = Path.home() / ".vscode" / "extensions"
        candidates = sorted(
            extension_root.glob("openai.chatgpt-*/bin/windows-x86_64/codex.exe"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return str(candidates[0]) if candidates else None

    async def create_session(self, working_directory: str, agent: str | None = None) -> CodexSession:
        executable = self._resolve_executable()
        if executable is None:
            raise ProviderUnavailableError(f"Codex CLI executable not found: {self.executable}")
        self.executable = executable
        logger.info("Resolved Codex CLI executable: %s", executable)
        working_path = Path(working_directory)
        if agent is not None:
            agent_path = working_path / ".github" / "agents" / f"{agent}.agent.md"
            if not agent_path.is_file():
                raise ProviderError(f"Agent profile not found: {agent}")
        return CodexSession(working_path, agent=agent)

    async def send(self, session: CodexSession, prompt: str, mode: str) -> str:
        effective_prompt = prompt
        if session.agent and not session.agent_instructions_sent:
            agent_path = session.working_directory / ".github" / "agents" / f"{session.agent}.agent.md"
            try:
                instructions = agent_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ProviderError(f"Could not read agent profile {session.agent}: {exc}") from exc
            effective_prompt = (
                f"Use the repository agent profile named '{session.agent}'. Follow its instructions "
                f"for this Codex thread.\n\n<agent_profile>\n{instructions}\n</agent_profile>\n\n"
                f"<user_request>\n{prompt}\n</user_request>"
            )
        if mode == "plan":
            effective_prompt = (
                "Plan mode: inspect the repository and return a concrete implementation plan. "
                "Do not modify files or execute mutating commands.\n\n" + prompt
            )
        if session.thread_id:
            args = [self.executable, "exec", "resume", "--json", session.thread_id, "-"]
        else:
            args = [
                self.executable,
                "exec",
                "--json",
                "--sandbox",
                "read-only" if mode == "plan" else self.sandbox,
                "-",
            ]
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                cwd=session.working_directory,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise ProviderUnavailableError(f"Could not start Codex CLI: {exc}") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(effective_prompt.encode("utf-8")),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise ProviderError(f"Codex timed out after {self.timeout_seconds:g} seconds.") from exc

        response = ""
        for raw_line in stdout.decode("utf-8", errors="replace").splitlines():
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                session.thread_id = event.get("thread_id") or event.get("threadId")
            item = event.get("item") or {}
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                response = item.get("text") or item.get("content") or response
            if event.get("type") in {"turn.failed", "error"}:
                message = event.get("message") or (event.get("error") or {}).get("message")
                if message:
                    raise ProviderError(str(message))
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            normalized_detail = detail.casefold()
            if "not logged in" in normalized_detail or (
                "login" in normalized_detail and "required" in normalized_detail
            ):
                raise ProviderAuthenticationError("Codex CLI is not logged in. Run `codex login`.")
            raise ProviderError(detail[-2000:] or f"Codex exited with code {process.returncode}.")
        if session.agent:
            session.agent_instructions_sent = True
        return response or "Codex completed without a final text response."

    async def close_session(self, session: CodexSession) -> None:
        # Codex exec processes end after each turn; thread_id enables later resume.
        return None

    async def close(self) -> None:
        return None
