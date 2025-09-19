from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime
import time

MA_SEARCH_URL = "https://corp.sec.state.ma.us/CorpWeb/CorpSearch/CorpSearch.aspx"

def search_ma(search_args):
    entity_name = (search_args or {}).get("entity_name")
    id_number = (search_args or {}).get("state_filing_number")

    if not entity_name and not id_number:
        return {"error": "Identification number or entity name required for Massachusetts search."}
    if id_number and (not id_number.isdigit() or len(id_number) != 9):
        return {"error": "ID number must be exactly 9 digits."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox", "--disable-infobars",
        ])
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/115.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 768},
            screen={"width": 1366, "height": 768},
        )
        # Light stealth
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        """)

        page = context.new_page()

        try:
            page.goto(MA_SEARCH_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(500)

            # Fill search form
            if id_number:
                page.check("#MainContent_rdoByIdentification")
                page.fill("#MainContent_txtIdentificationNumber", id_number)
            else:
                page.check("#MainContent_rdoByEntityName")
                page.fill("#MainContent_txtEntityName", entity_name)

            # Submit search
            try:
                with page.expect_navigation(wait_until="networkidle", timeout=6000):
                    page.locator("#MainContent_btnSearch").click()
            except PlaywrightTimeoutError:
                page.locator("#MainContent_btnSearch").click()
                page.wait_for_load_state("domcontentloaded")

            # Determine page type
            state = wait_for_results_or_detail(page)
            msg = get_trimmed_text(page, "#MainContent_lblMessage")
            if msg:
                return {"error": msg}

            if state == "detail":
                return extract_ma_detail(page)

            # Multiple results
            rows = page.locator("#MainContent_SearchControl_grdSearchResultsEntity tr.GridRow")
            row_count = rows.count()
            search_term = id_number or entity_name

            if row_count == 0:
                return {"error": f"No results found for entity: {search_term}"}
            
            # If multiple results are found, click the first one and extract the details.
            if row_count > 0:
                entity_link = rows.first.locator("th a, td a").first
                with page.expect_navigation(wait_until="networkidle", timeout=10000):
                    entity_link.click()
                return extract_ma_detail(page)


        except PlaywrightTimeoutError:
            return {"error": "Timeout while searching Massachusetts SOS"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}
        finally:
            browser.close()


def wait_for_results_or_detail(page, timeout_ms=15000):
    """Returns: 'detail' | 'results' | 'unknown'"""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        page.wait_for_timeout(200)
        if page.locator("#MainContent_lblEntityNameHeader").count():
            return "detail"
        if page.locator("#MainContent_SearchControl_grdSearchResultsEntity").count():
            return "results"
        if get_trimmed_text(page, "#MainContent_lblMessage"):
            return "unknown"
    return "unknown"


def get_trimmed_text(page, selector):
    try:
        el = page.locator(selector)
        return el.inner_text().strip() if el.count() else ""
    except:
        return ""

def extract_ma_address(page):
    """
    Extract the business address, preferring 'Records' address if present.
    Falls back to Principal/Principle Office address.
    Returns a cleaned, comma‑separated string or '' if not found.
    """
    # Try possible ID prefixes in order of preference
    for prefix in ("Rec", "Principal", "Principle"):
        street_sel = page.locator(f"#MainContent_lbl{prefix}Street")
        if street_sel.count():
            def clean_text(selector):
                if page.locator(selector).count():
                    txt = page.locator(selector).inner_text().strip()
                    # Replace non‑breaking spaces and strip again
                    return txt.replace("\xa0", " ").strip().rstrip(",")
                return ""

            parts = [
                clean_text(f"#MainContent_lbl{prefix}Street"),
                clean_text(f"#MainContent_lbl{prefix}City"),
                clean_text(f"#MainContent_lbl{prefix}State"),
                clean_text(f"#MainContent_lbl{prefix}Zip"),
                clean_text(f"#MainContent_lbl{prefix}Country"),
            ]

            # Filter out any empty strings before joining
            return ", ".join(p for p in parts if p)

    return ""

def extract_ma_detail(page):
    try:
        entity_name = page.locator("#MainContent_lblEntityNameHeader").inner_text().strip()
        registration_date = page.locator("#MainContent_lblOrganisationDate").inner_text().strip() \
            or get_trimmed_text(page, "#MainContent_lblOrganizationDate")

        # Format date
        formatted_date = registration_date
        for fmt in ("%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                formatted_date = datetime.strptime(registration_date, fmt).strftime("%m/%d/%Y")
                break
            except: 
                continue

        entity_type = get_trimmed_text(page, "#MainContent_lblEntityType")
        business_identification_number = get_trimmed_text(page, "#MainContent_lblIDNumber").replace("Identification Number:", "").strip()

        # Entity status
        inactive_date = get_trimmed_text(page, "#MainContent_lblInactiveDate")
        statusActive = not bool(inactive_date)
        entity_status = "Active" if statusActive else "Inactive"

        # Address
        address = extract_ma_address(page)

        return {
            "entity_name": entity_name,
            "registration_date": formatted_date,
            "entity_type": entity_type,
            "business_identification_number": business_identification_number,
            "entity_status": entity_status,
            "statusActive": statusActive,
            "address": address
        }

    except Exception as e:
        return {"error": f"Could not extract details from MA business page: {e}"}