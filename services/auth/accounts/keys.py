"""The RSA signing key: loading, dev-time generation, and its public JWK (Req 5, D-031).

Key material never leaves this module as text except as the PEM written to disk.
Nothing here logs or prints the private key (Req 5.1, 11.4).
"""

import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_SIZE = 2048
PUBLIC_EXPONENT = 65537


class SigningKeyError(Exception):
    """The key file is missing, unreadable, or isn't an RSA private key."""


def load_private_key(path: Path) -> rsa.RSAPrivateKey:
    """Load the unencrypted PEM private key at ``path``, or raise ``SigningKeyError``."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise SigningKeyError(f"{path} does not exist.") from None
    except OSError as exc:
        raise SigningKeyError(f"{path} is not readable ({exc.strerror}).") from None
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except (ValueError, TypeError):
        # Deliberately no detail from the parser: it must never echo file contents.
        raise SigningKeyError(f"{path} is not a valid unencrypted PEM private key.") from None
    if not isinstance(key, rsa.RSAPrivateKey):
        raise SigningKeyError(f"{path} is not an RSA private key.")
    return key


def generate_private_key_file(path: Path) -> rsa.RSAPrivateKey:
    """Generate an RSA-2048 key and write it to ``path`` atomically with mode 0600.

    The PEM is written to a temp file in the same directory (so the rename stays on one
    filesystem), fsynced, then moved into place with ``os.replace``. Readers see either
    no file or a complete key, never a partial one.
    """
    key = rsa.generate_private_key(public_exponent=PUBLIC_EXPONENT, key_size=KEY_SIZE)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # mkstemp already creates the file 0600; the explicit chmod documents and guarantees it.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(pem)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return key


def _b64url_uint(value: int) -> str:
    """Base64url (no padding) of an unsigned big-endian integer, minimal length (RFC 7518 §6.3)."""
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def jwk_thumbprint(jwk: dict[str, str]) -> str:
    """RFC 7638 thumbprint of an RSA JWK: SHA-256 over the canonical {e, kty, n} JSON."""
    canonical = json.dumps(
        {"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def public_jwk(public_key: rsa.RSAPublicKey) -> dict[str, str]:
    """The RSA public key's required JWK members (RFC 7517/7518)."""
    numbers = public_key.public_numbers()
    return {"kty": "RSA", "n": _b64url_uint(numbers.n), "e": _b64url_uint(numbers.e)}


def public_jwk_and_kid(private_key: rsa.RSAPrivateKey) -> tuple[dict[str, str], str]:
    """The JWKS entry for the signing key and its ``kid`` (Req 5.5).

    The ``kid`` is the RFC 7638 thumbprint, so the JWKS entry and the token header
    always agree without any separate configuration.
    """
    jwk = public_jwk(private_key.public_key())
    kid = jwk_thumbprint(jwk)
    return {**jwk, "kid": kid, "alg": "RS256", "use": "sig"}, kid
