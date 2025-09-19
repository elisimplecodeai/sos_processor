from playwright.sync_api import sync_playwright

def get_text_or_na(locator):
    """Return inner text if present, else 'N/A'."""
    try:
        text = locator.inner_text().strip()
        return text if text else "N/A"
    except:
        return "N/A"

# Searches Delaware Secretary of State site based on file number or entity name
def search_de(search_args, headless=True):
    file_number = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")

    if not (file_number or entity_name):
        return {"error": "Entity ID or entity name is required for Delaware search."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(
                "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx",
                timeout=60000
            )

            # Fill search form
            if file_number:
                page.fill('input[name="ctl00$ContentPlaceHolder1$frmFileNumber"]', file_number)
            else:
                page.fill('input[name="ctl00$ContentPlaceHolder1$frmEntityName"]', entity_name)

            page.click('input#ctl00_ContentPlaceHolder1_btnSubmit')
            page.wait_for_selector("table#tblResults", timeout=30000)

            rows = page.query_selector_all("table#tblResults tbody tr")

            if len(rows) <= 1: # The first row is always a header
                return {"error": "No valid results found."}

            # --- MODIFIED LOGIC TO SELECT A SINGLE RESULT ---
            # Default to the first result row.
            target_row = rows[1]

            # If searching by name and multiple results are found, try to find an exact match.
            if not file_number and len(rows) > 2:
                search_name_lower = entity_name.lower()
                # Iterate through all result rows (skipping the header)
                for row in rows[1:]:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        row_entity_name = get_text_or_na(cells[1])
                        if row_entity_name.lower() == search_name_lower:
                            target_row = row  # Found an exact match
                            break  # Stop searching

            # Click the link within the identified target row
            entity_link = target_row.query_selector("a[id*='lnkbtnEntityName']")
            if not entity_link:
                return {"error": "Entity registration link not found in the selected result row."}

            entity_link.click()
            page.wait_for_selector('span#ctl00_ContentPlaceHolder1_lblEntityName', timeout=15000)

            # Modular extraction
            def extract_field(selector):
                return get_text_or_na(page.locator(selector))

            entity_name_val = extract_field('span#ctl00_ContentPlaceHolder1_lblEntityName')
            registration_date = extract_field('span#ctl00_ContentPlaceHolder1_lblIncDate')
            entity_kind = extract_field('span#ctl00_ContentPlaceHolder1_lblEntityKind')
            file_number_val = extract_field('span#ctl00_ContentPlaceHolder1_lblFileNumber')
            agent_address = extract_field('span#ctl00_ContentPlaceHolder1_lblAgentAddress1')
            agent_city = extract_field('span#ctl00_ContentPlaceHolder1_lblAgentCity')
            agent_state = extract_field('span#ctl00_ContentPlaceHolder1_lblAgentState')
            agent_postal = extract_field('span#ctl00_ContentPlaceHolder1_lblAgentPostalCode')

            full_address = f"{agent_address}, {agent_city}, {agent_state} {agent_postal}" if agent_address != "N/A" else "N/A"

            return {
                "entity_name": entity_name_val,
                "registration_date": registration_date,
                "entity_type": entity_kind,
                "business_identification_number": file_number_val,
                "entity_status": "N/A",
                "statusActive": None,  # Status not provided, set to None for schema consistency
                "address": full_address
            }

        except Exception as e:
            return {"error": str(e)}
        finally:
            browser.close()