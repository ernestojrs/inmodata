import requests
from bs4 import BeautifulSoup

URL = "https://www.supercasas.com/sitemap.xml"

print("Downloading sitemap...")
r = requests.get(URL, timeout=30)
print("HTTP status:", r.status_code)
print("Content length:", len(r.text))

# Print first 500 chars of raw XML
print("\n--- RAW XML PREVIEW ---")
print(r.text[:500])
print("--- END PREVIEW ---\n")

# Parse with lxml-xml
soup = BeautifulSoup(r.text, "lxml-xml")

locs = soup.find_all("loc")

print("Total <loc> tags found:", len(locs))

with open("ALL_LOC_URLS.txt", "w", encoding="utf-8") as f:
    for i, loc in enumerate(locs[:20], start=1):
        print(f"{i}: {loc.text.strip()}")
    for loc in locs:
        f.write(loc.text.strip() + "\n")

print("\nSaved ALL_LOC_URLS.txt")
