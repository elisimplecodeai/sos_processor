import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Constants ---
DETAIL_URLS = {
    "business": "https://hbe.ehawaii.gov/documents/business.html",
    "reserved": "https://hbe.ehawaii.gov/documents/reserved.html",
    "trade":    "https://hbe.ehawaii.gov/documents/trade.html",
}
SEARCH_API = "https://hbe.ehawaii.gov/annuals/rest/search"


# Puts registration date into MM/DD/YYYY format
def normalize_date(raw):
    """Convert date to MM/DD/YYYY or return 'N/A'."""
    if not raw:
        return "N/A"
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return raw  # return as-is if unknown format


def format_address(raw):
    """Flatten multi-line address to single line."""
    return " ".join(raw.replace("\n", " ").split()) if raw else "N/A"

def extract_detail_data(soup):
    """Extract structured details from business, reserved, or trade pages."""
    text_map = {dt.get_text(strip=True).upper():
                dt.find_next_sibling("dd").get_text(" ", strip=True)
                if dt.find_next_sibling("dd") else ""
                for dt in soup.find_all("dt")}

    data = {
        "entity_name": "N/A", "registration_date": "N/A", "entity_type": "N/A",
        "business_identification_number": "N/A", "entity_status": "N/A",
        "statusActive": False, "address": "N/A"
    }

    if "MASTER NAME" in text_map:  # Business page
        data["entity_name"] = text_map.get("MASTER NAME", "N/A")
        data["entity_type"] = text_map.get("BUSINESS TYPE", "N/A")
        data["business_identification_number"] = text_map.get("FILE NUMBER", "N/A")
        data["entity_status"] = text_map.get("STATUS", "N/A")
        data["registration_date"] = normalize_date(text_map.get("REGISTRATION DATE"))
        data["address"] = format_address(text_map.get("PRINCIPAL ADDRESS", "N/A"))
    # Other page types can be added here if needed (e.g., "RESERVED NAME", "TRADE NAME")

    data["statusActive"] = data["entity_status"].upper() == "ACTIVE"
    return data

def fetch_details(file_number):
    """Fetch detail page (business, reserved, or trade) and extract data."""
    if not file_number:
        return None
    for detail_url in DETAIL_URLS.values():
        try:
            resp = requests.get(f"{detail_url}?fileNumber={file_number}", timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                details = extract_detail_data(soup)
                # Ensure we got valid data before returning
                if details and details.get("business_identification_number") != "N/A":
                    return details
        except requests.RequestException:
            continue
    return None

# Main search function
def search_hi(search_args):
    """Search Hawaii registry by filing number or entity name."""
    filing_num = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")

    if not filing_num and not entity_name:
        return {"error": "Filing number or entity name required for Hawaii search."}

    search_term = filing_num or entity_name
    payload = {"search": search_term, "page": 1, "limit": 20}
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(SEARCH_API, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"error": f"Search request failed: {e}"}
    except ValueError:
        return {"error": "Failed to parse JSON response from the server."}

    matches = data.get("matches", [])
    if not matches:
        return {"error": f"No results found for '{search_term}'."}

    # --- MODIFIED BEHAVIOR ---
    # If one or more results are found, always process the first one.
    top_result = matches[0]
    file_number = top_result.get("fileNumber", {}).get("asText")

    if not file_number:
        return {"error": "Could not extract a file number from the top search result."}
    
    details = fetch_details(file_number)
    
    if details:
        return details
    
    return {"error": f"Failed to fetch or parse details for file number {file_number}."}