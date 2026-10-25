import os
import json
import hashlib
import duckdb
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

DB_FILE = "data/dom_radar.db"
HISTORY_DIR = "data/history"
EXPORT_DIR = "public"
API_DIR = os.path.join(EXPORT_DIR, "v1")

TARGET_REGISTRY = [
    {
        "target_id": "github_public",
        "platform_name": "GitHub",
        "url": "https://github.com",
        "elements": [
            {
                "intent": "global_search_button",
                "primary": "button.header-search-button",
                "fallback": "button[data-target*='search']"
            },
            {
                "intent": "sign_in_nav",
                "primary": "a[href='/login']",
                "fallback": "header a[href*='login']"
            },
            {
                "intent": "sign_up_cta",
                "primary": "a[href*='/signup']",
                "fallback": "header a[href*='signup']"
            }
        ]
    },
    {
        "target_id": "pypi_registry",
        "platform_name": "PyPI",
        "url": "https://pypi.org",
        "elements": [
            {
                "intent": "package_search_input",
                "primary": "input#search",
                "fallback": "input[name='q']"
            },
            {
                "intent": "search_submit_button",
                "primary": "button.search-form__button",
                "fallback": "form.search-form button"
            }
        ]
    },
    {
        "target_id": "hacker_news",
        "platform_name": "Hacker News",
        "url": "https://news.ycombinator.com",
        "elements": [
            {
                "intent": "top_story_link",
                "primary": "span.titleline > a",
                "fallback": "td.title > span.titleline a"
            },
            {
                "intent": "search_box",
                "primary": "form[action='//hn.algolia.com/'] input[name='q']",
                "fallback": "input[name='q']"
            }
        ]
    },
    {
        "target_id": "cloudflare_status",
        "platform_name": "Cloudflare Status",
        "url": "https://www.cloudflarestatus.com",
        "elements": [
            {
                "intent": "overall_status_banner",
                "primary": "div.page-status",
                "fallback": "span.status"
            },
            {
                "intent": "incident_history_link",
                "primary": "a[href*='/history']",
                "fallback": "footer a[href*='history']"
            }
        ]
    }
]

def compute_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def test_selector(soup: BeautifulSoup, selector: str):
    try:
        found = soup.select_one(selector)
        if found:
            classes = " ".join(found.get("class", [])) if found.get("class") else ""
            return True, found.name, classes
    except Exception:
        pass
    return False, "", ""

def harvest_dom_targets():
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 DOMMutationRadar/1.0"
    }

    for target in TARGET_REGISTRY:
        url = target["url"]
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        for elem in target["elements"]:
            intent = elem["intent"]
            primary = elem["primary"]
            fallback = elem["fallback"]

            p_ok, p_tag, p_classes = test_selector(soup, primary)
            f_ok, f_tag, f_classes = test_selector(soup, fallback)

            if p_ok:
                status = "VERIFIED"
                resolved_tag = p_tag
                resolved_classes = p_classes
            elif f_ok:
                status = "MUTATED_FALLBACK_ACTIVE"
                resolved_tag = f_tag
                resolved_classes = f_classes
            else:
                status = "BROKEN_OBSOLETE"
                resolved_tag = ""
                resolved_classes = ""

            state_payload = {
                "target_id": target["target_id"],
                "intent": intent,
                "status": status,
                "classes": resolved_classes
            }

            results.append({
                "target_id": target["target_id"],
                "platform_name": target["platform_name"],
                "element_intent": intent,
                "primary_selector": primary,
                "fallback_selector": fallback,
                "resolved_tag": resolved_tag,
                "resolved_classes": resolved_classes,
                "verification_status": status,
                "content_hash": compute_hash(state_payload)
            })

    return results

def build_static_api(conn):
    os.makedirs(API_DIR, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    cur = conn.execute("SELECT * FROM verified_selectors ORDER BY target_id ASC, element_intent ASC")
    cols = [desc[0] for desc in cur.description]
    all_selectors = [dict(zip(cols, row)) for row in cur.fetchall()]

    with open(os.path.join(API_DIR, "active-selectors.json"), "w", encoding="utf-8") as f:
        json.dump({"metadata": {"updated_at": now_iso, "count": len(all_selectors)}, "selectors": all_selectors}, f, indent=2)

    cur_mut = conn.execute("SELECT * FROM verified_selectors WHERE verification_status != 'VERIFIED'")
    mutations = [dict(zip(cols, row)) for row in cur_mut.fetchall()]

    with open(os.path.join(API_DIR, "selector-mutations.json"), "w", encoding="utf-8") as f:
        json.dump({"metadata": {"updated_at": now_iso, "mutations_detected": len(mutations)}, "mutations": mutations}, f, indent=2)

    lines = [
        "# DOM Mutation Radar Wire",
        f"> Last Sync: {now_iso} UTC",
        "> Resilience Map: Active CSS & XPath selectors for autonomous browser-use agents.",
        "",
        "## Verified Selector Map"
    ]
    for s in all_selectors:
        status_tag = f"[{s['verification_status']}]"
        active_sel = s["primary_selector"] if s["verification_status"] == "VERIFIED" else s["fallback_selector"]
        lines.append(f"- **{s['platform_name']}** (`{s['element_intent']}`) {status_tag}: `{active_sel}`")

    with open(os.path.join(EXPORT_DIR, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    html = f"""<!DOCTYPE html><html><head><title>DOM Mutation Radar</title></head>
    <body style='font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;line-height:1.6;padding:0 1rem;'>
    <h1>📡 DOM Mutation Radar</h1>
    <p>Resilience index tracking DOM selector mutations and obfuscations across developer platforms.</p>
    <h3>Machine Feeds</h3>
    <ul>
      <li><a href='v1/active-selectors.json'>/v1/active-selectors.json</a> (Verified Selector Mapping)</li>
      <li><a href='v1/selector-mutations.json'>/v1/selector-mutations.json</a> (Broken &amp; Mutated Alerts)</li>
      <li><a href='llms.txt'>llms.txt</a> (Token-Efficient Digest)</li>
      <li><a href='selectors.parquet'>selectors.parquet</a> (Columnar Parquet Snapshot)</li>
    </ul>
    <h3>Monitored Target Elements</h3>
    <table border="1" cellpadding="6" style="border-collapse:collapse;width:100%;text-align:left;">
      <tr><th>Platform</th><th>Intent</th><th>Status</th><th>Active Selector</th><th>Resolved Tag</th></tr>
      {"".join([f"<tr><td>{s['platform_name']}</td><td><code>{s['element_intent']}</code></td><td><strong>{s['verification_status']}</strong></td><td><code>{s['primary_selector'] if s['verification_status'] == 'VERIFIED' else s['fallback_selector']}</code></td><td>{s['resolved_tag']}</td></tr>" for s in all_selectors])}
    </table>
    </body></html>"""
    with open(os.path.join(EXPORT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

def run():
    os.makedirs("data", exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

    conn = duckdb.connect(DB_FILE)
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.execute(f.read())

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")

    month_dir = os.path.join(HISTORY_DIR, year_str, month_str)
    os.makedirs(month_dir, exist_ok=True)
    daily_history_file = os.path.join(month_dir, f"{date_str}.jsonl")

    records = harvest_dom_targets()

    conn.execute("BEGIN TRANSACTION")

    for r in records:
        t_id = r["target_id"]
        plat = r["platform_name"].replace("'", "''")
        intent = r["element_intent"].replace("'", "''")
        prim = r["primary_selector"].replace("'", "''")
        fall = r["fallback_selector"].replace("'", "''")
        tag = r["resolved_tag"].replace("'", "''")
        cls = r["resolved_classes"].replace("'", "''")
        status = r["verification_status"]
        h = r["content_hash"]

        existing = conn.execute(f"""
            SELECT content_hash, verification_status 
            FROM verified_selectors 
            WHERE target_id = '{t_id}' AND element_intent = '{intent}'
        """).fetchone()

        if not existing:
            conn.execute(f"""
                INSERT INTO verified_selectors (
                    target_id, platform_name, element_intent, primary_selector,
                    fallback_selector, resolved_tag, resolved_classes, verification_status,
                    content_hash, last_verified_utc
                ) VALUES (
                    '{t_id}', '{plat}', '{intent}', '{prim}',
                    '{fall}', '{tag}', '{cls}', '{status}',
                    '{h}', '{now_iso}'
                )
            """)

            commit_id = conn.execute("SELECT nextval('seq_commit_id')").fetchone()[0]
            conn.execute(f"""
                INSERT INTO ledger (commit_id, timestamp_utc, operation, target_id, element_intent, selector_state, detail)
                VALUES ({commit_id}, '{now_iso}', 'INIT_SELECTOR', '{t_id}', '{intent}', '{status}', 'Baseline selector mapped')
            """)

            entry = {
                "commit_id": commit_id, "timestamp_utc": now_iso, "operation": "INIT_SELECTOR",
                "target_id": t_id, "intent": intent, "status": status, "content_hash": h
            }
            with open(daily_history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        elif existing[0] != h:
            old_status = existing[1]
            conn.execute(f"""
                UPDATE verified_selectors SET
                    resolved_tag = '{tag}',
                    resolved_classes = '{cls}',
                    verification_status = '{status}',
                    content_hash = '{h}',
                    last_verified_utc = '{now_iso}'
                WHERE target_id = '{t_id}' AND element_intent = '{intent}'
            """)

            commit_id = conn.execute("SELECT nextval('seq_commit_id')").fetchone()[0]
            conn.execute(f"""
                INSERT INTO ledger (commit_id, timestamp_utc, operation, target_id, element_intent, selector_state, detail)
                VALUES ({commit_id}, '{now_iso}', 'SELECTOR_MUTATION', '{t_id}', '{intent}', '{status}', 'Transition: {old_status} -> {status}')
            """)

            entry = {
                "commit_id": commit_id, "timestamp_utc": now_iso, "operation": "SELECTOR_MUTATION",
                "target_id": t_id, "intent": intent, "old_status": old_status, "new_status": status, "content_hash": h
            }
            with open(daily_history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    conn.execute("COMMIT")

    conn.execute(f"COPY (SELECT target_id, platform_name, element_intent, primary_selector, fallback_selector, verification_status, last_verified_utc FROM verified_selectors) TO '{EXPORT_DIR}/selectors.parquet' (FORMAT PARQUET)")
    build_static_api(conn)
    conn.close()

if __name__ == "__main__":
    run()
