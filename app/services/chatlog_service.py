"""SQLite log of questions and answers, for reviewing what the agents said."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def save(path: Path, project: str, question: str, answer: str, sources: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as con, con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS chats "
            "(at TEXT, project TEXT, question TEXT, answer TEXT, sources TEXT)"
        )
        con.execute(
            "INSERT INTO chats VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), project, question, answer, json.dumps(sources)),
        )
