import sqlite3

from scripts.smoke_test import Timings, extract_transcript, log_timings


def test_extract_transcript_ignores_timestamps() -> None:
    output = "[00:00:00.000 --> 00:00:02.000]  Hello trail!\n"
    assert extract_transcript(output) == "Hello trail!"


def test_extract_transcript_empty_is_safe() -> None:
    assert extract_transcript("whisper_log: silence") == ""


def test_log_timings_writes_sqlite(tmp_path) -> None:
    database = tmp_path / "latency.db"
    log_timings(Timings(5.0, 0.6, 1.0, 1.5, 0.8), "local-llm", "base", database)
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT stt_ms, llm_first_token_ms, llm_total_ms, tts_ms, turn_total_ms "
            "FROM turn_latency"
        ).fetchone()
    assert row == (600.0, 1000.0, 1500.0, 800.0, 7900.0)
