# Desk pipeline

The server records every conversation Alejo has into `~/best/desk/comms/`, prepares
work it expects him to want in `desk/generated/`, and sends him one Slack DM at 8 am
listing what awaits his decision. He answers in plain language in that thread and the
server applies it. The server never sends anything to anyone: it drafts, Alejo sends,
and the server notices the send and files a frozen copy in `sent/`.

Status: specified, not built. The [requirements](#required-work) list what has to
exist first.

## How this fits the server

- [delegation.md](delegation.md) lists "transcript processing" among the background
  services. This spec defines it, extends it to every conversation source, and adds
  generation and the digest. Its service rules apply here unchanged: systemd restarts,
  check-ins with the off-server checker, and the Val Town endpoint for any source that
  pushes webhooks.
- Its deny list (agents draft sends for Alejo) is the [sending rule](#sending) below.
- Everything runs as the `agent` user. Git pushes, `gog` and Anthropic API calls go
  through the [credential broker](setup.md#agent-user), so no job holds Alejo's tokens.
- The [mail digest](setup.md#mail-digest) keeps sorting the personal inbox. This
  pipeline reads the same mail for a different purpose: recording conversations.

## Desk and who writes what

[`~/best/desk/AGENTS.md`](/Users/alejo/best/desk/AGENTS.md) defines the layout
(`people/`, `comms/`, `requested/`, `generated/`, `sent/`), item naming and the shared
frontmatter fields. This spec defines only the server's behaviour and the fields
specific to it.

The server's clone is `/home/agent/best/desk`, so paths relative to `~/best` are the
same on the server and on the Macs. Each server job runs `git pull --rebase`, writes,
commits and pushes. Writers are split by folder so the machines rarely edit the same
file:

| Folder | Written by |
|---|---|
| `comms/` | Server |
| `generated/` | Server, including Alejo's review decisions on its items |
| `requested/` | Alejo's Macs |
| `sent/` | Alejo's Macs, and the server when it [detects a send](#detecting-sends) |
| `people/` | Server adds files for new identities; Alejo edits any of them |

When a rebase still conflicts, Alejo's version wins and the server redoes its change
on top if it still applies.

## Recording conversations

Sources:

1. Granola calls, through Granola's public API (the same API the `summarize-call`
   skill uses).
2. Gmail for `alejoacelas@gmail.com` and `alejo@impact-ops.org`, through `gog`. Skip
   mail that isn't direct engagement with people: notices, newsletters, receipts and
   other automated mail.
3. Every Slack workspace Alejo is in: all DMs and group DMs, plus channel threads he
   posted in or was mentioned in.
4. WhatsApp, read from the bridge's message store: every chat, including groups.

Client and 80,000 Hours conversations are recorded like everything else. Each source
is polled every 15 minutes; a source that can push webhooks may go through the Val
Town endpoint instead. The digest's own Slack thread is not recorded.

Each conversation thread is one file, `comms/YYYY-MM/<start date>-<slug>.md`, filed
under the month the thread started. When the thread continues, the server appends to
the same file, even in a later month. A thread is a Gmail thread, a Slack thread, a
Granola call, or, in chats without threads (WhatsApp, Slack DMs), a run of messages
with no gap longer than three days.

Body: for calls, a summary followed by the tidied transcript; for messages, each
message in order with sender, time and text, with quoted replies and signatures
removed. Attachments are listed by name and link, not copied.

Server-specific frontmatter:

- `source:` `granola`, `gmail`, `slack` or `whatsapp`, plus the account or workspace
  (e.g. `gmail alejo@impact-ops.org`).
- `thread:` the source's own thread ID (Gmail thread ID, Slack channel and thread
  timestamp, Granola meeting ID, WhatsApp chat ID), used to find the file when the
  thread continues.
- `link:` the thread's web URL, where the source has one.

`people:` lists everyone in the thread except Alejo. The server matches each email,
Slack ID or phone number against `people/`. An identity it can't match gets a new
`people/` file with whatever name and identity the source gives, and recording
continues without asking.

## Generated work

After each recording pass that brings new messages, and once each morning before the
digest, an agent reviews recent `comms/`, Alejo's calendar for the next two days, and
the rest of desk, and creates whatever items it judges useful. There is no fixed list
of triggers and no cap on the number of items. Its instructions:

- Be proactive: prep for tomorrow's call, the comparison someone asked for, the
  follow-up Alejo promised last week, an answer to a question left open in a thread.
- Alejo's attention narrows at each stage: most items get no review, a fraction get
  reviewed, and fewer still get sent. Make each item cheap to judge from its digest
  line, and ask whether the deliverable can be very short: three lines, a list of
  links, a draft reply.
- Weigh desk sources by trust: `comms/` is what people actually saw and said;
  `requested/` with `reviewed:` is endorsed by Alejo; `requested/` without it was asked
  for but is unchecked; `generated/` is a lead to verify.
- Read the discard reasons and the archived items' `why:` from the last 90 days, and
  stop producing what Alejo keeps dropping or ignoring.
- Revise an item when its thread moves on, until the item has `reviewed:`.

Each item is `generated/YYYY-MM/<date>-<slug>.md` (a folder when it has several files)
with `people:` and `from:`, plus:

- `why:` the trigger in one line, e.g. "Lizzie asked for a cloud-storage comparison on
  10 Sep".
- `next:` the proposed action, e.g. "send as a Google Doc" or "use as prep for
  Thursday's call".

The body's first line repeats `from:` as a relative Markdown link
(`[from](../../comms/2026-09/2026-09-10-lizzie-storage.md)`), because Umi's preview
follows relative links but may not make frontmatter clickable.

Models, through the Anthropic API with the personal Console organization's key:
`claude-opus-5-5` by default, `claude-haiku-5-5` for fast jobs or jobs with more than
20 parallel calls (such as filtering automated mail). No spending cap. The key sits in
`server-agents` and reaches jobs through a broker route; Claude Code jobs point
`ANTHROPIC_BASE_URL` at that route.

## Daily digest

Every day at 8 am in the timezone of Alejo's primary Google Calendar (re-read daily,
so it follows his travel), the server sends him a Slack DM. It lists every generated
item with no `reviewed:` or `discarded:`, most urgent first (a call tomorrow before a
promise made last week before a nice-to-have). Each item is one numbered line: who,
what, why, proposed next step and one link.

```
1. Lizzie (Acme) · cloud-storage comparison · she asked on 10 Sep · send as a Google Doc · <link>
```

On a day with nothing pending, no message is sent. Items Alejo doesn't mention stay
pending and reappear the next day.

Alejo replies in the thread in plain language, e.g. "send 2 after cutting the pricing
section, 4 for Friday's call, drop 5 because she already chose a provider". The server
applies it and replies in the thread with what it did, so a misreading can be
corrected with another reply:

1. Approved items get `reviewed:` with today's date, after any edit he asked for. A
   new use ("4 for Friday's call") updates `next:`.
2. Dropped items get `discarded:` with today's date and `discard_reason:` with his
   reason.
3. For items to send, the server prepares the send: a Gmail draft in the account the
   conversation used, or, for Slack and WhatsApp, the message text in the digest thread
   ready to paste. When the item should go as a Google Doc, the server creates the doc
   unshared and records it in `gdoc:`.

## Sending

The server never sends a message, shares a document or posts on Alejo's behalf. He
sends every draft himself.

### Detecting sends

When the server records an outgoing message from Alejo that links to or attaches a
`requested/` or `generated/` item, or its `gdoc:`, it:

1. copies the version sent (the attachment, the Google Doc exported at that moment, or
   the file as it was in git at that time) into `sent/YYYY-MM/<send date>-<slug>`,
   with `from:` pointing to the item and the link to the carrying message;
2. records the message in `comms/` as usual;
3. adds `reviewed:` to a generated item that lacks it.

Alejo does nothing extra.

## Review by editing, and archiving

When Alejo edits a generated item himself (a commit from a Mac that touches it), the
server adds `reviewed:` with that date and stops changing the item. It stays in
`generated/`.

Each morning, generated items without `reviewed:` that are more than 30 days old move
to `generated/archive/YYYY-MM/` (the month they were created) with `archived:` set to
that day. They keep `why:`, so generation can see which triggers Alejo ignores.

## Opening items

Every digest link is `https://agent-server.tail622085.ts.net/o?p=<path relative to
~/best>`, served by Tailscale Serve on the tailnet like `/mail`. The page rejects paths
that are absolute or contain `..`, then redirects:

- Mac: to `umi://open?path=<same path>`.
- Phone, and iPad (which reports itself as a Mac; tell it apart by
  `navigator.maxTouchPoints > 0`): to the file's GitHub page, built from the origin
  remote of the server's clone that contains the path, e.g.
  `https://github.com/alejoacelas/desk/blob/main/generated/2026-10/<file>`.

The page also shows the GitHub link, as a fallback when Umi doesn't open.

**Required in Umi** (`~/best/projects/2026-10-26-umi`; none of it exists yet): register
the `umi` URL scheme and handle `umi://open?path=<path>`. The handler resolves the path
against `~/best` and refuses anything outside it, fetches the containing repository and
fast-forwards it if it is behind and has no local changes, then opens the file in Umi's
editor.

## Measures after two weeks

Computed from desk frontmatter and `sent/` two weeks after the first digest:

1. Share of generated items reviewed, and share eventually sent.
2. Time from creation to a decision (`reviewed:` or `discarded:`): median and 90th
   percentile, plus the number archived with no decision.
3. Discard reasons, grouped by trigger (`why:`).

## Required work

Beyond building the pipeline itself:

1. Clone desk on the server as `agent` at `/home/agent/best/desk`.
2. The Val Town endpoint and the WhatsApp bridge, both still open in
   [setup.md](setup.md#remaining-steps).
3. Slack read access on the server for every workspace. Today the Slack credentials are
   browser-session tokens kept on the Mac.
4. The Granola API key and an Anthropic API key in `server-agents`, with broker routes.
5. A Slack app that can DM Alejo in the workspace that hosts the digest and read his
   replies.
6. The Umi URL scheme above.

## Open questions

1. Which Slack workspace hosts the digest DM.
2. [delegation.md](delegation.md#safety-nets) still says "No 80,000 Hours material on
   the server" (superseded by commit `91ee4d3`) and "Spending caps on API keys"
   (superseded by the no-cap decision here).
3. The `summarize-call` skill files Granola calls into desk from the Macs, which
   overlaps with the server owning `comms/`. It should either stop filing calls or
   write to `comms/` in the same format.
4. Alejo will get two morning messages: the mail digest at 07:00 London time and this
   digest at 08:00. Merge them or keep both.
5. The Slack scope above leaves out channel messages Alejo didn't take part in. Confirm
   that matches "record everything".
6. The `/o` links work only on devices connected to the tailnet, so the phone needs
   Tailscale running.
