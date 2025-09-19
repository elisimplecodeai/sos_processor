from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re

# URLs for Alabama SOS searches
AL_SEARCH_ID_URL = "https://arc-sos.state.al.us/CGI/corpnumber.mbr/input"
AL_SEARCH_NAME_URL = "https://arc-sos.state.al.us/CGI/CORPNAME.MBR/INPUT"
AL_BASE = "https://arc-sos.state.al.us"

# Helper: Extracts all detail table info into a dictionary
def extract_al_detail(page):
    detail = {}
    rows = page.locator("tr")
    for i in range(rows.count()):
        desc_locator = rows.nth(i).locator("td.aiSosDetailDesc")
        value_locator = rows.nth(i).locator("td.aiSosDetailValue")
        if desc_locator.count() > 0 and value_locator.count() > 0:
            desc = desc_locator.inner_text().strip()
            value = value_locator.inner_text().strip()
            detail[desc] = value
    return detail

#  Normalize AL detail fields into unified output format
def format_al_detail(entity_name, detail):
    # Extract individual fields with fallback to N/A
    entity_id = detail.get("Entity ID Number", "N/A")
    entity_type = detail.get("Entity Type", "N/A")
    raw_address = detail.get("Principal Address", "N/A")
    status = detail.get("Status", "N/A")
    formation_date = detail.get("Formation Date", "N/A")

    # Clean address: replace <br> or newline with ', ' and collapse extra spaces
    address = re.sub(r'[\n\r]+', ', ', raw_address).strip()
    address = re.sub(r'\s{2,}', ' ', address)

    # Build final object
    return {
        "entity_name": entity_name,
        "registration_date": formation_date,  # already MM/DD/YYYY
        "entity_type": entity_type,
        "business_identification_number": entity_id,
        "entity_status": status,
        "statusActive": status.strip().lower() == "exists",
        "address": address,
    }

# Main search function
def search_al(search_args):
    """
    Searches the Alabama Secretary of State website by entity ID or entity name.
    If any matches are found, it returns the full details for the top result.
    """
    entity_id = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")
    if not entity_id and not entity_name:
        return {"error": "Entity ID or entity name required for Alabama search."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # --- Search by entity ID ---
            if entity_id:
                page.goto(AL_SEARCH_ID_URL)
                page.fill('input[name="corp"]', entity_id)
                page.click('input[type="submit"]')
                page.wait_for_load_state('domcontentloaded', timeout=10000)

                if "No matches found" in page.content():
                    return {"error": f"No results found for entity ID: {entity_id}"}

                page.wait_for_selector("td.aiSosDetailDesc", timeout=5000)
                entity_name_found = page.locator("thead:first-of-type td.aiSosDetailHead").inner_text().strip()
                detail = extract_al_detail(page)
                return format_al_detail(entity_name_found, detail)

            # --- Search by entity name ---
            page.goto(AL_SEARCH_NAME_URL)
            page.fill('input[name="search"]', entity_name)
            page.select_option('select[name="type"]', "ALL")
            page.click('input[type="submit"]')
            page.wait_for_load_state('domcontentloaded', timeout=10000)

            if "No matches found" in page.content():
                return {"error": f"No results found for entity name: {entity_name}"}

            rows = page.locator("div.views-element-container table tbody tr")
            results = []
            for i in range(rows.count()):
                link_cells = rows.nth(i).locator("td a")
                if link_cells.count() >= 2:
                    link = link_cells.nth(1).get_attribute("href")
                    if link:
                        results.append({"link": AL_BASE + link})

            if not results:
                return {"error": f"No valid results found on the page for entity: {entity_name}"}

            # --- MODIFIED BEHAVIOR ---
            # If one or more results are found, always process the first one.
            first_result = results[0]
            page.goto(first_result["link"])
            page.wait_for_selector("td.aiSosDetailDesc", timeout=10000)

            entity_name_found = page.locator("thead:first-of-type td.aiSosDetailHead").inner_text().strip()
            detail = extract_al_detail(page)
            return format_al_detail(entity_name_found, detail)

        except PlaywrightTimeoutError:
            return {"error": "Timeout while searching Alabama SOS. The website may be slow or unavailable."}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {e}"}
        finally:
            browser.close()