import requests
import re
import json
from urllib.parse import urljoin

CT_SEARCH_URL = "https://service.ct.gov/business/s/onlinebusinesssearch"
CT_AURA_URL = "https://service.ct.gov/business/s/sfsites/aura"

# ----- Robust extractors ------------------------------------------------------
FWUID_PATTERNS = [
    # Extract fwuid from <meta name="fwuid" content="...">
    re.compile(r'<meta[^>]+name=["\']fwuid["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    # Extract fwuid from window.Aura JS object
    re.compile(r'window\.Aura\s*=\s*{.*?"fwuid"\s*:\s*"([^"]+)"', re.S),
    # Extract fwuid from window.__AURA_CONTEXT__ JS object
    re.compile(r'__AURA_CONTEXT__\s*=\s*{.*?"fwuid"\s*:\s*"([^"]+)"', re.S),
    # Generic fwuid JSON string
    re.compile(r'"fwuid"\s*:\s*"([^"]+)"')
]

APP_MARKUP_PATTERNS = [
    # Extract app markup identifier
    re.compile(r'"APPLICATION@markup://siteforce:communityApp"\s*:\s*"([^"]+)"'),
]

SCRIPT_SRC_PATTERN = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', re.I)

def parse_ct_business_details(rv, fallback_name=None, html=None):
    entity_name = rv.get("businessName") or fallback_name or "N/A"
    registration_date = rv.get("dateFormed") or "N/A"
    entity_type = rv.get("businessType") or "N/A"
    business_id = rv.get("businessALEI") or "N/A"
    entity_status = rv.get("businessStatus") or "N/A"
    status_active = entity_status.upper() == "ACTIVE"

    address = rv.get("businessAddress") or rv.get("mailingAddress") or "N/A"
    address = re.sub(r'\s+', ' ', address).strip()
    
    # Extract ALEI from JSON using either 'businessALEI' or fallback to 'connecticutAlei' if not present
    business_id = rv.get("businessALEI") or rv.get("connecticutAlei") or "N/A"
    # If ALEI is in 'US-CT.BER:0285290' format, extract just the numeric portion
    if business_id.startswith("US-CT.") and ":" in business_id:
        business_id = business_id.split(":")[-1]

    return {
        "entity_name": entity_name,
        "registration_date": registration_date,
        "entity_type": entity_type,
        "business_identification_number": business_id,
        "entity_status": entity_status,
        "statusActive": status_active,
        "address": address
    }

def try_extract_fwuid(text):
    """Attempt to extract fwuid token from given text using multiple patterns."""
    for pat in FWUID_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def try_extract_app_markup(text):
    """Attempt to extract app markup token from given text."""
    for pat in APP_MARKUP_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def extract_from_html_or_scripts(session, base_url, html):
    """Try extracting fwuid and app markup from HTML or external scripts."""
    # Try inline extraction first
    fwuid = try_extract_fwuid(html)
    app_markup = try_extract_app_markup(html)
    if fwuid and app_markup:
        return fwuid, app_markup

    # If not found, crawl external scripts that likely contain bootstrap tokens
    script_srcs = SCRIPT_SRC_PATTERN.findall(html)
    # Prioritize scripts under /s/sfsites/ path
    prioritized = sorted(script_srcs, key=lambda s: ("/s/sfsites/" not in s, len(s)))

    for src in prioritized:
        if "/s/sfsites/" not in src:
            continue
        full = src if src.startswith("http") else urljoin(base_url, src)
        try:
            r = session.get(full, timeout=20)
            if r.status_code == 200 and r.text:
                if not fwuid:
                    fwuid = try_extract_fwuid(r.text)
                if not app_markup:
                    app_markup = try_extract_app_markup(r.text)
                if fwuid and app_markup:
                    return fwuid, app_markup
        except requests.RequestException:
            continue

    raise ValueError("Could not extract fwuid or app markup from initial HTML or scripts.")

def search_ct(search_args):
    """
    Search Connecticut business registry by ALEI (state_filing_number) or entity name.
    Returns a single, normalized details record.
    """
    alei = (search_args or {}).get("state_filing_number")
    entity_name = (search_args or {}).get("entity_name")

    if not alei and not entity_name:
        return {"error": "Either ALEI or entity name required for Connecticut search."}

    if alei:
        search_string = alei.strip()
        search_exact = False
    else:
        search_string = entity_name.strip()
        search_exact = True

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })

    # Initial GET to retrieve fwuid/app markup
    initial_resp = session.get(CT_SEARCH_URL, timeout=30)
    if initial_resp.status_code != 200 or not initial_resp.text:
        return {"error": f"Failed initial GET ({initial_resp.status_code})."}

    try:
        fwuid, app_markup = extract_from_html_or_scripts(session, "https://service.ct.gov", initial_resp.text)
    except Exception as e:
        return {"error": f"Failed to extract fwuid/app markup: {e}"}

    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Referer": CT_SEARCH_URL,
        "Origin": "https://service.ct.gov",
        "Accept": "*/*",
        "User-Agent": session.headers["User-Agent"],
    }

    # Step 1: Search
    search_payload = {
        "message": json.dumps({
            "actions": [{
                "id": "155;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "",
                    "classname": "brs_onlineEnquiryBusinessSearch",
                    "method": "getBusiness",
                    "params": {
                        "searchString": search_string,
                        "searchExactName": search_exact,
                        "type": "",
                        "isExportClicked": True
                    },
                    "cacheable": False,
                    "isContinuation": False
                }
            }]
        }),
        "aura.context": json.dumps({
            "mode": "PROD",
            "fwuid": fwuid,
            "app": "siteforce:communityApp",
            "loaded": {"APPLICATION@markup://siteforce:communityApp": app_markup},
            "dn": [], "globals": {}, "uad": True
        }),
        "aura.pageURI": "/business/s/onlinebusinesssearch",
        "aura.token": "null"
    }

    r1 = session.post(f"{CT_AURA_URL}?r=12&aura.ApexAction.execute=1", headers=headers, data=search_payload, timeout=30)

    try:
        data = r1.json()
    except ValueError:
        m = re.search(r'^\s*({.*})\s*$', r1.text, re.S)
        data = json.loads(m.group(1)) if m else {}

    if not data:
        return {"error": f"Empty or non-JSON search response (status {r1.status_code}).", "debug": r1.text[:500]}

    try:
        search_results = data["actions"][0]["returnValue"]["returnValue"]
        count = search_results["resultCount"]
    except Exception as e:
        return {"error": f"Error parsing search results: {e}", "debug": data}

    if count == 0:
        return {"error": "No results found."}
        
    # --- MODIFIED LOGIC TO SELECT A SINGLE RESULT ---
    result_list = search_results.get("resultList") or []
    result = None

    # If multiple results were found and search was by name, try to find an exact match.
    if count > 1 and entity_name:
        search_name_lower = entity_name.lower()
        for res in result_list:
            if res.get("businessName", "").lower() == search_name_lower:
                result = res
                break  # Found exact match, so we stop looking.

    # If no exact match was found, or if there was only one result, or if search was by number,
    # default to the first result in the list.
    if not result and result_list:
        result = result_list[0]
    
    if not result:
        return {"error": "Could not identify a primary result from the search list."}

    account_id = result.get("accountId")
    if not account_id:
        return {"entity_name": result.get("businessName"), "error": "Missing accountId for details."}

    # Step 2: Fetch details for the selected account
    details_payload = {
        "message": json.dumps({
            "actions": [{
                "id": "159;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "",
                    "classname": "brs_onlineEnquiryBusinessSearch",
                    "method": "getBusinessDetails",
                    "params": {"accountId": account_id},
                    "cacheable": False,
                    "isContinuation": False
                }
            }]
        }),
        "aura.context": json.dumps({
            "mode": "PROD",
            "fwuid": fwuid,
            "app": "siteforce:communityApp",
            "loaded": {"APPLICATION@markup://siteforce:communityApp": app_markup},
            "dn": [], "globals": {}, "uad": True
        }),
        "aura.pageURI": "/business/s/onlinebusinesssearch",
        "aura.token": "null"
    }

    r2 = session.post(f"{CT_AURA_URL}?r=14&aura.ApexAction.execute=1", headers=headers, data=details_payload, timeout=30)

    try:
        details = r2.json()
    except ValueError:
        m = re.search(r'^\s*({.*})\s*$', r2.text, re.S)
        details = json.loads(m.group(1)) if m else {}

    if not details:
        return {"entity_name": result.get("businessName"), "error": f"Empty or non-JSON details response.", "debug": r2.text[:500]}

    try:
        rv = details["actions"][0]["returnValue"]["returnValue"]
        return parse_ct_business_details(rv, fallback_name=result.get("businessName"), html=r2.text)
    except Exception as e:
        return parse_ct_business_details({}, fallback_name=result.get("businessName"), html=r2.text) | {
            "error": f"Error parsing business details: {e}",
            "debug": details
        }