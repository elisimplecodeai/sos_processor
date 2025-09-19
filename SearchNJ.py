import re
from playwright.sync_api import sync_playwright

def search_nj(search_args):
    """
    Searches NJ business entities by entity ID or name.
    If multiple results are found, it returns the full details of the top result.
    """
    entity_id = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")

    if not (entity_id or entity_name):
        return {"error": "Entity ID or entity name required for New Jersey search."}

    # Validating entity id is 10 digits
    if entity_id and (not entity_id.isdigit() or len(entity_id) != 10):
        return {"error": "Entity ID must be exactly 10 digits for New Jersey search."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            if entity_id:
                page.goto("https://www.njportal.com/DOR/BusinessNameSearch/Search/EntityId", timeout=30000)
                page.wait_for_selector("#EntityId", timeout=10000)
                page.fill("#EntityId", entity_id)
            else:
                page.goto("https://www.njportal.com/DOR/BusinessNameSearch/Search/BusinessName", timeout=30000)
                page.wait_for_selector("#BusinessName", timeout=10000)
                page.fill("#BusinessName", entity_name)

            page.click('input[type=submit].btn-success')
            page.wait_for_load_state('domcontentloaded', timeout=15000)

            error_alert = page.query_selector(".alert-danger")
            if error_alert and "no records were found" not in error_alert.inner_text().lower():
                return {"error": f"Search error: {error_alert.inner_text().strip()}"}

            rows = page.query_selector_all("#DataTables_Table_0 tbody tr")
            
            # This handles cases where the table exists but is empty, or the "no records" message appears.
            if not rows or (len(rows) == 1 and "No matching records found" in rows[0].inner_text()):
                search_term = entity_id or entity_name
                return {"error": f"No results found for '{search_term}'."}

            # --- MODIFIED BEHAVIOR ---
            # If one or more results are found, always process the first one.
            top_result_row = rows[0]
            cells = top_result_row.query_selector_all("td")

            if len(cells) < 5:
                return {"error": "Unexpected table format in search results."}

            business_name = cells[0].inner_text().strip() or "N/A"
            entity_id_val = cells[1].inner_text().strip() or "N/A"
            entity_type = cells[3].inner_text().strip() or "N/A"
            registration_date = cells[4].inner_text().strip() or "N/A"

            return {
                "entity_name": business_name,
                "registration_date": registration_date,
                "entity_type": entity_type,
                "business_identification_number": entity_id_val,
                "entity_status": "N/A",  # Status is not provided on the results page
                "statusActive": False,    # Assuming not active as status is unknown
                "address": "N/A"        # Address is not provided on the results page
            }

        except Exception as e:
            return {"error": f"An unexpected error occurred: {e}"}
        finally:
            browser.close()