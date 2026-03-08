import importlib.util
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from typing import List, Tuple
from unittest import mock

import numpy as np
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "voice_assistant.py"

spec = importlib.util.spec_from_file_location("voice_assistant_under_test", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Failed to load module spec from {MODULE_PATH}")
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: List[Tuple[str, bool]] = []

    def speak(self, text: str, allow_barge_in: bool = True) -> bool:
        self.spoken.append((text, allow_barge_in))
        return True


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        return self._payload


class _SlowStopEngine:
    """Fake pyttsx3 engine that lingers after stop() to emulate jagged overlap races."""

    def __init__(self, tracker: dict, linger_after_stop_s: float = 2.2) -> None:
        self._tracker = tracker
        self._linger_after_stop_s = linger_after_stop_s
        self._stop_event = threading.Event()

    def say(self, _text: str) -> None:
        return None

    def runAndWait(self) -> None:
        with self._tracker["lock"]:
            self._tracker["active"] += 1
            self._tracker["max_active"] = max(
                self._tracker["max_active"],
                self._tracker["active"],
            )

        self._stop_event.wait(timeout=6.0)
        threading.Event().wait(self._linger_after_stop_s)

        with self._tracker["lock"]:
            self._tracker["active"] -= 1

    def stop(self) -> None:
        self._stop_event.set()


class VoiceAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.audio = np.zeros((16000, 1), dtype=np.int16)

    def test_single_turn_mode_reproduces_no_followup_without_rewake(self) -> None:
        """Reproduces Ethan's bug report path when multi-turn is off."""
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", False))
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_MAX_TURNS", 3))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 0))

            mock_record = stack.enter_context(
                mock.patch.object(va, "record_audio", side_effect=[self.audio, self.audio])
            )
            mock_transcribe = stack.enter_context(
                mock.patch.object(
                    va,
                    "transcribe",
                    side_effect=["can you hear me", "second follow up"],
                )
            )
            mock_query = stack.enter_context(
                mock.patch.object(va, "query_backend", side_effect=["yes, i can hear you", "never used"])
            )

            va.handle_wake_session(object(), tts, history)

        self.assertEqual(mock_record.call_count, 1)
        self.assertEqual(mock_transcribe.call_count, 1)
        self.assertEqual(mock_query.call_count, 1)
        self.assertEqual(history[-2]["content"], "can you hear me")

    def test_multi_turn_enabled_handles_followup_without_new_wake(self) -> None:
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", True))
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_MAX_TURNS", 2))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 0))
            stack.enter_context(mock.patch.object(va, "FOLLOWUP_PROMPT", ""))

            stack.enter_context(
                mock.patch.object(va, "record_audio", side_effect=[self.audio, self.audio])
            )
            stack.enter_context(
                mock.patch.object(
                    va,
                    "transcribe",
                    side_effect=["can you hear me", "what about now"],
                )
            )
            mock_query = stack.enter_context(
                mock.patch.object(
                    va,
                    "query_backend",
                    side_effect=["yes", "still hearing you"],
                )
            )

            va.handle_wake_session(object(), tts, history)

        self.assertEqual(mock_query.call_count, 2)
        self.assertEqual(mock_query.call_args_list[0].args[0], "can you hear me")
        self.assertEqual(mock_query.call_args_list[1].args[0], "what about now")
        self.assertEqual(len(history), 4)

    def test_multi_turn_three_turns_remain_stable(self) -> None:
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", True))
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_MAX_TURNS", 3))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 0))
            stack.enter_context(mock.patch.object(va, "FOLLOWUP_PROMPT", ""))

            stack.enter_context(
                mock.patch.object(
                    va,
                    "record_audio",
                    side_effect=[self.audio, self.audio, self.audio],
                )
            )
            stack.enter_context(
                mock.patch.object(
                    va,
                    "transcribe",
                    side_effect=["turn one", "turn two", "turn three"],
                )
            )
            mock_query = stack.enter_context(
                mock.patch.object(
                    va,
                    "query_backend",
                    side_effect=["reply one", "reply two", "reply three"],
                )
            )

            va.handle_wake_session(object(), tts, history)

        self.assertEqual(mock_query.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in mock_query.call_args_list],
            ["turn one", "turn two", "turn three"],
        )
        self.assertEqual(len(history), 6)

    def test_followup_no_speech_ends_session(self) -> None:
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", True))
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_MAX_TURNS", 3))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 0))
            stack.enter_context(mock.patch.object(va, "SESSION_END_PROMPT", ""))
            stack.enter_context(mock.patch.object(va, "FOLLOWUP_PROMPT", ""))
            stack.enter_context(mock.patch.object(va, "FOLLOWUP_TIMEOUT_PROMPT", "say hey boy"))

            mock_record = stack.enter_context(
                mock.patch.object(va, "record_audio", side_effect=[self.audio, self.audio])
            )
            stack.enter_context(
                mock.patch.object(va, "transcribe", side_effect=["first request", ""])
            )
            mock_query = stack.enter_context(
                mock.patch.object(va, "query_backend", return_value="first reply")
            )

            va.handle_wake_session(object(), tts, history)

        spoken_texts = [entry[0] for entry in tts.spoken]
        self.assertIn("say hey boy", spoken_texts)
        self.assertEqual(mock_record.call_count, 2)
        self.assertEqual(mock_query.call_count, 1)
        self.assertEqual(len(history), 2)

    def test_followup_no_speech_has_reprompt_before_timeout(self) -> None:
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", True))
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_MAX_TURNS", 3))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 1))
            stack.enter_context(mock.patch.object(va, "FOLLOWUP_PROMPT", ""))
            stack.enter_context(mock.patch.object(va, "SESSION_END_PROMPT", ""))
            stack.enter_context(
                mock.patch.object(va, "FOLLOWUP_NO_SPEECH_PROMPT", "still here")
            )
            stack.enter_context(
                mock.patch.object(va, "FOLLOWUP_TIMEOUT_PROMPT", "say hey boy when ready")
            )

            mock_record = stack.enter_context(
                mock.patch.object(
                    va,
                    "record_audio",
                    side_effect=[self.audio, self.audio, self.audio],
                )
            )
            stack.enter_context(
                mock.patch.object(va, "transcribe", side_effect=["first request", "", ""])
            )
            mock_query = stack.enter_context(
                mock.patch.object(va, "query_backend", return_value="first reply")
            )

            va.handle_wake_session(object(), tts, history)

        spoken_texts = [entry[0] for entry in tts.spoken]
        self.assertIn("still here", spoken_texts)
        self.assertIn("say hey boy when ready", spoken_texts)
        self.assertEqual(mock_record.call_count, 3)
        self.assertEqual(mock_query.call_count, 1)

    def test_wake_only_transcript_is_reprompted_then_retried(self) -> None:
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", False))
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_MAX_TURNS", 1))
            stack.enter_context(mock.patch.object(va, "WAKE_ONLY_RETRY_LIMIT", 1))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 1))
            stack.enter_context(mock.patch.object(va, "WAKE_ONLY_PROMPT", "need command"))

            stack.enter_context(
                mock.patch.object(va, "record_audio", side_effect=[self.audio, self.audio])
            )
            stack.enter_context(
                mock.patch.object(va, "transcribe", side_effect=["hey boy", "tell me a joke"])
            )
            mock_query = stack.enter_context(
                mock.patch.object(va, "query_backend", return_value="joke reply")
            )

            va.handle_wake_session(object(), tts, history)

        spoken_texts = [entry[0] for entry in tts.spoken]
        self.assertIn("need command", spoken_texts)
        self.assertEqual(mock_query.call_count, 1)
        self.assertEqual(mock_query.call_args.args[0], "tell me a joke")

    def test_trim_history_respects_character_budget(self) -> None:
        history = []
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "HISTORY_MAX_MESSAGES", 20))
            stack.enter_context(mock.patch.object(va, "HISTORY_MAX_CHARS", 40))

            va.append_history_turn(history, "one", "alpha")
            va.append_history_turn(history, "two", "bravo")
            va.append_history_turn(history, "three", "charlie")
            va.append_history_turn(history, "four", "delta")

        total_chars = sum(len(item.get("content", "")) for item in history)
        self.assertLessEqual(total_chars, 40)
        self.assertTrue(any(item["content"] == "delta" for item in history))

    def test_query_openclaw_api_maps_rate_limit(self) -> None:
        history = []
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "API_KEY", "test-key"))
            stack.enter_context(mock.patch.object(va, "API_BASE_URL", "http://example.test"))
            stack.enter_context(mock.patch.object(va, "MODEL_NAME", "gpt-test"))
            stack.enter_context(
                mock.patch.object(
                    va.requests,
                    "post",
                    return_value=_FakeResponse(status_code=429, text="rate limit"),
                )
            )

            result = va.query_openclaw_api("hello", history)

        self.assertIn("rate limit", result.lower())

    def test_record_audio_retries_once_then_succeeds(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "AUDIO_RETRY_ATTEMPTS", 2))
            stack.enter_context(mock.patch.object(va, "AUDIO_RETRY_BACKOFF_S", 0.0))
            stack.enter_context(mock.patch.object(va, "AUDIO_RETRY_BACKOFF_MAX_S", 0.0))
            stack.enter_context(mock.patch.object(va, "DEBUG_SAVE_AUDIO", False))
            stack.enter_context(mock.patch.object(va.time, "sleep", return_value=None))

            mock_rec = stack.enter_context(
                mock.patch.object(va.sd, "rec", side_effect=[RuntimeError("temp audio failure"), self.audio])
            )

            recorded = va.record_audio(1, label="test")

        self.assertEqual(mock_rec.call_count, 2)
        self.assertEqual(recorded.shape, self.audio.shape)

    def test_stt_error_is_spoken_as_recovery_message(self) -> None:
        tts = FakeTTS()
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "MULTI_TURN_ENABLED", False))
            stack.enter_context(mock.patch.object(va, "NO_SPEECH_RETRY_LIMIT", 0))
            stack.enter_context(mock.patch.object(va, "record_audio", return_value=self.audio))
            stack.enter_context(mock.patch.object(va, "transcribe", return_value=""))
            stack.enter_context(
                mock.patch.object(va, "get_last_stt_error", return_value="Deepgram transcription timed out.")
            )

            va.handle_wake_session(object(), tts, history)

        spoken = [text for text, _ in tts.spoken]
        self.assertIn("Deepgram transcription timed out.", spoken)

    def test_codex_command_builder_injects_fast_defaults(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "CODEX_MODEL_NAME", "gpt-5.3-codex"))
            stack.enter_context(mock.patch.object(va, "CODEX_REASONING_LEVEL", "low"))

            command = va.build_codex_cli_command("codex exec")

        self.assertIn("codex exec", command)
        self.assertIn("-m gpt-5.3-codex", command)
        self.assertIn("model_reasoning_effort=low", command)

    def test_query_backend_codex_uses_normalized_command(self) -> None:
        history = []

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "ASSISTANT_BACKEND", "codex_cli"))
            stack.enter_context(mock.patch.object(va, "CODEX_CLI_COMMAND", "codex exec"))
            stack.enter_context(mock.patch.object(va, "CODEX_MODEL_NAME", "gpt-5.3-codex"))
            stack.enter_context(mock.patch.object(va, "CODEX_REASONING_LEVEL", "low"))

            mock_query_cli = stack.enter_context(
                mock.patch.object(va, "query_cli_backend", return_value="ok")
            )

            result = va.query_backend("hello", history)

        self.assertEqual(result, "ok")
        normalized_command = mock_query_cli.call_args.args[0]
        self.assertIn("-m gpt-5.3-codex", normalized_command)
        self.assertIn("model_reasoning_effort=low", normalized_command)

    def test_codex_command_builder_does_not_duplicate_existing_flags(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(va, "CODEX_MODEL_NAME", "gpt-5.3-codex"))
            stack.enter_context(mock.patch.object(va, "CODEX_REASONING_LEVEL", "low"))

            command = va.build_codex_cli_command(
                "codex exec -m gpt-5.3-codex -c model_reasoning_effort=low"
            )

        self.assertEqual(command.count("-m gpt-5.3-codex"), 1)
        self.assertEqual(command.count("model_reasoning_effort=low"), 1)

    def test_barge_in_tts_prevents_parallel_overlap_on_lingering_stop(self) -> None:
        tracker = {
            "active": 0,
            "max_active": 0,
            "lock": threading.Lock(),
        }

        def engine_factory() -> _SlowStopEngine:
            return _SlowStopEngine(tracker=tracker, linger_after_stop_s=2.2)

        tts = va.BargeInTTS()

        with mock.patch.object(va.pyttsx3, "init", side_effect=engine_factory):
            tts.speak("first", allow_barge_in=False)
            tts.speak("second", allow_barge_in=False)

        self.assertEqual(
            tracker["max_active"],
            1,
            "Expected serialized playback; overlapping TTS workers indicate duplicate audio race.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
