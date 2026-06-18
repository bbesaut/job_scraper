from playwright.async_api import async_playwright
from datetime import datetime
from lxml import html as lxml_html
import re
import json
import os

def load_greenflags():
    filepath = os.path.join(os.path.dirname(__file__), '..', 'greenflags.txt')
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("WARNING: greenflags.txt not found! Using default filters.")
        return ["IT", "java", "c#", "software", "web"]

async def scrape_jobup_ch():
    target_url = "https://www.jobup.ch/fr/emplois/?publication-date=1&region=27&region=31&region=32&region=40&region=47&term=entwickler"
    job_offers = []

    keywords = load_greenflags()
    escaped_kws = [re.escape(kw) for kw in keywords]
    regex_pattern = re.compile(r'(?i)(?<![a-z])(' + '|'.join(escaped_kws) + r')(?![a-z])')

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # 1. Charger la liste des offres
            page = await browser.new_page()
            await page.goto(target_url)
            await page.wait_for_load_state("networkidle")
            html_content = await page.content()
            await page.close()

            # Extraire le JSON __INIT__
            match = re.search(r'__INIT__\s*=\s*', html_content)
            if not match:
                print("Erreur: __INIT__ introuvable")
                await browser.close()
                return []

            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(html_content, match.end())
            jobs = data.get('vacancy', {}).get('results', {}).get('main', {}).get('results', [])

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] - [{len(jobs)}] FOUND on jobup.ch. Checking greenflags...")

            # 2. Visiter chaque offre dans le même browser
            for job in jobs:
                title = job.get('title', 'Unknown Title')
                place = job.get('place', 'Unknown')
                company = job.get('company', {}).get('name', 'Unknown Company')
                publication_date = job.get('publicationDate', '')
                job_id = job.get('id', '')
                full_url = f"https://www.jobup.ch/fr/emplois/detail/{job_id}/" if job_id else "No link"

                raw_details = ""
                if full_url != "No link":
                    try:
                        detail_page = await browser.new_page()
                        await detail_page.goto(full_url)
                        await detail_page.wait_for_load_state("networkidle")
                        detail_html = await detail_page.content()
                        await detail_page.close()

                        tree = lxml_html.fromstring(detail_html)
                        details_block = tree.xpath('//div[@data-cy="vacancy-description"]')
                        if details_block:
                            text_list = details_block[0].xpath('.//text()')
                            raw_details = " ".join([t.strip() for t in text_list if t.strip()])

                    except Exception as e:
                        print(f"Error fetching details for {title}: {e}")

                if not raw_details or not regex_pattern.search(raw_details):
                    continue

                salary = job.get('salary')
                salary_str = "Unknown"
                if salary:
                    min_val = salary.get('range', {}).get('minValue', '')
                    max_val = salary.get('range', {}).get('maxValue', '')
                    currency = salary.get('currency', 'CHF')
                    if min_val and max_val:
                        salary_str = f"{min_val}-{max_val} {currency}/an"

                grades = job.get('employmentGrades', [])
                workload = f"{grades[0]}-{grades[1]}%" if len(grades) == 2 else "Unknown"

                job_data = {
                    "title": title,
                    "company": company,
                    "location": place,
                    "workload": workload,
                    "salary": salary_str,
                    "publication_date": publication_date,
                    "raw_details": raw_details,
                    "url": full_url,
                    "source": "jobup.ch"
                }
                job_offers.append(job_data)

            await browser.close()

    except Exception as e:
        print(f"An error occurred during scraping: {e}")

    return job_offers