import requests
from bs4 import BeautifulSoup
import re
import time

SITEMAP_URL = "https://www.supercasas.com/sitemap.xml"
HEADERS = {
    "User-Agent": "InmoDataResearchBot/1.0(educational research)"
}    

LISTING_REGEX = re.compile(
    r"https://www\.supercasas\.com/.+/\d+/?$"
)

def save_and_count():
    print("Starting to scrape listing URLs...")
    print("Downloading sitemap...")
    response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=30)   
    response.raise_for_status()
    xml_text = response.content.decode("utf-8-sig")
    print("Sitemap downloaded successfully.")
    soup = BeautifulSoup(xml_text, "xml")
    count = 0
    locs = soup.find_all("loc")
    print(f"Total <loc> tags found in sitemap: {len(locs)}")
    with open("Listing_urls.txt","w",encoding="utf-8") as f:
        print("Extracting URLs from sitemap...")
        for i, loc in enumerate(locs, start=1):
            url = loc.text.strip()

            if i % 500 == 0:
                print(f"Processed {i}/{len(locs)} <locs> from sitemap...")           

            if LISTING_REGEX.match(url):
                count += 1
                f.write(url + "\n")

                if count % 100 == 0:
                    print(f"Saved {count} listing URLs to file.")
            time.sleep(1)  # Be polite to the server

    print(f"Scraping completed. Total listing URLs saved: {count}")

if __name__ == "__main__":
    save_and_count()
                    