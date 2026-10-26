"""API tests: status codes, payload structure, auth failures, repeated identical requests."""
import uuid

import pytest
import requests

pytestmark = pytest.mark.usefixtures("clean_state")


def test_extract_creates_job_with_expected_payload(base_url, auth):
    r = requests.post(f"{base_url}/api/extract", json={"document_id": "doc-1"}, headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"job_id", "document_id", "status"}
    assert body["document_id"] == "doc-1"
    assert body["status"] == "queued"
    uuid.UUID(body["job_id"])  # raises if not a valid UUID


@pytest.mark.parametrize("headers", [
    {},                                         # no token
    {"Authorization": "Bearer wrong-token"},    # wrong token
    {"Authorization": "test-token"},            # missing "Bearer" scheme
])
def test_extract_rejects_bad_auth(base_url, headers):
    r = requests.post(f"{base_url}/api/extract", json={"document_id": "doc-1"}, headers=headers)
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}


@pytest.mark.parametrize("payload", [
    None,                        # empty body
    {},                          # missing field
    {"document_id": ""},         # empty string (boundary)
    {"document_id": "   "},      # whitespace only
    {"document_id": 123},        # wrong type
])
def test_extract_rejects_invalid_payload(base_url, auth, payload):
    r = requests.post(f"{base_url}/api/extract", json=payload, headers=auth)
    assert r.status_code == 400


def test_repeated_identical_request_does_not_create_duplicate(base_url, auth):
    headers = {**auth, "Idempotency-Key": "abc-123"}
    first = requests.post(f"{base_url}/api/extract", json={"document_id": "doc-9"}, headers=headers)
    second = requests.post(f"{base_url}/api/extract", json={"document_id": "doc-9"}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]


def test_get_deal_returns_record_and_404_for_unknown(base_url, auth):
    ok = requests.get(f"{base_url}/api/deals/1", headers=auth)
    assert ok.status_code == 200
    assert ok.json()["target_name"] == "Northwind Clinics"
    assert requests.get(f"{base_url}/api/deals/999", headers=auth).status_code == 404


def test_approval_cannot_be_bypassed_through_the_api(base_url):
    """Calling the submit endpoint directly must fail without a review."""
    item = requests.post(f"{base_url}/api/items", json={"title": "Acquire Northwind"}).json()
    r = requests.post(f"{base_url}/api/items/{item['id']}/submit")
    assert r.status_code == 409
    assert "review required" in r.json()["error"]
