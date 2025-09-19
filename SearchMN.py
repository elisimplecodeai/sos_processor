from playwright.sync_api import sync_playwright, TimeoutError
import re
import html
 
def format_date(text):
    if not text:
        return ""
    # Normalize MM/DD/YYYY if possible
    parts = text.strip().split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        return f"{parts[0].zfill(2)}/{parts[1].zfill(2)}/{parts[2]}"
    return text.strip()

# Fixing address format if multi line syntax
def clean_address(raw_html):
    if not raw_html:
        return ""
    # Remove <address> tags completely
    no_tags = re.sub(r"</?address>", "", raw_html, flags=re.IGNORECASE)
    # Replace <br> and <br/> with commas
    no_tags = no_tags.replace("<br>", ", ").replace("<br/>", ", ")
    # Collapse extra whitespace/newlines
    no_tags = (
        no_tags
        .replace("\n", ", ")
        .replace("\r", "")
        .replace("\t", " ")
    )
    # Decode HTML entities like &amp;
    decoded = html.unescape(no_tags)
    # Clean up double spaces and strip ends
    return re.sub(r"\s{2,}", " ", decoded).strip()

def parse_details(page):
    """Extract all required fields from the detail page."""
    try:
        page.locator("#filingSummary").wait_for(timeout=3000)

        def get_text(label):
            sel = f"#filingSummary dl dt:text('{label}') + dd"
            el = page.locator(sel)
            return el.inner_text().strip() if el.count() > 0 else ""

        def get_html(label):
            sel = f"#filingSummary dl dt:text('{label}') + dd"
            el = page.locator(sel)
            return el.inner_html() if el.count() > 0 else ""

        entity_type = get_text("Business Type")
        file_number = get_text("File Number")
        registration_date = format_date(get_text("Filing Date"))
        entity_status = get_text("Status")

        # Address: pick whichever appears first
        address_html = get_html("Principal Place of Business Address")
        if not address_html:
            address_html = get_html("Registered Office Address")
        address = clean_address(address_html)

        # Normalize statusActive flag
        status_active = entity_status and entity_status.strip().lower() in ["active / in good standing", "active"]

        return {
            "registration_date": registration_date,
            "entity_type": entity_type,
            "business_identification_number": file_number,
            "entity_status": entity_status,
            "statusActive": status_active,
            "address": address,
        }
    except Exception:
        return None

def get_row_data(row):
    try:
        name_el = row.query_selector("strong")
        name = name_el.inner_text().strip() if name_el else ""
        status_el = row.query_selector("small > div.row:nth-of-type(2) div.col-md-3 span")
        status = status_el.inner_text().strip() if status_el else ""
        href_el = row.query_selector("a:has-text('Details')")
        href = href_el.get_attribute("href") if href_el else None
        return {"entity_name": name, "status": status, "details_href": href}
    except:
        return None

def search_mn(search_args):
    file_number = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")
    base_url = "https://mblsportal.sos.state.mn.us/Business/Search"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
            ignore_https_errors=True,
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
        page = context.new_page()
        page.goto(base_url, wait_until="load")

        # --- Search by file number ---
        if file_number:
            page.click("a[href='#fileNumberTab'], #fileNumberTab")
            page.fill("#FileNumber", file_number)
            page.click("#fileNumberTab button[type='submit']")
        # --- Search by business name ---
        elif entity_name:
            page.click("a[href='#businessNameTab'], #businessNameTab")
            page.fill("#BusinessName", entity_name)
            page.click("#businessNameTab button[type='submit']")
        else:
            browser.close()
            return {"error": "File number or business name required for Minnesota search."}

        try:
            page.wait_for_selector("table.table tbody tr", timeout=5000)
        except TimeoutError:
            browser.close()
            search_term = file_number or entity_name
            return {"error": f"No results found for '{search_term}'."}

        # Collect rows
        rows = page.query_selector_all("table.table tbody tr")
        valid_rows = [r for r in (get_row_data(x) for x in rows) if r and r["entity_name"]]

        if not valid_rows:
            browser.close()
            search_term = file_number or entity_name
            return {"error": f"No results found for '{search_term}'."}

        # Whether one or multiple results are found, always take the first one.
        top_result = valid_rows[0]
        details_href = top_result.get("details_href")

        if not details_href:
            browser.close()
            return {"error": "Could not find a details link for the top search result."}
        
        page.goto("https://mblsportal.sos.state.mn.us" + details_href)
        
        try:
            page.wait_for_selector("#filingSummary", timeout=5000)
        except TimeoutError:
            browser.close()
            return {"error": "Could not load the business details page."}
        
        details = parse_details(page)
        if not details:
            browser.close()
            return {"error": "Failed to parse details from the business page."}

        browser.close()
        return {
            "entity_name": top_result["entity_name"],
            **details
        }