import socket
import sqlite3
import threading

import pytest
import requests
from werkzeug.serving import make_server

from app import seed_db

TOKEN = "test-token"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "deals.db"
    seed_db.build(str(path))
    return str(path)


@pytest.fixture(scope="session")
def base_url(db_path, monkeypatch_session):
    monkeypatch_session.setenv("QA_DB_PATH", db_path)
    from app import server
    server.DB_PATH = db_path
    port = _free_port()
    srv = make_server("127.0.0.1", port, server.app)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


@pytest.fixture(scope="session")
def monkeypatch_session():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(autouse=False)
def clean_state(base_url):
    requests.post(f"{base_url}/api/_reset")
    yield


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def clean_db(db_path):
    con = sqlite3.connect(db_path)
    yield con
    con.close()


@pytest.fixture
def dirty_db(tmp_path):
    path = tmp_path / "dirty.db"
    seed_db.build(str(path), dirty=True)
    con = sqlite3.connect(path)
    yield con
    con.close()
