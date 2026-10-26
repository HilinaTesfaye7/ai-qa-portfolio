"""A small mock service that imitates the tools described in the job post:
- an AI "extraction" API that pulls financial fields out of documents
- an approval tracker where nothing may be submitted without a review

It is intentionally simple so the tests, not the app, are the focus.
"""
import os
import sqlite3
import uuid

from flask import Flask, jsonify, request, render_template_string

API_TOKEN = os.environ.get("QA_API_TOKEN", "test-token")
DB_PATH = os.environ.get("QA_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "deals.db"))

app = Flask(__name__)

# Idempotency store: the same Idempotency-Key must return the same job, never a duplicate.
_jobs_by_key = {}
# Approval tracker state, in memory for the demo.
_items = {}


def _authorized():
    return request.headers.get("Authorization") == f"Bearer {API_TOKEN}"


@app.post("/api/extract")
def extract():
    if not _authorized():
        return jsonify(error="unauthorized"), 401

    body = request.get_json(silent=True)
    if not body or not isinstance(body.get("document_id"), str) or not body["document_id"].strip():
        return jsonify(error="document_id is required"), 400

    key = request.headers.get("Idempotency-Key")
    if key and key in _jobs_by_key:
        return jsonify(_jobs_by_key[key]), 200

    job = {
        "job_id": str(uuid.uuid4()),
        "document_id": body["document_id"],
        "status": "queued",
    }
    if key:
        _jobs_by_key[key] = job
    return jsonify(job), 201


@app.get("/api/deals/<int:deal_id>")
def get_deal(deal_id):
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    con.close()
    if row is None:
        return jsonify(error="not found"), 404
    return jsonify(dict(row)), 200


# ---------- Approval tracker ----------

@app.post("/api/items")
def create_item():
    title = (request.get_json(silent=True) or {}).get("title", "Untitled")
    item_id = str(len(_items) + 1)
    _items[item_id] = {"id": item_id, "title": title, "reviewed": False, "submitted": False}
    return jsonify(_items[item_id]), 201


@app.post("/api/items/<item_id>/review")
def review_item(item_id):
    item = _items.get(item_id)
    if not item:
        return jsonify(error="not found"), 404
    item["reviewed"] = True
    return jsonify(item), 200


@app.post("/api/items/<item_id>/submit")
def submit_item(item_id):
    item = _items.get(item_id)
    if not item:
        return jsonify(error="not found"), 404
    # The server enforces the rule; the UI hiding the button is not enough.
    if not item["reviewed"]:
        return jsonify(error="review required before submission"), 409
    item["submitted"] = True
    return jsonify(item), 200


@app.post("/api/_reset")
def reset():
    _items.clear()
    _jobs_by_key.clear()
    return "", 204


TRACKER_HTML = """
<!doctype html>
<html><head><meta charset="utf-8"><title>Priority Tracker</title></head>
<body>
  <h1>Priority Tracker</h1>
  <input id="title" placeholder="Item title" />
  <button id="create">Create item</button>
  <div id="item" hidden>
    <p>Item <span id="item-id"></span>: <span id="item-title"></span></p>
    <button id="review">Mark as reviewed</button>
    <button id="submit" disabled>Submit</button>
  </div>
  <p id="status" role="status"></p>
<script>
let id = null;
const $ = (s) => document.querySelector(s);
$('#create').onclick = async () => {
  const r = await fetch('/api/items', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title: $('#title').value})});
  const item = await r.json(); id = item.id;
  $('#item-id').textContent = item.id; $('#item-title').textContent = item.title;
  $('#item').hidden = false; $('#status').textContent = 'Created';
};
$('#review').onclick = async () => {
  await fetch(`/api/items/${id}/review`, {method: 'POST'});
  $('#submit').disabled = false; $('#status').textContent = 'Reviewed';
};
$('#submit').onclick = async () => {
  const r = await fetch(`/api/items/${id}/submit`, {method: 'POST'});
  $('#status').textContent = r.ok ? 'Submitted' : 'Blocked: review required';
};
</script>
</body></html>
"""


@app.get("/tracker")
def tracker():
    return render_template_string(TRACKER_HTML)


if __name__ == "__main__":
    app.run(port=5005)
