from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import DEFAULT_DB, db_status, ensure_db, export_json, get_inspection, list_inspections
from .registry_reports import backup_database, export_csv, generate_html_report, query_inspections, registry_summary


def cmd_status(args) -> int:
    print(json.dumps(db_status(Path(args.database)), ensure_ascii=False, indent=2))
    return 0


def cmd_create(args) -> int:
    path = ensure_db(Path(args.database))
    print(json.dumps(db_status(path), ensure_ascii=False, indent=2))
    return 0


def cmd_list(args) -> int:
    print(json.dumps(list_inspections(args.limit, Path(args.database)), ensure_ascii=False, indent=2))
    return 0


def cmd_export(args) -> int:
    path = export_json(Path(args.output), Path(args.database))
    print(path)
    return 0


def cmd_show(args) -> int:
    item = get_inspection(args.module_code, Path(args.database))
    if item is None:
        raise SystemExit(f"Module not found: {args.module_code}")
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0


def cmd_find(args) -> int:
    rows = query_inspections(
        module_contains=args.module,
        result=args.result,
        profile=args.profile,
        date_from=args.date_from,
        date_to=args.date_to,
        limit=args.limit,
        db_path=Path(args.database),
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args) -> int:
    print(json.dumps(registry_summary(Path(args.database)), ensure_ascii=False, indent=2))
    return 0


def cmd_export_csv(args) -> int:
    rows = query_inspections(
        module_contains=args.module,
        result=args.result,
        profile=args.profile,
        date_from=args.date_from,
        date_to=args.date_to,
        limit=args.limit,
        db_path=Path(args.database),
    )
    path = export_csv(Path(args.output), db_path=Path(args.database), rows=rows)
    print(path)
    return 0


def cmd_report(args) -> int:
    path = generate_html_report(
        Path(args.output),
        module_code=args.module_code,
        db_path=Path(args.database),
    )
    print(path)
    return 0


def cmd_backup(args) -> int:
    path = backup_database(Path(args.output), Path(args.database))
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gps-registry", description="GPS Lab inspection registry")
    p.add_argument("--database", default=str(DEFAULT_DB))
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("status")
    q.set_defaults(func=cmd_status)

    q = sub.add_parser("create")
    q.set_defaults(func=cmd_create)

    q = sub.add_parser("list")
    q.add_argument("--limit", type=int, default=100)
    q.set_defaults(func=cmd_list)

    q = sub.add_parser("export-json")
    q.add_argument("output")
    q.set_defaults(func=cmd_export)

    q = sub.add_parser("show")
    q.add_argument("module_code")
    q.set_defaults(func=cmd_show)

    q = sub.add_parser("find")
    q.add_argument("--module")
    q.add_argument("--result")
    q.add_argument("--profile")
    q.add_argument("--date-from")
    q.add_argument("--date-to")
    q.add_argument("--limit", type=int, default=100)
    q.set_defaults(func=cmd_find)

    q = sub.add_parser("summary")
    q.set_defaults(func=cmd_summary)

    q = sub.add_parser("export-csv")
    q.add_argument("output")
    q.add_argument("--module")
    q.add_argument("--result")
    q.add_argument("--profile")
    q.add_argument("--date-from")
    q.add_argument("--date-to")
    q.add_argument("--limit", type=int, default=1000000)
    q.set_defaults(func=cmd_export_csv)

    q = sub.add_parser("report")
    q.add_argument("output")
    q.add_argument("--module-code")
    q.set_defaults(func=cmd_report)

    q = sub.add_parser("backup")
    q.add_argument("output")
    q.set_defaults(func=cmd_backup)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
