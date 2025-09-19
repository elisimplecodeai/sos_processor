import re
import time
from playwright.sync_api import sync_playwright

IDAHO_SEARCH_URL = "https://sosbiz.idaho.gov/search/business"

def extract_details_from_drawer(page):
    """
    Extracts all entity details from the details drawer.
    This version includes the corrected address selection logic.
    """
    data = {
        "entity_name": "N/A",
        "business_identification_number": None,
        "registration_date": "N/A",
        "entity_type": "N/A",
        "entity_status": "N/A",
        "statusActive": False,
        "address": "N/A",
        "formed_in": "N/A",
        "agent_info": "N/A",
    }

    title_element = page.query_selector("div.title-box h4")
    if title_element:
        full_title = title_element.inner_text().strip()
        match = re.search(r"^(.*?)\s*\(([A-Za-z0-9]+)\)$", full_title)
        if match:
            data["entity_name"] = match.group(1).strip()
            data["business_identification_number"] = match.group(2).strip()
        else:
            data["entity_name"] = full_title

    principal_address, mailing_address, registrant_text = None, None, None
    for row in page.query_selector_all("table.details-list tbody tr"):
        label_el = row.query_selector("td.label")
        value_el = row.query_selector("td.value")
        if not label_el or not value_el:
            continue
        
        label = label_el.inner_text().strip().upper()
        value = value_el.inner_text().strip()

        if label == "INITIAL FILING DATE":
            data["registration_date"] = value
        elif label in ("FILING TYPE", "ENTITY TYPE"):
            data["entity_type"] = value
        elif label == "STATUS":
            data["entity_status"] = value
            status_lower = value.lower()
            data["statusActive"] = any(s in status_lower for s in ["active", "good standing", "current", "existing"])
        elif label == "PRINCIPAL ADDRESS":
            principal_address = value
        elif label == "MAILING ADDRESS":
            mailing_address = value
        elif label == "FORMED IN":
            data["formed_in"] = value
        elif label == "AGENT":
            data["agent_info"] = value
        elif label == "FILE NUMBER" and not data["business_identification_number"]:
             data["business_identification_number"] = value
        elif label == "REGISTRANT":
            registrant_text = value

    # --- CORRECTED ADDRESS LOGIC ---
    # 1. Use Principal Address only if it's a real, valid address.
    if principal_address and principal_address.upper() != 'N/A':
        data["address"] = principal_address.replace('\n', ', ')
    # 2. Otherwise, use Mailing Address if it's a real, valid address.
    elif mailing_address and mailing_address.upper() != 'N/A':
        data["address"] = mailing_address.replace('\n', ', ')
    # 3. As a last resort, parse the Registrant field.
    elif registrant_text:
        parts = registrant_text.split('\n')
        if len(parts) > 1:
            data["address"] = ', '.join(parts[1:]).strip()

    # Clean up the dictionary before returning
    keys_to_remove_if_na = ["formed_in", "agent_info"]
    final_data = {k: v for k, v in data.items() if not (k in keys_to_remove_if_na and v == "N/A")}

    return final_data

def parse_entity_row_for_multiple_results(row):
    name_cell = row.query_selector("td:nth-child(1) > div > span.cell")
    full_text = name_cell.inner_text().strip() if name_cell else ""
    match = re.search(r"^(.*?)\s*\(([A-Za-z0-9]+)\)$", full_text)
    return {"entity_name": match.group(1).strip(), "file_number": match.group(2).strip()} if match else {"entity_name": full_text, "file_number": "N/A"}

def search_id(search_args):
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name required for Idaho search."}
    search_term = entity_name

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        try:
            page.goto(IDAHO_SEARCH_URL, wait_until="domcontentloaded")

            search_input = page.wait_for_selector('input.search-input', state="visible")
            search_input.fill(search_term)
            time.sleep(1)

            page.wait_for_function('document.querySelector("button.search-button")?.getAttribute("aria-disabled") === "false"')
            page.click("button.search-button")
            
            page.wait_for_selector("div.table-wrapper, div.empty-placeholder-wrapper", timeout=15000)

            if page.query_selector("div.empty-placeholder-wrapper"):
                return {"error": f"No results found for '{search_term}'."}

            rows = page.query_selector_all("div.table-wrapper table tbody tr")
            if not rows:
                return {"error": f"No results found for '{search_term}'."}

            target_row = None
            if len(rows) == 1:
                target_row = rows[0]
            else:
                search_term_lower = search_term.lower()
                exact_match = None
                potential_matches = []

                for row in rows:
                    parsed_data = parse_entity_row_for_multiple_results(row)
                    entity_name_lower = parsed_data["entity_name"].lower()

                    if entity_name_lower == search_term_lower:
                        exact_match = row
                        break
                    
                    if entity_name_lower.startswith(search_term_lower):
                        potential_matches.append((parsed_data, row))

                if exact_match:
                    target_row = exact_match
                elif potential_matches:
                    best_match = min(potential_matches, key=lambda item: len(item[0]["entity_name"]))
                    target_row = best_match[1]

            if target_row:
                clickable = target_row.query_selector("td div[role='button']")
                if not clickable:
                    return {"error": "Business registration link not found in the target result row."}
                
                clickable.click()
                page.wait_for_selector("div.drawer.show table.details-list tr.detail", timeout=10000)
                
                return extract_details_from_drawer(page)
            else:
                return {
                    "error": f"Multiple results found for '{search_term}', but no suitable match was identified.",
                    "top_results": [parse_entity_row_for_multiple_results(row) for row in rows[:5]]
                }

        except Exception as e:
            return {"error": f"Idaho search error: {str(e)}"}
        finally:
            browser.close()