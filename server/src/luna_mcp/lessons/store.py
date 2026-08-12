"""Persistent lesson store backed by SQLite."""
import hashlib
import os
import pathlib
import sqlite3
import threading
import time
from dataclasses import dataclass

from luna_mcp.lessons.version_store import VersionStoreMixin


@dataclass
class Lesson:
    build_hash: str
    cmd: str
    pattern_kind: str
    situation: str
    action: str
    outcome: str = ""
    token_cost: int = 0
    hits: int = 0


def _project_namespace(plugin_path: str = "") -> str:
    plugin = plugin_path or os.environ.get("LUNA_PLUGIN_PATH", "")
    if plugin:
        return hashlib.sha256(plugin.encode()).hexdigest()[:12]
    return os.environ.get("LUNA_PROJECT_ID", "default")


class LessonStore(VersionStoreMixin):
    def __init__(self, db_path: pathlib.Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=1.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY,
                build_hash TEXT NOT NULL,
                cmd TEXT NOT NULL,
                pattern_kind TEXT NOT NULL,
                situation TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT DEFAULT '',
                token_cost INTEGER DEFAULT 0,
                hits INTEGER DEFAULT 0,
                last_seen REAL,
                UNIQUE(build_hash, cmd, situation)
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_lookup ON lessons(cmd, build_hash)")
        self._conn.commit()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Add typemap-aware columns if missing. Idempotent."""
        cur = self._conn.execute("PRAGMA table_info(lessons)")
        cols = {row[1] for row in cur.fetchall()}
        additions = []
        if "class_hash" not in cols:
            additions.append("ALTER TABLE lessons ADD COLUMN class_hash TEXT DEFAULT ''")
        if "sig_hash" not in cols:
            additions.append("ALTER TABLE lessons ADD COLUMN sig_hash TEXT DEFAULT ''")
        if "typemap_version" not in cols:
            additions.append("ALTER TABLE lessons ADD COLUMN typemap_version TEXT DEFAULT ''")
        if "deprecated" not in cols:
            additions.append("ALTER TABLE lessons ADD COLUMN deprecated INTEGER DEFAULT 0")
        if "source" not in cols:
            additions.append("ALTER TABLE lessons ADD COLUMN source TEXT DEFAULT 'user'")
        for sql in additions:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        if additions:
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_typemap ON lessons(class_hash, sig_hash, deprecated)"
            )
            self._conn.commit()

    def add(self, lesson: Lesson, update_action: bool = False) -> None:
        update_clause = "hits=hits+1, last_seen=excluded.last_seen"
        if update_action:
            update_clause += ", action=excluded.action, outcome=excluded.outcome"
        with self._lock:
            self._conn.execute(f"""
                INSERT INTO lessons(build_hash,cmd,pattern_kind,situation,action,outcome,token_cost,hits,last_seen)
                VALUES(?,?,?,?,?,?,?,1,?)
                ON CONFLICT(build_hash,cmd,situation) DO UPDATE SET
                    {update_clause}
            """, (
                lesson.build_hash, lesson.cmd, lesson.pattern_kind,
                lesson.situation, lesson.action, lesson.outcome,
                lesson.token_cost, time.time(),
            ))
            self._conn.commit()

    def find(self, cmd: str, build_hash: str, situation_substr: str = "") -> list:
        pattern = f"%{situation_substr}%" if situation_substr else "%"
        with self._lock:
            cur = self._conn.execute("""
                SELECT build_hash,cmd,pattern_kind,situation,action,outcome,token_cost,hits
                FROM lessons
                WHERE cmd=? AND (build_hash=? OR build_hash='*') AND situation LIKE ?
                ORDER BY (build_hash=?) DESC, hits DESC
                LIMIT 5
            """, (cmd, build_hash, pattern, build_hash))
            cols = ["build_hash", "cmd", "pattern_kind", "situation", "action", "outcome", "token_cost", "hits"]
            return [Lesson(**dict(zip(cols, row))) for row in cur.fetchall()]

    def find_by_kind(self, cmd: str, pattern_kind: str, limit: int = 10) -> list:
        """Find lessons by exact pattern_kind. No build_hash filter — used by domain experts."""
        with self._lock:
            cur = self._conn.execute("""
                SELECT build_hash,cmd,pattern_kind,situation,action,outcome,token_cost,hits
                FROM lessons
                WHERE cmd=? AND pattern_kind=?
                ORDER BY hits DESC
                LIMIT ?
            """, (cmd, pattern_kind, limit))
            cols = ["build_hash", "cmd", "pattern_kind", "situation", "action", "outcome", "token_cost", "hits"]
            return [Lesson(**dict(zip(cols, row))) for row in cur.fetchall()]

    def prune(self, max_rows: int = 500) -> int:
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            if count <= max_rows:
                return 0
            to_delete = count - max_rows
            self._conn.execute(
                "DELETE FROM lessons WHERE id IN "
                "(SELECT id FROM lessons ORDER BY hits ASC, last_seen ASC LIMIT ?)",
                (to_delete,),
            )
            self._conn.commit()
            return to_delete

    def add_typemap(self, lesson: Lesson, class_hash: str, sig_hash: str,
                    typemap_version: str, source: str = "user") -> None:
        """Upsert lesson with typemap-aware key. source='seed' always updates action."""
        update_action = "CASE WHEN excluded.source='seed' THEN excluded.action ELSE action END"
        with self._lock:
            self._conn.execute(f"""
                INSERT INTO lessons(build_hash, cmd, pattern_kind, situation, action, outcome,
                                    token_cost, hits, last_seen, class_hash, sig_hash,
                                    typemap_version, deprecated, source)
                VALUES('*', ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(build_hash, cmd, situation) DO UPDATE SET
                  hits=hits+1, last_seen=excluded.last_seen,
                  action={update_action},
                  deprecated=0, source=excluded.source
            """, (
                lesson.cmd, lesson.pattern_kind, lesson.situation, lesson.action,
                lesson.outcome, lesson.token_cost, time.time(),
                class_hash, sig_hash, typemap_version, source,
            ))
            self._conn.commit()

    def find_typemap(self, cmd: str, class_hash: str, situation_substr: str = "") -> list:
        """Lookup lessons by typemap class key. Survives build changes."""
        pattern = f"%{situation_substr}%" if situation_substr else "%"
        with self._lock:
            cur = self._conn.execute("""
                SELECT build_hash, cmd, pattern_kind, situation, action, outcome, token_cost, hits
                FROM lessons
                WHERE cmd=? AND class_hash=? AND deprecated=0 AND situation LIKE ?
                ORDER BY hits DESC LIMIT 5
            """, (cmd, class_hash, pattern))
            cols = ["build_hash", "cmd", "pattern_kind", "situation", "action", "outcome", "token_cost", "hits"]
            return [Lesson(**dict(zip(cols, row))) for row in cur.fetchall()]

    def deprecate_by_signature_change(self, class_hash: str, new_sig_hash: str) -> int:
        """Mark lessons deprecated when class signature changed. Returns count."""
        with self._lock:
            cur = self._conn.execute("""
                UPDATE lessons SET deprecated=1
                WHERE class_hash=? AND sig_hash != ? AND deprecated=0
            """, (class_hash, new_sig_hash))
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        self._conn.close()
