"""Publish only the public TradeX national GDP fields."""
import json
import math
from datetime import datetime, timezone
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

def main():
    request = Request(SOURCE, headers={"Accept": "application/json", "User-Agent": "UCSN-GDP-Snapshot/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read(2_000_001))
    data = snapshot(payload)
    out = Path("public")
    out.mkdir(exist_ok=True)
    (out / "gdp-snapshot.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>TradeX public GDP</title><h1>TradeX public GDP</h1><p><a href="gdp-snapshot.json">Latest GDP snapshot (JSON)</a></p>', encoding="utf-8")
    print(f"Prepared {len(data['countries'])} national GDP records")

if __name__ == "__main__":
    main()
