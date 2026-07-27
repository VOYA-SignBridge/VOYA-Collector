"""Ed25519 signing for SOT — the "only registered machines can write" boundary.

Trust model (identical code everywhere, secret differs):
  - Each registered machine holds its OWN Ed25519 private key, stored OUTSIDE
    the repo (default ~/.voya/sot_private.key), so it is never committed and
    never pushed to GitHub. A server that pulls the code gets everything EXCEPT
    the private key, so it cannot sign — hence cannot publish.
  - Public keys of registered machines are committed to app/sot/authorized_keys.json
    (public keys are not secret). Readers verify against this list. A rogue
    writer cannot add itself without a git commit you control, and versions it
    writes without a matching private key are rejected by every reader.

Ed25519 is used via the `cryptography` package (already present as a dependency
of python-jose[cryptography]); raw 32-byte keys are stored base64.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

# Private key lives OUTSIDE the repo tree so it is never committed / pushed.
DEFAULT_PRIVATE_KEY_PATH = Path(
    os.environ.get("SOT_PRIVATE_KEY_PATH", str(Path.home() / ".voya" / "sot_private.key"))
)
# Public-key allowlist IS committed in the repo (public keys are not secret).
AUTHORIZED_KEYS_PATH = Path(__file__).parent / "authorized_keys.json"


# ---------------------------------------------------------------------------
# Keypair generation / (de)serialization
# ---------------------------------------------------------------------------

def generate_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def private_key_to_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return base64.b64encode(raw).decode("ascii")


def private_key_from_b64(data: str) -> Ed25519PrivateKey:
    raw = base64.b64decode(data.strip())
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def fingerprint(public_b64: str) -> str:
    """Short, human-readable id of a public key (for logs / `keygen` output)."""
    digest = hashlib.sha256(public_b64.encode("ascii")).hexdigest()
    return digest[:16]


# ---------------------------------------------------------------------------
# Private key file I/O (registered machines only)
# ---------------------------------------------------------------------------

def save_private_key(
    private_key: Ed25519PrivateKey, path: Path = DEFAULT_PRIVATE_KEY_PATH, *, force: bool = False
) -> Path:
    """Persist the private key with 0600 perms. Refuses to clobber unless force."""
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(
            f"Private key already exists at {path}. Refuse to overwrite (use force=True). "
            "Overwriting would orphan every version this machine already signed."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(private_key_to_b64(private_key), encoding="ascii")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 (best-effort on Windows)
    except OSError:
        pass
    return path


def load_private_key(path: Path = DEFAULT_PRIVATE_KEY_PATH) -> Ed25519PrivateKey:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No SOT private key at {path}. This machine is NOT registered as a writer "
            "(run `python -m app.sot.cli keygen`). Servers/VPS are read-only by design."
        )
    return private_key_from_b64(path.read_text(encoding="ascii"))


# ---------------------------------------------------------------------------
# Sign / verify
# ---------------------------------------------------------------------------

def sign(private_key: Ed25519PrivateKey, data: bytes) -> str:
    return base64.b64encode(private_key.sign(data)).decode("ascii")


def verify(public_b64: str, data: bytes, signature_b64: str) -> bool:
    """Return True iff `signature_b64` is a valid signature of `data` by public_b64."""
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        pub.verify(base64.b64decode(signature_b64), data)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Authorized-key registry (committed in the repo)
# ---------------------------------------------------------------------------

def load_authorized_keys(path: Path = AUTHORIZED_KEYS_PATH) -> List[Dict[str, str]]:
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON list of key entries")
    return raw


def add_authorized_key(
    name: str, public_b64: str, path: Path = AUTHORIZED_KEYS_PATH, *, today: Optional[date] = None
) -> List[Dict[str, str]]:
    """Append a machine's public key to the allowlist (then the user commits it).

    Idempotent on public_key; a duplicate public key is rejected so re-running
    keygen can't silently create two entries. A duplicate NAME with a different
    key is also rejected — pick a distinct name per machine.
    """
    keys = load_authorized_keys(path)
    for entry in keys:
        if entry.get("public_key") == public_b64:
            raise ValueError(f"Public key already registered under name={entry.get('name')!r}")
        if entry.get("name") == name:
            raise ValueError(f"Name {name!r} already used by a different key; choose another name")
    keys.append(
        {
            "name": name,
            "public_key": public_b64,
            "fingerprint": fingerprint(public_b64),
            "added_at": (today or date.today()).isoformat(),
        }
    )
    Path(path).write_text(json.dumps(keys, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return keys


def verify_with_authorized(
    data: bytes, signature_b64: str, authorized: List[Dict[str, str]]
) -> Optional[str]:
    """Return the NAME of the authorized key that validates the signature, else None.

    None => reject: the content was not signed by any registered machine.
    """
    for entry in authorized:
        pub = entry.get("public_key")
        if pub and verify(pub, data, signature_b64):
            return entry.get("name") or entry.get("fingerprint") or "unknown"
    return None
