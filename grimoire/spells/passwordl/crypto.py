# SPDX-License-Identifier: GPL-3.0-or-later
"""PasswordL's vault file (no Qt). Only vetted primitives from the `cryptography` package (python3-cryptography):
nothing here is home-made crypto.

    master password ──Argon2id (salt, 256 MiB, 3 passes, 4 lanes)──▶ key-encryption key
    random 256-bit vault key, sealed with the KEK by ChaCha20-Poly1305
    the vault (JSON), sealed with the vault key by ChaCha20-Poly1305

Each seal has its own random 96-bit nonce and authenticates the file's header (format, KDF parameters, salt) as
associated data, so a changed header fails to open instead of weakening anything. Changing the master password
rewraps the vault key only. A wrong password and a tampered file both raise BadPassword (the AEAD can't tell them
apart, and neither should we).
"""
import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

MAGIC = "grimoire-passwordl"
VERSION = 1
KDF_DEFAULT = {"alg": "argon2id", "memory": 262144, "iterations": 3, "lanes": 4}     # memory in KiB
KDF_LIMITS = {"memory": (65536, 4194304), "iterations": (1, 20), "lanes": (1, 16)}    # refuse silly/hostile headers


class BadPassword(Exception):
    """Wrong master password, or the file was changed."""


class BadFile(Exception):
    """Not a PasswordL vault, or one from a newer version."""


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _unb64(s) -> bytes:
    if not isinstance(s, str):
        raise BadFile("field is not text")
    try:
        return base64.b64decode(s, validate=True)
    except ValueError as e:
        raise BadFile("bad base64") from e


def derive(password: str, salt: bytes, kdf: dict) -> bytes:
    if kdf.get("alg") != "argon2id":
        raise BadFile("unknown key derivation")
    for k, (lo, hi) in KDF_LIMITS.items():
        if not isinstance(kdf.get(k), int) or not lo <= kdf[k] <= hi:
            raise BadFile(f"key derivation {k} out of range")
    return Argon2id(salt=salt, length=32, iterations=kdf["iterations"], lanes=kdf["lanes"],
                    memory_cost=kdf["memory"]).derive(password.encode("utf-8"))


def _aad(header: dict) -> bytes:
    """The header fields that are authenticated with every seal, in a fixed order."""
    return json.dumps({k: header[k] for k in ("magic", "version", "kdf", "salt")}, sort_keys=True,
                      separators=(",", ":")).encode()


class Sealed:
    """An open vault's keys. Holds the vault key while unlocked; forget() drops it."""

    def __init__(self, header: dict, vault_key: bytes):
        self.header = header
        self._key = vault_key

    @classmethod
    def create(cls, password: str, kdf: dict | None = None) -> "Sealed":
        header = {"magic": MAGIC, "version": VERSION, "kdf": dict(kdf or KDF_DEFAULT), "salt": _b64(os.urandom(16))}
        sealed = cls(header, os.urandom(32))
        sealed._wrap(password)
        return sealed

    def _wrap(self, password: str):
        kek = derive(password, _unb64(self.header["salt"]), self.header["kdf"])
        nonce = os.urandom(12)
        self.header["key_nonce"] = _b64(nonce)
        self.header["key"] = _b64(ChaCha20Poly1305(kek).encrypt(nonce, self._key, _aad(self.header)))

    def change_password(self, new_password: str):
        """New salt, new KEK, same vault key (the contents need no re-encryption, but seal() runs next anyway)."""
        self.header["salt"] = _b64(os.urandom(16))
        self._wrap(new_password)

    @classmethod
    def open(cls, blob: bytes, password: str) -> tuple["Sealed", bytes]:
        """(Sealed, the vault's plaintext JSON bytes). Raises BadFile or BadPassword."""
        try:
            header = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise BadFile("not a vault") from e
        if not isinstance(header, dict) or header.get("magic") != MAGIC:
            raise BadFile("not a vault")
        if header.get("version") != VERSION:
            raise BadFile("made by a newer PasswordL")
        if not isinstance(header.get("kdf"), dict):
            raise BadFile("no key derivation")
        kek = derive(password, _unb64(header.get("salt")), header["kdf"])
        aad = _aad(header)
        try:
            key = ChaCha20Poly1305(kek).decrypt(_unb64(header.get("key_nonce")), _unb64(header.get("key")), aad)
            data = ChaCha20Poly1305(key).decrypt(_unb64(header.get("nonce")), _unb64(header.get("data")), aad)
        except (InvalidTag, ValueError) as e:
            raise BadPassword() from e
        return cls({k: header[k] for k in ("magic", "version", "kdf", "salt", "key_nonce", "key")}, key), data

    def seal(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        out = dict(self.header)
        out["nonce"] = _b64(nonce)
        out["data"] = _b64(ChaCha20Poly1305(self._key).encrypt(nonce, plaintext, _aad(self.header)))
        return json.dumps(out, indent=1).encode()

    def forget(self):
        self._key = b""
