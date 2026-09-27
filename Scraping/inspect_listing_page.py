import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("Scraping")/ "inspection"

HEADERS = {
    "User-Agent": "InmoDataAuthorizedImporter/1.0",
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
}

def print_snippets(text,keyword):
    text_lower = text.lower()
    keyword_lower = keyword.lower()

    position = text_lower.find(keyword_lower)

    if position == -1:
        print(f"- No se encontro : {keyword}")
        return

    start = max(0, position - 120)
    end = min(len(text), position + 220)

    print(f"\n Fragmento para '{keyword}':")
    print(text[start:end])

def inspect_listing(url):
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)

    response = requests.get(
        url,
        headers= HEADERS,
        timeout = 30,
    )

    print(f"Estado HTTP: {response.status_code}")
    print(f"URL final: {response.url}")
    print(f"Tipo de contenido: {response.headers.get('Content-Type')}")

    html_path = OUTPUT_DIR / "sample_listing.html"
    html_path.write_text(
        response.text,
        encoding="utf-8"
    )

    print(f"HTML guardado en: {html_path}")

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    print(f"Titulo: {soup.title.get_text(strip=True) if soup.title else 'Sin titulo'}")

    text = soup.get_text(" ",strip=True)
    text = re.sub(r"\s+", " ", text)

    text_path = OUTPUT_DIR / "sample_listing_text.txt"

    text_path.write_text(
        text,
        encoding="utf-8",
    )

    print(f"Texto guardado en: {text_path}")

    json_ld_scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    )

    print(f"Bloques JSON-LD encontrados: {len(json_ld_scripts)}")

    for index, script in enumerate(json_ld_scripts, start=1):
        json_path = OUTPUT_DIR / f"json_ld_{index}.txt"

        json_path.write_text(
            script.get_text(strip=True),
            encoding="utf-8",
        )

        print(f"JSOND-LD guardado en: {json_path}")

    print("\nBuscando datos relevantes:")

    for keyword in [
        "US$",
        "RD$",
        "Precio",
        "m²",
        "Habitaciones",
        "Baños",
        "Parqueos",
        "Venta",
        "Alquiler",
        "Sector",
        "Ubicación",
    ]:
        print_snippets(text, keyword)

if __name__ == "__main__":
    if len(sys.argv) !=2:
        print(
            "Uso python Scraping\\inspect_listing_page.py"
            "\"https://www.supercasas.com/.../123456/\""


        )

        raise SystemExit(1)

    inspect_listing(sys.argv[1])

    
    
