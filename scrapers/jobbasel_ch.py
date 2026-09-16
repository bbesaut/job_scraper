import os
import sys
import requests
from lxml import html as lxml_html
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant
except ImportError:
    # Allows running this file directly (e.g. `python jobbasel_ch.py` from inside scrapers/)
    # by adding the project root to sys.path so the `scrapers` package can be found.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant

MAX_AGE = timedelta(hours=2)
PARIS_TZ = ZoneInfo("Europe/Paris")

SEARCH_URL = "https://api.jobbasel.ch/frontend/vacancy/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

CATEGORY_IDS = [57, 43, 44, 41, 56, 52, 54, 55, 45, 59, 50, 60, 49, 42, 47, 48, 58, 46, 51, 53]

SEARCH_PARAMS_BASE = {
    "search": "software",
    "category[]": CATEGORY_IDS,
    "placeType": "kanton",
    "placeCode": "",
    "pageSize": 50,
    "order": "by_date",
}

# The API only accepts a single canton per request (no array support for `place`),
# so each canton is fetched separately and merged/deduped by id in fetch_all_items().
PLACES = [
    {"place": "Basel-Stadt", "placeValue": "Basel-Stadt (Kanton)"},
    {"place": "Basel-Landschaft", "placeValue": "Basel-Landschaft (Kanton)"},
]


def strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    tree = lxml_html.fromstring(raw_html)
    text_list = tree.xpath('//text()')
    return " ".join(t.strip() for t in text_list if t.strip())


def dedupe_snippet(text: str) -> str:
    """The jobbasel.ch API repeats the same highlighted snippet around the
    matched search term (e.g. "... X ...  ... X ...") in activity/requirements/offer,
    which double-counts keyword hits in is_relevant(). Collapsing repeated
    "..."-separated chunks restores the true number of distinct mentions."""
    seen = set()
    unique_chunks = []
    for chunk in text.split("..."):
        chunk = chunk.strip()
        if chunk and chunk not in seen:
            seen.add(chunk)
            unique_chunks.append(chunk)
    return " ".join(unique_chunks)


def fetch_place_items(session: requests.Session, place_params: dict) -> list:
    items = []
    page = 1
    while True:
        params = {**SEARCH_PARAMS_BASE, **place_params, "page": page}
        response = session.get(SEARCH_URL, headers=HEADERS, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        page_items = data.get("items", [])
        items.extend(page_items)
        total = data.get("total", len(items))
        if not page_items or len(items) >= total:
            break
        page += 1
    return items


def fetch_all_items(session: requests.Session) -> list:
    items_by_id = {}
    for place_params in PLACES:
        for item in fetch_place_items(session, place_params):
            items_by_id[item["id"]] = item
    return list(items_by_id.values())


def scrape_jobbasel_ch():
    job_offers = []
    keywords = load_greenflags()
    regex_pattern = build_pattern(keywords)
    greyflag_pattern = build_pattern(load_greyflags())

    try:
        with requests.Session() as session:
            items = fetch_all_items(session)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - [{len(items)}] FOUND on jobbasel.ch. Checking greenflags...")

        for item in items:
            title = strip_html(item.get("title", "")) or "Unknown Title"

            raw_details = " ".join(
                dedupe_snippet(strip_html(item.get(field, "")))
                for field in ("activity", "requirements", "offer")
            ).strip()

            if not is_relevant(regex_pattern, title, raw_details, greyflag_pattern):
                continue

            company = item.get("company", {}).get("name", "Unknown Company")
            location = item.get("workplaceCity") or item.get("company", {}).get("city", "Unknown")

            value_min = item.get("typeValueMin")
            value_max = item.get("typeValueMax")
            if value_min is not None and value_max is not None:
                workload = f"{value_min}%" if value_min == value_max else f"{value_min}-{value_max}%"
            else:
                workload = "Unknown"

            full_url = item.get("urlDescription") or item.get("urlApplication") or "No link"

            job_offers.append({
                "title": title,
                "company": company,
                "location": location,
                "workload": workload,
                "contract": "Unknown",
                "publication_date": item.get("dateFirstPublished", ""),
                "raw_details": raw_details,
                "url": full_url,
                "source": "jobbasel.ch"
            })
        return job_offers
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []


def _published_recently(item: dict) -> bool:
    raw_date = item.get("dateFirstPublished")
    if not raw_date:
        return False
    try:
        published = datetime.fromisoformat(raw_date)
    except ValueError:
        return False
    return datetime.now(PARIS_TZ) - published <= MAX_AGE


if __name__ == "__main__":
    regex_pattern = build_pattern(load_greenflags())
    greyflag_pattern = build_pattern(load_greyflags())

    with requests.Session() as session:
        items = fetch_all_items(session)

    recent_items = [i for i in items if _published_recently(i)]

    relevant_items = []
    for item in recent_items:
        title = strip_html(item.get("title", ""))
        raw_details = " ".join(
            dedupe_snippet(strip_html(item.get(field, ""))) for field in ("activity", "requirements", "offer")
        ).strip()
        if is_relevant(regex_pattern, title, raw_details, greyflag_pattern):
            relevant_items.append(item)

    max_age_hours = int(MAX_AGE.total_seconds() // 3600)
    print(
        f"{len(relevant_items)}/{len(items)} annonces publiées il y a moins de {max_age_hours}h "
        f"et pertinentes (greenflags) :\n"
    )
    for item in relevant_items:
        published = datetime.fromisoformat(item["dateFirstPublished"]).astimezone(PARIS_TZ)
        print(f"- [{published.strftime('%Y-%m-%d %H:%M')}] {strip_html(item.get('title', ''))}")
