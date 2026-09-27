import argparse
import csv
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import requests
from bs4 import BeautifulSoup

CSV_COLUMNS = [
    "source",
    "source_listing_id",
    "source_url",
    "property_type",
    "operation_type",
    "sector",
    "city",
    "price",
    "currency",
    "area_m2",
    "bedrooms",
    "bathrooms",
    "parking_spaces",
    "is_active",
]

REJECTED_COLUMNS = [
    "source_url",
    "reason",
]

HEADERS = {
    "User-Agent": "InmoDataAuthorizedImporter/1.0",
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
}

class AccessLimitError(Exception):
    pass

def normalize_url(value):
    value = value.strip()
    markdown_match = re.fullmatch(
         r"\[.*?\]\((https?://[^)]+)\)",
        value,
    )

    if markdown_match:
        return markdown_match.group(1)

    return value

def normalize_text(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    return re.sub(r"\s+", " ", text)

def decimal_from_text(value):
    normalized_value = value.replace(",", "").strip()

    try:
        return Decimal(normalized_value)
    except InvalidOperation as error:
        raise ValueError(
            f"No se pudo convertir a numero: {value}"
        ) from error 

def extract_required_match(pattern, text, field_name):
    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE
    )

    if not match:
        raise ValueError(
            f"No se encontro el campo requerido: {field_name}"
        )

    return match


def page_is_missing(html):
    missing_messages = [
        "404 - File or directory not found.",
        "The resource you are looking for might have been removed",
        "Página no encontrada",
    ]

    return any(
        message.lower() in html.lower()
        for message in missing_messages
    )

def normalize_sector(sector):
     sector_aliases = {
        "Ensanche Naco": "Naco",
        "El Millon": "El Millón",
        "Bella Vista Sur": "Bella Vista",
    }

     return  sector_aliases.get(sector.strip(), sector.strip())


def extract_listing(url, html):

    if page_is_missing(html):
        raise ValueError(
            "La publicación ya no está disponible."
        )
    
    if "/apartamentos-" not in url.lower():
        raise ValueError(
            "La URL no corresponde a un apartamento."
        )

    if not re.search(
        r"\bVenta:\s*(?:US\$|RD\$)",
        html,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            "La propiedad no está publicada como venta."
        )

    listing_id_match = re.search(
        r"/(\d+)/?$",
        url,
    )

    if not listing_id_match:
        raise ValueError(
            "No se pudo, obtener el id de la propiedad desde la URL"
        )

    price_match = extract_required_match(
        r"venta: \s*(US\$|RD\$)\s*([\d,.]+)",
        html,
        "precio de venta"
    )

    currency_symbol = price_match.group(1).upper()
    price = decimal_from_text(price_match.group(2))

    currency = {
        "US$": "USD",
        "RD$": "DOP",
    }.get(currency_symbol)

    if not currency:
        raise ValueError("Moneda no compatible")

    if not currency:
        raise ValueError("Moneda no compatible")

    if (
        currency == "USD"
        and Decimal("100") <= price < Decimal("10000")
    ):
        price = price * Decimal("1000")

    if currency == "USD" and price < Decimal("10000"):
        raise ValueError(
        "El precio encontrado es demasiado bajo para "
        "un apartamento en venta. Se rechazó para revisión."
        )

    location_match = extract_required_match(
        r"Localización: \s*(.+?)\s+Condición:",
        html,
        "localización",
    )

    location = location_match.group(1).strip()

    if ">" not in location:
        raise ValueError(
            "La localizacion no contiene uan estrcutura de sector"
        )

    sector = location.split(">")[-1].strip()
    sector = normalize_sector(sector)

    SECTOR_ALIASES = {
    "Ensanche Naco": "Naco",
    "Naco": "Naco",
    "El Millon": "El Millón",
    "El Millón": "El Millón",
    "Bella Vista Sur": "Bella Vista",
    }

    sector = SECTOR_ALIASES.get(sector, sector)



    if not sector:

        raise ValueError("No se pudo determinar el sector")

    if "santo domingo" not in location.lower():
        raise ValueError(
            "la propiedad esta fuera de santo domingo"
        )

    construction_match = extract_required_match(
        r"Construcción:\s*([\d,.]+)\s*(?:Mt2|m2|m²)",
        html,
        "área de construcción",
    )

    bedrooms_match = extract_required_match(
        r"(\d+)\s+habitaci(?:ón|ones)",
        html,
        "habitaciones",
    )

    bathrooms_match = extract_required_match(
        r"([\d,.]+)\s+baño(?:s)?",
        html,
        "baños",
    )

    parking_match = extract_required_match(
        r"(\d+)\s+parqueo(?:s)?",
        html,
        "parqueos",
    )

    area_m2 = decimal_from_text(construction_match.group(1))

    if area_m2 <= 0:
        raise ValueError(
             "El área de construcción debe ser mayor que cero."
        )

    return {
        "source": "supercasas",
        "source_listing_id": (
            f"SUPERCASAS-{listing_id_match.group(1)}"
        ),
        "source_url": url,
        "property_type": "apartment",
        "operation_type": "sale",
        "sector": sector,
        "city": "Santo Domingo",
        "price": str(price),
        "currency": currency,
        "area_m2": str(
            area_m2
        ),
        "bedrooms": bedrooms_match.group(1),
        "bathrooms": str(
            decimal_from_text(bathrooms_match.group(1))
        ),
        "parking_spaces": parking_match.group(1),
        "is_active": "true",
    }

def get_urls(input_path, limit):
    seen_urls = set()
    for line in input_path.read_text(
        encoding="utf-8-sig",
    ).splitlines():
        url = normalize_url(line)

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        yield url

        if limit and len(seen_urls) >= limit:
            return


def download_html(session, url):
    response = session.get(
        url,
        timeout = 30,
    )

    if response.status_code in {403,429}:
        raise AccessLimitError(
            f"El sitio respondió {response.status_code}. "
            "La extracción se detuvo para respetar el acceso permitido"
        )

    response.raise_for_status()

    return response.text

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extrae datos autorizados de Supercasas "
            "a un CSV compatible con Inmodata"
        )
    )

    parser.add_argument(
        "--input",
        default="Listing_urls.txt",
        help="Archivo de texto con una URL por linea.",
    )

    parser.add_argument(
        "--output",
        default="raw_data/supercasas_listings.csv",
        help="CSV válido para importar en InmoData.",
    )

    parser.add_argument(
        "--rejected-output",
        default="raw_data/supercasas_rejected.csv",
        help="CSV con URLs no procesadas y su motivo.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Cantidad máxima de URLs a procesar.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Segundos de espera entre solicitudes.",
    )

    arguments = parser.parse_args()

    input_path = Path(arguments.input)
    ouput_path = Path(arguments.output)
    rejected_path = Path(arguments.rejected_output)

    if not input_path.exists():
        raise SystemExit(
            f"No existe el archivo de URLs: {input_path}"
        )

    ouput_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rejected_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    extracted_rows = []
    rejected_rows = []

    session = requests.Session()
    session.headers.update(HEADERS)

    urls = list(
        get_urls(
            input_path,
            arguments.limit,
        )
    )

    print(f"URLs seleccionadas: {len(urls)}")

    for index, url in enumerate(urls,start=1):
        print(f"[{index}/{len(urls)}] Procesado: {url}")

        try:
            html = download_html(session,url)
            text = normalize_text(html)

            listing = extract_listing(url, text)
            extracted_rows.append(listing)

            print(
                " OK: "
                f"{listing['sector']} | "
                f"{listing['currency']} {listing['price']} | "
                f"{listing['area_m2']} m²"
            )

        except AccessLimitError as error:
            print(f" DETENIDO: {error}")
            rejected_rows.append(
                {
                    "source_url": url,
                    "reason": str(error),
                }
            )

            break
        except (
            requests.RequestException,
            ValueError,
        ) as error:
            print (f" RECHAZADO: {error}")

            rejected_rows.append(
                {
                    "source_url": url,
                    "reason": str(error),
                }
            )

        if index < len(urls):
            time.sleep(arguments.delay)

    with ouput_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=CSV_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(extracted_rows)

    with rejected_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as rejected_file:
        writer = csv.DictWriter(
            rejected_file,
            fieldnames=REJECTED_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(rejected_rows)

    print()
    print(f"Propiedades extraídas: {len(extracted_rows)}")
    print(f"URLs rechazadas: {len(rejected_rows)}")
    print(f"CSV para importar: {ouput_path}")
    print(f"CSV rechazado: {rejected_path}")

if __name__ == "__main__":
    main()

    