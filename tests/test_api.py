"""Local API exposure and input validation regression tests."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agents.api import app
from agents.models import SystemTaskPayload
from cli import main as supervisor_main


def test_api_key_enforcement(monkeypatch):
    monkeypatch.setenv("AUDITOR_API_KEY", "unit-test-token")
    client = TestClient(app)
    payload = {"task_id": "T1", "target_identifier": "KEY-01", "primary_metric": 12.0}
    assert client.get("/health").status_code == 200
    assert client.post("/api/audit", json=payload).status_code == 401
    res = client.post("/api/audit", json=payload, headers={"X-API-Key": "unit-test-token"})
    assert res.status_code == 200
    assert res.json()["task_id"] == "T1"
    assert client.get("/api/audit/logs").status_code == 401


def test_phi_in_nested_attributes_rejected(monkeypatch):
    monkeypatch.setenv("AUDITOR_API_KEY", "unit-test-token")
    payload = {
        "task_id": "T2", "target_identifier": "KEY-02",
        "primary_metric": 12.0,
        "attributes": {"comment": "Patient MRN-1234567 requires follow-up"},
    }
    response = TestClient(app).post("/api/audit", json=payload, headers={"X-API-Key": "unit-test-token"})
    assert response.status_code == 422
    assert "MRN-1234567" not in response.text


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_metrics_rejected(value):
    with pytest.raises(ValidationError):
        SystemTaskPayload(task_id="T", target_identifier="KEY", primary_metric=value)


def test_external_listener_requires_key(monkeypatch):
    monkeypatch.delenv("AUDITOR_API_KEY", raising=False)
    assert supervisor_main(["serve", "--host", "0.0.0.0"]) == 2
