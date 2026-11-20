import json

import add_city
import build_city


def test_slug_and_aliases():
    assert add_city.slug("Navi Mumbai") == "navi-mumbai"
    assert add_city.slug("  São Paulo ") == "s-o-paulo"
    assert add_city.MB_ALIASES[add_city.slug("Bengaluru")] == "bangalore"


def test_clamp_bbox_caps_huge_regions_around_the_centre():
    s, w, n, e = add_city.clamp_bbox([17.9, 73.3, 19.4, 75.2], 18.52, 73.85)
    assert round(n - s, 2) == add_city.MAX_SPAN and round(e - w, 2) == add_city.MAX_SPAN
    assert s < 18.52 < n and w < 73.85 < e


def test_clamp_bbox_widens_tiny_boxes():
    s, w, n, e = add_city.clamp_bbox([12.0, 77.0, 12.001, 77.001], 12.0005, 77.0005)
    assert n - s >= 0.06 - 1e-9 and e - w >= 0.06 - 1e-9


def test_zoom_is_closer_for_smaller_cities():
    assert add_city.zoom_for([28.33, 76.88, 28.55, 77.16]) > add_city.zoom_for([18.3, 73.6, 18.75, 74.05])


def _square(lng, lat, d):
    return [[lng, lat], [lng + d, lat], [lng + d, lat + d], [lng, lat + d], [lng, lat]]


def test_osm_projects_keeps_complexes_and_skips_neighbourhoods(tmp_path):
    areas = {"type": "FeatureCollection", "features": [
        {"properties": {"osm": "way/1", "name": "Green Meadows"}, "geometry": {"type": "Polygon", "coordinates": [_square(75.80, 26.90, 0.003)]}},
        {"properties": {"osm": "way/2", "name": "Whole Ward"}, "geometry": {"type": "Polygon", "coordinates": [_square(75.70, 26.80, 0.05)]}},
    ]}
    cx = [
        {"k": "place", "name": "Malviya Nagar", "lng": 75.801, "lat": 26.901},
        {"k": "complex", "osm": "way/3", "name": "Tower A", "ring": _square(75.8005, 26.9005, 0.0003), "building": "apartments"},
        {"k": "complex", "osm": "way/4", "name": "Sunrise Heights", "ring": _square(75.85, 26.95, 0.0003), "building": "apartments", "flats": "120"},
    ]
    (tmp_path / "osm_areas.geojson").write_text(json.dumps(areas))
    (tmp_path / "osm_complexes.json").write_text(json.dumps(cx))
    got = {p["name"]: p for p in build_city.osm_projects(tmp_path)}
    assert set(got) == {"Green Meadows", "Sunrise Heights"}
    assert got["Green Meadows"]["config_text"] == "apartment"  # has an apartment building inside
    assert got["Green Meadows"]["locality"] == "Malviya Nagar"
    assert got["Sunrise Heights"]["units"] == 120
    assert got["Sunrise Heights"]["url"] == "https://www.openstreetmap.org/way/4"
