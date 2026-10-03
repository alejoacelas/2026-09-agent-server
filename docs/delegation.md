# Delegation plan

Goal: any task Alejandro is working on can be handed to the server and run to
completion without checking back with him. Agents make reversible choices on
their own, log them, and only surface what is truly blocked.

Two systems do this:

1. **Hands-on:** work Alejandro is actively doing, run on the server.
2. **Background:** things already running there, checked automatically so they
   keep working as expected.

## 1. Hands-on

- Orca on the Mac is paired with `orca-ide serve` on the server over Tailscale.
  Worktrees, terminals, and agents run on the server and appear in the Mac app.
- Handing off a task in progress: `orca worktree create` targeting the server
  environment with `--agent claude --prompt "<brief>"`. Candidate for a small
  skill that writes the brief from the current session.
- Code and notes sync through git. Clone the `~/best` repositories the server
  needs once.
- From the phone: Claude Remote Control and Orca mobile pairing
  (`orca serve --mobile-pairing`).

## 2. Background

**Services** (webhook worker, WhatsApp bridge, transcript processing):

- systemd restarts each service when it crashes.
- Each service checks in with an off-server checker after every run. A scheduled
  Val Town job emails Alejandro when a check-in is late, which also catches the
  whole server being down.
- Webhooks arrive at a Val Town HTTP endpoint that stores them in its SQLite. The
  server pulls jobs from there, so it has no public port besides SSH.

**Agent tasks:**

1. Each task is a file, `tasks/<id>.md`: brief, done-check (a command or a clear
   criterion), status (`running`, `done`, `blocked`), Orca terminal handle, and
   Claude session ID. Workers update the status and write a reason when blocked.
2. Workers run in Orca worktrees, so they're visible from the Mac.
3. A Stop hook refuses to let a worker end its turn while its task is `running`
   and tells it to keep going or mark itself blocked. Capped at a few refusals.
4. A systemd timer runs a watchdog script every ~10 minutes. For each `running`
   task:
   - Idle worker: send "continue; if stuck, mark blocked and say why". After 3
     nudges without progress, mark `blocked`.
   - Process gone (crash, reboot): relaunch in the same worktree with
     `claude --resume <session-id>`.
   - Usage limit hit: wait for the reset time shown in the terminal, or move the
     task to Codex.
   - Marked `done`: run the done-check; on failure, reopen with the output. Use a
     cheap LLM call only for fuzzy criteria.
5. Alerts go out only for `blocked` tasks and down services. When one fires, the
   watchdog can start a Claude session to investigate, so the alert arrives with
   a diagnosis.

To verify once Orca runs on the server: how reliably `orca-ide terminal show`
distinguishes idle, working, and waiting-for-input. If it doesn't, the watchdog
reads the screen instead.

## Interruption sources and mitigations

1. **The agent chooses to ask.**
   - A server-only instruction layer, loaded through `agent-context`: "You are
     unattended. When a choice is ambiguous, pick the reversible option, record it
     in the task's decision notes, and continue."
   - Reversible actions replace confirmations: move to trash instead of deleting,
     work on branches, write drafts instead of sending.
   - The server's Claude settings deny `AskUserQuestion`.
2. **The agent stops before it's done.** Stop hook and watchdog, above.
3. **Tool approvals.** Claude runs in bypass mode. Codex runs with
   `approval_policy = "never"` and `sandbox_mode = "danger-full-access"` in the
   server's config. The server being a disposable, backed-up VM is what makes
   this acceptable.
4. **Missing access.** See Access below.
5. **Limits and crashes.** Task state lives in files and git; the watchdog
   resumes or relaunches workers.

## Access

- 1Password: a service account that can only read the vault `server-agents`. Copy
  an item into that vault to give agents access to it. Items that hold TOTP
  secrets let agents fill 2FA codes (`op item get --otp`).
- Websites: Browser Use cloud profiles (`bu-cloud`), refreshed from local Chrome
  with `bu-cloud sync`. Only the Browser Use API key needs to be on the server.
- GitHub (`gh` token), Google (`gcloud auth login --no-launch-browser`), Claude
  and Codex (`orca-ide account add`, device login for Codex).
- Still Mac-only: local Chrome, the phone over adb, Granola's local data, the
  Slack skill's browser cookies. Tasks needing these stay on the Mac for now.
- Untested: whether claude.ai connectors (Gmail, Calendar, Drive) are available
  to Claude Code on the server.

## Safety nets

- Hetzner daily backups; agents push everything to git.
- A short deny list for external actions: sending email or messages, payments,
  making repositories public. Agents draft these for Alejandro to approve in a batch.
- Spending caps on API keys.
- No 80,000 Hours material on the server.
- The WhatsApp bridge runs as its own Linux user, with sending disabled.

## Escalation without blocking

When a question can't be avoided, the agent sends it with a push notification or
writes it to its task file, then continues on other parts or on a default.
Alejandro answers when convenient, from the phone through Remote Control.

## Supervisor

A Claude coordinator in Orca (using Orca orchestration's ask/reply) can answer
workers' questions, given Alejandro's instruction files, decision records, and a
log of his past answers. Whether this is worth building depends on the
supervisor experiment below. Hermes Agent (Nous Research) is the alternative to
revisit if the experiment shows value and chatting with the supervisor from the
phone matters; its workers would need to be launched through the `orca` CLI to
stay visible in Orca.

## Transcript scan

Measures which interruptions the setup would have avoided, before building all of it.

1. Sources: Claude Code sessions in `~/.claude/projects` (146 project folders)
   and Codex sessions in `~/.codex/sessions`.
2. Subagents find every point where a session waited on Alejandro: an
   `AskUserQuestion` call, a permission denial, an assistant turn ending in a
   question, or Alejandro stepping in to unblock something. Also sessions that
   ended unfinished and were never resumed.
3. Each is assigned to one of the five interruption sources and judged: would
   this setup have avoided it?
4. Supervisor experiment: for each "agent chose to ask" case, a subagent plays
   the supervisor with Alejandro's instruction files and decision records, and
   answers. Compare with what Alejandro actually answered. A high match rate
   means a supervisor is worth building; a low one means better briefs are the fix.
5. Output: a table of interruption counts by source, before and after the setup,
   plus the supervisor match rate.

## Open decisions

- Scan range: all history, or the last ~2 months (cheaper, closer to current work).
- Which external actions go on the deny list beyond sending, payments, and
  making repositories public.
- Whether the Stop hook ships, given the token cost of a worker that loops.
