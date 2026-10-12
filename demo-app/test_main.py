from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_accueil():
    reponse = client.get("/")
    assert reponse.status_code == 200


def test_health():
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok"}


def test_error500():
    reponse = client.get("/chaos/error500")
    assert reponse.status_code == 500