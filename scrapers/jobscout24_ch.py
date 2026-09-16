import requests
from lxml import html
from datetime import datetime
import time
from scrapers.relevance import load_greenflags, load_greyflags, build_pattern, is_relevant

TARGET_URL = "https://www.jobscout24.ch/fr/jobs/?ft=software%2Csoftware&actuality=0&psz=4000"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def fetch_raw_details(url):
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        detail_tree = html.fromstring(response.content)
        blocks = detail_tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " job-description ")]')
        if not blocks:
            return ""
        block = blocks[0]
        for bad in block.xpath('.//style') + block.xpath('.//script'):
            bad.getparent().remove(bad)
        text_list = block.xpath('.//text()')
        return " ".join(t.strip() for t in text_list if t.strip())
    except Exception as e:
        print(f"Error fetching details for {url}: {e}")
        return ""


def scrape_jobscout24_ch():
    job_offers = []

    keywords = load_greenflags()
    regex_pattern = build_pattern(keywords)
    greyflag_pattern = build_pattern(load_greyflags())

    try:
        response = requests.get(TARGET_URL, headers=HEADERS)
        response.raise_for_status()
        tree = html.fromstring(response.content)

        # li.job-list-item (with or without "active") > div.upper-line > a
        items = tree.xpath('//li[contains(concat(" ", normalize-space(@class), " "), " job-list-item ")]')

        new_items = []
        seen_hrefs = set()
        for item in items:
            dates = item.xpath('.//p[contains(concat(" ", normalize-space(@class), " "), " job-date ")]')
            if not any(d.text_content().strip() == "New" for d in dates):
                continue

            link = item.xpath('.//div[contains(concat(" ", normalize-space(@class), " "), " upper-line ")]//a')
            href = link[0].get("href", "") if link else ""
            if href and href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            new_items.append(item)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - [{len(new_items)}] FOUND on jobscout24.ch. Checking greenflags...")

        for item in new_items:
            link = item.xpath('.//div[contains(concat(" ", normalize-space(@class), " "), " upper-line ")]//a')
            link = link[0] if link else None
            title = link.text_content().strip() if link is not None else "Unknown Title"
            href = link.get("href", "") if link is not None else ""
            full_url = f"https://www.jobscout24.ch{href}" if href else "No link"

            raw_details = ""
            if full_url != "No link":
                raw_details = fetch_raw_details(full_url)
                time.sleep(0.5)

            if not is_relevant(regex_pattern, title, raw_details, greyflag_pattern):
                continue

            attr_spans = item.xpath('.//p[contains(concat(" ", normalize-space(@class), " "), " job-attributes ")]//span')
            company = attr_spans[0].text_content().strip() if len(attr_spans) > 0 else "Unknown Company"
            location = attr_spans[1].text_content().strip() if len(attr_spans) > 1 else "Unknown"

            tags = item.xpath('.//span[contains(concat(" ", normalize-space(@class), " "), " tag-readonly ")]')
            workload = ""
            for tag in tags:
                tag_text = tag.text_content().strip()
                if "%" in tag_text:
                    workload = tag_text
                    break

            job_offers.append({
                "title": title, "company": company, "location": location,
                "workload": workload, "contract": "", "url": full_url, "source": "jobscout24.ch"
            })
        return job_offers
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []


if __name__ == "__main__":
    results = scrape_jobscout24_ch()
    print(f"\n{len(results)} offres retenues après filtrage.")
    for r in results:
        print(f"- {r['title']} @ {r['company']} ({r['location']}) - {r['url']}")
