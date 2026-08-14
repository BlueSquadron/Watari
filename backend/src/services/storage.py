"""S3-compatible object storage service for evidence files.

Uses boto3 with synchronous calls wrapped in `asyncio.to_thread` so the
async event loop stays responsive. MinIO and AWS S3 are both supported
via the `S3_ENDPOINT_URL` configuration.

Responsibilities:
- Upload bytes to a tenant/case-scoped S3 key
- Download objects to bytes
- Delete objects
- SHA256 hash computation (streaming-friendly)
- Password-protected encryption/decryption via AES-256-GCM with a key
  derived from the password using scrypt (industry-standard KDF)
- Ensure the configured bucket exists (one-time setup)
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from typing import cast

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from src.utils import get_settings

_SCRYPT_N = 2**15  # ~32MB — balances security and responsiveness
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_SALT_LEN = 16
_AESGCM_NONCE_LEN = 12
_AESGCM_KEY_LEN = 32  # 256-bit

_s3_client: BaseClient | None = None
_bucket_ready = False


def _client() -> BaseClient:
    global _s3_client
    if _s3_client is None:
        s = get_settings()
        _s3_client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name="us-east-1",  # MinIO ignores this, AWS uses it
        )
    return _s3_client


def _sync_ensure_bucket() -> None:
    global _bucket_ready
    if _bucket_ready:
        return
    s = get_settings()
    try:
        _client().head_bucket(Bucket=s.s3_bucket_name)
    except ClientError as err:
        code = err.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchBucket", "NotFound"):
            _client().create_bucket(Bucket=s.s3_bucket_name)
        else:
            raise
    _bucket_ready = True


async def ensure_bucket() -> None:
    await asyncio.to_thread(_sync_ensure_bucket)


def build_key(tenant_id: str, case_id: str, storage_uuid: str) -> str:
    """Build an S3 key that namespaces evidence per tenant and case."""
    return f"evidence/{tenant_id}/{case_id}/{storage_uuid}"


def compute_sha256(data: bytes) -> str:
    """Return the hex SHA-256 of the given bytes."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Password-based encryption helpers
# ---------------------------------------------------------------------------


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=_AESGCM_KEY_LEN,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_with_password(plaintext: bytes, password: str) -> bytes:
    """Encrypt plaintext with AES-256-GCM using a scrypt-derived key.

    Output layout: salt(16) || nonce(12) || ciphertext+tag
    """
    salt = os.urandom(_SCRYPT_SALT_LEN)
    nonce = os.urandom(_AESGCM_NONCE_LEN)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return salt + nonce + ct


def decrypt_with_password(ciphertext: bytes, password: str) -> bytes:
    """Decrypt a payload produced by `encrypt_with_password`.

    Raises `cryptography.exceptions.InvalidTag` on wrong password or
    tampered ciphertext.
    """
    if len(ciphertext) < _SCRYPT_SALT_LEN + _AESGCM_NONCE_LEN + 16:
        raise ValueError("ciphertext too short")
    salt = ciphertext[:_SCRYPT_SALT_LEN]
    nonce = ciphertext[_SCRYPT_SALT_LEN : _SCRYPT_SALT_LEN + _AESGCM_NONCE_LEN]
    ct = ciphertext[_SCRYPT_SALT_LEN + _AESGCM_NONCE_LEN :]
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, associated_data=None)


# ---------------------------------------------------------------------------
# S3 operations (async wrappers around sync boto3)
# ---------------------------------------------------------------------------


async def upload_bytes(
    key: str, data: bytes, content_type: str = "application/octet-stream"
) -> None:
    await ensure_bucket()
    s = get_settings()
    await asyncio.to_thread(
        _client().put_object,
        Bucket=s.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


async def download_bytes(key: str) -> bytes:
    s = get_settings()
    obj = await asyncio.to_thread(_client().get_object, Bucket=s.s3_bucket_name, Key=key)
    body = obj["Body"]
    data = await asyncio.to_thread(body.read)
    return cast(bytes, data)


async def delete_object(key: str) -> None:
    s = get_settings()
    try:
        await asyncio.to_thread(_client().delete_object, Bucket=s.s3_bucket_name, Key=key)
    except ClientError:
        # Deleting a non-existent object is acceptable
        pass


async def object_exists(key: str) -> bool:
    s = get_settings()
    try:
        await asyncio.to_thread(_client().head_object, Bucket=s.s3_bucket_name, Key=key)
        return True
    except ClientError:
        return False


__all__ = [
    "ensure_bucket",
    "build_key",
    "compute_sha256",
    "encrypt_with_password",
    "decrypt_with_password",
    "upload_bytes",
    "download_bytes",
    "delete_object",
    "object_exists",
]
