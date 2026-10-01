from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_SCHEMA_VERSION = 2
DEFAULT_DB = Path.home() / ".gpslab" / "gpslab.sqlite3"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def db_status(path: Path = DEFAULT_DB) -> dict[str, Any]:
    path = Path(path).expanduser()
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
        "records": 0,
        "schema_version": None,
    }
    if not path.is_file():
        return result

    try:
        uri_path = path.resolve().as_posix()
        with sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True) as con:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='inspections'"
            ).fetchone()
            if row:
                result["records"] = int(
                    con.execute("SELECT COUNT(*) FROM inspections").fetchone()[0]
                )
            result["schema_version"] = int(
                con.execute("PRAGMA user_version").fetchone()[0]
            )
    except sqlite3.Error as exc:
        result["error"] = str(exc)
    return result


def ensure_db(path: Path = DEFAULT_DB) -> Path:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL UNIQUE,
                factory_id TEXT,
                identity_source TEXT,
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
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(inspections)").fetchall()
        }
        if "factory_id" not in columns:
            con.execute("ALTER TABLE inspections ADD COLUMN factory_id TEXT")
        if "identity_source" not in columns:
            con.execute("ALTER TABLE inspections ADD COLUMN identity_source TEXT")

        con.execute("CREATE INDEX IF NOT EXISTS idx_inspections_tested_at ON inspections(tested_at_utc)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_inspections_factory_id ON inspections(factory_id)")
        con.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")
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


def preview_next_module_code(
    tested_at_utc: str | None = None,
    db_path: Path = DEFAULT_DB,
) -> str:
    tested_at_utc = tested_at_utc or utc_now_iso()
    path = Path(db_path).expanduser()
    if not path.is_file():
        dt = datetime.fromisoformat(tested_at_utc.replace("Z", "+00:00"))
        return f"GPS6-{dt.year}-00001"
    with sqlite3.connect(path) as con:
        return next_module_code(con, tested_at_utc)


def build_rinv_text(module_code: str, tested_at_utc: str) -> str:
    dt = datetime.fromisoformat(tested_at_utc.replace("Z", "+00:00"))
    # 30-byte CFG-RINV budget; ASCII and human-readable.
    text = f"{module_code} {dt:%Y%m%d} OK"
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


def add_factory_inspection(
    *,
    factory_id: str,
    payload: dict[str, Any],
    board: str,
    receiver: str,
    sw_version: str | None,
    hw_version: str | None,
    result: str = "PASS",
    profile: str = "PCAS-TIME-01",
    identity_source: str = "PCAS06,1",
    tested_at_utc: str | None = None,
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Insert/update a factory-identified receiver without inventing a local module ID.

    The factory identifier itself is used as module_code so the registry remains
    simple and human-readable. If the same factory ID is seen again, the existing
    row is refreshed instead of creating duplicates.
    """
    factory_id = factory_id.strip()
    if not factory_id:
        raise ValueError("factory_id must not be empty")

    tested_at_utc = tested_at_utc or utc_now_iso()
    db_path = ensure_db(db_path)
    payload_json = json.dumps(
        _json_ready(payload), ensure_ascii=False, sort_keys=True
    )
    created_at = utc_now_iso()

    with sqlite3.connect(db_path) as con:
        existing = con.execute(
            """
            SELECT id, module_code
            FROM inspections
            WHERE factory_id=? OR module_code=?
            ORDER BY id DESC LIMIT 1
            """,
            (factory_id, factory_id),
        ).fetchone()

        if existing:
            inspection_id = int(existing[0])
            module_code = str(existing[1])
            con.execute(
                """
                UPDATE inspections
                SET factory_id=?, identity_source=?, tested_at_utc=?, board=?,
                    receiver=?, sw_version=?, hw_version=?, result=?, profile=?,
                    payload_json=?
                WHERE id=?
                """,
                (
                    factory_id,
                    identity_source,
                    tested_at_utc,
                    board,
                    receiver,
                    sw_version,
                    hw_version,
                    result,
                    profile,
                    payload_json,
                    inspection_id,
                ),
            )
            created = False
        else:
            module_code = factory_id
            con.execute(
                """
                INSERT INTO inspections (
                    module_code, factory_id, identity_source, tested_at_utc,
                    board, receiver, sw_version, hw_version, result, profile,
                    rinv_before, rinv_after, payload_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    module_code,
                    factory_id,
                    identity_source,
                    tested_at_utc,
                    board,
                    receiver,
                    sw_version,
                    hw_version,
                    result,
                    profile,
                    None,
                    None,
                    payload_json,
                    created_at,
                ),
            )
            inspection_id = int(
                con.execute("SELECT last_insert_rowid()").fetchone()[0]
            )
            created = True

    return {
        "id": inspection_id,
        "module_code": module_code,
        "factory_id": factory_id,
        "tested_at_utc": tested_at_utc,
        "database": str(db_path),
        "created": created,
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
            SELECT id, module_code, factory_id, identity_source, tested_at_utc,
                   board, receiver, sw_version, hw_version, result, profile,
                   rinv_before, rinv_after
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


def update_inspection(
    module_code: str,
    *,
    result: str | None = None,
    rinv_after: str | None = None,
    payload: dict[str, Any] | None = None,
    db_path: Path = DEFAULT_DB,
) -> None:
    path = Path(db_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)

    sets: list[str] = []
    values: list[Any] = []
    if result is not None:
        sets.append("result=?")
        values.append(result)
    if rinv_after is not None:
        sets.append("rinv_after=?")
        values.append(rinv_after)
    if payload is not None:
        sets.append("payload_json=?")
        values.append(json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True))
    if not sets:
        return

    values.append(module_code)
    with sqlite3.connect(path) as con:
        cur = con.execute(
            f"UPDATE inspections SET {', '.join(sets)} WHERE module_code=?",
            tuple(values),
        )
        if cur.rowcount != 1:
            raise KeyError(module_code)


def get_inspection(module_code: str, db_path: Path = DEFAULT_DB) -> dict[str, Any] | None:
    path = Path(db_path).expanduser()
    if not path.is_file():
        return None
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM inspections WHERE module_code=?",
            (module_code,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item


def find_inspection_by_rinv(
    rinv_text: str,
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any] | None:
    path = Path(db_path).expanduser()
    if not path.is_file():
        return None
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM inspections WHERE rinv_after=? ORDER BY id DESC LIMIT 1",
            (rinv_text,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item
