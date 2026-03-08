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

### [2026-03-07 00:38 Europe/London] Assistant
"Post-smoke hardening:
- Fixed installer model download fallback (primary URL failure now auto-falls back to HuggingFace mirror).
- Added Homebrew tap workflow and validated dry-run install command.
- Committed and pushed updates on top of e0ec36a -> 2069c9f."

### [2026-03-07 00:43 Europe/London] User
"Oh, there's no built in or end to end or Open skill? We should make one. We should make the CLI of this into one. Can Open Claw skills just be CLI tools? Instructions to install if it doesn't exist and use it, put it into the path. Mac and ideally Windows, but I don't have Windows to test it on, so we can only test it on Mac for now. Also, have you checked the UI works and everything? Also okay. Look. I haven't checked the project yet, but you did it in Swift. I want it to be cross platform with Electron, with TypeScript. Look at the existing Okay. Keep the Swift MVP there. I'll test it later. But I have an existing project somewhere in my home folder, my projects folder, on the computer. Look at it for Electron advice and guidance and also AI music video studio for like rough guidance on how to set up the mono repo and style guides and types, etcetera. So, yeah, do a sub agent for that. Obviously, because it's a long running app, you should automatically be doing sub agents for this. I already told you in the past to do that."

### [2026-03-07 00:51 Europe/London] User
"That is the CLI that is. And, also, make end to end tests running and all that. Also, how was the status of the other agents?"

### [2026-03-07 00:51 Europe/London] Assistant
"In-progress implementation update:
- Added OpenClaw-skill-style package folder under `skills/heyboy-voice-assistant/` with SKILL.md + references.
- Added Windows best-effort scripts (`scripts/install.ps1`, `scripts/install_part1_deps.ps1`, `scripts/heyboy.ps1`) and docs marking untested status.
- Added practical E2E smoke+integration test harness for macOS (`scripts/tests/e2e_smoke_macos.sh`) plus deterministic test backend (`scripts/tests/smoke_backend.py`).
- Updated README/docs with exact E2E commands, validation status, and explicit UI verification boundaries.
- Running local E2E smoke now and capturing artifacts under `artifacts/e2e/<timestamp>/`."

### [2026-03-08 00:58 Europe/London] User
"Okay. There's a few issues. After so the first turn still works, but then the second turn, I just hear two Hey Boys playing jagged audio just after each other. You need to do a full review in a sub agent for all this kind of buggy stuff because this is really not working. Do some proper end to end testing. Like, it's literally playing two in parallel the second time I talk. Also, it's still taking quite a bit of time. Between when I say something it responds, is it on the fastest model possible? Does it pass the flag in or how does it work?"

### [2026-03-08 01:01 Europe/London] User
"Sorry. I might not have explained this. The the it just off the second turn, it plays two audios in parallel over each other, just slightly jagged."

### [2026-03-08 01:14 Europe/London] Assistant
"Reliability + latency hardening completed:
- Isolated second-turn duplicate/jagged audio root cause to TTS playback race in `BargeInTTS` (shared done event/engine state allowed overlap when previous worker lingered after timeout/stop).
- Reworked TTS playback state management to serialize utterances and drain stale in-flight playback before starting next utterance.
- Added codex command normalization for latency-sensitive defaults (`-m` + `model_reasoning_effort`) so wrapper consistently passes model/reasoning flags.
- Expanded regression tests for duplicate playback, multi-turn stability, and codex latency defaults.
- Re-ran unit and E2E smoke validation with passing results."
