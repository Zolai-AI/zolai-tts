"""Shared test fixtures.

Autouse env isolation: entry points (cli.main, server.main) call
``zolai_tts.env.ensure_loaded()``, which reads the developer's real ``.env``
into ``os.environ``. Without this fixture, a test that invokes the CLI can
leak ``ZOLAI_TTS_*`` values into every later test in the same process.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _restore_environment():
    saved = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(saved)
