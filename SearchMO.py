from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import html, re

MO_SEARCH_URL = "https://bsd.sos.mo.gov/BusinessEntity/BESearch.aspx?SearchType=0"
BASE_URL = "https://bsd.sos.mo.gov"

# -------------------------------------------------------------------------
# Utility: Clean and normalize address text
# -------------------------------------------------------------------------
def format_address(raw_text: str) -> str:
    """Clean up address text into a single line."""
    if not raw_text:
        return "N/A"
    text = html.unescape(raw_text)
    text = re.sub(r'\s+', ' ', text)  # collapse multiple spaces/newlines
    return text.strip(" ,")

# -------------------------------------------------------------------------
# Utility: Extract details from the Missouri detail page
# -------------------------------------------------------------------------
def parse_mo_detail(page):
    """Extracts full entity info from Missouri detail page."""
    entity_name = page.inner_text(
        "#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBEDetail_lBENameValue"
    ).strip()

    entity_type = page.inner_text(
        "#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBEDetail_lBETypeValue"
    ).strip()

    business_id = page.inner_text(
        "#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBEDetail_lBEBINValue"
    ).strip()

    status = page.inner_text(
        "#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBEDetail_cellStatusValue"
    ).strip()

    status_active = "active" in status.lower() or "good" in status.lower()

    registration_date = page.inner_text(
        "#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBEDetail_cellCreatedValue"
    ).strip()

    # Get clean text (no HTML tags) for address
    address_text = page.inner_text(
        "#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBEDetail_cellBEAddressValue"
    ).strip()
    address = format_address(address_text)

    return {
        "entity_name": entity_name,
        "registration_date": registration_date,
        "entity_type": entity_type,
        "business_identification_number": business_id,
        "entity_status": status,
        "statusActive": status_active,
        "address": address,
    }

# -------------------------------------------------------------------------
# MAIN FUNCTION: search_mo
# -------------------------------------------------------------------------
def search_mo(search_args, headless=True):
    """
    Search Missouri Business Entity Records by charter number or business name.

    Returns:
    - If any matches are found, it returns the full entity data for the top result.
    - If no matches are found, it returns an error dictionary.
    """
    charter_number = search_args.get("state_filing_number", "").strip()
    business_name = search_args.get("entity_name", "").strip()

    if not charter_number and not business_name:
        return {"error": "Charter number or business name required for Missouri search."}

    with sync_playwright() as p:
        # --- Launch browser ---
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/5.37.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
            ignore_https_errors=True
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
        page = context.new_page()

        try:
            # -----------------------------------------------------------------
            # Fill in search fields
            # -----------------------------------------------------------------
            page.goto(MO_SEARCH_URL, wait_until="domcontentloaded")

            if charter_number:
                page.select_option(
                    'select#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_ddlBESearchType',
                    '3'  # Charter No.
                )
                page.fill(
                    'input#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_tbBusinessID',
                    charter_number
                )
            else:
                page.select_option(
                    'select#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_ddlBESearchType',
                    '0'  # Business Name
                )
                page.fill(
                    'input#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_tbBusinessName',
                    business_name
                )

            # Click SEARCH button
            page.click(
                'div#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_stdbtnSearch_divStandardButtonTop'
            )

            # -----------------------------------------------------------------
            # Wait for results
            # -----------------------------------------------------------------
            page.wait_for_selector(
                'table#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_SearchResultGrid_ctl00, div:has-text("No records to display.")',
                timeout=10000
            )

            # -----------------------------------------------------------------
            # Handle "No records"
            # -----------------------------------------------------------------
            if page.is_visible("div:has-text('No records to display.')"):
                return {"error": f"No records found for '{charter_number or business_name}'."}

            # -----------------------------------------------------------------
            # Extract search result rows
            # -----------------------------------------------------------------
            rows = page.query_selector_all(
                'table#ctl00_ctl00_ContentPlaceHolderMain_ContentPlaceHolderMainSingle_ppBESearch_bsPanel_SearchResultGrid_ctl00 tbody tr'
            )
            entities = []
            for row in rows:
                cls = row.get_attribute("class") or ""
                if "rgHeader" in cls or "rgPager" in cls:
                    continue  # skip headers/pagers

                business_cell = row.query_selector("td:nth-child(4) a")
                if business_cell:
                    href = business_cell.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = BASE_URL + href
                    entities.append({"detail_url": href})

            # -----------------------------------------------------------------
            # Process the top result
            # -----------------------------------------------------------------
            if not entities:
                return {"error": "No valid business entities found in the search results."}
            
            # --- Whether single or multiple results, navigate to the first one's detail page ---
            top_result = entities[0]
            page.goto(top_result["detail_url"], wait_until="domcontentloaded")
            data = parse_mo_detail(page)
            return data

        except PlaywrightTimeoutError:
            return {"error": "The search page timed out or failed to load properly."}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {e}"}
        finally:
            browser.close()