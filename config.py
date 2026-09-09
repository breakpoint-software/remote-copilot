from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_signing_secret: str
    slack_app_token: str | None
    projects_root: Path
    copilot_timeout_seconds: float
    codex_executable: str
    codex_sandbox: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("SLACK_BOT_TOKEN", "")
        secret = os.getenv("SLACK_SIGNING_SECRET", "")
        if not token or not secret:
            raise RuntimeError("SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET are required")
        return cls(
            slack_bot_token=token,
            slack_signing_secret=secret,
            slack_app_token=os.getenv("SLACK_APP_TOKEN") or None,
            projects_root=Path(os.getenv("PROJECTS_ROOT", "C:\\")),
            copilot_timeout_seconds=float(os.getenv("COPILOT_TIMEOUT_SECONDS", "600")),
            codex_executable=os.getenv("CODEX_EXECUTABLE", "codex"),
            codex_sandbox=os.getenv("CODEX_SANDBOX", "workspace-write"),
            port=int(os.getenv("PORT", "3000")),
        )
