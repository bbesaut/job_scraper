import os
import sys
import requests
from lxml import etree, html as lxml_html
from datetime import datetime

try:
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant
except ImportError:
    # Allows running this file directly (e.g. `python swissas_teamtailor.py` from inside scrapers/)
    # by adding the project root to sys.path so the `scrapers` package can be found.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant

COMPANY = "Swiss AviationSoftware"

# TeamTailor career sites expose every job (with its full HTML description) as an RSS
# feed, so no HTML scraping and no per-job detail request is needed. Any other
# `<company>.teamtailor.com` site can be added the same way by changing this URL.
FEED_URL = "https://swissas.teamtailor.com/jobs.rss"

# Only jobs with at least one location matching one of these (case-insensitive) are kept.
TARGET_AREAS = ("allschwil", "basel")

TT_NS = {"tt": "https://teamtailor.com/locations"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml",
}


def strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    tree = lxml_html.fromstring(raw_html)
    return " ".join(t.strip() for t in tree.xpath('//text()') if t.strip())


def fetch_items(session: requests.Session) -> list:
    response = session.get(FEED_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    root = etree.fromstring(response.content)
    return root.findall("./channel/item")


def _text(item, path: str, default: str = "") -> str:
    node = item.find(path, TT_NS)
    return (node.text or "").strip() if node is not None else default


def _location(item) -> str:
    cities = [(c.text or "").strip() for c in item.findall(".//tt:location/tt:city", TT_NS)]
    return ", ".join(c for c in cities if c) or "Unknown"


def _in_target_area(item) -> bool:
    """True if any of the job's locations is in the Basel area (matches city or location name)."""
    for location in item.findall(".//tt:location", TT_NS):
        label = " ".join(
            (location.findtext(f"tt:{field}", default="", namespaces=TT_NS) or "").strip()
            for field in ("name", "city")
        ).lower()
        if any(area in label for area in TARGET_AREAS):
            return True
    return False


def scrape_swissas_teamtailor():
    job_offers = []
    regex_pattern = build_pattern(load_greenflags())
    greyflag_pattern = build_pattern(load_greyflags())

    try:
        with requests.Session() as session:
            items = fetch_items(session)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - [{len(items)}] FOUND on swissas.teamtailor.com. Checking greenflags...")

        for item in items:
            if not _in_target_area(item):
                continue

            title = _text(item, "title", "Unknown Title")
            raw_details = strip_html(_text(item, "description"))

            if not is_relevant(regex_pattern, title, raw_details, greyflag_pattern):
                continue

            job_offers.append({
                "title": title,
                "company": COMPANY,
                "location": _location(item),
                "workload": "Unknown",
                "contract": "Unknown",
                "publication_date": _text(item, "pubDate"),
                "raw_details": raw_details,
                "url": _text(item, "link", "No link"),
                "source": "swissas.teamtailor.com"
            })
        return job_offers
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []


if __name__ == "__main__":
    offers = scrape_swissas_teamtailor()
    print(f"{len(offers)} annonces pertinentes (greenflags) :\n")
    for offer in offers:
        print(f"- {offer['title']} ({offer['location']}) -> {offer['url']}")
