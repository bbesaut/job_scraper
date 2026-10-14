import os
import re
import sys
import requests
from lxml import html as lxml_html
from datetime import datetime

try:
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant
except ImportError:
    # Allows running this file directly (e.g. `python jetaviation.py` from inside scrapers/)
    # by adding the project root to sys.path so the `scrapers` package can be found.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant

COMPANY = "Jet Aviation"
BASE_URL = "https://jobs.jetaviation.com"

# SAP SuccessFactors career site. The list has no JSON API: pagination is a numeric offset
# appended to the path (`.../8766702/` -> rows 1+, `.../8766702/25/` -> rows 26+).
LIST_URL = f"{BASE_URL}/go/Europe/8766702/"

# Only jobs whose location contains one of these (case-insensitive) are kept.
TARGET_AREAS = ("basel",)

# Safety net so a site that ignores the offset can never make the loop run forever.
MAX_PAGES = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def _clean(text: str) -> str:
    return " ".join(text.split())


def _job_id(url: str) -> str:
    """The trailing number of `/job/<slug>/<id>/` — stable even if the slug changes."""
    match = re.search(r"/(\d+)/?$", url)
    return match.group(1) if match else url


def parse_rows(tree) -> list:
    rows = []
    for row in tree.xpath('//tr[contains(@class, "data-row")]'):
        links = row.xpath('.//a[contains(@class, "jobTitle-link")]')
        if not links:
            continue
        href = links[0].get("href", "")
        rows.append({
            "id": _job_id(href),
            "title": _clean(links[0].text_content()),
            "url": BASE_URL + href,
            "location": _clean(" ".join(row.xpath('.//td[contains(@class, "colLocation")]//text()'))),
            "category": _clean(" ".join(row.xpath('.//span[@class="jobFacility"]//text()'))),
            "date": _clean(" ".join(row.xpath('.//span[@class="jobDate"]//text()'))),
        })
    return rows


def _total_results(tree):
    label = _clean(" ".join(tree.xpath('//span[@class="paginationLabel"]//text()')))
    match = re.search(r"of\s+(\d+)", label)
    return int(match.group(1)) if match else None


def fetch_all_rows(session: requests.Session) -> list:
    rows_by_id = {}
    offset = 0
    for _ in range(MAX_PAGES):
        url = LIST_URL if offset == 0 else f"{LIST_URL}{offset}/"
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        tree = lxml_html.fromstring(response.content)

        rows = parse_rows(tree)
        new_rows = [r for r in rows if r["id"] not in rows_by_id]
        if not new_rows:
            break
        for row in new_rows:
            rows_by_id[row["id"]] = row

        offset += len(rows)
        total = _total_results(tree)
        if total is not None and offset >= total:
            break
    return list(rows_by_id.values())


def fetch_description(session: requests.Session, url: str) -> str:
    try:
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        tree = lxml_html.fromstring(response.content)
        blocks = tree.xpath('//span[@itemprop="description"]')
        return _clean(blocks[0].text_content()) if blocks else ""
    except Exception as e:
        print(f"Error fetching details for {url}: {e}")
        return ""


def _in_target_area(row: dict) -> bool:
    location = row["location"].lower()
    return any(area in location for area in TARGET_AREAS)


def scrape_jetaviation():
    job_offers = []
    regex_pattern = build_pattern(load_greenflags())
    greyflag_pattern = build_pattern(load_greyflags())

    try:
        with requests.Session() as session:
            rows = fetch_all_rows(session)
            local_rows = [r for r in rows if _in_target_area(r)]

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] - [{len(rows)}] FOUND on jobs.jetaviation.com. Checking greenflags...")

            for row in local_rows:
                raw_details = fetch_description(session, row["url"])

                if not is_relevant(regex_pattern, row["title"], raw_details, greyflag_pattern):
                    continue

                job_offers.append({
                    "title": row["title"],
                    "company": COMPANY,
                    "location": row["location"],
                    "workload": "Unknown",
                    "contract": row["category"] or "Unknown",
                    "publication_date": row["date"],
                    "raw_details": raw_details,
                    "url": row["url"],
                    "source": "jobs.jetaviation.com"
                })
        return job_offers
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []


if __name__ == "__main__":
    offers = scrape_jetaviation()
    print(f"{len(offers)} annonces pertinentes (greenflags) :\n")
    for offer in offers:
        print(f"- [{offer['publication_date']}] {offer['title']} ({offer['location']}) -> {offer['url']}")
