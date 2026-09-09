from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

from config import Settings
from copilot_controller.session_manager import SessionManager
from providers import CodexProvider, CopilotProvider
from slack.handlers import register_handlers

load_dotenv()
log_path = Path(__file__).resolve().with_name("remote-copilot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_path, encoding="utf-8"),
    ],
    force=True,
)
settings = Settings.from_env()
logger = logging.getLogger(__name__)
logger.warning(
    "[REMOTE-COPILOT] application loaded; socket_mode=%s log_file=%s",
    bool(settings.slack_app_token),
    log_path,
)
bolt_app = App(token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret)
providers = {
    "copilot": CopilotProvider(settings.copilot_timeout_seconds),
    "codex": CodexProvider(
        settings.codex_executable,
        settings.copilot_timeout_seconds,
        settings.codex_sandbox,
    ),
}
register_handlers(bolt_app, settings, SessionManager(providers), providers)

web_app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)


@web_app.post("/slack/events")
def slack_events():
    return handler.handle(request)


@web_app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    if settings.slack_app_token:
        from slack_bolt.adapter.socket_mode import SocketModeHandler

        logger.warning("[REMOTE-COPILOT] starting Slack app in Socket Mode")
        SocketModeHandler(bolt_app, settings.slack_app_token).start()
    else:
        logger.warning("[REMOTE-COPILOT] starting Slack app in HTTP mode on port %s", settings.port)
        web_app.run(host="0.0.0.0", port=settings.port)
