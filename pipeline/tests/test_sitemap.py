import mb_crawl


def test_sitemap_matches_city_parts_and_other_cities_by_suffix(monkeypatch):
    monkeypatch.setattr(mb_crawl, "project_sitemaps", lambda: {
        "pdp_Beyond_Thane1.xml.gz": [
            "https://www.magicbricks.com/senwin-residency-kalyan-beyond-thane-pdpid-4d42",
            "https://www.magicbricks.com/the-residences-kalyan-west-beyond-thane-pdpid-4d43",
            "https://www.magicbricks.com/lodha-palava-dombivli-east-beyond-thane-pdpid-4d44",
        ],
        "pdp_otherCities.xml.gz": [
            "https://www.magicbricks.com/shiv-aradhana-dombivli-kalyan-pdpid-4d45",
            "https://www.magicbricks.com/anand-sheetal-kalyan-pur-kanpur-pdpid-4d46",
        ],
    })
    hits = mb_crawl.sitemap_matches(["kalyan"])
    assert len(hits["pdp_Beyond_Thane1.xml.gz"]) == 2
    assert hits["pdp_otherCities.xml.gz"] == ["https://www.magicbricks.com/shiv-aradhana-dombivli-kalyan-pdpid-4d45"]
