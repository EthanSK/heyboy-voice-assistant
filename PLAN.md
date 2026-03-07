# PLAN.md — Heyboy Voice Assistant Project

## Canonical Chat Log (verbatim project conversation)

> NOTE: This file backfills HeyBoy project messages so far and will be appended as work progresses.

### [2026-03-07 00:00 Europe/London] User
"Okay. I have another project I want to do with OpenClaw on my Mac mini. I wanna be able to speak to it. I wanna be able to say, hey, boy, and that we saw I have an always running, maybe locally running model that just is acts as the basic detector for HeyBoy, and then it starts up a listener of my voice with a real time voice or conversational API. And then OpenClaw responds with the 5.2 model. Maybe on low thinking or something that's fast. Yeah. Low thinking. Let's try low thinking for now. And that's just speech to text. And, also, it should be interruption detection so I can interrupt it. I first this we're gonna do this in two parts, and we're gonna set a cron job every ten minutes for the next half an hour to check on the progress of this whole project. So want you to keep a plan, do this in projects properly, like how we've done all the projects. And If possible, if you can start a new chat, keep track of the sub agents. I think the context is getting quite high here. Restart a new chat. Also, keep track of the producer player sub agent. Yeah. I just wanna be able to talk to you. I wanna say, hey, boy. Start listening for five, ten seconds. Connect me with my API token based thing. Yeah. Actually, also, in a separate Telegram message, me if there is any existing skills or repos that do that. I want just another sub agent to research if the existence of that. And every ten minutes, give me the status of all the sub agents, every single sub agent, just for the next hour until nothing has changed. And if it fails, figure out why it's failed. If it's stupid, continue the operation without me having to butt in. But, yeah, first, start a new chat."

### [2026-03-07 00:05 Europe/London] Assistant
"Got it — done, point-by-point:
- Default model is **GPT‑5.3 Codex** (`openai-codex/gpt-5.3-codex`).
- Default thinking is now **high**.
- Sub-agent default thinking rule is now **xhigh**.
- I tried starting a true thread-bound “new chat”, but Telegram here still blocks subagent thread binding, so I started fresh dedicated project runs instead."

### [2026-03-07 00:05 Europe/London] Assistant
"Project runs now active:
- `heyboy-voice-part1` → `31699ab5-8ef6-4c34-a748-003999a0e7a1` (xhigh)
- `heyboy-voice-existing-solutions` → `4dccc6c6-bead-45c6-8018-7a8a92e9c9cf` (xhigh)
- `producer-player-build` still tracked → `776b8e9e-a28e-438b-a5e4-4a78ac3a7f73`

I instructed the HeyBoy build run to create/manage:
`/Users/ethansk/Projects/openclaw-heyboy-voice/PLAN.md`
and execute this as **Part 1** of 2."

### [2026-03-07 00:05 Europe/London] Assistant
"Monitoring scheduled:
- All-subagent status checks at **+10, +20, +30, +40, +50, +60 min**
- Includes auto-recovery attempt instruction for obvious failed/stalled runs
- Plus supervision checkpoints on new runs at **+5/+10/+30**

I’ll send change-based updates from those checks (quiet if unchanged)."

### [2026-03-07 00:05 Europe/London] Assistant
"Separate message as requested: I launched a dedicated research sub-agent for existing skills/repos that already do wake-word + realtime voice + interruption handling. I’ll send that findings summary as its own Telegram message when it completes.

Config/rule files updated:
- `/Users/ethansk/.openclaw/openclaw.json` (thinkingDefault=high)
- `/Users/ethansk/.openclaw/workspace/AGENTS.md` (sub-agent thinking default rule = xhigh)"

### [2026-03-07 00:07 Europe/London] User
"Also, I want you to keep a plan dot m d file that contains all the messages I send you about this HeyBoy project. I wanna keep track of every message back and forth that we send each other about this project in the repo. Also, make sure to commit the repo. Let's make it open source as well. Let's also make it so it works with your locally installed, Claude code or codec CLI. You can just select or any other CLI. And yeah. This should be an open source public repo. And it should also work with OpenClaw if you've got that installed because you so I expect users who download it to have one of these things installed and just have a nice setup, easy setup CLI process kinda inspired by OpenClaw. By the way, did you start a new chat? Or were you unable to? It's fine if you weren't able to, but I just wanna know. And, oh, yeah, go back and add all the previous conversations about this project so far into that plan dot m d file."

---

## Current Execution Plan

### Part 1 (in progress)
- [ ] Build wake-word + short listen window + OpenClaw request flow (fast/low-thinking target path)
- [ ] Add interruption handling (barge-in)
- [ ] Add setup CLI flow (OpenClaw-inspired)
- [ ] Add compatibility paths for OpenClaw / Codex CLI / Claude Code
- [ ] Commit all Part 1 work
- [ ] Prepare open-source/public repo metadata and publish if auth allows

### Part 2 (next)
- [ ] Iterate UX polish + robust daemonization + packaging + launch-at-login + reliability hardening

## Active Subagents
- `heyboy-voice-part1` (steered with expanded scope)
- `heyboy-voice-existing-solutions`
- `producer-player-build` (separate project, still tracked)
- `wordfinder-landing-release-pipeline` (legacy stale run being monitored)

---

### [2026-03-07 00:09 Europe/London] User
"Also, I want you to keep a plan dot m d file that contains all the messages I send you about this HeyBoy project. I wanna keep track of every message back and forth that we send each other about this project in the repo. Also, make sure to commit the repo. Let's make it open source as well. Let's also make it so it works with your locally installed, Claude code or codec CLI. You can just select or any other CLI. And yeah. This should be an open source public repo. And it should also work with OpenClaw if you've got that installed because you so I expect users who download it to have one of these things installed and just have a nice setup, easy setup CLI process kinda inspired by OpenClaw. By the way, did you start a new chat? Or were you unable to? It's fine if you weren't able to, but I just wanna know. And, oh, yeah, go back and add all the previous conversations about this project so far into that plan dot m d file."

### [2026-03-07 00:11 Europe/London] User
"Also, I want you to keep a plan dot m d file that contains all the messages I send you about this HeyBoy project. I wanna keep track of every message back and forth that we send each other about this project in the repo. Also, make sure to commit the repo. Let's make it open source as well. Let's also make it so it works with your locally installed, Claude code or codec CLI. You can just select or any other CLI. And yeah. This should be an open source public repo. And it should also work with OpenClaw if you've got that installed because you so I expect users who download it to have one of these things installed and just have a nice setup, easy setup CLI process kinda inspired by OpenClaw. By the way, did you start a new chat? Or were you unable to? It's fine if you weren't able to, but I just wanna know. And, oh, yeah, go back and add all the previous conversations about this project so far into that plan dot m d file."

### [2026-03-07 00:12 Europe/London] Assistant
"Progress update: pulled latest, continued from commit e0ec36a, and implemented compatibility scaffolding for OpenClaw API/Codex CLI/Claude Code CLI + generic CLI."

### [2026-03-07 00:17 Europe/London] User
"I don't want the repo to be called OpenCraw Heyboy Voice. Just Heyboy voice assistant, and the description should be, like, works with any AI subscription. Works with any of your AI subscriptions. Sorry."

### [2026-03-07 00:18 Europe/London] Assistant
"Applied naming update: repo renamed to `heyboy-voice-assistant` and tagline standardized to 'Works with any of your AI subscriptions.'"

### [2026-03-07 00:22 Europe/London] User
"Is there a way, by the way, to make HeyBoy downloadable? And then it's just got everything it needs to just work out the box. You just leave it running as an app or as a CLI tool and also add Homebrew support. You can just install it with Brew, the app itself. Also, it should be hey boy dash voice dash. Actually, no. Sorry. Ignore that. It should be up till now. But yeah."

### [2026-03-07 00:23 Europe/London] User
"I want you to send a screenshot of it to me and test the app works in a sub agent."

### [2026-03-07 00:35 Europe/London] Assistant
"Smoke tests completed in this run:
- CLI path: `scripts/heyboy run` starts successfully and reaches wake-listen loop.
- App/daemon path: LaunchAgent install/start/status/stop verified (`scripts/heyboy app ...`).
- Screenshot proof saved: `/Users/ethansk/.openclaw/workspace/artifacts/heyboy-voice-proof.png`.
- Added downloadability docs, one-command installer (`scripts/install.sh`), and Homebrew formula (`Formula/heyboy-voice-assistant.rb`)."
