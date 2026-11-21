"""Add any city to Flat Finder by name: find it, fetch its data, build the map files.

usage: python3 pipeline/add_city.py "Pune"                 # Magicbricks if it covers the city, else OpenStreetMap
       python3 pipeline/add_city.py "Hyderabad" --max 1500  # cap how many Magicbricks projects are crawled (default 3000)
       python3 pipeline/add_city.py "Mumbai" --all          # crawl every Magicbricks project (can take hours)
       python3 pipeline/add_city.py "Lisbon"                 # outside India: housing complexes from OpenStreetMap
       python3 pipeline/add_city.py "Pune" --osm-only        # skip Magicbricks

Every step is cached and resumable: run the same command again after a network failure and it carries on.
The result is web/public/data/<id>.json and friends, and the city appears in the site's city picker.
"""
import json
import math
import os
import pathlib
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import mb_parse
import net

ROOT = pathlib.Path(__file__).parent
CITIES_FILE = ROOT.parent / "data" / "cities.json"
UA_BROWSER = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
UA_TOOL = "flat-finder/0.2 (city setup; https://github.com/archit-suryawanshi/flat-finder)"
DEFAULT_MAX = 3000
MAX_SPAN = 0.45  # degrees: Overpass gets slow and the map gets crowded beyond a large city's size
# Magicbricks URL names for cities whose usual English name differs
MB_ALIASES = {"gurugram": "gurgaon", "bengaluru": "bangalore", "bombay": "mumbai", "madras": "chennai", "calcutta": "kolkata",
              "new-bombay": "navi-mumbai", "noida-extension": "greater-noida"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def geocode(name):
    """Best city-like match from OpenStreetMap Nominatim: name, country, centre and bounding box."""
    q = urllib.parse.urlencode({"q": name, "format": "jsonv2", "limit": 10, "addressdetails": 1, "accept-language": "en"})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": UA_TOOL})
    results = json.loads(net.urlopen(req, timeout=30).read())
    if not results:
        raise SystemExit(f'No place called "{name}" found on OpenStreetMap. Check the spelling, or add the country: "{name}, India".')

    def rank(r):
        kind = r.get("addresstype") or r.get("type")
        cityish = kind in ("city", "town", "municipality", "borough", "suburb", "village") or (r.get("category") == "boundary" and 10 <= r.get("place_rank", 0) <= 16)
        return (cityish, r.get("importance") or 0)

    best = max(results, key=rank)
    s, n, w, e = (float(x) for x in best["boundingbox"])
    addr = best.get("address") or {}
    label = best.get("name") or addr.get("city") or addr.get("town") or name
    return {"name": label, "country": (addr.get("country_code") or "").lower(), "lat": float(best["lat"]), "lng": float(best["lon"]),
            "bbox": clamp_bbox([s, w, n, e], float(best["lat"]), float(best["lon"])), "display": best.get("display_name")}


def clamp_bbox(b, lat, lng, max_span=MAX_SPAN, min_span=0.06):
    s, w, n, e = b
    half_lat = min(max((n - s) / 2, min_span / 2), max_span / 2)
    half_lng = min(max((e - w) / 2, min_span / 2), max_span / 2)
    c_lat = min(max(lat, s), n) if n - s <= max_span else lat
    c_lng = min(max(lng, w), e) if e - w <= max_span else lng
    return [round(c_lat - half_lat, 4), round(c_lng - half_lng, 4), round(c_lat + half_lat, 4), round(c_lng + half_lng, 4)]


def zoom_for(bbox):
    s, w, n, e = bbox
    span = max(e - w, (n - s) * 1.6, 0.02)
    return round(min(14.0, math.log2(1200 * 360 / (256 * span))), 1)


def magicbricks_slug(*names):
    """The Magicbricks city name whose project list has results, or None (Magicbricks lists about 15 Indian cities)."""
    tried = []
    for n in names:
        s = slug(n)
        for cand in (MB_ALIASES.get(s), s):
            if not cand or cand in tried:
                continue
            tried.append(cand)
            url = f"https://www.magicbricks.com/residential-projects-in-{cand}-nprid/page-1"
            try:
                html = net.urlopen(urllib.request.Request(url, headers={"User-Agent": UA_BROWSER}), timeout=40).read().decode("utf-8", "ignore")
            except urllib.error.HTTPError as e:
                print(f"  magicbricks: {cand} -> HTTP {e.code}", flush=True)
                continue
            except Exception as e:  # blocked or offline: fall back to OpenStreetMap
                print(f"  magicbricks: {cand} -> {e}", flush=True)
                continue
            total = mb_parse.parse_total(html) or 0
            print(f"  magicbricks: {cand} -> {total:,} projects", flush=True)
            if total > 0:
                return cand, total
    return None, 0


def run(*args):
    print("\n$ python3 " + " ".join(args), flush=True)
    t = time.time()
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)
    print(f"  done in {time.time() - t:.0f}s", flush=True)


def bbox_from_projects(city_id, fallback):
    """Most projects' extent (2nd to 98th percentile, padded), so outliers with wrong coordinates don't stretch the map."""
    f = ROOT / "out" / city_id / "mb_projects.json"
    pts = [(p["lat"], p["lng"]) for p in json.loads(f.read_text()) if p.get("lat") and p.get("lng")] if f.exists() else []
    if len(pts) < 20:
        return fallback
    lats, lngs = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
    q = lambda v, f: v[min(len(v) - 1, int(f * len(v)))]
    b = [q(lats, 0.02) - 0.02, q(lngs, 0.02) - 0.02, q(lats, 0.98) + 0.02, q(lngs, 0.98) + 0.02]
    return clamp_bbox(b, statistics.median(lats), statistics.median(lngs))


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = set(a for a in argv if a.startswith("--"))
    if not args:
        raise SystemExit(__doc__)
    query = " ".join(args) if "--max" not in argv else " ".join(a for a in args if a != argv[argv.index("--max") + 1])
    cap = None if "--all" in flags else int(argv[argv.index("--max") + 1]) if "--max" in argv else DEFAULT_MAX

    cities = json.loads(CITIES_FILE.read_text())
    known = {slug(v["name"]): k for k, v in cities.items()} | {k: k for k in cities}
    existing = known.get(slug(query)) or known.get(MB_ALIASES.get(slug(query), ""))

    print(f'Finding "{query}" on OpenStreetMap...', flush=True)
    place = geocode(query)
    print(f"  {place['display']}\n  centre {place['lat']:.4f}, {place['lng']:.4f}  bbox {place['bbox']}", flush=True)
    city_id = existing or known.get(slug(place["name"])) or slug(place["name"])
    cfg = dict(cities.get(city_id) or {})
    cfg.setdefault("name", place["name"])
    cfg.setdefault("country", place["country"])

    mb, total = (cfg.get("magicbricks"), None) if cfg.get("magicbricks") else (None, 0)
    if not mb and place["country"] == "in" and "--osm-only" not in flags:
        print("Checking Magicbricks...", flush=True)
        mb, total = magicbricks_slug(query, place["name"])
    if "--osm-only" in flags:
        mb = None
    cfg["source"] = "magicbricks" if mb else "osm"
    if mb:
        cfg["magicbricks"] = mb
    else:
        cfg.pop("magicbricks", None)
    cfg.setdefault("bbox", place["bbox"])
    cfg["center"] = cfg.get("center") or [round(place["lng"], 4), round(place["lat"], 4)]
    cfg["zoom"] = cfg.get("zoom") or zoom_for(cfg["bbox"])
    cities[city_id] = cfg
    CITIES_FILE.write_text(json.dumps(cities, indent=1) + "\n")
    print(f"\nCity id: {city_id}  source: {cfg['source']}", flush=True)

    if mb:
        crawl = ["mb_crawl.py", "list", city_id] + (["--max", str(cap)] if cap else [])
        if cap and total and total > cap:
            print(f"  crawling the first {cap:,} of {total:,} projects (use --all for every one)", flush=True)
        run(*crawl)
        run("mb_crawl.py", "projects", city_id)
        if city_id != "gurgaon":  # Gurugram's tuned box stays as it is
            cfg["bbox"] = bbox_from_projects(city_id, cfg["bbox"])
            s, w, n, e = cfg["bbox"]
            cfg["center"] = [round((w + e) / 2, 4), round((s + n) / 2, 4)]
            cfg["zoom"] = zoom_for(cfg["bbox"])
            CITIES_FILE.write_text(json.dumps(cities, indent=1) + "\n")
    run("osm_fetch.py", city_id)
    if not mb:
        run("osm_fetch.py", city_id, "complexes")
    run("build_city.py", city_id)
    if os.environ.get("GITHUB_OUTPUT"):  # tell the workflow which id to commit
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"city_id={city_id}\n")
    print(f"\n{cfg['name']} is ready. Open the site with ?city={city_id}, e.g.\n  cd web && npm install && npm run dev  ->  http://localhost:5173/?city={city_id}", flush=True)
    return city_id


if __name__ == "__main__":
    main(sys.argv[1:])
