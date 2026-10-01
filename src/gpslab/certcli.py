from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

from .certification import (
    RINVPassRecord,
    load_public_key,
    verify_receipt,
    write_station_keys,
)


def cmd_init(args) -> int:
    password1 = getpass.getpass("New station private-key passphrase: ").encode("utf-8")
    password2 = getpass.getpass("Repeat passphrase: ").encode("utf-8")
    if not password1:
        raise SystemExit("Refusing empty private-key passphrase.")
    if password1 != password2:
        raise SystemExit("Passphrases do not match.")

    meta = write_station_keys(
        Path(args.directory).expanduser(),
        station_name=args.station_name,
        password=password1,
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nKeep station_private.pem secret. Publish station_public.pem or its fingerprint.")
    return 0


def cmd_verify_receipt(args) -> int:
    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    public_key = load_public_key(Path(args.public_key))
    result = verify_receipt(receipt, public_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_decode_rinv(args) -> int:
    raw = bytes.fromhex(args.hex.replace(" ", ""))
    record = RINVPassRecord.unpack(raw)
    print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gps-cert",
        description="GPS Lab signed certification receipt tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-station", help="Generate an Ed25519 station key pair.")
    p.add_argument("--station-name", required=True)
    p.add_argument(
        "--directory",
        default=str(Path.home() / ".gpslab" / "certification"),
    )
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("verify-receipt", help="Verify a signed local receipt.")
    p.add_argument("receipt")
    p.add_argument("--public-key", required=True)
    p.set_defaults(func=cmd_verify_receipt)

    p = sub.add_parser("decode-rinv", help="Decode a 30-byte GPS Lab PASS RINV record.")
    p.add_argument("hex")
    p.set_defaults(func=cmd_decode_rinv)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
