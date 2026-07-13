import requests
import xml.etree.ElementTree as ET
import csv
import os
import time
from datetime import datetime

# Configuration
SEARCH_TERMS = ["hematology", "thrombosis", "sickle cell disease"]
DAYS_BACK = 120
MAX_RESULTS = 200
DOWNLOAD_FOLDER = "papers"
CSV_FILE = "collection.csv"

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
OA_API_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"



def search_pubmed(query, days_back=30, max_results=20):
    """Search PubMed for recent articles matching the query."""
    url = f"{BASE_URL}esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "reldate": days_back,
        "datetype": "edat",
        "retmode": "xml"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()

    # Parse the XML response to pull out article IDs
    root = ET.fromstring(response.text)
    pmids = [id_elem.text for id_elem in root.findall(".//Id")]
    count = root.findtext(".//Count", default="0")

    print(f"Found {count} results for '{query}', retrieved {len(pmids)} PMIDs")
    return pmids

def fetch_article_details(pmids):
    """Fetch detailed metadata for a list of PMIDs."""
    if not pmids:
        return []

    url = f"{BASE_URL}efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    articles = []
    
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")

        title = article.findtext(".//ArticleTitle", default="No title")

        authors = []
        for author in article.findall(".//Author"):
            last_name = author.findtext("LastName", default="")
            fore_name = author.findtext("ForeName", default="")
            if last_name:
                authors.append(f"{last_name} {fore_name}".strip())
        authors_str = "; ".join(authors[:5])
        if len(authors) > 5:
            authors_str += " et al."

        pub_date = article.find(".//PubDate")
        year = pub_date.findtext("Year", default="") if pub_date is not None else ""
        month = pub_date.findtext("Month", default="") if pub_date is not None else ""
        day = pub_date.findtext("Day", default="") if pub_date is not None else ""
        date_str = f"{year} {month} {day}".strip()

        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(part.text or "" for part in abstract_parts)

        doi = ""
        for article_id in article.findall(".//ArticleId"):
            if article_id.get("IdType") == "doi":
                doi = article_id.text or ""
                break

        pmc_id = ""
        for article_id in article.findall(".//ArticleId"):
            if article_id.get("IdType") == "pmc":
                pmc_id = article_id.text or ""
                break

        articles.append({
            "pmid": pmid,
            "title": title,
            "authors": authors_str,
            "date": date_str,
            "abstract": abstract[:500],
            "doi": doi,
            "pmc_id": pmc_id
        })

    return articles
    
def check_pdf_availability(pmc_id):
    """Check if a PDF is available for download via PMC OA API."""
    params = {"id": pmc_id}
    response = requests.get(OA_API_URL, params=params)
    response.raise_for_status()

    root = ET.fromstring(response.text)

    # Look for a link element with format="pdf"
    for link in root.findall(".//link"):
        if link.get("format") == "pdf":
            href = link.get("href", "")
            # Convert FTP URLs to HTTPS and account for the 2026 'deprecated/' folder shift
            if href.startswith("ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/"):
                href = href.replace(
                    "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/",
                    "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/"
                )
            elif href.startswith("ftp://ftp.ncbi.nlm.nih.gov"):
                href = href.replace(
                    "ftp://ftp.ncbi.nlm.nih.gov",
                    "https://ftp.ncbi.nlm.nih.gov"
                )
            return href

    return None

def download_pdf(url, filename, folder):
    """Download a PDF file to the specified folder."""
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    # Skip if already downloaded
    if os.path.exists(filepath):
        print(f"  Already downloaded: {filename}")
        return filepath

    # Stream the download to handle large files
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"  Downloaded: {filename}")
    return filepath


def load_existing_pmids(csv_file):
    """Load PMIDs already in the collection CSV."""
    if not os.path.exists(csv_file):
        return set()

    existing = set()
    with open(csv_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.add(row["pmid"])
    return existing


def save_to_csv(articles, csv_file):
    """Save article metadata to the collection CSV."""
    file_exists = os.path.exists(csv_file)

    # Added "search_term" column to the schema
    fieldnames = [
        "pmid", "search_term", "title", "authors", "date", "doi",
        "pmc_id", "pdf_downloaded", "pdf_filename", "added_date", "abstract"
    ]

    with open(csv_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for article in articles:
            writer.writerow(article)

def print_collection_summary(csv_file):
    """Print a summary report of the current collection."""
    if not os.path.exists(csv_file):
        print("No collection found yet.")
        return

    with open(csv_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    with_pdf = sum(1 for r in rows if r["pdf_downloaded"] == "Yes")

    print("\nCOLLECTION SUMMARY")
    print("-" * 40)
    print(f"Total articles: {total}")
    print(f"PDFs downloaded: {with_pdf}")
    print(f"Metadata only: {total - with_pdf}")

    terms = {}
    for row in rows:
        t = row.get("search_term", "Unknown")
        terms[t] = terms.get(t, 0) + 1

    print(f"\nArticles by topic:")
    for term, count in sorted(terms.items(), key=lambda x: x[1], reverse=True):
        print(f"  {term}: {count} articles")

def main():
    """Main function to run the PubMed monitor."""
    print("=" * 60)
    print("PubMed Research Paper Monitor")
    print("=" * 60)

    existing_pmids = load_existing_pmids(CSV_FILE)
    print(f"\nExisting papers in collection: {len(existing_pmids)}")

    all_new_articles = []

    for term in SEARCH_TERMS:
        print(f"\nSearching for: {term}")
        print("-" * 40)

        pmids = search_pubmed(term, days_back=DAYS_BACK, max_results=MAX_RESULTS)
        time.sleep(0.4)

        new_pmids = [p for p in pmids if p not in existing_pmids]
        print(f"New papers to process: {len(new_pmids)}")

        if not new_pmids:
            continue

        articles = fetch_article_details(new_pmids)
        time.sleep(0.4)

        for article in articles:
            article["pdf_downloaded"] = "No"
            article["pdf_filename"] = ""
            article["added_date"] = datetime.now().strftime("%Y-%m-%d")
            article["search_term"] = term

            if article["pmc_id"]:
                print(f"\n  Checking PDF for: {article['title'][:60]}...")
                time.sleep(0.4)

                pdf_url = check_pdf_availability(article["pmc_id"])

                if pdf_url:
                    filename = f"{article['pmc_id']}.pdf"
                    try:
                        download_pdf(pdf_url, filename, DOWNLOAD_FOLDER)
                        article["pdf_downloaded"] = "Yes"
                        article["pdf_filename"] = filename
                    except Exception as e:
                        print(f"  Failed to download: {e}")

            all_new_articles.append(article)
            existing_pmids.add(article["pmid"])

    if all_new_articles:
        save_to_csv(all_new_articles, CSV_FILE)
        print(f"\n{'=' * 60}")
        print(f"Added {len(all_new_articles)} new papers to {CSV_FILE}")
        pdfs = sum(1 for a in all_new_articles if a["pdf_downloaded"] == "Yes")
        print(f"Downloaded {pdfs} PDFs to '{DOWNLOAD_FOLDER}/' folder")
    else:
        print(f"\n{'=' * 60}")
        print("No new papers found.")

    print_collection_summary(CSV_FILE)
    print("=" * 60)
 



if __name__ == "__main__":
    main()