"""Nightly database copies and restore (phase 6)."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.backup import backup_database, list_backups, restore_database
from scripts.set_password import write_hash

NOW = datetime(2026, 10, 18, 3, 30, tzinfo=UTC)


def make_db(path: Path, value: str) -> str:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")
        conn.execute("DELETE FROM t")
        conn.execute("INSERT INTO t VALUES (?)", (value,))
    return f"sqlite:///{path}"


def read(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        return str(conn.execute("SELECT v FROM t").fetchone()[0])


def test_backup_copies_the_database_and_keeps_only_the_last_ones(tmp_path: Path) -> None:
    url = make_db(tmp_path / "app.db", "night 0")
    backups = tmp_path / "backups"
    for night in range(4):
        backup_database(url, backups, keep=3, now=NOW + timedelta(days=night))

    copies = list_backups(backups)
    assert [p.name for p in copies] == [
        "app_sport-20261021-033000.db",
        "app_sport-20261020-033000.db",
        "app_sport-20261019-033000.db",
    ]
    assert read(copies[0]) == "night 0"


def test_restore_puts_a_copy_back_and_keeps_the_current_one_aside(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    url = make_db(db, "before")
    copy = backup_database(url, tmp_path / "backups", keep=14, now=NOW)
    assert copy is not None
    make_db(db, "after a mistake")

    aside = restore_database(url, copy)

    assert read(db) == "before"
    assert read(aside) == "after a mistake"


def test_no_backup_without_a_sqlite_file(tmp_path: Path) -> None:
    assert backup_database("sqlite://", tmp_path, keep=3, now=NOW) is None
    assert backup_database(f"sqlite:///{tmp_path / 'missing.db'}", tmp_path, 3, NOW) is None


def test_set_password_replaces_only_its_line(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("APP_ENV=development\nAPP_PASSWORD_HASH=\nLOG_LEVEL=INFO\n")
    write_hash(env, "$argon2id$v=19$m=65536$abc")
    assert env.read_text() == (
        "APP_ENV=development\nAPP_PASSWORD_HASH='$argon2id$v=19$m=65536$abc'\nLOG_LEVEL=INFO\n"
    )
    write_hash(tmp_path / "new.env", "$argon2id$x")
    assert (tmp_path / "new.env").read_text() == "APP_PASSWORD_HASH='$argon2id$x'\n"
