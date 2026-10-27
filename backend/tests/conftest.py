import os
from pathlib import Path

import pytest

os.environ.setdefault("JUPITER_DATABASE_URL", "sqlite:///" + str(Path("/tmp/jupiter-test.sqlite")))
os.environ.setdefault("NEBIUS_API_KEY", "")
os.environ.setdefault("NEBIUS_OFFLINE_DEMO", "false")
os.environ["JUPITER_DATABASE_URL"] = "sqlite:///" + str(Path("/tmp/jupiter-test.sqlite"))

from app.config import get_settings  # noqa: E402
from app import db as dbmod  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    get_settings.cache_clear()
    url = f"sqlite:///{tmp_path / 'jupiter.sqlite'}"
    monkeypatch.setenv("JUPITER_DATABASE_URL", url)
    get_settings.cache_clear()
    dbmod._engine = None
    dbmod._Session = None
    yield
    if dbmod._engine is not None:
        dbmod._engine.dispose()
    dbmod._engine = None
    dbmod._Session = None
    get_settings.cache_clear()
