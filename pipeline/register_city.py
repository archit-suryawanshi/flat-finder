"""Put one city's entry back into data/cities.json and rebuild the site's city menu.

Used by the "Add a city" workflow: several runs can finish at once, so each one starts from the newest main,
re-adds only its own city, and pushes. usage: python3 pipeline/register_city.py <id> <entry.json>
"""
import json
import pathlib
import sys

import build_city

ROOT = pathlib.Path(__file__).parent
FILE = ROOT.parent / "data" / "cities.json"

if __name__ == "__main__":
    city_id, entry = sys.argv[1], json.loads(pathlib.Path(sys.argv[2]).read_text())
    cities = json.loads(FILE.read_text())
    cities[city_id] = entry
    FILE.write_text(json.dumps(cities, indent=1) + "\n")
    build_city.write_city_index()
    print("registered", city_id, "->", sorted(json.loads((build_city.WEB / "cities.json").read_text())))
