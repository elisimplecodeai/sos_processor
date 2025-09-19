import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def launch_browser():
    """Launches a Chromium browser with stealth settings and returns context and page."""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    context.add_init_script("""Object.defineProperty(navigator, 'webdriver', { get: () => false });""")
    page = context.new_page()
    return p, browser, context, page

def fill_search_form(page, search_term):
    """Fills the search input and submits the form."""
    search_input = page.wait_for_selector('input.search-input', state="visible", timeout=15000)
    search_input.click()
    search_input.fill(search_term)
    time.sleep(1)

    page.wait_for_function(
        'document.querySelector("button.search-button")?.getAttribute("aria-disabled") === "false"',
        timeout=5000
    )
    page.click("button.search-button")

def check_for_errors(page):
    """Check for error banners on the page and return error text if any."""
    for selector in [".search-error", ".alert-danger"]:
        error_div = page.query_selector(selector)
        if error_div:
            return error_div.inner_text().strip()
    return None

def parse_and_extract_details(page, result_row):
    """
    From a result row, clicks to the details page and extracts all required fields, including the agent's address.
    """
    entity_name_cell = result_row.query_selector("td:nth-child(1) > div > span.cell")
    entity_name = entity_name_cell.inner_text().strip() if entity_name_cell else "N/A"

    clickable_element = result_row.query_selector("td div[role='button']")
    if not clickable_element:
        return {"error": "Could not find a clickable link to the business details page."}

    clickable_element.click()
    page.wait_for_selector("table.details-list", timeout=10000)

    def safe_get(label):
        """Helper to safely extract text value next to a label."""
        row_selector = f"table.details-list tbody tr:has(td.label:has-text('{label}'))"
        value_selector = f"{row_selector} >> td.value"
        
        if page.locator(value_selector).count() > 0:
            value = page.locator(value_selector).inner_text().strip()
            return value if value else "N/A"
        return "N/A"

    # --- Standard Details Extraction ---
    registration_date = safe_get("Initial Filing Date")
    entity_type = safe_get("Entity Type")
    entity_status = safe_get("Status")
    business_id = safe_get("Record #")
    statusActive = "active" in entity_status.lower()

    # --- Agent Address Extraction ---
    agent_address = "N/A"
    agent_info_selector = "table.details-list tbody tr:has(td.label:has-text('Agent Name')) >> td.value"
    agent_info_element = page.locator(agent_info_selector)

    if agent_info_element.count() > 0:
        # inner_text() preserves line breaks, which we use to separate address lines
        full_agent_text = agent_info_element.inner_text().strip()
        lines = [line.strip() for line in full_agent_text.split('\n') if line.strip()]
        
        # The agent's name is the first line. The address is all subsequent lines.
        if len(lines) > 1:
            agent_address = ", ".join(lines[1:])

    return {
        "entity_name": entity_name,
        "registration_date": registration_date,
        "entity_type": entity_type,
        "business_identification_number": business_id,
        "entity_status": entity_status,
        "statusActive": statusActive,
        "address": agent_address  # This is the Registered Agent's address
    }

def search_nm(search_args):
    """
    Searches for a business in New Mexico's SOS database.
    If any results are found, it returns the full details of the first one.
    """
    file_number = search_args.get("state_filing_number")
    entity_name_input = search_args.get("entity_name")

    if not (file_number or entity_name_input):
        return {"error": "Business ID/file number or entity name required for New Mexico search."}

    search_term = file_number or entity_name_input
    
    if len(search_term) < 2:
        return {"error": "Search term must be at least 2 characters long."}

    p, browser, context, page = None, None, None, None
    try:
        p, browser, context, page = launch_browser()

        page.goto("https://enterprise.sos.nm.gov/search/business", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        fill_search_form(page, search_term)

        try:
            page.wait_for_selector("div.table-wrapper, .alert-danger, .search-error", timeout=15000)
        except PlaywrightTimeoutError:
            return {"error": "Search timed out or the results page did not load."}

        error_msg = check_for_errors(page)
        if error_msg:
            return {"error": error_msg}

        rows = page.query_selector_all("div.table-wrapper table tbody tr")
        if not rows:
            return {"error": f"No results found for '{search_term}'."}

        return parse_and_extract_details(page, rows[0])

    except Exception as e:
        return {"error": f"An unexpected error occurred during the NM search: {e}"}

    finally:
        if browser:
            browser.close()
        if p:
            p.stop()