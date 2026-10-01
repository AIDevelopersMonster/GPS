from __future__ import annotations

import csv
import html
import json
import sqlite3
from pathlib import Path
from typing import Any

from .registry import DEFAULT_DB, db_status, get_inspection


def query_inspections(
    *,
    module_contains: str | None = None,
    result: str | None = None,
    profile: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 1000,
    db_path: Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    path = Path(db_path).expanduser()
    if not path.is_file():
        return []

    where: list[str] = []
    params: list[Any] = []

    if module_contains:
        where.append("module_code LIKE ?")
        params.append(f"%{module_contains}%")
    if result and result.upper() != "ALL":
        where.append("result = ?")
        params.append(result)
    if profile:
        where.append("profile = ?")
        params.append(profile)
    if date_from:
        where.append("tested_at_utc >= ?")
        params.append(date_from)
    if date_to:
        where.append("tested_at_utc <= ?")
        params.append(date_to)

    sql = (
        "SELECT id, module_code, tested_at_utc, board, receiver, sw_version, "
        "hw_version, result, profile, rinv_before, rinv_after FROM inspections"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, int(limit)))

    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def registry_summary(db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    path = Path(db_path).expanduser()
    status = db_status(path)
    result_data: dict[str, Any] = {
        "database": status,
        "results": {},
        "profiles": {},
        "first_tested_at_utc": None,
        "last_tested_at_utc": None,
    }
    if not path.is_file():
        return result_data

    with sqlite3.connect(path) as con:
        for name, count in con.execute(
            "SELECT result, COUNT(*) FROM inspections GROUP BY result ORDER BY result"
        ):
            result_data["results"][name] = int(count)
        for name, count in con.execute(
            "SELECT profile, COUNT(*) FROM inspections GROUP BY profile ORDER BY profile"
        ):
            result_data["profiles"][name] = int(count)
        row = con.execute(
            "SELECT MIN(tested_at_utc), MAX(tested_at_utc) FROM inspections"
        ).fetchone()
        if row:
            result_data["first_tested_at_utc"] = row[0]
            result_data["last_tested_at_utc"] = row[1]
    return result_data


def export_csv(
    output: Path,
    *,
    db_path: Path = DEFAULT_DB,
    rows: list[dict[str, Any]] | None = None,
) -> Path:
    if rows is None:
        rows = query_inspections(limit=1_000_000, db_path=db_path)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "module_code", "tested_at_utc", "board", "receiver",
        "sw_version", "hw_version", "result", "profile",
        "rinv_before", "rinv_after",
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return output


def backup_database(output: Path, db_path: Path = DEFAULT_DB) -> Path:
    source = Path(db_path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(source)

    output = Path(output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(output) as dst:
        src.backup(dst)
    return output


def generate_html_report(
    output: Path,
    *,
    module_code: str | None = None,
    db_path: Path = DEFAULT_DB,
) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    summary = registry_summary(db_path)
    if module_code:
        item = get_inspection(module_code, db_path)
        if item is None:
            raise KeyError(module_code)
        rows = [item]
        title = f"GPS Lab report - {module_code}"
    else:
        rows = query_inspections(limit=1_000_000, db_path=db_path)
        title = "GPS Lab inspection registry report"

    def esc(value: Any) -> str:
        return html.escape("-" if value is None else str(value))

    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            f"<td>{esc(row.get('id'))}</td>"
            f"<td>{esc(row.get('module_code'))}</td>"
            f"<td>{esc(row.get('tested_at_utc'))}</td>"
            f"<td>{esc(row.get('board'))}</td>"
            f"<td>{esc(row.get('receiver'))}</td>"
            f"<td>{esc(row.get('sw_version'))}</td>"
            f"<td>{esc(row.get('hw_version'))}</td>"
            f"<td>{esc(row.get('result'))}</td>"
            f"<td>{esc(row.get('profile'))}</td>"
            f"<td>{esc(row.get('rinv_after'))}</td>"
            "</tr>"
        )

    details = ""
    if module_code and rows:
        pretty = json.dumps(rows[0].get("payload", {}), ensure_ascii=False, indent=2)
        details = "<h2>Diagnostic snapshot</h2><pre>" + html.escape(pretty) + "</pre>"

    counts = ", ".join(
        f"{html.escape(str(k))}: {int(v)}"
        for k, v in (summary.get("results") or {}).items()
    ) or "none"

    document = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 28px; color: #202124; }}
.meta {{ padding: 12px; background: #f2f4f7; margin: 12px 0 20px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border: 1px solid #d9dde3; padding: 7px 9px; text-align: left; vertical-align: top; }}
th {{ background: #eef1f5; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f7f7f7; padding: 14px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="meta">
<div><b>Database:</b> {esc((summary.get("database") or {}).get("path"))}</div>
<div><b>Records:</b> {esc((summary.get("database") or {}).get("records"))}</div>
<div><b>Results:</b> {html.escape(counts)}</div>
<div><b>UTC range:</b> {esc(summary.get("first_tested_at_utc"))} - {esc(summary.get("last_tested_at_utc"))}</div>
</div>
<table>
<thead><tr>
<th>ID</th><th>Module</th><th>Tested UTC</th><th>Board</th><th>Receiver</th>
<th>SW</th><th>HW</th><th>Result</th><th>Profile</th><th>RINV</th>
</tr></thead>
<tbody>{''.join(body_rows)}</tbody>
</table>
{details}
<p>Engineering record generated by GPS Lab.</p>
</body>
</html>
"""
    output.write_text(document, encoding="utf-8")
    return output
