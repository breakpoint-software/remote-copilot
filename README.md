# Slack → Local GitHub Copilot Controller

A minimal Slack Bolt app that discovers Git repositories directly beneath a local root and sends prompts to either the official GitHub Copilot SDK or the official OpenAI Codex CLI.

The provider-neutral session manager keeps Slack independent of the coding-agent implementation. Both providers discover repository `.github/agents/*.agent.md` profiles. Copilot selects them through its SDK; Codex injects the selected profile into the first turn of its native CLI thread. Codex also supports Ask and read-only Plan modes and resumes its native thread ID for follow-up messages.

## Setup

1. Use Python 3.11 or newer and run `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`. The application loads it automatically.
3. In your Slack app, add the `commands`, `chat:write`, `files:write`, and `chat:write.public` bot scopes as appropriate for the target channels. `files:write` is required because responses longer than 3,000 characters are uploaded as files in the Slack thread.
4. Recommended for local use: enable Socket Mode, create an app-level `xapp-` token with `connections:write`, and set `SLACK_APP_TOKEN`. Enable Interactivity; request URLs are not needed in Socket Mode.
5. HTTP alternative: omit `SLACK_APP_TOKEN`, create `/copilot` with request URL `https://<public-host>/slack/events`, enable Interactivity with the same URL, and expose port 3000 through an HTTPS tunnel.
6. Authenticate the local Copilot CLI/SDK before starting the service.

For Codex, authenticate the installed CLI separately with `codex login`. The application does not read or store OpenAI credentials; the Codex CLI owns authentication and its local session data.

Run with `python app.py`. In Slack, enter `/copilot`, select a project and mode/agent, enter a prompt, and submit.

Each `/copilot` invocation creates a parent Slack message. The initial prompt and all Copilot responses are posted in its thread. Later human replies in that thread are sent to the same user/project Copilot session. Only the user who started the session can continue it.

To receive thread replies, subscribe the Slack app to the appropriate bot events for where it will run: `message.channels` for public channels, `message.groups` for private channels, `message.im` for direct messages, and/or `message.mpim` for group direct messages. Add the corresponding history scopes (`channels:history`, `groups:history`, `im:history`, or `mpim:history`) and reinstall the app after scope changes.

Confirm the local server with `curl http://127.0.0.1:3000/health`. Slack cannot call a localhost URL: expose port 3000 through an HTTPS tunnel and use the resulting public URL plus `/slack/events` for both the slash command and Interactivity request URLs.

## MVP limitations

Sessions are in memory and disappear on restart. Only immediate child directories of `PROJECTS_ROOT` are discovered. Responses are posted only after completion and may be split/truncated by Slack limits in a future iteration. There is no interactive permission bridge: this MVP uses the SDK's `PermissionHandler.approve_all`, so Slack app access must be restricted to trusted users. One process is assumed.
