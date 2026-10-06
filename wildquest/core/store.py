"""SQLite persistence for quest runs, player progress, events, and latency."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StoredRun:
    run_id: int
    quest_id: str
    state: str
    persona: str
    version: int


@dataclass(frozen=True)
class PlayerProgress:
    xp: int
    streak: int


class QuestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS player_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    xp INTEGER NOT NULL DEFAULT 0 CHECK (xp >= 0),
                    streak INTEGER NOT NULL DEFAULT 0 CHECK (streak >= 0),
                    current_run_id INTEGER REFERENCES quest_runs(id)
                );
                CREATE TABLE IF NOT EXISTS quest_runs (
                    id INTEGER PRIMARY KEY,
                    quest_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN (
                        'offered', 'active', 'verifying', 'completed', 'skipped', 'ended'
                    )),
                    persona TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quest_events (
                    id INTEGER PRIMARY KEY,
                    run_id INTEGER NOT NULL REFERENCES quest_runs(id),
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS llm_latency (
                    id INTEGER PRIMARY KEY,
                    stage TEXT NOT NULL,
                    first_token_ms REAL NOT NULL CHECK (first_token_ms >= 0),
                    total_ms REAL NOT NULL CHECK (total_ms >= 0),
                    success INTEGER NOT NULL CHECK (success IN (0, 1)),
                    created_at TEXT NOT NULL
                );
                INSERT OR IGNORE INTO player_state (id) VALUES (1);
                """
            )

    def current_run(self) -> StoredRun | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT r.id, r.quest_id, r.state, r.persona, r.version
                FROM player_state p
                LEFT JOIN quest_runs r ON r.id = p.current_run_id
                WHERE p.id = 1
                """
            ).fetchone()
        if row is None or row["id"] is None:
            return None
        return StoredRun(row["id"], row["quest_id"], row["state"], row["persona"], row["version"])

    def progress(self) -> PlayerProgress:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT xp, streak FROM player_state WHERE id = 1"
            ).fetchone()
        assert row is not None
        return PlayerProgress(row["xp"], row["streak"])

    def create_run(self, quest_id: str, persona: str) -> StoredRun:
        now = _now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO quest_runs (quest_id, state, persona, created_at, updated_at)
                VALUES (?, 'offered', ?, ?, ?)
                """,
                (quest_id, persona, now, now),
            )
            run_id = int(cursor.lastrowid)
            connection.execute(
                "UPDATE player_state SET current_run_id = ? WHERE id = 1", (run_id,)
            )
            connection.execute(
                """
                INSERT INTO quest_events (run_id, from_state, to_state, reason, created_at)
                VALUES (?, NULL, 'offered', 'quest offered', ?)
                """,
                (run_id, now),
            )
        return StoredRun(run_id, quest_id, "offered", persona, 0)

    def transition(
        self,
        run: StoredRun,
        to_state: str,
        reason: str,
        *,
        xp_award: int = 0,
        completed: bool = False,
        reset_streak: bool = False,
    ) -> StoredRun:
        now = _now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE quest_runs
                SET state = ?, version = version + 1, updated_at = ?
                WHERE id = ? AND state = ? AND version = ?
                """,
                (to_state, now, run.run_id, run.state, run.version),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("quest state changed concurrently")
            if completed:
                connection.execute(
                    "UPDATE player_state SET xp = xp + ?, streak = streak + 1 WHERE id = 1",
                    (xp_award,),
                )
            elif reset_streak:
                connection.execute("UPDATE player_state SET streak = 0 WHERE id = 1")
            connection.execute(
                """
                INSERT INTO quest_events (run_id, from_state, to_state, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run.run_id, run.state, to_state, reason, now),
            )
        return StoredRun(
            run.run_id, run.quest_id, to_state, run.persona, run.version + 1
        )

    def completed_quest_ids(self) -> set[str]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT quest_id FROM quest_runs WHERE state = 'completed'"
            ).fetchall()
        return {row["quest_id"] for row in rows}

    def log_llm_latency(
        self, stage: str, first_token_s: float, total_s: float, success: bool
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO llm_latency
                    (stage, first_token_ms, total_ms, success, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    stage,
                    round(first_token_s * 1000, 3),
                    round(total_s * 1000, 3),
                    int(success),
                    _now(),
                ),
            )

