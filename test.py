import requests
import re
import json

url = "https://www.jobup.ch/fr/emplois/?publication-date=1&region=27&region=31&region=32&region=40&region=47&term=entwickler"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

response = requests.get(url, headers=headers, timeout=15)

match = re.search(r'__INIT__\s*=\s*', response.text)
start = match.end()
decoder = json.JSONDecoder()
data, _ = decoder.raw_decode(response.text, start)

jobs = data.get('vacancy', {}).get('results', {}).get('main', {}).get('results', [])
print(f"Offres trouvées: {len(jobs)}")