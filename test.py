import httpx
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

PARAMS = {
    "publicationDateFrom": "2026-06-18 00:00:00",
    "publicationDateTo": "2026-06-19 23:59:59",
    "query": "entwickler",
    "regionIds": [27, 31, 32, 40, 47],
}

SEARCH_URL = "https://job-search-api.jobup.ch/search"
DETAIL_URL_TEMPLATE = "https://www.jobup.ch/api/v1/public/search/job/{id}"


def main():
    resp = httpx.get(SEARCH_URL, headers=HEADERS, params=PARAMS, timeout=20)
    data = resp.json()
    documents = data.get("documents", [])
    print(f"Nombre d'offres: {len(documents)}\n")

    if not documents:
        print("Aucune offre, rien à inspecter.")
        return

    first = documents[0]
    print("=== Clés disponibles dans un document de /search ===")
    print(list(first.keys()))

    print("\n=== Contenu complet du 1er document (liste) ===")
    print(json.dumps(first, indent=2, ensure_ascii=False)[:3000])

    job_id = first.get("id")
    print(f"\n\n=== Appel détail pour id={job_id} ===")
    resp2 = httpx.get(DETAIL_URL_TEMPLATE.format(id=job_id), headers=HEADERS, timeout=20)
    print(f"Status: {resp2.status_code}")
    if resp2.status_code == 200:
        detail = resp2.json()
        print("=== Clés disponibles dans le détail ===")
        print(list(detail.keys()))
        print("\n=== Contenu complet (détail) ===")
        print(json.dumps(detail, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()