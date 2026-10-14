import os
import re
import sys
import time
import requests
from datetime import datetime
from lxml import html as lxml_html

try:
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant
except ImportError:
    # Allows running this file directly (e.g. `python amacaerospace.py` from inside scrapers/)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant

LISTING_URL = "https://www.amacaerospace.com/job-openings/"
BASEL_CATEGORY = "project_category-basel0"
DETAIL_DELAY_SECONDS = 0.3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

WORKLOAD_RANGE = re.compile(r'(\d{2,3})\s*%?\s*[-–]\s*(\d{2,3})\s*%')
WORKLOAD_SINGLE = re.compile(r'(\d{2,3})\s*%')
# Everything after this heading is generic employer boilerplate (holidays, canteen, Christmas party...).
OFFER_SECTION = re.compile(r'what we offer', re.IGNORECASE)

# The titles are very short, so the greenflags run on the description. It never changes once
# published, so it's fetched once per job and kept for the life of the process.
_details_cache = {}


def clean_text(raw: str) -> str:
    return " ".join(raw.split())


def extract_workload(title: str) -> str:
    match = WORKLOAD_RANGE.search(title)
    if match:
        return f"{match.group(1)}-{match.group(2)}%"
    match = WORKLOAD_SINGLE.search(title)
    if match:
        return f"{match.group(1)}%"
    return "Unknown"


def fetch_listing(session: requests.Session) -> list:
    """Returns [{"title", "url"}] for the Basel tab only (the page also lists Turkey, France, UK)."""
    response = session.get(LISTING_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    tree = lxml_html.fromstring(response.content)

    cards = tree.xpath(
        f'//div[contains(@class, "et_pb_portfolio_item") and contains(@class, "{BASEL_CATEGORY}")]'
    )
    jobs = []
    for card in cards:
        link = card.xpath('.//h2[contains(@class, "et_pb_module_header")]/a')
        if not link:
            continue
        jobs.append({"title": clean_text(link[0].text_content()), "url": link[0].get("href")})
    return jobs


def fetch_details(session: requests.Session, url: str) -> str:
    if url in _details_cache:
        return _details_cache[url]

    response = session.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    tree = lxml_html.fromstring(response.content)

    blocks = tree.xpath('//article[contains(@class, "project")]//div[contains(@class, "entry-content")]')
    text = clean_text(blocks[0].text_content()) if blocks else ""
    text = OFFER_SECTION.split(text, maxsplit=1)[0].strip()

    _details_cache[url] = text
    time.sleep(DETAIL_DELAY_SECONDS)
    return text


def scrape_amacaerospace():
    job_offers = []
    regex_pattern = build_pattern(load_greenflags())
    greyflag_pattern = build_pattern(load_greyflags())

    try:
        with requests.Session() as session:
            listing = fetch_listing(session)

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] - [{len(listing)}] FOUND on amacaerospace.com. Checking greenflags...")

            for job in listing:
                try:
                    raw_details = fetch_details(session, job["url"])
                except requests.RequestException as e:
                    # A single broken detail page shouldn't hide the other offers; the title is still checked.
                    print(f"Could not fetch details for {job['url']}: {e}")
                    raw_details = ""

                if not is_relevant(regex_pattern, job["title"], raw_details, greyflag_pattern):
                    continue

                job_offers.append({
                    "title": job["title"],
                    "company": "AMAC Aerospace",
                    "location": "Basel",
                    "workload": extract_workload(job["title"]),
                    "contract": "Unknown",
                    # The site stamps every job with the same import date, so there is no real one.
                    "publication_date": "",
                    "raw_details": raw_details,
                    "url": job["url"],
                    "source": "amacaerospace.com",
                })
        return job_offers
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []


if __name__ == "__main__":
    offers = scrape_amacaerospace()
    print(f"{len(offers)} relevant offers:\n")
    for offer in offers:
        print(f"- {offer['title']} ({offer['workload']})\n  {offer['url']}")
