from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import DEFAULT_DB, db_status, ensure_db, export_json, list_inspections


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
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
