"""Signing key: ``ensure_signing_key`` and the RFC 7638 ``kid`` (Req 5.1-5.5, 11.4, D-031)."""

import base64
import io
import stat
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django.fixtures import Settings

from accounts import keys


@pytest.fixture
def key_path(tmp_path: Path, settings: Settings) -> Path:
    path = tmp_path / "keys" / "signing.pem"
    settings.AUTH_SIGNING_KEY_PATH = path
    return path


def _run() -> str:
    out = io.StringIO()
    call_command("ensure_signing_key", stdout=out, stderr=out)
    return out.getvalue()


def test_debug_creates_key_once_and_is_idempotent(key_path: Path, settings: Settings) -> None:
    settings.DEBUG = True

    first_output = _run()
    assert key_path.is_file()
    original = key_path.read_bytes()
    key = keys.load_private_key(key_path)
    assert key.key_size == 2048
    _, kid = keys.public_jwk_and_kid(key)
    assert f"kid={kid}" in first_output

    second_output = _run()
    assert key_path.read_bytes() == original
    assert "present" in second_output

    # Never prints key material (Req 5.1, 11.4).
    for output in (first_output, second_output):
        assert "PRIVATE KEY" not in output
        assert original.decode() not in output
    # No temp files left next to the key.
    assert list(key_path.parent.iterdir()) == [key_path]


def test_generated_key_is_mode_0600(key_path: Path, settings: Settings) -> None:
    settings.DEBUG = True
    _run()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


def test_refuses_to_generate_when_debug_off(key_path: Path, settings: Settings) -> None:
    settings.DEBUG = False
    with pytest.raises(CommandError, match="AUTH_SIGNING_KEY_PATH"):
        _run()
    assert not key_path.exists()


def test_existing_valid_key_is_accepted_when_debug_off(key_path: Path, settings: Settings) -> None:
    keys.generate_private_key_file(key_path)
    settings.DEBUG = False
    assert "present" in _run()


@pytest.mark.parametrize("debug", [True, False])
def test_rejects_corrupt_file_and_never_overwrites_it(
    key_path: Path, settings: Settings, debug: bool
) -> None:
    settings.DEBUG = debug
    key_path.parent.mkdir(parents=True)
    key_path.write_bytes(b"-----BEGIN PRIVATE KEY-----\nnot a key\n-----END PRIVATE KEY-----\n")
    with pytest.raises(CommandError, match="AUTH_SIGNING_KEY_PATH") as excinfo:
        _run()
    assert "not a key" not in str(excinfo.value)
    assert key_path.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----\nnot a key")


def test_load_rejects_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "signing.pem"
    keys.generate_private_key_file(path)
    path.chmod(0o000)
    try:
        if path.stat().st_uid == 0:  # root can read anything; nothing to assert
            pytest.skip("running as root")
        with pytest.raises(keys.SigningKeyError, match="not readable"):
            keys.load_private_key(path)
    finally:
        path.chmod(0o600)


# RFC 7638 §3.1 example RSA public key and its documented thumbprint.
RFC7638_N = (
    "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAt"
    "VT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn6"
    "4tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FD"
    "W2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n9"
    "1CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINH"
    "aQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw"
)
RFC7638_E = "AQAB"
RFC7638_THUMBPRINT = "NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs"


def _b64url_to_int(value: str) -> int:
    return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")


def test_rfc7638_known_answer() -> None:
    # The thumbprint ignores non-required members such as alg and kid.
    rfc_jwk = {
        "kty": "RSA",
        "n": RFC7638_N,
        "e": RFC7638_E,
        "alg": "RS256",
        "kid": "2011-04-29",
    }
    assert keys.jwk_thumbprint(rfc_jwk) == RFC7638_THUMBPRINT

    # And our JWK encoding of the same public key reproduces the RFC's members exactly.
    public_key = rsa.RSAPublicNumbers(
        _b64url_to_int(RFC7638_E), _b64url_to_int(RFC7638_N)
    ).public_key()
    assert keys.public_jwk(public_key) == {"kty": "RSA", "n": RFC7638_N, "e": RFC7638_E}


def test_public_jwk_and_kid_agree(tmp_path: Path) -> None:
    key = keys.generate_private_key_file(tmp_path / "signing.pem")
    jwk, kid = keys.public_jwk_and_kid(key)
    assert jwk["kid"] == kid == keys.jwk_thumbprint(jwk)
    assert jwk["kty"] == "RSA"
    assert jwk["alg"] == "RS256"
    assert jwk["use"] == "sig"
    assert "d" not in jwk  # public members only
