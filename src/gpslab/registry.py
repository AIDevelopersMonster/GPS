from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_SCHEMA_VERSION = 1
DEFAULT_DB = Path.home() / ".gpslab" / "gpslab.sqlite3"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_db(path: Path = DEFAULT_DB) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL UNIQUE,
                tested_at_utc TEXT NOT NULL,
                board TEXT,
                receiver TEXT,
                sw_version TEXT,
                hw_version TEXT,
                result TEXT NOT NULL,
                profile TEXT NOT NULL,
                rinv_before TEXT,
                rinv_after TEXT,
                payload_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_inspections_tested_at ON inspections(tested_at_utc)")
        con.execute("PRAGMA user_version = 1")
    return path


def next_module_code(con: sqlite3.Connection, tested_at_utc: str) -> str:
    dt = datetime.fromisoformat(tested_at_utc.replace("Z", "+00:00"))
    year = dt.year
    row = con.execute(
        "SELECT module_code FROM inspections WHERE module_code LIKE ? ORDER BY id DESC LIMIT 1",
        (f"GPS6-{year}-%",),
    ).fetchone()
    seq = 1
    if row:
        try:
            seq = int(row[0].rsplit("-", 1)[1]) + 1
        except Exception:
            seq = 1
    return f"GPS6-{year}-{seq:05d}"


def build_rinv_text(module_code: str, tested_at_utc: str) -> str:
    dt = datetime.fromisoformat(tested_at_utc.replace("Z", "+00:00"))
    # 30-byte CFG-RINV budget; ASCII and human-readable.
    text = f"GPSLAB {module_code} {dt:%Y%m%d}"
    if len(text.encode("ascii")) > 30:
        raise ValueError("RINV text exceeds 30 bytes")
    return text


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if isinstance(value, bytes):
        return {"hex": value.hex().upper()}
    return value


def add_inspection(
    *,
    payload: dict[str, Any],
    board: str,
    receiver: str,
    sw_version: str | None,
    hw_version: str | None,
    result: str,
    profile: str = "NEO6M-LAB-01",
    tested_at_utc: str | None = None,
    rinv_before: str | None = None,
    rinv_after: str | None = None,
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any]:
    tested_at_utc = tested_at_utc or utc_now_iso()
    db_path = ensure_db(db_path)
    with sqlite3.connect(db_path) as con:
        module_code = next_module_code(con, tested_at_utc)
        con.execute(
            """
            INSERT INTO inspections (
                module_code, tested_at_utc, board, receiver, sw_version, hw_version,
                result, profile, rinv_before, rinv_after, payload_json, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                module_code,
                tested_at_utc,
                board,
                receiver,
                sw_version,
                hw_version,
                result,
                profile,
                rinv_before,
                rinv_after,
                json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True),
                utc_now_iso(),
            ),
        )
        inspection_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {
        "id": inspection_id,
        "module_code": module_code,
        "tested_at_utc": tested_at_utc,
        "rinv_text": build_rinv_text(module_code, tested_at_utc),
        "database": str(db_path),
    }


def update_rinv(module_code: str, rinv_after: str, db_path: Path = DEFAULT_DB) -> None:
    db_path = ensure_db(db_path)
    with sqlite3.connect(db_path) as con:
        cur = con.execute(
            "UPDATE inspections SET rinv_after=? WHERE module_code=?",
            (rinv_after, module_code),
        )
        if cur.rowcount != 1:
            raise KeyError(module_code)


def list_inspections(limit: int = 100, db_path: Path = DEFAULT_DB) -> list[dict[str, Any]]:
    db_path = ensure_db(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT id, module_code, tested_at_utc, board, receiver, sw_version,
                   hw_version, result, profile, rinv_before, rinv_after
            FROM inspections ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def export_json(output: Path, db_path: Path = DEFAULT_DB) -> Path:
    db_path = ensure_db(db_path)
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM inspections ORDER BY id").fetchall()
    data = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        data.append(item)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
