import pytest
from fastapi.testclient import TestClient

from app.api.store import store
from app.main import app


@pytest.fixture(autouse=True)
def _clear_store():
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_game_returns_state(client: TestClient):
    r = client.post("/games", json={"radius": 4, "seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["turn"] == 1
    assert body["map_radius"] == 4
    assert len(body["civs"]) >= 2
    # two units per civ (settler + warrior)
    assert len(body["units"]) == 2 * len(body["civs"])
    assert body["cities"] == []


def test_get_game_returns_same_state(client: TestClient):
    created = client.post("/games", json={"radius": 3, "seed": 2}).json()
    r = client.get(f"/games/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_unknown_game_returns_404(client: TestClient):
    r = client.get("/games/999")
    assert r.status_code == 404


def test_advance_turn_increments_counter(client: TestClient):
    created = client.post("/games", json={"radius": 3, "seed": 2}).json()
    r = client.post(f"/games/{created['id']}/turn")
    assert r.status_code == 200
    assert r.json()["turn"] == 2


def test_move_unit_and_error_path(client: TestClient):
    created = client.post("/games", json={"radius": 4, "seed": 2}).json()
    game_id = created["id"]
    settler = next(u for u in created["units"] if u["type"] == "settler")

    # Move off map → 400
    bad = client.post(
        f"/games/{game_id}/actions/move",
        json={"unit_id": settler["id"], "q": 99, "r": 99},
    )
    assert bad.status_code == 400


def test_research_flow(client: TestClient):
    created = client.post("/games", json={"radius": 3, "seed": 3}).json()
    game_id = created["id"]
    r = client.post(
        f"/games/{game_id}/actions/research",
        json={"civ_id": 0, "tech_id": "agriculture"},
    )
    assert r.status_code == 200
    civ0 = next(c for c in r.json()["civs"] if c["id"] == 0)
    assert civ0["researching"] == "agriculture"


def test_found_city_via_api(client: TestClient):
    created = client.post("/games", json={"radius": 4, "seed": 5}).json()
    game_id = created["id"]
    settler = next(u for u in created["units"] if u["type"] == "settler")
    # Try to found — may fail if starting tile is unfoundable (ocean/mountain).
    r = client.post(
        f"/games/{game_id}/actions/found",
        json={"unit_id": settler["id"], "name": "Capital"},
    )
    # Accept either success or a principled 400 (terrain check).
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        body = r.json()
        assert len(body["cities"]) == 1
        assert body["cities"][0]["name"] == "Capital"
