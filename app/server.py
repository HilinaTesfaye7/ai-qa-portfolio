"""A small mock service that imitates the tools described in the job post:
- an AI "extraction" API that pulls financial fields out of documents
- an approval tracker where nothing may be submitted without a review

It is intentionally simple so the tests, not the app, are the focus.
"""
import os
import sqlite3
import uuid

from flask import Flask, jsonify, request

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
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Priority Tracker | DealDesk</title>
<style>
  :root {
    --bg: #f4f6fa; --panel: #ffffff; --border: #e3e7ee; --text: #1b2333; --muted: #6b7486;
    --primary: #3b5bdb; --primary-dark: #2f4ac0; --nav: #121a2b; --nav-text: #a9b3c7;
    --green: #2b8a3e; --green-bg: #e6f4ea; --amber: #b36b00; --amber-bg: #fff4e0;
    --red: #c92a2a; --red-bg: #fdecec; --blue-bg: #e8eefc;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", -apple-system, Roboto, Helvetica, Arial, sans-serif;
         background: var(--bg); color: var(--text); font-size: 14px; }
  .app { display: flex; min-height: 100vh; }

  /* Sidebar */
  .sidebar { width: 232px; background: var(--nav); color: var(--nav-text); padding: 20px 14px; flex-shrink: 0; }
  .brand { display: flex; align-items: center; gap: 10px; color: #fff; font-weight: 600; font-size: 16px;
           padding: 0 8px 22px; }
  .logo { width: 30px; height: 30px; border-radius: 8px; background: var(--primary); display: grid;
          place-items: center; font-weight: 700; }
  .nav-label { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; padding: 14px 10px 6px; color: #6f7a90; }
  .nav a { display: flex; align-items: center; gap: 10px; padding: 9px 10px; border-radius: 6px;
           color: var(--nav-text); text-decoration: none; }
  .nav a:hover { background: #1c263b; color: #fff; }
  .nav a.active { background: #22304d; color: #fff; }
  .nav .count { margin-left: auto; background: var(--primary); color: #fff; border-radius: 10px;
                font-size: 11px; padding: 1px 7px; }

  /* Top bar */
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .topbar { height: 60px; background: var(--panel); border-bottom: 1px solid var(--border); display: flex;
            align-items: center; justify-content: space-between; padding: 0 28px; }
  .search { width: 340px; max-width: 50%; padding: 8px 12px; border: 1px solid var(--border);
            border-radius: 6px; background: var(--bg); font: inherit; }
  .user { display: flex; align-items: center; gap: 10px; }
  .avatar { width: 34px; height: 34px; border-radius: 50%; background: #dbe4ff; color: var(--primary);
            display: grid; place-items: center; font-weight: 600; }
  .user small { display: block; color: var(--muted); }

  /* Content */
  .content { padding: 26px 28px 40px; max-width: 1100px; width: 100%; }
  .crumbs { color: var(--muted); font-size: 13px; }
  h1 { font-size: 22px; margin: 4px 0 4px; }
  .subtitle { color: var(--muted); margin: 0 0 22px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 20px;
          margin-bottom: 18px; box-shadow: 0 1px 2px rgba(16, 24, 40, .04); }
  .card h2 { font-size: 15px; margin: 0 0 4px; }
  .card .hint { color: var(--muted); margin: 0 0 14px; font-size: 13px; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; }
  input[type=text] { flex: 1; min-width: 220px; padding: 10px 12px; border: 1px solid #cdd3de;
                     border-radius: 6px; font: inherit; }
  input[type=text]:focus { outline: 2px solid #c5d0fa; border-color: var(--primary); }

  button { font: inherit; font-weight: 600; padding: 10px 16px; border-radius: 6px; cursor: pointer;
           border: 1px solid transparent; }
  .btn-primary { background: var(--primary); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: var(--primary-dark); }
  .btn-secondary { background: #fff; color: var(--text); border-color: #cdd3de; }
  .btn-secondary:hover:not(:disabled) { background: #f1f3f7; }
  button:disabled { background: #e9ecf2; color: #9aa3b3; border-color: #e9ecf2; cursor: not-allowed; }

  /* Approval item */
  .item-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
               border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 16px; }
  .item-ref { color: var(--muted); font-size: 12px; font-weight: 600; letter-spacing: .03em; }
  .item-name { font-size: 18px; font-weight: 600; margin-top: 2px; }
  .pill { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; white-space: nowrap; }
  .pill.draft { background: var(--amber-bg); color: var(--amber); }
  .pill.reviewed { background: var(--blue-bg); color: var(--primary); }
  .pill.submitted { background: var(--green-bg); color: var(--green); }
  .pill.blocked { background: var(--red-bg); color: var(--red); }

  .meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
  .meta div small { display: block; color: var(--muted); font-size: 12px; margin-bottom: 2px; }

  .steps { display: flex; margin: 0 0 22px; padding: 0; list-style: none; }
  .steps li { flex: 1; position: relative; text-align: center; color: var(--muted); font-size: 13px; }
  .steps li::before { content: ""; position: absolute; top: 13px; left: -50%; width: 100%; height: 2px;
                      background: var(--border); z-index: 0; }
  .steps li:first-child::before { display: none; }
  .steps .dot { position: relative; z-index: 1; width: 28px; height: 28px; border-radius: 50%; margin: 0 auto 6px;
                display: grid; place-items: center; background: #fff; border: 2px solid var(--border);
                font-weight: 600; font-size: 12px; }
  .steps li.done { color: var(--text); }
  .steps li.done .dot { background: var(--primary); border-color: var(--primary); color: #fff; }
  .steps li.done::before { background: var(--primary); }

  .checklist { background: #f8f9fc; border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px;
               margin-bottom: 18px; color: var(--muted); }
  .checklist ul { margin: 6px 0 0; padding-left: 18px; }
  .actions { display: flex; gap: 10px; justify-content: flex-end; }

  #status { margin: 0 0 18px; padding: 11px 14px; border-radius: 8px; font-weight: 600;
            background: var(--blue-bg); color: var(--primary); border: 1px solid #cdd8fa; }
  #status:empty { display: none; }
  #status.ok { background: var(--green-bg); color: var(--green); border-color: #bfe3c9; }
  #status.error { background: var(--red-bg); color: var(--red); border-color: #f5c2c2; }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase;
       letter-spacing: .04em; padding: 0 10px 10px; border-bottom: 1px solid var(--border); }
  td { padding: 12px 10px; border-bottom: 1px solid #eef1f5; }
  tr:last-child td { border-bottom: none; }

  @media (max-width: 860px) {
    .sidebar, .search { display: none; }
    .meta { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand"><span class="logo">D</span> DealDesk</div>
    <nav class="nav">
      <div class="nav-label">Workspace</div>
      <a href="#">Dashboard</a>
      <a href="#">Deal pipeline</a>
      <a href="#">Data rooms</a>
      <a href="#">AI extraction</a>
      <a href="#" class="active">Approvals <span class="count">3</span></a>
      <div class="nav-label">Insights</div>
      <a href="#">Reports</a>
      <a href="#">Audit log</a>
    </nav>
  </aside>

  <div class="main">
    <header class="topbar">
      <input class="search" type="search" placeholder="Search deals, documents, approvals..." aria-label="Search">
      <div class="user">
        <span class="avatar">HT</span>
        <div>Hilina Tesfaye<small>Acquisitions analyst</small></div>
      </div>
    </header>

    <main class="content">
      <div class="crumbs">Approvals / Priority tracker</div>
      <h1>Priority Tracker</h1>
      <p class="subtitle">Every acquisition item must be reviewed before it can be submitted to the investment committee.</p>

      <p id="status" role="status"></p>

      <section class="card">
        <h2>New approval request</h2>
        <p class="hint">Name the acquisition or decision that needs sign-off.</p>
        <div class="row">
          <input id="title" type="text" placeholder="e.g. Acquire Northwind Clinics" />
          <button id="create" class="btn-primary">Create item</button>
        </div>
      </section>

      <section id="item" class="card" hidden>
        <div class="item-head">
          <div>
            <div class="item-ref">APR-<span id="item-id"></span></div>
            <div class="item-name" id="item-title"></div>
          </div>
          <span id="state-pill" class="pill draft">Awaiting review</span>
        </div>

        <div class="meta">
          <div><small>Requested by</small>Hilina Tesfaye</div>
          <div><small>Reviewer</small>Deal review team</div>
          <div><small>Created</small><span id="created-at"></span></div>
          <div><small>Priority</small>High</div>
        </div>

        <ol class="steps">
          <li id="step-created"><div class="dot">1</div>Created</li>
          <li id="step-reviewed"><div class="dot">2</div>Reviewed</li>
          <li id="step-submitted"><div class="dot">3</div>Submitted</li>
        </ol>

        <div class="checklist">
          Before submitting, the reviewer confirms:
          <ul>
            <li>Extracted figures match the source financial statements</li>
            <li>Statements are signed and the auditor is identified</li>
            <li>The data room has no missing or duplicate documents</li>
          </ul>
        </div>

        <div class="actions">
          <button id="review" class="btn-secondary">Mark as reviewed</button>
          <button id="submit" class="btn-primary" disabled>Submit</button>
        </div>
      </section>

      <section class="card">
        <h2>Recent approvals</h2>
        <p class="hint">Items submitted in the last 30 days.</p>
        <table>
          <thead><tr><th>Reference</th><th>Item</th><th>Deal value</th><th>Status</th></tr></thead>
          <tbody>
            <tr><td>APR-0412</td><td>Acquire Summit Physio Group</td><td>$2,310,000</td><td><span class="pill submitted">Submitted</span></td></tr>
            <tr><td>APR-0409</td><td>Acquire Blue Harbor Dental</td><td>$845,000</td><td><span class="pill reviewed">Reviewed</span></td></tr>
            <tr><td>APR-0405</td><td>Northwind Clinics, Q4 earn-out</td><td>$305,000</td><td><span class="pill draft">Awaiting review</span></td></tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</div>
<script>
let id = null;
const $ = (s) => document.querySelector(s);

function setStatus(text, kind) {
  $('#status').textContent = text;
  $('#status').className = kind || '';
}
function setPill(text, kind) {
  $('#state-pill').textContent = text;
  $('#state-pill').className = 'pill ' + kind;
}

$('#create').onclick = async () => {
  const r = await fetch('/api/items', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title: $('#title').value})});
  const item = await r.json(); id = item.id;
  $('#item-id').textContent = String(item.id).padStart(4, '0');
  $('#item-title').textContent = item.title || 'Untitled';
  $('#created-at').textContent = new Date().toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'});
  $('#step-created').className = 'done';
  $('#step-reviewed').className = '';
  $('#step-submitted').className = '';
  $('#submit').disabled = true;
  setPill('Awaiting review', 'draft');
  $('#item').hidden = false;
  setStatus('Created');
};
$('#review').onclick = async () => {
  await fetch(`/api/items/${id}/review`, {method: 'POST'});
  $('#submit').disabled = false;
  $('#step-reviewed').className = 'done';
  setPill('Reviewed', 'reviewed');
  setStatus('Reviewed');
};
$('#submit').onclick = async () => {
  const r = await fetch(`/api/items/${id}/submit`, {method: 'POST'});
  if (r.ok) {
    $('#step-submitted').className = 'done';
    setPill('Submitted', 'submitted');
    setStatus('Submitted', 'ok');
  } else {
    setPill('Blocked', 'blocked');
    setStatus('Blocked: review required', 'error');
  }
};
</script>
</body>
</html>
"""


@app.get("/tracker")
def tracker():
    return TRACKER_HTML


if __name__ == "__main__":
    app.run(port=5005)
