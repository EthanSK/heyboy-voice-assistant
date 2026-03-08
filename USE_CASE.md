# USE_CASE.md — HeyBoy Interaction Matrix

Last updated: 2026-03-08

## Scope

This document captures the practical user/system interactions for HeyBoy and marks each as:

- **Implemented** (behavior exists in code now)
- **Implemented + Tested** (covered by automated test in this repo)
- **Out of scope (now)** (explicitly deferred)

Primary focus for this pass: **multi-turn reliability** and avoiding the “first turn works, second turn goes silent” failure mode.

---

## 1) Core Conversation & Multi-Turn

| ID | Use case | Expected behavior | Status | Evidence |
|---|---|---|---|---|
| MT-01 | User says wake phrase | Assistant detects wake phrase and enters listen mode | Implemented | `wait_for_wake_phrase()` |
| MT-02 | First turn after wake | Assistant plays listen ack and records request | Implemented | `handle_wake_session()` |
| MT-03 | User asks follow-up without saying wake again | Assistant continues in same session and answers follow-up | Implemented + Tested | `MULTI_TURN_ENABLED`, `tests/test_voice_assistant.py::test_multi_turn_enabled_handles_followup_without_new_wake` |
| MT-04 | Follow-up turn start clarity | Assistant can give an optional short follow-up cue (default off for lower latency) | Implemented | `FOLLOWUP_PROMPT` (default empty) |
| MT-05 | Follow-up no speech (single miss) | Assistant gives short audible reprompt instead of silent failure | Implemented + Tested | `FOLLOWUP_NO_SPEECH_PROMPT`, `test_followup_no_speech_has_reprompt_before_timeout` |
| MT-06 | Follow-up no speech (retries exhausted) | Assistant ends session with explicit pause message (no self-triggering wake phrase) | Implemented + Tested | `FOLLOWUP_TIMEOUT_PROMPT`, `test_followup_no_speech_ends_session` |
| MT-07 | Wake phrase only transcript (no command) | Assistant asks for an actual request | Implemented + Tested | `is_wake_only_transcript()`, `test_wake_only_transcript_is_reprompted_then_retried` |
| MT-08 | Multi-turn disabled intentionally | Single-turn behavior preserved (needs wake for each new request) | Implemented + Tested | `MULTI_TURN_ENABLED=False`, `test_single_turn_mode_reproduces_no_followup_without_rewake` |
| MT-09 | Session turn cap reached | Session exits at configured max turns | Implemented | `MULTI_TURN_MAX_TURNS` loop bound |
| MT-10 | Initial no speech after wake | Assistant reprompts and exits after configured retry limit | Implemented | `NO_SPEECH_RETRY_LIMIT` path |

---

## 2) Interruptions & TTS

| ID | Use case | Expected behavior | Status | Evidence |
|---|---|---|---|---|
| TTS-01 | Assistant speaking and user interrupts | Playback stops on barge-in threshold | Implemented | `BargeInTTS.speak()` |
| TTS-02 | Non-interruptible prompts (ack/setup) | Assistant waits for short prompt completion, with timeout safety | Implemented | `allow_barge_in=False` + forced stop timeout |
| TTS-03 | TTS thread hangs | Assistant force-stops engine and recovers | Implemented | stop + join fallback in `BargeInTTS` |
| TTS-04 | Barge-in monitor stream error | Warn and continue (no crash loop) | Implemented | exception handling in barge-in monitor |
| TTS-05 | Second-turn duplicate/jagged overlap | New utterance drains any stale playback before starting | Implemented + Tested | `test_barge_in_tts_prevents_parallel_overlap_on_lingering_stop` |
| TTS-06 | Duplicate short prompt fired twice quickly | Deduplicate identical TTS text in short window | Implemented + Tested | `TTS_DUPLICATE_WINDOW_MS`, `test_barge_in_tts_dedupes_duplicate_prompt_within_window` |
| TTS-07 | Self-wake after assistant speaks wake-like phrase | Wake detector cooldown after playback prevents immediate self-trigger | Implemented + Tested | `WAKE_SUPPRESS_AFTER_TTS_MS`, `test_wake_suppress_until_tracks_last_tts_playback_end` |

---

## 3) STT / Audio Input Reliability

| ID | Use case | Expected behavior | Status | Evidence |
|---|---|---|---|---|
| STT-01 | Local Vosk transcription success | Transcript returned and sanitized | Implemented | `transcribe_vosk_local()` + `sanitize_transcript()` |
| STT-02 | Deepgram selected but API key missing | User gets explicit spoken config error | Implemented | `transcribe_deepgram()` + last STT error path |
| STT-03 | Deepgram timeout/network/auth/rate-limit/server errors | User gets mapped recovery message | Implemented | `transcribe_deepgram()` status mapping |
| STT-04 | Transcription too long/noisy | Transcript capped to max chars (protects prompt latency) | Implemented | `MAX_TRANSCRIPT_CHARS` |
| STT-05 | Transient mic open/record failure | Audio operation retries before fail | Implemented + Tested | `run_audio_with_retries()`, `test_record_audio_retries_once_then_succeeds` |
| STT-06 | User finishes speaking early | Capture ends after trailing silence (lower latency) | Implemented + Tested | `EARLY_ENDPOINTING_ENABLED`, `test_record_audio_endpointing_stops_after_trailing_silence` |
| STT-07 | STT backend misconfigured | Clear runtime error and safe exit | Implemented | `STT_BACKEND` validation in `main()` |

---

## 4) LLM/API & CLI Backend Routing

| ID | Use case | Expected behavior | Status | Evidence |
|---|---|---|---|---|
| BE-01 | OpenAI-compatible API success | Uses system prompt + bounded history | Implemented | `query_openclaw_api()` |
| BE-02 | API rejects reasoning fields | Retries without reasoning payload fields | Implemented | request retry logic |
| BE-03 | API 401/403/404/408/429/5xx | User gets specific recovery-safe message | Implemented + Tested (429) | `query_openclaw_api()`, `test_query_openclaw_api_maps_rate_limit` |
| BE-04 | CLI backend executable missing | User gets explicit setup guidance | Implemented | `command_exists()` path |
| BE-05 | Codex auth expired/reused token | User gets direct `codex logout/login` remediation | Implemented | `summarize_cli_failure_for_user()` |
| BE-06 | Codex model/flags omitted in command | Wrapper injects low-latency defaults (`-m gpt-5.2`, `reasoning none`) | Implemented + Tested | `build_codex_cli_command()`, codex command tests |
| BE-07 | CLI returns empty text | User gets explicit empty-response fallback | Implemented | `query_cli_backend()` |
| BE-08 | Backend returns blank/None | Assistant speaks configured fallback | Implemented | `EMPTY_BACKEND_REPLY` |

---

## 5) Session State, History, Startup, Recovery

| ID | Use case | Expected behavior | Status | Evidence |
|---|---|---|---|---|
| SYS-01 | Multiple HeyBoy processes launched | Single-instance lock prevents contention | Implemented | `acquire_instance_lock()` |
| SYS-02 | Invalid runtime config values | Startup validation fails fast with clear logs | Implemented | `validate_runtime_config()` |
| SYS-03 | Unhandled loop exception | Loop logs and recovers (does not crash permanently) | Implemented | main loop exception handler |
| SYS-04 | Long sessions with many turns | History bounded by message count and char budget | Implemented + Tested | `trim_history()`, `test_trim_history_respects_character_budget` |
| SYS-05 | STT error during session | User hears recovery message instead of silence | Implemented + Tested | `get_last_stt_error()`, `test_stt_error_is_spoken_as_recovery_message` |

---

## 6) Explicitly Out-of-Scope (This Pass)

| ID | Use case | Why out-of-scope now | Future direction |
|---|---|---|---|
| OOS-01 | Beamforming / far-field noise suppression | Requires DSP stack + mic array assumptions | Add optional RNNoise/WebRTC pipeline |
| OOS-02 | Adaptive semantic endpointing | Current design uses RMS-based trailing-silence endpointing | Add richer VAD + semantic end-of-utterance model |
| OOS-03 | Speaker diarization / voice identity | Not required for single-user assistant target | Integrate diarization model later |
| OOS-04 | Offline neural TTS voices | pyttsx3 chosen for lightweight local baseline | Add optional neural TTS backend |
| OOS-05 | Multilingual wake-word model switching | Wake path currently normalized text on one phrase | Add language profile + wake model selection |
| OOS-06 | Automatic backend failover across providers | Could hide failures but increases complexity/risk | Add opt-in failover policy |

---

## Validation Checklist (Executed)

- `scripts/tests/run_voice_assistant_unit.sh`
- `HEYBOY_ALLOW_DAEMON_SKIP=1 scripts/tests/e2e_smoke_macos.sh`

These validate multi-turn behavior, no-reply regression protection, backend mapping, audio retry behavior, and overall run-loop/app lifecycle smoke paths.
