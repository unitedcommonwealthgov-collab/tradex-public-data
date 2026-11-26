"""Publish only the public TradeX national GDP fields."""
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://tradex.ucsn.fyi/api/world"
INACTIVE = {"promethea", "greica", "atsqia", "inmoria", "akragideion", "dagestan"}

def snapshot(payload):
    rows = payload["countries"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing or empty countries list")
    countries = []
    for row in rows:
        name = str(row["short_name"]).strip()
        nation_id = str(row["id"]).strip()
        if name.casefold() in INACTIVE or nation_id.casefold() in INACTIVE:
            continue
        amount = float(row["amount_euro"])
        if not name or not nation_id or not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid national GDP record")
        countries.append({"id": nation_id, "short_name": name, "amount_euro": amount})
    if not countries:
        raise ValueError("No eligible countries")
    if len({c["id"] for c in countries}) != len(countries):
        raise ValueError("Duplicate nation IDs")
    countries.sort(key=lambda c: (-c["amount_euro"], c["short_name"].casefold()))
    return {"updated": datetime.now(timezone.utc).isoformat(), "countries": countries}

def add_history(data, out):
    history_path = out / "gdp-history.json"
    previous_path = out / "gdp-snapshot.json"
    records = json.loads(history_path.read_text(encoding="utf-8"))["records"] if history_path.exists() else []
    if not records and previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        records.append({"updated": previous["updated"], "gdp": {c["id"]: c["amount_euro"] for c in previous["countries"]}})
    now = datetime.fromisoformat(data["updated"])
    records = [r for r in records if 0 < (now - datetime.fromisoformat(r["updated"])).total_seconds() <= 31 * 86400]
    records.sort(key=lambda r: r["updated"])
    for days, field in [(1, "change_24h"), (7, "change_7d"), (30, "change_30d")]:
        target = now - timedelta(days=days)
        candidates = [r for r in records if abs((datetime.fromisoformat(r["updated"]) - target).total_seconds()) <= 3600]
        baseline = min(candidates, key=lambda r: abs((datetime.fromisoformat(r["updated"]) - target).total_seconds())) if candidates else None
        for country in data["countries"]:
            old = baseline["gdp"].get(country["id"]) if baseline else None
            country[field] = round((country["amount_euro"] - old) / old * 100, 4) if old is not None and old > 0 else None
    # Display a shorter, explicitly labelled comparison until daily history exists.
    for country in data["countries"]:
        country["display_change"] = country["change_24h"]
        country["comparison_hours"] = None
        if country["change_24h"] is not None:
            target = now - timedelta(days=1)
            daily = min((r for r in records if abs((datetime.fromisoformat(r["updated"]) - target).total_seconds()) <= 3600), key=lambda r: abs((datetime.fromisoformat(r["updated"]) - target).total_seconds()))
            country["comparison_hours"] = round((now - datetime.fromisoformat(daily["updated"])).total_seconds() / 3600, 2)
        else:
            eligible = [r for r in records if (now - datetime.fromisoformat(r["updated"])).total_seconds() <= 86400 and r["gdp"].get(country["id"], 0) > 0]
            if eligible:
                first = eligible[0]
                old = first["gdp"][country["id"]]
                country["display_change"] = round((country["amount_euro"] - old) / old * 100, 4)
                country["comparison_hours"] = round((now - datetime.fromisoformat(first["updated"])).total_seconds() / 3600, 2)
    records.append({"updated": data["updated"], "gdp": {c["id"]: c["amount_euro"] for c in data["countries"]}})
    history_path.write_text(json.dumps({"records": records}, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")

def main():
    request = Request(SOURCE, headers={"Accept": "application/json", "User-Agent": "UCSN-GDP-Snapshot/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read(2_000_001))
    data = snapshot(payload)
    out = Path("public")
    out.mkdir(exist_ok=True)
    add_history(data, out)
    (out / "gdp-snapshot.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>TradeX public GDP</title><h1>TradeX public GDP</h1><p><a href="gdp-snapshot.json">Latest GDP snapshot (JSON)</a></p>', encoding="utf-8")
    print(f"Prepared {len(data['countries'])} national GDP records")

if __name__ == "__main__":
    main()
