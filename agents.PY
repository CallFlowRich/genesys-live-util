#!/usr/bin/env python3
"""
agents_html.py

- Authenticates to Genesys Cloud
- Fetches queue members and their utilizations
- Generates a browser-viewable HTML report (utilization.html) with improved styling
- Hides Agent ID column and excludes 'workitem' utilization
"""

import requests, json, sys, webbrowser, os

# CONFIG — fill in your values here
CLIENT_ID     = "b5cfd3ca-e1e0-4af2-86ba-a815f618e62a"
CLIENT_SECRET = "hPp4KSICLFJV1hoMsoxTXuXKY594TkKmsKcA2IjsrnE"
ORG_REGION    = "mypurecloud.com.au"
QUEUE_ID      = "bbb33ce0-ba79-4649-a78c-5adfddeebe41"

# Endpoints
TOKEN_URL     = f"https://login.{ORG_REGION}/oauth/token"
BASE_URL      = f"https://api.{ORG_REGION}"
QUEUE_MEMBERS = f"{BASE_URL}/api/v2/routing/queues/{QUEUE_ID}/members"
UTIL_FMT      = f"{BASE_URL}/api/v2/routing/users/{{user_id}}/utilization"

def authenticate():
    resp = requests.post(TOKEN_URL, auth=(CLIENT_ID, CLIENT_SECRET), data={"grant_type":"client_credentials"})
    resp.raise_for_status()
    return resp.json()["access_token"]

def get_queue_members(token):
    headers = {"Authorization": f"Bearer {token}"}
    params = {"pageSize":100, "pageNumber":1}
    members = []
    while True:
        r = requests.get(QUEUE_MEMBERS, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        for m in data.get("entities", []):
            uid = (m.get("user") or {}).get("id") or m.get("id")
            name = (m.get("user") or {}).get("name") or m.get("name")
            members.append((uid, name))
        if not data.get("nextUri"):
            break
        params["pageNumber"] += 1
    return members

def get_util(token, user_id):
    r = requests.get(
        UTIL_FMT.format(user_id=user_id),
        headers={"Authorization":f"Bearer {token}"},
        params={"queueId": QUEUE_ID}
    )
    r.raise_for_status()
    return r.json().get("utilization", {})

def make_html_report(results):
    # Determine all media types across agents, excluding 'workitem'
    media_types = set()
    for util in results.values():
        media_types.update(util.keys())
    media_types.discard('workitem')
    media_types = sorted(media_types)

    # Build HTML
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Queue Utilization Report - Inbound Sales </title>",
        "<style>",
        "  body { font-family: 'Segoe UI', Tahoma, Verdana, sans-serif; background: #f0f2f5; margin: 0; }",
        "  .container { max-width: 1200px; margin: 2rem auto; background: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }",
        "  h1 { text-align: center; margin-bottom: 1.5rem; color: #333; }",
        "  table { width: 100%; border-collapse: collapse; }",
        "  thead { background: #0073e6; color: #fff; }",
        "  th, td { padding: 0.75rem 1rem; border: 1px solid #ddd; text-align: center; }",
        "  tbody tr:nth-child(odd) { background: #fafafa; }",
        "  tbody tr:hover { background: #ececec; }",
        "</style>",
        "</head>",
        "<body>",
        "<div class='container'>",
        f"<h1>Utilization Report for Queue Inbound Sales</h1>",
        "<table>",
        "  <thead>",
        "    <tr><th>Agent Name</th>" + "".join(f"<th>{m}</th>" for m in media_types) + "</tr>",
        "  </thead>",
        "  <tbody>"
    ]

    for (_, name), util in results.items():
        html.append("    <tr>")
        html.append(f"      <td>{name}</td>")
        for m in media_types:
            cap = util.get(m, {}).get("maximumCapacity", "-")
            html.append(f"      <td>{cap}</td>")
        html.append("    </tr>")

    html += [
        "  </tbody>",
        "</table>",
        "</div>",
        "</body>",
        "</html>"
    ]
    return "\n".join(html)

def main():
    try:
        token = authenticate()
    except Exception as e:
        print("❌ Authentication failed:", e, file=sys.stderr)
        sys.exit(1)

    members = get_queue_members(token)
    if not members:
        print("No queue members found.", file=sys.stderr)
        sys.exit(1)

    results = {}
    for uid, name in members:
        try:
            results[(uid, name)] = get_util(token, uid)
        except Exception:
            results[(uid, name)] = {}

    html = make_html_report(results)
    out = "utilization.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    webbrowser.open("file://" + os.path.abspath(out))

if __name__ == "__main__":
    main()
