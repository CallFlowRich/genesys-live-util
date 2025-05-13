#!/usr/bin/env python3
"""
Live Genesys Cloud Utilization Viewer (LOCAL VERSION)

- Flask server that displays live utilization
- Auto-refreshes every 30s
- Credentials embedded for local use (remove before production)
"""

from flask import Flask, render_template_string, jsonify
import requests, os, time

# === CREDENTIALS === (for local use only)
CLIENT_ID     = "b5cfd3ca-e1e0-4af2-86ba-a815f618e62a"
CLIENT_SECRET = "hPp4KSICLFJV1hoMsoxTXuXKY594TkKmsKcA2IjsrnE"
ORG_REGION    = "mypurecloud.com.au"
QUEUE_ID      = "bbb33ce0-ba79-4649-a78c-5adfddeebe41"

# === ENDPOINTS ===
TOKEN_URL     = f"https://login.{ORG_REGION}/oauth/token"
BASE_URL      = f"https://api.{ORG_REGION}"
QUEUE_MEMBERS = f"{BASE_URL}/api/v2/routing/queues/{QUEUE_ID}/members"
UTILIZATION   = f"{BASE_URL}/api/v2/routing/users/{{user_id}}/utilization"

app = Flask(__name__)
token_cache = {"token": None, "expiry": 0}

def authenticate():
    now = time.time()
    if token_cache["token"] and now < token_cache["expiry"] - 60:
        return token_cache["token"]

    resp = requests.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"}
    )
    resp.raise_for_status()
    data = resp.json()
    token_cache["token"] = data["access_token"]
    token_cache["expiry"] = now + data.get("expires_in", 3600)
    return token_cache["token"]

def get_queue_members(token):
    headers = {"Authorization": f"Bearer {token}"}
    params = {"pageSize": 100, "pageNumber": 1}
    members = []

    while True:
        resp = requests.get(QUEUE_MEMBERS, headers=headers, params=params)
        resp.raise_for_status()
        page = resp.json()
        for m in page.get("entities", []):
            uid = (m.get("user") or {}).get("id") or m.get("id")
            name = (m.get("user") or {}).get("name") or m.get("name")
            members.append((uid, name))
        if not page.get("nextUri"):
            break
        params["pageNumber"] += 1

    return members

def fetch_utilization():
    token = authenticate()
    members = get_queue_members(token)
    results = []
    media_types = set()

    for uid, name in members:
        try:
            r = requests.get(
                UTILIZATION.format(user_id=uid),
                headers={"Authorization": f"Bearer {token}"},
                params={"queueId": QUEUE_ID}
            )
            r.raise_for_status()
            util = r.json().get("utilization", {})
        except:
            util = {}

        util.pop("workitem", None)
        for m in util:
            media_types.add(m)
        results.append({"name": name, "util": util})

    return sorted(media_types), results

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live Queue Utilization</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; margin: 0; }
    .container { max-width: 1200px; margin: 2rem auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    h1 { text-align: center; color: #333; margin-bottom: 1.5rem; }
    table { width: 100%; border-collapse: collapse; }
    thead { background: #0073e6; color: #fff; }
    th, td { padding: 0.75rem 1rem; border: 1px solid #ddd; text-align: center; }
    tbody tr:nth-child(odd) { background: #fafafa; }
    tbody tr:hover { background: #ececec; }
    #last { text-align: center; color: #666; margin-top: 1rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Live Utilization for Queue {{queue}}</h1>
    <div id="last">Loading...</div>
    <table id="tbl">
      <thead><tr><th>Agent Name</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <script>
    async function refresh() {
      const resp = await fetch('/data');
      const js = await resp.json();
      const tbl = document.getElementById('tbl');
      const hdr = ['<th>Agent Name</th>'].concat(js.mediaTypes.map(m => `<th>${m}</th>`)).join('');
      tbl.tHead.innerHTML = `<tr>${hdr}</tr>`;
      const rows = js.results.map(r => `<tr>` +
        ['<td>' + r.name + '</td>']
        .concat(js.mediaTypes.map(m => `<td>${r.util[m]?.maximumCapacity || '-'}</td>`))
        .join('') + `</tr>`
      ).join('');
      tbl.tBodies[0].innerHTML = rows;
      document.getElementById('last').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
    }
    refresh(); setInterval(refresh, 30000);
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, queue=QUEUE_ID)

@app.route("/data")
def data():
    try:
        media_types, results = fetch_utilization()
        return jsonify({"mediaTypes": media_types, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
