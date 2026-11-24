"""Engine + session factory. Dialect is configuration, not code.

Resolution order for the database URL:
  1. explicit argument
  2. `ZOLAI_TTS_DB_URL` (canonical; accepts sqlite:/// or postgresql+psycopg://)
  3. `DATABASE_URL` (hosting convention, same formats)
  4. `<store_dir>/studio.db` as `sqlite:///…`

Extra dialect notes:
  * SQLite gets WAL + a busy timeout so the studio's concurrent requests from
    the browser don't hit "database is locked".
  * PostgreSQL gets a sized connection pool.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel

from . import models  # noqa: F401  (registers tables on SQLModel.metadata)


def _safe(url: str) -> str:
    """Strip credentials from a URL before it reaches a message or log."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    _, host = rest.split("@", 1)
    return f"{scheme}://***@{host}"


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def default_sqlite_url() -> str:
    from zolai_tts.paths import store_dir

    return f"sqlite:///{store_dir() / 'studio.db'}"


def resolve_database_url(url: str | None = None) -> str:
    candidate = (url or _env("ZOLAI_TTS_DB_URL") or _env("DATABASE_URL") or "").strip()
    if not candidate:
        return default_sqlite_url()
    if candidate.startswith("postgres://"):
        # Heroku/Supabase style URLs need the psycopg dialect.
        candidate = candidate.replace("postgres://", "postgresql+psycopg://", 1)
    if candidate.startswith("postgresql://"):
        candidate = candidate.replace("postgresql://", "postgresql+psycopg://", 1)
    if candidate.startswith("sqlite:///") or candidate.startswith("postgresql"):
        return candidate
    if candidate.endswith(".db") or candidate.startswith("/"):
        return f"sqlite:///{candidate}"
    raise ValueError(f"Unsupported database URL {candidate!r} (use sqlite:/// or postgresql://).")


def dialect_of(url: str) -> str:
    if url.startswith("postgresql"):
        return "postgresql"
    if url.startswith("sqlite"):
        return "sqlite"
    return "unknown"


def build_engine(url: str) -> Engine:
    dialect = dialect_of(url)
    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    if dialect == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    elif dialect == "postgresql":
        kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_timeout": 20})
    engine = create_engine(url, **kwargs)

    if dialect == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(
            dbapi_connection: Any, _record: Any
        ) -> None:  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()

    return engine


class Database:
    """Engine holder with schema bootstrap and a session context manager."""

    def __init__(self, url: str | None = None, *, create: bool | None = None) -> None:
        self.url = resolve_database_url(url)
        self.dialect = dialect_of(self.url)
        try:
            self.engine = build_engine(self.url)
        except ModuleNotFoundError as exc:  # driver extra not installed
            extra = "postgres" if self.dialect == "postgresql" else self.dialect
            raise RuntimeError(
                f"Database dialect {self.dialect!r} needs the `{extra}` extra: "
                f"uv sync --extra {extra} (missing module: {exc.name})"
            ) from exc
        should_create = True if create is None else create
        if should_create and os.getenv("ZOLAI_TTS_DB_AUTO_CREATE", "1") != "0":
            try:
                self.init_schema()
            except OperationalError as exc:
                raise RuntimeError(
                    f"Cannot reach the {self.dialect} database ({_safe(self.url)}): {exc}"
                ) from exc

    def init_schema(self) -> None:
        """Create missing tables, then add columns missing from existing ones.

        ``create_all`` is create-only: it never alters a table that already
        exists, so a model field added after first run would silently 500 on
        every query. This sync is strictly additive (``ALTER TABLE ADD COLUMN``)
        and never drops or rewrites anything, on either dialect.
        """
        SQLModel.metadata.create_all(self.engine)
        sync_additive_columns(self.engine)
        self._created = True

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session

    def info(self) -> dict[str, Any]:
        """Non-secret connection summary (credentials always masked)."""
        return {
            "dialect": self.dialect,
            "url": _safe(self.url),
            "sqlite_path": self.url[len("sqlite:///") :]
            if self.url.startswith("sqlite:///")
            else None,
        }

    def dispose(self) -> None:
        self.engine.dispose()


_DEFAULT: Database | None = None


def sync_additive_columns(engine: Engine) -> list[str]:
    """Add model columns that an existing table lacks (strictly additive).

    ``create_all`` is create-only, so a field added to a model after the first
    run would make every query fail with "no such column". This issues one
    ``ALTER TABLE … ADD COLUMN`` per missing column — never a drop, type change
    or rewrite — so it is safe on SQLite and PostgreSQL alike.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    added: list[str] = []
    for table in SQLModel.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue  # create_all just made it complete
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            sql = _add_column_sql(engine.dialect, table.name, column)
            with engine.begin() as conn:
                conn.exec_driver_sql(sql)
            added.append(f"{table.name}.{column.name}")
    return added


def _add_column_sql(dialect: Any, table_name: str, column: Any) -> str:
    quote = dialect.identifier_preparer.quote
    sql_type = column.type.compile(dialect=dialect)
    statement = f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote(column.name)} {sql_type}"
    scalar_default = (
        column.default.arg
        if column.default is not None and column.default.is_scalar
        else _server_default(column)
    )
    if not column.nullable:
        statement += f" NOT NULL DEFAULT {_literal(scalar_default, column.nullable)}"
    elif scalar_default is not None:
        statement += f" DEFAULT {_literal(scalar_default, True)}"
    return statement


def _server_default(column: Any) -> Any:
    default = column.server_default
    if default is None:
        return None
    arg = getattr(default, "arg", None)
    return getattr(arg, "text", arg)


def _literal(value: Any, nullable: bool) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    # No usable scalar: backfill history rows with a marker instead of failing.
    return "NULL" if nullable else "'unknown'"


def get_database(url: str | None = None) -> Database:
    """Process-wide handle (lazy). Tests pass an explicit URL."""
    global _DEFAULT
    if url is not None:
        return Database(url)
    if _DEFAULT is None:
        _DEFAULT = Database()
    return _DEFAULT


def reset_database() -> None:
    global _DEFAULT
    if _DEFAULT is not None:
        _DEFAULT.dispose()
    _DEFAULT = None


def store_dir_for_db() -> Path:
    from zolai_tts.paths import store_dir

    return store_dir()
