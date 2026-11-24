"""Object storage for generated audio: local filesystem or Cloudflare R2.

R2 is S3-compatible, so this uses boto3's S3 client with an R2 endpoint and
path-style addressing. Audio objects never live in the database — the DB stores
the backend name plus the object key, so moving files between local disk and
R2 is a copy job, not a schema change.

Credentials are resolved from the in-memory session store (`zolai_tts.secrets`)
or the environment, and are never persisted.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .paths import objects_dir

Backend = Literal["local", "r2"]


def key_for(kind: str, identifier: str, audio_format: str = "wav") -> str:
    now = datetime.now(UTC)
    safe_id = identifier.replace("/", "_").replace("\\", "_")
    return f"{kind}/{now:%Y/%m}/{safe_id}.{audio_format}"


class StorageBackend:
    name: str = "base"

    def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def local_path(self, key: str) -> Path | None:
        return None

    def presign(self, key: str, expires_seconds: int = 3600) -> str | None:
        return None

    def info(self) -> dict[str, Any]:
        return {"backend": self.name}


@dataclass
class LocalStorage(StorageBackend):
    """Content-addressed-ish storage under the store directory (offline default)."""

    root: Path

    name = "local"

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if not str(candidate).startswith(str(root)):
            raise ValueError(f"Object key escapes the storage root: {key!r}")
        return candidate

    def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_suffix(path.suffix + ".meta.json").write_text(
            json.dumps({"content_type": content_type, "bytes": len(data)}, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()
        meta = path.with_suffix(path.suffix + ".meta.json")
        if meta.exists():
            meta.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def local_path(self, key: str) -> Path | None:
        path = self._resolve(key)
        return path if path.is_file() else None

    def content_type(self, key: str) -> str:
        meta = (self.root / key).with_suffix(Path(key).suffix + ".meta.json")
        try:
            return str(
                json.loads(meta.read_text(encoding="utf-8")).get("content_type")
                or "application/octet-stream"
            )
        except (OSError, ValueError):
            return "application/octet-stream"

    def info(self) -> dict[str, Any]:
        used = sum(f.stat().st_size for f in self.root.rglob("*") if f.is_file())
        return {"backend": "local", "root": str(self.root), "bytes_used": used}


@dataclass
class R2Storage(StorageBackend):
    """Cloudflare R2 through the S3 API (boto3)."""

    bucket: str
    account_id: str
    access_key_id: str
    secret_access_key: str
    region: str = "auto"
    endpoint_url: str = ""
    _client: Any = None

    name = "r2"

    def __post_init__(self) -> None:
        self.endpoint_url = self.endpoint_url or (
            f"https://{self.account_id}.r2.cloudflarestorage.com" if self.account_id else ""
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.bucket and self.access_key_id and self.secret_access_key and self.endpoint_url
        )

    def client(self) -> Any:
        if self._client is None:
            import boto3  # noqa: PLC0415  (optional extra)
            from botocore.config import Config  # noqa: PLC0415

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region or "auto",
                config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
            )
        return self._client

    def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> None:
        self.client().put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client().get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client().delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError  # noqa: PLC0415

        try:
            self.client().head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def presign(self, key: str, expires_seconds: int = 3600) -> str | None:
        return self.client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=int(max(60, min(expires_seconds, 7 * 24 * 3600))),
        )

    def info(self) -> dict[str, Any]:
        return {
            "backend": "r2",
            "bucket": self.bucket,
            "endpoint": self.endpoint_url,
            "account_id_masked": mask(self.account_id),
            "access_key_masked": mask(self.access_key_id),
            "configured": self.configured,
        }


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return f"{value[:2]}***"
    return f"{value[:6]}***{value[-4:]}"


def _env_first(*names: str) -> str:
    from . import secrets as secrets_store  # local import: avoids a cycle

    for name in names:
        stored = secrets_store.get_secret(name)
        if stored:
            return stored
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def r2_from_environment() -> R2Storage:
    return R2Storage(
        bucket=_env_first("ZOLAI_TTS_R2_BUCKET", "R2_BUCKET", "AWS_BUCKET"),
        account_id=_env_first("ZOLAI_TTS_R2_ACCOUNT_ID", "R2_ACCOUNT_ID", "AWS_ACCOUNT_ID"),
        access_key_id=_env_first(
            "ZOLAI_TTS_R2_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"
        ),
        secret_access_key=_env_first(
            "ZOLAI_TTS_R2_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"
        ),
        region=_env_first("ZOLAI_TTS_R2_REGION", "AWS_REGION") or "auto",
        endpoint_url=_env_first("ZOLAI_TTS_R2_ENDPOINT_URL", "R2_ENDPOINT_URL"),
    )


@dataclass
class StorageHub:
    """Routes reads/writes to the active backend with a local mirror fallback."""

    local: LocalStorage
    r2: R2Storage
    preferred: Backend = "local"

    def active(self) -> StorageBackend:
        if self.preferred == "r2" and self.r2.configured:
            return self.r2
        return self.local

    def backend(self, name: str | None) -> StorageBackend:
        if name == "r2":
            if not self.r2.configured:
                raise RuntimeError("R2 storage requested but not configured")
            return self.r2
        if name == "local":
            return self.local
        return self.active()

    def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> str:
        backend = self.active()
        backend.put(key, data, content_type=content_type)
        if self.preferred == "r2" and isinstance(backend, R2Storage):
            with contextlib.suppress(OSError):  # local mirror keeps playback working offline
                self.local.put(key, data, content_type=content_type)
        return backend.name

    def read(self, backend_name: str | None, key: str) -> tuple[bytes, str]:
        """Fetch bytes plus the backend that served them (falls back to local)."""
        if backend_name == "r2" and self.r2.configured:
            try:
                return self.r2.get(key), "r2"
            except Exception:  # noqa: BLE001  (any provider/storage error falls back)
                pass
        if self.local.exists(key):
            return self.local.get(key), "local"
        if self.r2.configured:
            return self.r2.get(key), "r2"
        raise FileNotFoundError(key)

    def delete(self, backend_name: str | None, key: str) -> None:
        for backend in (
            (self.local, self.r2) if backend_name is None else (self.backend(backend_name),)
        ):
            if isinstance(backend, R2Storage) and not backend.configured:
                continue
            with contextlib.suppress(Exception):  # best-effort across backends
                backend.delete(key)

    def local_path(self, backend_name: str | None, key: str) -> Path | None:
        return self.local.local_path(key) if self.local.exists(key) else None

    def local_object_path(self, key: str) -> Path | None:
        """Mirror path on local disk, whether or not the object lives there yet."""
        return self.local.local_path(key)

    def presign(
        self, backend_name: str | None, key: str, expires_seconds: int = 3600
    ) -> str | None:
        try:
            return self.backend(backend_name or "r2").presign(key, expires_seconds)
        except Exception:  # noqa: BLE001  (unsigned access is optional)
            return None

    def info(self) -> dict[str, Any]:
        return {
            "preferred": self.preferred,
            "active": self.active().name,
            "local": self.local.info(),
            "r2": self.r2.info(),
        }


def build_storage(preferred: str | None = None, store_root: Path | None = None) -> StorageHub:
    raw = preferred or os.getenv("ZOLAI_TTS_STORAGE_BACKEND") or "local"
    choice = raw.strip().lower()
    if choice not in {"local", "r2", "auto"}:
        raise ValueError("storage must be 'local', 'r2', or 'auto'")
    r2 = r2_from_environment()
    if choice in {"r2", "auto"} and not r2.configured:
        if choice == "r2":
            raise RuntimeError(
                "R2 selected but not configured: need bucket, account id, access key, secret key "
                "(ZOLAI_TTS_R2_* or R2_* environment variables)"
            )
        choice = "local"
    return StorageHub(
        local=LocalStorage(store_root or objects_dir()),
        r2=r2,
        preferred="local" if choice == "auto" else choice,  # type: ignore[arg-type]
    )


def copy_local_to_r2(hub: StorageHub, source_root: Path) -> int:
    """One-time migration helper: upload existing local objects by key."""
    if not hub.r2.configured:
        raise RuntimeError("R2 is not configured")
    root = source_root.resolve()
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.endswith(".meta.json"):
            continue
        key = str(path.relative_to(root))
        hub.r2.put(key, path.read_bytes(), content_type=hub.local.content_type(key))
        count += 1
    return count
