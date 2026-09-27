import argparse
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ElementTree
import requests

SITEMAP_URL = "https://www.supercasas.com/sitemap.xml"

HEADERS = {
    "User-Agent": "InmoDataAuthorizedImporter/1.0",
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
}

def tag_name(element):
    return element.tag.rsplit("}",1)[-1]

def get_sitemap_urls():

    session = requests.Session()
    session.headers.update(HEADERS)

    pending_sitemaps = [SITEMAP_URL]
    visited_sitemaps = set()

    while pending_sitemaps:
        sitemap_url = pending_sitemaps.pop(0)

        if sitemap_url in visited_sitemaps:
            continue

        visited_sitemaps.add(sitemap_url)

        response = session.get(
            sitemap_url,
            timeout=30,
        )

        response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        root_name = tag_name(root)

        locations = [
            element.text.strip()
            for element in root.iter()
            if tag_name(element) == "loc"
            and element.text
        ]

        if root_name == "sitemapindex":
            pending_sitemaps.extend(locations)

        elif root_name == "urlset":
            yield from locations

        else:
            print(
                f"Sitemap ignorado por formato no reconocido: "
                f"{sitemap_url}"
            )

def get_target_sector_slug(url,sector_slugs):
    parsed_url = urlparse(url)

    if parsed_url.netloc.lower() != "www.supercasas.com":
        return None

    path = parsed_url.path.strip("/").lower()

    for sector_slug in sector_slugs:
        apartment_path = (
             f"apartamentos-{sector_slug}/"
        )

        apartment_sale_path= (
             f"apartamentos-venta-{sector_slug}/"
        )

        if (
            path.startswith(apartment_path) 
            or path.startswith(apartment_sale_path)
        ):
            return sector_slug

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Obtiene URLs de apartamentos en venta para sectores "
            "específicos de SuperCasas."
        )
    )

    parser.add_argument(
        "--sectors",
        default="el-millon",
        help=(
            "Sectores separados por coma usando el slug de la URL. "
            "Ejemplo: el-millon,naco,piantini"
        ),
    )

    parser.add_argument(
        "--output",
        default="Scraping/target_urls.txt",
        help="Archivo de salida con una URL por línea.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Número máximo de URLs que se guardarán por sector.",
    )

    arguments = parser.parse_args()

    sector_slugs = {
        sector.strip().lower()
        for sector in arguments.sectors.split(",")
        if sector.strip()
    }

    if not sector_slugs:
        raise SystemExit(
            "Debes indicar al menos un sector."
        )

    output_path = Path(arguments.output)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    selected_urls=[]
    seen_urls = set()

    selected_counts = {
        sector_slug: 0
        for sector_slug in sector_slugs
    }

    print("Descargando sitemap...")

    for url in get_sitemap_urls():

        sector_slug = get_target_sector_slug(
            url,
            sector_slugs,
        )

        if not sector_slug:
            continue
       

        if url in seen_urls:
            continue

        if selected_counts[sector_slug] >= arguments.limit:
            continue

        seen_urls.add(url)
        selected_urls.append(url)
        selected_counts[sector_slug] += 1

        if all(
            count >= arguments.limit
            for count in selected_counts.values()
        ):
            break

        

    output_path.write_text(
        "\n".join(selected_urls) + "\n",
        encoding="utf-8",
    )

    print(f"Sectores buscados: {', '.join(sorted(sector_slugs))}")
    print(f"URLs guardadas: {len(selected_urls)}")
    for sector_slug in sorted(selected_counts):
        print(
             f"  {sector_slug}: "
            f"{selected_counts[sector_slug]} URLs"
        )
    print(f"Archivo creado: {output_path}")

if __name__ == "__main__":
    main()


