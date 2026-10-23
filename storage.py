"""Penyimpanan riwayat deteksi emosi berbasis SQLite."""

import csv
import io
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'browser',
    face_index  INTEGER NOT NULL DEFAULT 0,
    emotion     TEXT    NOT NULL,
    confidence  REAL    NOT NULL DEFAULT 0,
    scores      TEXT,
    x INTEGER, y INTEGER, w INTEGER, h INTEGER,
    age         INTEGER,
    gender      TEXT,
    snapshot    TEXT
);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans(timestamp);
CREATE INDEX IF NOT EXISTS idx_scans_emotion ON scans(emotion);
"""

EXPORT_COLUMNS = [
    "id", "timestamp", "source", "face_index", "emotion", "confidence",
    "x", "y", "w", "h", "age", "gender", "snapshot",
]


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class EmotionStore:
    def __init__(self, path):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def add_faces(self, faces, source="browser", snapshot=None, timestamp=None):
        timestamp = timestamp or now_iso()
        rows = []
        for i, face in enumerate(faces):
            r = face.get("region") or {}
            rows.append((
                timestamp, source, i, face["dominant_emotion"],
                float(face.get("confidence", 0)), json.dumps(face.get("emotions", {})),
                r.get("x"), r.get("y"), r.get("w"), r.get("h"),
                face.get("age"), face.get("gender"), snapshot if i == 0 else None,
            ))
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                "INSERT INTO scans (timestamp, source, face_index, emotion, confidence,"
                " scores, x, y, w, h, age, gender, snapshot)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()
        return len(rows)

    def recent(self, limit=100, emotion=None):
        query = "SELECT * FROM scans"
        params = []
        if emotion:
            query += " WHERE emotion = ?"
            params.append(emotion)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def stats(self):
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
            by_emotion = self._conn.execute(
                "SELECT emotion, COUNT(*) AS n, AVG(confidence) AS avg_conf"
                " FROM scans GROUP BY emotion ORDER BY n DESC"
            ).fetchall()
            by_hour = self._conn.execute(
                "SELECT substr(timestamp, 1, 13) AS hour, emotion, COUNT(*) AS n"
                " FROM scans GROUP BY hour, emotion ORDER BY hour DESC LIMIT 168"
            ).fetchall()
            span = self._conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM scans"
            ).fetchone()
        return {
            "total": total,
            "first": span[0],
            "last": span[1],
            "by_emotion": {
                r["emotion"]: {"count": r["n"], "avg_confidence": round(r["avg_conf"] or 0, 2)}
                for r in by_emotion
            },
            "by_hour": [dict(r) for r in reversed(by_hour)],
        }

    def clear(self):
        with self._lock:
            n = self._conn.execute("DELETE FROM scans").rowcount
            self._conn.commit()
        return n

    def export_csv(self):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        with self._lock:
            for row in self._conn.execute(
                f"SELECT {', '.join(EXPORT_COLUMNS)} FROM scans ORDER BY id"
            ):
                writer.writerow(list(row))
        return buf.getvalue()

    @staticmethod
    def _row_to_dict(row):
        d = dict(row)
        d["scores"] = json.loads(d["scores"]) if d.get("scores") else {}
        return d
