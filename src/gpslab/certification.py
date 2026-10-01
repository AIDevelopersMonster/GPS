from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

RINV_MAGIC = b"GLP1"
RINV_DATA_LEN = 30
RINV_BINARY_FLAG = 0x02
RINV_MODULE_ID_LEN = 8
RINV_KEY_ID_LEN = 4
RINV_RECEIPT_HASH_LEN = 10


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def unix_seconds_from_iso(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(dt.timestamp())


def module_id_text(module_id: bytes) -> str:
    if len(module_id) != RINV_MODULE_ID_LEN:
        raise ValueError("module_id must be 8 bytes")
    h = module_id.hex().upper()
    return f"GPS6-{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


def public_key_raw(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    return hashlib.sha256(public_key_raw(public_key)).hexdigest().upper()


def station_key_id(public_key: Ed25519PublicKey) -> bytes:
    return hashlib.sha256(public_key_raw(public_key)).digest()[:RINV_KEY_ID_LEN]


@dataclass(frozen=True)
class RINVPassRecord:
    module_id: bytes
    tested_at_unix: int
    station_key_id: bytes
    receipt_hash_prefix: bytes

    def pack(self) -> bytes:
        if len(self.module_id) != RINV_MODULE_ID_LEN:
            raise ValueError("module_id must be 8 bytes")
        if len(self.station_key_id) != RINV_KEY_ID_LEN:
            raise ValueError("station_key_id must be 4 bytes")
        if len(self.receipt_hash_prefix) != RINV_RECEIPT_HASH_LEN:
            raise ValueError("receipt_hash_prefix must be 10 bytes")

        data = (
            RINV_MAGIC
            + self.module_id
            + int(self.tested_at_unix).to_bytes(4, "big", signed=False)
            + self.station_key_id
            + self.receipt_hash_prefix
        )
        if len(data) != RINV_DATA_LEN:
            raise AssertionError("RINV record must be exactly 30 bytes")
        return data

    @classmethod
    def unpack(cls, data: bytes) -> "RINVPassRecord":
        if len(data) != RINV_DATA_LEN:
            raise ValueError("RINV record must be exactly 30 bytes")
        if data[:4] != RINV_MAGIC:
            raise ValueError("not a GPS Lab PASS v1 RINV record")
        return cls(
            module_id=data[4:12],
            tested_at_unix=int.from_bytes(data[12:16], "big"),
            station_key_id=data[16:20],
            receipt_hash_prefix=data[20:30],
        )

    def to_dict(self) -> dict[str, Any]:
        tested = datetime.fromtimestamp(self.tested_at_unix, tz=timezone.utc)
        return {
            "format": RINV_MAGIC.decode("ascii"),
            "module_id": module_id_text(self.module_id),
            "module_id_hex": self.module_id.hex().upper(),
            "tested_at_unix": self.tested_at_unix,
            "tested_at_utc": tested.isoformat().replace("+00:00", "Z"),
            "station_key_id": self.station_key_id.hex().upper(),
            "receipt_hash_prefix": self.receipt_hash_prefix.hex().upper(),
            "rinv_hex": self.pack().hex(" ").upper(),
        }


def make_core(
    *,
    module_id: bytes,
    tested_at_utc: str,
    station_name: str,
    station_public_key_sha256: str,
    profile: str,
    receiver: dict[str, Any],
    checks: list[dict[str, Any]],
    measurements: dict[str, Any],
) -> dict[str, Any]:
    passed = all(bool(item.get("pass")) for item in checks)
    return {
        "schema": "gpslab-attestation-core-v1",
        "module_id": module_id_text(module_id),
        "module_id_hex": module_id.hex().upper(),
        "tested_at_utc": tested_at_utc,
        "station": {
            "name": station_name,
            "public_key_sha256": station_public_key_sha256,
        },
        "test": {
            "profile": profile,
            "result": "PASS" if passed else "FAIL",
            "checks": checks,
            "measurements": measurements,
        },
        "receiver": receiver,
    }


def build_rinv_record(core: dict[str, Any], public_key: Ed25519PublicKey) -> RINVPassRecord:
    if core["test"]["result"] != "PASS":
        raise ValueError("refusing to build PASS RINV record for a failed test")
    module_id = bytes.fromhex(core["module_id_hex"])
    core_hash = hashlib.sha256(canonical_json(core)).digest()
    return RINVPassRecord(
        module_id=module_id,
        tested_at_unix=unix_seconds_from_iso(core["tested_at_utc"]),
        station_key_id=station_key_id(public_key),
        receipt_hash_prefix=core_hash[:RINV_RECEIPT_HASH_LEN],
    )


def create_signed_receipt(
    *,
    core: dict[str, Any],
    rinv: RINVPassRecord,
    write_evidence: dict[str, Any],
    private_key: Ed25519PrivateKey,
    public_key: Ed25519PublicKey,
) -> dict[str, Any]:
    unsigned = {
        "schema": "gpslab-certification-receipt-v1",
        "core": core,
        "rinv": rinv.to_dict(),
        "write_evidence": write_evidence,
        "signature": {
            "algorithm": "Ed25519",
            "public_key_sha256": public_key_fingerprint(public_key),
        },
    }
    signed_bytes = canonical_json(unsigned)
    signature = private_key.sign(signed_bytes)
    receipt_id = hashlib.sha256(signed_bytes + signature).hexdigest().upper()
    receipt = dict(unsigned)
    receipt["signature"] = dict(unsigned["signature"])
    receipt["signature"]["value_base64"] = base64.b64encode(signature).decode("ascii")
    receipt["receipt_id"] = receipt_id
    return receipt


def verify_receipt(receipt: dict[str, Any], trusted_public_key: Ed25519PublicKey) -> dict[str, Any]:
    signature_info = dict(receipt.get("signature") or {})
    signature_b64 = signature_info.pop("value_base64", None)
    receipt_id = receipt.get("receipt_id")
    if not signature_b64 or not receipt_id:
        raise ValueError("receipt is missing signature or receipt_id")

    unsigned = {
        "schema": receipt.get("schema"),
        "core": receipt.get("core"),
        "rinv": receipt.get("rinv"),
        "write_evidence": receipt.get("write_evidence"),
        "signature": signature_info,
    }
    signed_bytes = canonical_json(unsigned)
    signature = base64.b64decode(signature_b64)
    trusted_public_key.verify(signature, signed_bytes)

    expected_id = hashlib.sha256(signed_bytes + signature).hexdigest().upper()
    if expected_id != receipt_id:
        raise ValueError("receipt_id mismatch")

    fingerprint = public_key_fingerprint(trusted_public_key)
    if signature_info.get("public_key_sha256") != fingerprint:
        raise ValueError("receipt public-key fingerprint does not match trusted key")

    rinv_hex = (receipt.get("rinv") or {}).get("rinv_hex", "").replace(" ", "")
    record = RINVPassRecord.unpack(bytes.fromhex(rinv_hex))
    core = receipt.get("core") or {}
    core_hash = hashlib.sha256(canonical_json(core)).digest()
    if record.receipt_hash_prefix != core_hash[:RINV_RECEIPT_HASH_LEN]:
        raise ValueError("RINV receipt-hash prefix does not match receipt core")
    if record.module_id.hex().upper() != core.get("module_id_hex"):
        raise ValueError("RINV module ID does not match receipt core")
    if record.station_key_id != station_key_id(trusted_public_key):
        raise ValueError("RINV station key ID does not match trusted key")
    if core.get("test", {}).get("result") != "PASS":
        raise ValueError("receipt does not attest PASS")

    return {
        "valid": True,
        "receipt_id": receipt_id,
        "module_id": core.get("module_id"),
        "tested_at_utc": core.get("tested_at_utc"),
        "profile": core.get("test", {}).get("profile"),
        "station": core.get("station", {}).get("name"),
        "public_key_sha256": fingerprint,
    }


def save_receipt(receipt: dict[str, Any], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    module_id = receipt["core"]["module_id"].replace("/", "_")
    stamp = receipt["core"]["tested_at_utc"].replace(":", "").replace("-", "")
    path = directory / f"{stamp}_{module_id}_{receipt['receipt_id'][:12]}.json"
    path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_private_key(path: Path, password: bytes | None) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("private key is not Ed25519")
    return key


def load_public_key(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("public key is not Ed25519")
    return key


def write_station_keys(
    directory: Path,
    *,
    station_name: str,
    password: bytes,
) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    private_path = directory / "station_private.pem"
    public_path = directory / "station_public.pem"
    metadata_path = directory / "station.json"
    receipts_path = directory / "receipts"

    if private_path.exists() or public_path.exists():
        raise FileExistsError("station key files already exist; refusing to overwrite")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        )
    )
    try:
        os.chmod(private_path, 0o600)
    except OSError:
        pass

    public_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    receipts_path.mkdir(exist_ok=True)

    metadata = {
        "schema": "gpslab-certification-station-v1",
        "station_name": station_name,
        "created_at_utc": utc_now_iso(),
        "algorithm": "Ed25519",
        "public_key_sha256": public_key_fingerprint(public_key),
        "station_key_id": station_key_id(public_key).hex().upper(),
        "public_key_file": public_path.name,
        "private_key_file": private_path.name,
        "receipts_directory": receipts_path.name,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def new_module_id() -> bytes:
    return secrets.token_bytes(RINV_MODULE_ID_LEN)
