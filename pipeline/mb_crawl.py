"""Polite, cached, resumable Magicbricks crawler.

usage: python mb_crawl.py list <city> [--max N]  # list pages -> out/<city>/mb_index.json (first N projects, default all)
       python mb_crawl.py projects <city>         # every project page -> out/<city>/mb_projects.json
<city> is a key in data/cities.json (default: the first one).
"""
import gzip
import hashlib
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

import mb_parse
import net

ROOT = pathlib.Path(__file__).parent
CACHE = ROOT / "cache" / "mb"
OUT = ROOT / "out"
CITIES = json.loads((ROOT.parent / "data" / "cities.json").read_text())
CITY = next((a for a in sys.argv[1:] if a in CITIES), next(iter(CITIES)))
CFG = CITIES[CITY]
LIST_URL = "https://www.magicbricks.com/residential-projects-in-" + CFG["magicbricks"] + "-nprid/page-{}"
OUT = OUT / CITY
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
DELAY = 1.0


def fetch(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html.gz")
    if f.exists() and f.stat().st_size > 2000:
        return gzip.decompress(f.read_bytes()).decode("utf-8", "ignore")
    for attempt in range(3):
        try:
            # some portal URLs carry spaces or non-breaking spaces in the slug
            safe = urllib.parse.quote(url.replace("\xa0", " ").strip(), safe=":/?=&%#+,;@-._~")
            req = urllib.request.Request(safe, headers={"User-Agent": UA})
            html = net.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
            f.write_bytes(gzip.compress(html.encode("utf-8"), 9))
            time.sleep(DELAY)
            return html
        except Exception as e:  # network hiccup: back off and retry
            print("  retry", attempt + 1, url, e, flush=True)
            time.sleep(5 * (attempt + 1))
    return None


def max_projects():
    if "--max" in sys.argv:
        return int(sys.argv[sys.argv.index("--max") + 1])
    return None


def crawl_list():
    first = fetch(LIST_URL.format(1))
    total = mb_parse.parse_total(first)
    pages = -(-min(total, max_projects() or total) // 20)
    projects = {}
    t0 = time.time()
    for n in range(1, pages + 1):
        html = fetch(LIST_URL.format(n))
        if not html:
            continue
        for c in mb_parse.parse_list_page(html):
            projects[c["psmid"]] = mb_parse.card_to_project(c)
        left = (time.time() - t0) / n * (pages - n) / 60
        print(f"list pages {n}/{pages}: {len(projects)} projects, ~{left:.0f} min left for the list", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mb_index.json").write_text(json.dumps(list(projects.values()), indent=0))
    print("total reported", total, "collected", len(projects), flush=True)


def crawl_projects():
    index = json.loads((OUT / "mb_index.json").read_text())
    from concurrent.futures import ThreadPoolExecutor

    def one(p):
        html = fetch(p["url"])
        try:
            detail = mb_parse.parse_project_page(html) if html else {}
        except Exception as e:
            print("  parse failed", p["url"], e, flush=True)
            detail = {}
        return {**p, **{k: v for k, v in detail.items() if v not in (None, [], "")}}

    out = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, merged in enumerate(ex.map(one, index), 1):
            out.append(merged)
            if i % 50 == 0 or i == len(index):
                left = (time.time() - t0) / i * (len(index) - i) / 60
                print(f"project pages {i}/{len(index)}, ~{left:.0f} min left for project pages", flush=True)
                (OUT / "mb_projects.json").write_text(json.dumps(out, indent=0))


if __name__ == "__main__":
    {"list": crawl_list, "projects": crawl_projects}[sys.argv[1]]()
