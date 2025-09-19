import re
import time
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError

def launch_browser(headless=True) -> (Browser, Page):
    # Start Playwright and launch Chromium browser with stealth settings to reduce detection
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    # Override webdriver property to avoid bot detection
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => false });")
    page = context.new_page()
    return browser, page

def navigate_to_search_page(page: Page, url: str = "https://www.sosnc.gov/online_services/search") -> None:
    # Navigate to the NC SOS business search page and wait for DOM content to load
    page.goto(url, wait_until="domcontentloaded")
    # Pause briefly to allow page JavaScript to settle
    page.wait_for_timeout(2000)

def configure_search_options(page: Page, using_entity_number: bool) -> None:
    # Choose search type dropdown: either SOSID (ID number) or Corporation Name
    page.select_option("select#CorpSearchType", value="SOSID" if using_entity_number else "CORPORATION")
    time.sleep(0.5)  # Wait to ensure selection applied

    if not using_entity_number:
        # For name search, select exact match option to avoid partial matches
        page.select_option("select#Words", value="EXACT")
        time.sleep(0.5)

def perform_search(page: Page, search_term: str) -> None:
    # Fill the search input with SOSID or entity name, then submit the form
    page.fill("input#SearchCriteria", search_term)
    time.sleep(0.5)
    page.click("button#SubmitButton")
    # Wait to allow search results to load
    page.wait_for_timeout(2000)

def check_no_results(page: Page) -> bool:
    # Check for the presence of a no-results message
    no_results_span = page.query_selector("span.boldSpan")
    if no_results_span:
        text = no_results_span.text_content().strip()
        if "Records Found:" in text:
            match = re.search(r"Records\s*Found:\s*(\d+)", text)
            # If zero records found, indicate no results
            if match and int(match.group(1)) == 0:
                return True
    return False

def get_search_result_headings(page: Page) -> list:
    # Get all result heading elements (each corresponds to a business record accordion)
    return page.query_selector_all("div.searchAccordion__heading")

def extract_details_from_result(page: Page, heading) -> dict:
    # Click the result accordion heading to expand it
    heading.click()
    page.wait_for_selector("div.searchAccordion__content", timeout=10000)
    content = page.query_selector("div.searchAccordion__content")

    # Default values
    entity_name, formed_date, entity_type, sosid, status = "N/A", "N/A", "N/A", "N/A", "N/A"
    status_active = False
    address = "N/A"

    # Extract entity name from accordion heading
    header_button = heading.query_selector("button")
    if header_button:
        name_el = header_button.query_selector("div.searchHeader")
        header_text = name_el.text_content().strip() if name_el else ""
        parts = header_text.split("•")
        entity_name = re.sub(r"\s+", " ", parts[0].strip())

    # Loop through detail rows in accordion to extract basic fields
    for div in content.query_selector_all("div.para-small"):
        label_el = div.query_selector("span.boldSpan")
        if not label_el: continue
        label_text = label_el.text_content().strip()
        full_text = div.text_content().replace(label_text, "").strip()
        full_text = re.sub(r"\s+", " ", full_text)  # clean whitespace

        if "Date formed" in label_text: formed_date = full_text
        elif "Business type" in label_text: entity_type = full_text
        elif "Sosid" in label_text: sosid = full_text
        elif "Status" in label_text:
            status = full_text
            status_active = any(k in full_text.lower() for k in ["current", "active"])
        elif "Legal name" in label_text: entity_name = full_text

    # CLICK DETAIL PAGE LINK TO GET ADDRESS
    more_info_link = content.query_selector("a.searchResultsLink[href*='Business_Registration_profile']")
    if more_info_link:
        more_info_link.click()
        page.wait_for_selector("section.usa-section--singleEntry", timeout=10000)
        detail_section = page.query_selector("section.usa-section--singleEntry")
        if detail_section:
            for addr_block in detail_section.query_selector_all("div.para-small"):
                label_el = addr_block.query_selector("span.boldSpan")
                if label_el and "Principal office" in label_el.text_content():
                    inner_div = addr_block.query_selector("div.para-small")
                    if inner_div:
                        address_text = inner_div.inner_text().replace("\n", ", ")
                        address = re.sub(r"\s+", " ", address_text).strip()
                    break

    return {
        "entity_name": entity_name, "registration_date": formed_date,
        "entity_type": entity_type, "business_identification_number": sosid,
        "entity_status": status, "statusActive": status_active, "address": address
    }

def search_nc(search_args: dict) -> dict:
    entity_number = search_args.get("state_filing_number")
    entity_name_input = search_args.get("entity_name")

    if not (entity_number or entity_name_input):
        return {"error": "Secretary of State Identification Number (SOSID) or business name required for North Carolina search."}

    using_entity_number = bool(entity_number)
    search_term = entity_number if using_entity_number else entity_name_input

    browser, page = launch_browser(headless=True)
    try:
        navigate_to_search_page(page)
        configure_search_options(page, using_entity_number)
        perform_search(page, search_term)

        if check_no_results(page):
            return {"error": f"No results found for '{search_term}'."}

        headings = get_search_result_headings(page)
        if not headings:
            return {"error": "No results were found on the page, or the page structure has changed."}

        # --- MODIFIED BEHAVIOR ---
        # If one or more results are found, always process the first one.
        return extract_details_from_result(page, headings[0])

    except Exception as e:
        return {"error": f"An unexpected error occurred during the NC search: {e}"}
    finally:
        browser.close()