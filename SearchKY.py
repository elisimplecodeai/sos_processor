from playwright.sync_api import sync_playwright, TimeoutError
from urllib.parse import urljoin

SEARCH_URL = "https://sosbes.sos.ky.gov/BusSearchNProfile/search.aspx"

def do_search(page, search_text):
    """Navigates and performs the initial search."""
    page.goto(SEARCH_URL, timeout=30000)
    page.wait_for_selector("#MainContent_txtSearch")
    page.select_option("#MainContent_ddlSearchBy", "Business Name or Organization Number")
    page.fill("#MainContent_txtSearch", str(search_text))
    page.click("#MainContent_BSearch")

def check_no_results(page):
    """Checks for the 'No results found' message."""
    try:
        no_result_div = page.wait_for_selector("#MainContent_pNOSearchresults", timeout=3000)
        return "No matching organizations were found" in no_result_div.inner_text()
    except TimeoutError:
        return False

def parse_results(page, search_args):
    """
    Parses the search results table, implementing 'best guess' logic for multiple results.
    """
    search_term = search_args.get("entity_name") or search_args.get("state_filing_number")

    try:
        page.wait_for_selector("#MainContent_gvSearchResults", timeout=5000)
    except TimeoutError:
        return {"error": "Results table not found."}

    rows = page.query_selector_all("#MainContent_gvSearchResults tbody tr")
    data_rows = [r for r in rows if "Headerbg" not in (r.get_attribute("class") or "")]

    if not data_rows:
        return {"error": "No data rows found in results table."}

    # If only one result, it's our target
    if len(data_rows) == 1:
        tds = data_rows[0].query_selector_all("td")
        href = tds[0].query_selector("a").get_attribute("href")
        return {"single": True, "detail_href": href}

    # If multiple results, find the best match
    search_term_lower = search_term.lower()
    exact_match_row = None
    potential_matches = []

    for row in data_rows:
        tds = row.query_selector_all("td")
        if not tds: continue
        name = tds[0].inner_text().strip()
        
        if name.lower() == search_term_lower:
            exact_match_row = row
            break
        
        if name.lower().startswith(search_term_lower):
            potential_matches.append((name, row))

    target_row = None
    if exact_match_row:
        target_row = exact_match_row
    elif potential_matches:
        # Pick the shortest name from the potential matches
        best_match = min(potential_matches, key=lambda item: len(item[0]))
        target_row = best_match[1]

    if target_row:
        href = target_row.query_selector("td:first-child a").get_attribute("href")
        return {"single": True, "detail_href": href}

    # If no suitable match is found, return the top 5 for user to refine search
    top_results = [{"entity_name": r.query_selector_all("td")[0].inner_text().strip(),
                    "organization_id": r.query_selector_all("td")[1].inner_text().strip()}
                   for r in data_rows[:5]]
    return {
        "error": f"Multiple results found for '{search_term}', but no suitable match was identified.",
        "top_results": top_results
    }


def parse_single_result_detail(page, detail_href=None):
    """
    Navigates to the detail page (if needed) and scrapes all available information.
    """
    if detail_href:
        detail_url = urljoin(SEARCH_URL, detail_href)
        page.goto(detail_url, timeout=30000)
    
    page.wait_for_selector("div.company-info-container")

    data = {
        "entity_name": "N/A",
        "business_identification_number": "N/A",
        "entity_type": "N/A",
        "entity_status": "N/A",
        "statusActive": False,
        "registration_date": "N/A",
        "address": "N/A",
    }

    for r in page.query_selector_all("div.company-info-container div.grid-row"):
        label_el = r.query_selector("div.grid-label")
        value_el = r.query_selector("div.grid-value")
        if not label_el or not value_el:
            continue
        
        label = label_el.inner_text().strip().lower()
        # Use inner_html to preserve <br> tags for easy replacement
        value = value_el.inner_html().replace('<br>', '\n').strip()

        if label == "organization number":
            data["business_identification_number"] = value
        elif label == "name":
            data["entity_name"] = value
        elif label == "company type":
            data["entity_type"] = value
        elif label == "status":
            data["entity_status"] = value
            # Status can be "A - Active"
            data["statusActive"] = value.upper().startswith("A")
        elif label == "organization date":
            data["registration_date"] = value
        elif label == "principal office":
            data["address"] = value.replace("\n", ", ").strip()


    return data

def search_ky(search_args):
    search_text = search_args.get("entity_name") or search_args.get("state_filing_number")
    if not search_text:
        return {"error": "Organization number or entity name required for Kentucky search."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            do_search(page, search_text)

            if check_no_results(page):
                return {"error": f"No matching organizations were found for '{search_text}'."}

            # Check if search by number led directly to the detail page
            if page.query_selector("div.company-info-container"):
                return parse_single_result_detail(page)

            # Otherwise, parse the results table to find the correct entity
            parsed = parse_results(page, search_args)
            if parsed.get("single"):
                return parse_single_result_detail(page, parsed["detail_href"])
            else:
                # This will now only be returned if no suitable match is found
                return parsed

        except Exception as e:
            return {"error": f"An unexpected error occurred: {str(e)}"}
        finally:
            browser.close()

# # --- Example of how to run the function ---
# if __name__ == '__main__':
#     # This search will now find "APPLE INC." and scrape it successfully.
#     search_args = {"entity_name": "apple"}
#     result = search_ky(search_args)
#     import json
#     print(json.dumps(result, indent=2))