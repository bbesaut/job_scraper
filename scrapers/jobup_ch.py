import httpx
import asyncio
import re
import os
from datetime import datetime
from lxml import html as lxml_html

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8",
}

SEARCH_URL = "https://job-search-api.jobup.ch/search"
DETAIL_URL_TEMPLATE = "https://www.jobup.ch/api/v1/public/search/job/{id}"

EMPLOYMENT_TYPES = {
    "1": "Temporaire",
    "2": "Stage",
    "3": "Apprentissage",
    "4": "Indépendant",
    "5": "CDI",
    "6": "CDD",
}

SEARCH_PARAMS_BASE = {
    "publicationDateFrom": None,
    "publicationDateTo": None,
    "query": "entwickler",
    "regionIds": [27, 31, 32, 40, 47],
}


def load_greenflags():
    filepath = os.path.join(os.path.dirname(__file__), '..', 'greenflags.txt')
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("WARNING: greenflags.txt not found! Using default filters.")
        return ["IT", "java", "c#", "software", "web"]


def strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    tree = lxml_html.fromstring(raw_html)
    text_list = tree.xpath('//text()')
    return " ".join(t.strip() for t in text_list if t.strip())


async def fetch_detail(client: httpx.AsyncClient, job_id: str, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        try:
            resp = await client.get(
                DETAIL_URL_TEMPLATE.format(id=job_id), headers=HEADERS, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching detail for {job_id}: {e}")
            return {}


async def fetch_all_search_pages(client: httpx.AsyncClient, params: dict) -> list:
    documents = []
    page = 1
    while True:
        page_params = {**params, "page": page}
        resp = await client.get(SEARCH_URL, headers=HEADERS, params=page_params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        documents.extend(data.get("documents", []))
        num_pages = data.get("numPages", 1)
        if page >= num_pages:
            break
        page += 1
    return documents


async def scrape_jobup_ch():
    job_offers = []
    keywords = load_greenflags()
    escaped_kws = [re.escape(kw) for kw in keywords]
    regex_pattern = re.compile(r'(?i)(?<![a-z])(' + '|'.join(escaped_kws) + r')(?![a-z])')

    today = datetime.now().strftime("%Y-%m-%d")
    search_params = {
        **SEARCH_PARAMS_BASE,
        "publicationDateFrom": f"{today} 00:00:00",
        "publicationDateTo": f"{today} 23:59:59",
    }

    semaphore = asyncio.Semaphore(4)

    async with httpx.AsyncClient(http2=True) as client:
        try:
            documents = await fetch_all_search_pages(client, search_params)
        except Exception as e:
            print(f"Erreur lors de la récupération de la liste jobup.ch: {e}")
            return []

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - [{len(documents)}] FOUND on jobup.ch. Checking greenflags...")

        detail_tasks = [fetch_detail(client, doc["id"], semaphore) for doc in documents]

        # return_exceptions=True évite que le gather freeze/crash si une requête plante
        details_list = await asyncio.gather(*detail_tasks, return_exceptions=True)

        for doc, detail in zip(documents, details_list):
            # On ignore les exceptions retournées
            if not detail or isinstance(detail, Exception):
                continue

            raw_details = strip_html(detail.get("template_text", ""))
            if not raw_details or not regex_pattern.search(raw_details):
                continue

            job_id = doc.get("id", "")
            full_url = f"https://www.jobup.ch/fr/emplois/detail/{job_id}/" if job_id else "No link"

            grades = doc.get("employmentGrades", [])
            workload = f"{grades[0]}-{grades[-1]}%" if grades else "Unknown"

            type_ids = doc.get("employmentTypeIds", [])
            contract = ", ".join(EMPLOYMENT_TYPES.get(str(tid), f"#{tid}") for tid in type_ids) if type_ids else "Unknown"

            job_offers.append({
                "title": doc.get("title", "Unknown Title"),
                "company": doc.get("company", {}).get("name", "Unknown Company"),
                "location": doc.get("place", "Unknown"),
                "workload": workload,
                "contract": contract,
                "salary": "Unknown",
                "publication_date": doc.get("publicationDate", ""),
                "raw_details": raw_details,
                "url": full_url,
                "source": "jobup.ch"
            })

    return job_offers


if __name__ == "__main__":
    results = asyncio.run(scrape_jobup_ch())
    print(f"\n{len(results)} offres retenues après filtrage.")
    for r in results:
        print(f"- {r['title']} @ {r['company']} ({r['location']}) - {r['url']}")