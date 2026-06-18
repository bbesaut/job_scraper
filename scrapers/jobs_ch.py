import requests
from lxml import html
from datetime import datetime
import time
import os
import re

def load_greenflags():
    filepath = os.path.join(os.path.dirname(__file__), '..', 'greenflags.txt')
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # On retourne une liste propre sans les sauts de ligne
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("WARNING: greenflags.txt not found! Using default filters.")
        return ["IT", "java", "c#", "software", "web"]

def scrape_jobs_ch():
    target_url = "https://www.jobs.ch/fr/offres-emplois/?publication-date=0.5&region=8&region=12&region=14&term=d%C3%A9veloppeur" 
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    job_offers = []
    
    keywords = load_greenflags()
    
    escaped_kws = [re.escape(kw) for kw in keywords]
    regex_pattern = re.compile(r'(?i)(?<![a-z])(' + '|'.join(escaped_kws) + r')(?![a-z])')
    
    try:
        response = requests.get(target_url, headers=headers)
        response.raise_for_status() 
        tree = html.fromstring(response.content)
        job_cards = tree.xpath('//a[@data-cy="job-link"]')
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - [{len(job_cards)}] FOUND on jobs.ch. Checking greenflags...")
        
        for card in job_cards:
            title_list = card.xpath('./@title')
            title = title_list[0] if title_list else "Unknown Title"
            
            url_list = card.xpath('./@href')
            url_path = url_list[0] if url_list else ""
            full_url = f"https://www.jobs.ch{url_path}" if url_path else "No link"
            
            raw_details = ""
            if full_url != "No link":
                try:
                    detail_resp = requests.get(full_url, headers=headers)
                    detail_tree = html.fromstring(detail_resp.content)
                    
                    details_block = detail_tree.xpath('//div[@data-cy="vacancy-description"]')
                    
                    if details_block:
                        block = details_block[0]
                        for section in block.xpath('.//section'):
                            section.getparent().remove(section)
                            
                        text_list = block.xpath('.//text()')
                        full_text = " ".join([t.strip() for t in text_list if t.strip()])
                        if full_text:
                            raw_details = full_text
                        
                    time.sleep(0.5) 
                except Exception as e:
                    print(f"Error fetching details for {title}: {e}")

            if not raw_details or not regex_pattern.search(raw_details):
                continue

            company_list = card.xpath('.//p[contains(@class, "fw_bold")]/text()')
            company = company_list[0].strip() if company_list else "Unknown Company"
            
            loc_list = card.xpath('.//span[contains(text(), "Lieu de travail")]/following-sibling::p/text()')
            location = loc_list[0].strip() if loc_list else "Unknown"
            
            work_list = card.xpath('.//span[contains(text(), "Taux d\'activité")]/following-sibling::p/text()')
            workload = work_list[0].strip() if work_list else "Unknown"
            
            contract_list = card.xpath('.//span[contains(text(), "Type de contrat")]/following-sibling::p/text()')
            contract = contract_list[0].strip() if contract_list else "Unknown"
            
            job_data = {
                "title": title,
                "company": company,
                "location": location,
                "workload": workload,
                "contract": contract,
                "raw_details": raw_details, 
                "url": full_url,
                "source": "jobs.ch"
            }
            job_offers.append(job_data)
            
        return job_offers
        
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return []