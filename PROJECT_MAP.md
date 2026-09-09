# Project Map

## Overview

`remote-copilot` is a Python Flask/Slack Bolt application that lets Slack users run prompts against local coding agents (GitHub Copilot SDK or OpenAI Codex CLI) against Git repositories discovered on the local filesystem. It is a single-process MVP: Slack is the only UI, sessions are in-memory, and providers are abstracted behind a common interface so Slack code never depends on a specific agent implementation.

## Applications

### Main App
Path: `app.py`

Entry point: `app.py` (`python app.py`)

Purpose: Wires everything together — loads `.env`/`Settings`, configures logging (`remote-copilot.log`), constructs the Slack Bolt `App`, instantiates providers (`CopilotProvider`, `CodexProvider`) and the `SessionManager`, registers Slack handlers, and starts either Socket Mode (if `SLACK_APP_TOKEN` set) or an HTTP Flask server exposing `/slack/events` and `/health`.

### Configuration
Path: `config.py`

Purpose: `Settings` dataclass loaded from environment variables (`Settings.from_env()`): Slack tokens/secrets, `PROJECTS_ROOT`, Copilot/Codex timeouts, Codex executable/sandbox mode, HTTP port.

## Backend / Domain Logic

### Session Management
Path: `copilot_controller/`

Key files: `session_manager.py`, `client.py`

Purpose: `SessionManager` owns one active agent session per (provider, Slack user, project) key, using per-key `asyncio.Lock`s to serialize sends. Delegates actual agent calls to the selected `AgentProvider`. `client.py` likely wraps lower-level SDK/CLI client concerns (check when touching Copilot SDK integration).

### Providers (agent abstraction)
Path: `providers/`

Key files: `base.py`, `copilot.py`, `codex.py`

Purpose: Provider-neutral interface (`AgentProvider` Protocol in `base.py`: `create_session`, `send`, `close_session`, `close`) plus error types (`ProviderError`, `ProviderUnavailableError`, `ProviderAuthenticationError`). `copilot.py` implements `CopilotProvider` using the official GitHub Copilot SDK. `codex.py` implements `CodexProvider`, driving the OpenAI Codex CLI as a subprocess, supporting Ask/Plan modes and resuming native Codex thread IDs. Both read `.github/agents/*.agent.md` profiles from target repos for agent selection.

### Project Discovery
Path: `projects/discovery.py`

Purpose: Discovers Git repositories as immediate children of `PROJECTS_ROOT` (`discover_projects`), resolves a project by name only from that discovered list (`resolve_project`, never trusts client-supplied paths), and discovers available agent profiles under `<project>/.github/agents/` (`discover_agents`).

## Frontend / Interface

### Slack Integration
Path: `slack/`

Key files: `handlers.py`, `modals.py`, `commands.py`, `responses.py`

Purpose:
- `handlers.py`: Registers Bolt event/command/view handlers; `ThreadContext` tracks per-thread owner/provider/project/selection state; `AsyncRunner` bridges Slack's sync handlers to the async provider/session-manager code on a dedicated background event loop.
- `commands.py`: Slash command definitions (e.g. `/copilot`).
- `modals.py`: Builds the `/copilot` modal (project, mode/agent, prompt selection) — `copilot_modal`.
- `responses.py`: Posts agent output back into the Slack thread (`post_thread_response`); handles Slack's message-length limits (long responses uploaded as files).

## Authentication / Authorization

- Slack: Bot/signing-secret/app tokens configured via `.env` and `Settings` (`SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`). Only the Slack user who started a thread's session can continue it (enforced in `slack/handlers.py` via `ThreadContext.owner_user_id`).
- Copilot SDK: uses `PermissionHandler.approve_all` (no interactive permission bridge) — access control is therefore entirely at the Slack app-install level.
- Codex CLI: authenticated out-of-band via `codex login`; this app never reads/stores OpenAI credentials.

## External Integrations

| Integration | Location | Purpose |
|---|---|---|
| Slack Bolt (Socket Mode / HTTP) | `app.py`, `slack/` | Primary UI: slash commands, modals, threaded messages |
| GitHub Copilot SDK | `providers/copilot.py` | Executes prompts via official Copilot SDK session |
| OpenAI Codex CLI | `providers/codex.py` | Executes prompts via local `codex` executable/subprocess |
| Local filesystem (`PROJECTS_ROOT`) | `projects/discovery.py` | Source of discoverable Git repositories/projects |

## Tests

Path: `tests/`

Files: `test_codex_provider.py`, `test_discovery.py`, `test_modals.py`, `test_session_manager.py`, `test_slack_responses.py`

Coverage mirrors the main modules: Codex provider behavior, project discovery, Slack modal construction, session manager concurrency/locking, and Slack response formatting/posting.

## Configuration & Deployment

- `.env` / `.env.example`: runtime configuration (Slack tokens, `PROJECTS_ROOT`, timeouts, port). Loaded automatically via `python-dotenv` in `app.py`.
- `requirements.txt`: Python dependencies (Flask, slack_bolt, dotenv, Copilot SDK, etc.).
- No containerization/CI/CD or infra-as-code present; deployment is manual (`python app.py`), run locally or behind an HTTPS tunnel for Slack's HTTP mode.
- Logging: configured in `app.py`, writes to `remote-copilot.log` at repo root plus stdout.

## Important Relationships

```text
Slack (slash command / modal / thread reply)
 ↓
slack/handlers.py  (ThreadContext, AsyncRunner)
 ↓
copilot_controller/session_manager.py  (per user+project+provider session, locking)
 ↓
providers/base.py (AgentProvider interface)
 ↓         ↓
providers/copilot.py   providers/codex.py
 ↓                          ↓
GitHub Copilot SDK      Codex CLI subprocess

projects/discovery.py → supplies project list & .github/agents/*.agent.md profiles
                          to slack/modals.py (selection UI) and providers (agent injection)

config.py Settings → consumed by app.py to construct Slack app, providers, and Flask server
```
