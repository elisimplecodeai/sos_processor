from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

MS_SOS_URL = "https://corp.sos.ms.gov/corp/portal/c/page/corpbusinessidsearch/portal.aspx#"


# ---------------- Helper Functions ---------------- #
def launch_browser(headless=True):
    """Launch a Playwright Chromium browser and return page object."""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    page = browser.new_page()
    return p, browser, page


def navigate_to_search(page):
    """Go to the Mississippi SOS search page."""
    page.goto(MS_SOS_URL, timeout=60000)


def fill_search(page, entity_name="", business_id=""):
    """Fill in the search form for either business ID or entity name."""
    if business_id:
        page.locator("li[role='tab'] >> text=Business ID").click()
        page.wait_for_selector("#businessIdTextBox", state="visible", timeout=5000)
        page.fill("#businessIdTextBox", business_id)
        page.keyboard.press("Enter")
    else:
        page.check("#rbExact")
        page.fill("#businessNameTextBox", entity_name)
        page.click("#businessNameSearchButton")
    # A short wait can help ensure the search submission is processed
    page.wait_for_timeout(3000)


def extract_registration_date(page):
    """Extract registration date from the detail page."""
    date_cell = page.locator(
        "//td[contains(., 'Effective Date') or contains(., 'Creation Date')]/following-sibling::td[1]"
    )
    if date_cell.count() > 0:
        return date_cell.first.inner_text().strip()
    return ""


def extract_detail_page_data(page):
    """Extract full entity details from the detail page, normalizing missing values to 'N/A' and formatting address."""
    
    def safe_text(selector, placeholder_values=None, formatter=None):
        """Helper to get text or 'N/A' if missing or matches placeholder, with optional formatter."""
        if placeholder_values is None:
            placeholder_values = []
        try:
            # **FIX:** Target the .first element to avoid strict mode violations
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=2000) # Wait for the first element to be visible
            val = locator.inner_text().strip()
            
            if not val or val.upper() in (p.upper() for p in placeholder_values):
                return "N/A"
            if formatter:
                val = formatter(val)
            return val
        except PlaywrightTimeoutError:
            # This will happen if the selector finds no elements within the timeout
            return "N/A"

    # Address formatter
    def format_address(addr):
        addr = addr.replace("\u00a0", " ") # non-breaking space
        addr = addr.replace("\n", ", ")    # newlines
        return " ".join(addr.split()).strip() # collapse multiple spaces

    # Entity name
    entity_name_detail = safe_text(
        "div#printDiv2 table.subTable:nth-of-type(1) tr:nth-of-type(2) td:nth-of-type(1)"
    )

    # Registration date
    registration_date = extract_registration_date(page) or "N/A"

    # Entity type
    entity_type = safe_text(
        "//td[normalize-space()='Business Type:']/following-sibling::td[1]"
    )

    # Business ID
    business_identification_number = safe_text(
        "//td[normalize-space()='Business ID:']/following-sibling::td[1]"
    )

    # Status
    entity_status = safe_text(
        "//td[normalize-space()='Status:']/following-sibling::td[1]"
    )

    # Boolean active status
    active_keywords = ["good standing", "active", "in compliance"]
    status_active = any(
        entity_status.lower().startswith(k) for k in active_keywords
    )

    # Address
    address = safe_text(
        "//td[normalize-space()='Principal Office Address:']/following-sibling::td[1]",
        placeholder_values=["NO PRINCIPAL OFFICE ADDRESS FOUND"],
        formatter=format_address
    )

    return {
        "entity_name": entity_name_detail,
        "registration_date": registration_date,
        "entity_type": entity_type,
        "business_identification_number": business_identification_number,
        "entity_status": entity_status,
        "statusActive": status_active,
        "address": address
    }


# ---------------- Main Search Function ---------------- #
def search_ms(search_args):
    """Search Mississippi SOS business database."""
    entity_name = (search_args.get("entity_name") or "").strip()
    business_id = (search_args.get("business_id") or "").strip()

    if not (entity_name or business_id):
        return {"error": "Business ID or entity name required for Mississippi search."}

    p, browser, page = launch_browser(headless=True)
    try:
        navigate_to_search(page)
        fill_search(page, entity_name=entity_name, business_id=business_id)

        # Check if the page landed directly on a details page
        if page.locator("div#printDiv2").count() > 0:
            return extract_detail_page_data(page)

        # If not, check for a results table
        results_table = page.locator("table[role='grid'] tbody")
        if results_table.count() > 0:
            first_row = results_table.locator("tr").first
            if first_row.count() > 0:
                # Click the details link in the first row
                first_row.locator("a:has-text('Details')").click()
                page.wait_for_selector("div#printDiv2", state="visible", timeout=10000)
                return extract_detail_page_data(page)

        # If neither a details page nor a results table with rows is found
        return {"error": f"No results found for '{business_id or entity_name}'."}
        
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}
        
    finally:
        browser.close()
        p.stop()