import re
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# swissdevjobs.ch is an IT-only board with few listings, so no keyword relevance filter is applied.
# The listing API returns every Swiss job in one call and has no description field.
API_URL = "https://swissdevjobs.ch/api/jobsLight"
JOB_URL_PREFIX = "https://swissdevjobs.ch/jobs/"
CITY_CATEGORY = "Basel"

# Avoids flooding the channel with stale postings the first time the sent-jobs memory is empty.
MAX_AGE = timedelta(days=30)
PARIS_TZ = ZoneInfo("Europe/Paris")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

WORKLOAD_RANGE = re.compile(r'(\d{2,3})\s*%?\s*[-–]\s*(\d{2,3})\s*%')
WORKLOAD_SINGLE = re.compile(r'(\d{2,3})\s*%')


def extract_workload(title: str) -> str:
    """The API has no workload field; it only ever appears in the title, e.g. "(80 – 100%)"."""
    match = WORKLOAD_RANGE.search(title)
    if match:
        return f"{match.group(1)}-{match.group(2)}%"
    match = WORKLOAD_SINGLE.search(title)
    if match:
        return f"{match.group(1)}%"
    return "Unknown"


def _parse_date(raw_date: str):
    if not raw_date:
        return None
    try:
        return datetime.fromisoformat(raw_date)
    except ValueError:
        return None


def _is_live(item: dict, now: datetime) -> bool:
    if item.get("isPaused") or item.get("deactivatedOn"):
        return False
    expires_on = _parse_date(item.get("expiresOn"))
    return expires_on is None or expires_on > now


def _is_recent(item: dict, now: datetime) -> bool:
    published = _parse_date(item.get("activeFrom"))
    return published is not None and now - published <= MAX_AGE


def _format_salary(item: dict) -> str:
    salary_from = item.get("annualSalaryFrom")
    salary_to = item.get("annualSalaryTo")
    if salary_from and salary_to:
        return f"CHF {salary_from:,} - {salary_to:,}".replace(",", "'")
    return ""


def scrape_swissdevjobs_ch():
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=20)
        response.raise_for_status()
        items = response.json()

        now = datetime.now(PARIS_TZ)
        basel_items = [i for i in items if i.get("cityCategory") == CITY_CATEGORY]
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - [{len(basel_items)}] FOUND on swissdevjobs.ch ({CITY_CATEGORY}).")

        job_offers = []
        for item in basel_items:
            if not _is_live(item, now) or not _is_recent(item, now):
                continue

            title = " ".join(item.get("name", "").split()) or "Unknown Title"
            tags = item.get("technologies") or item.get("filterTags") or []
            details = [_format_salary(item), item.get("expLevel", ""), ", ".join(tags)]

            job_offers.append({
                "title": title,
                "company": item.get("company", "Unknown Company"),
                "location": item.get("actualCity") or item.get("cityCategory", "Unknown"),
                "workload": extract_workload(title),
                "contract": item.get("jobType") or "Unknown",
                "publication_date": item.get("activeFrom", ""),
                "raw_details": " | ".join(d for d in details if d),
                "url": f"{JOB_URL_PREFIX}{item['jobUrl']}",
                "source": "swissdevjobs.ch",
            })
        return job_offers
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []


if __name__ == "__main__":
    offers = scrape_swissdevjobs_ch()
    print(f"{len(offers)} offers published in the last {MAX_AGE.days} days:\n")
    for offer in offers:
        print(f"- [{offer['publication_date'][:10]}] {offer['title']} @ {offer['company']} "
              f"({offer['location']}, {offer['workload']}, {offer['contract']})")
        print(f"  {offer['url']}")
        print(f"  {offer['raw_details']}")
