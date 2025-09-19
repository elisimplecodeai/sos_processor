from playwright.sync_api import sync_playwright, TimeoutError
import time

SEARCH_URL = "https://www.ark.org/corp-search/index.php"

def search_ar(search_args, headless=True, max_results=5, slow_mo=0):
    filing_num = search_args.get("state_filing_number")
    entity_name = search_args.get("entity_name")

    if not filing_num and not entity_name:
        return {"error": "Filing number or entity name required for Arkansas search."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = browser.new_page()
        page.goto(SEARCH_URL, timeout=60000)

        # Fill the search form
        if filing_num:
            page.fill("#FilingNum", str(filing_num))
        else:
            page.fill("#CorporationName", entity_name)

        # Submit search
        page.locator("button.btn.btn-primary:has-text('Search')").first.click()

        # Handle "No Results Found" alert quickly
        try:
            page.wait_for_selector("div.alert.alert-danger:has-text('No Results Found')", timeout=3000)
            return {"error": "No valid results found."}
        except TimeoutError:
            pass

        # Wait for table rows or direct modal
        try:
            page.wait_for_selector("table.dataTable-table tbody tr", timeout=8000)
        except TimeoutError:
            if _is_modal_open(page):
                _wait_for_modal_ready(page, timeout=8000)
                record = _extract_modal(page)
                return record
            return {"error": "No results table or modal appeared."}

        # Process table rows
        rows = page.locator("table.dataTable-table tbody tr")
        total = rows.count()
        take = min(total, max_results)
        results = []

        for i in range(take):
            row = rows.nth(i)
            label = _safe_first_cell_text(row)
            try:
                _open_details_modal(page, row, timeout=15000, force_name_cell=True)
                _wait_for_modal_ready(page, timeout=15000)
                record = _extract_modal(page)
                if not record["entity_name"]:
                    record["entity_name"] = label
                results.append(record)
            except TimeoutError:
                pass
            finally:
                _close_modal_if_open(page)

        # --- MODIFIED RETURN LOGIC TO ALWAYS RETURN A SINGLE, FULL RESULT ---

        # If no results were successfully scraped, return an error.
        if not results:
            return {"error": "No valid results found."}

        # If multiple results were found and the search was by name,
        # try to find an exact match to the searched name.
        if len(results) > 1 and entity_name:
            search_name_lower = entity_name.lower()
            for record in results:
                # Check for a case-insensitive exact name match
                if record.get("entity_name", "").lower() == search_name_lower:
                    return record  # Return the exact match immediately

        # If no exact match was found, or if there was only one result to begin with,
        # or if the search was by filing number, return the first result in the list.
        return results[0]
# helpers 
def _safe_first_cell_text(row):
    try:
        tds = row.locator("td")
        if tds.count() > 0:
            return tds.first.inner_text().strip()
    except Exception:
        return None
    return None

def _is_modal_open(page):
    modal = page.locator("#detail-modal.show:visible, #modalBody:visible, .modal-body:visible")
    return modal.count() > 0 and modal.first.is_visible()

def _open_details_modal(page, row, timeout=15000, force_name_cell=False):
    if _is_modal_open(page):
        return

    # Try to find a clickable element
    selectors = [
        "button:has-text('Details')",
        "a:has-text('Details')",
        "td a",
        "a",
        "button"
    ]
    target = None
    for sel in selectors:
        loc = row.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            target = loc.first
            break

    # Fallback: click first cell if no explicit button
    if force_name_cell or target is None:
        name_cell = row.locator("td").first
        target = name_cell if name_cell.count() > 0 else row

    try:
        target.scroll_into_view_if_needed()
    except Exception:
        pass
    page.wait_for_timeout(150)

    # Wait for network event triggered by modal open
    try:
        with page.expect_response(
            lambda r: ("/livewire/message/corp-detail-modal" in r.url) and (r.request.method == "POST"),
            timeout=timeout
        ):
            target.click()
    except TimeoutError:
        try:
            target.click(force=True)
        except Exception:
            try:
                target.dblclick()
            except Exception:
                pass

    page.locator("#modalBody:visible, .modal-body:visible").first.wait_for(
        state="visible", timeout=timeout
    )

def _wait_for_modal_ready(page, timeout=15000):
    modal = page.locator("#modalBody:visible, .modal-body:visible").first
    modal.wait_for(state="visible", timeout=timeout)
    deadline = time.time() + (timeout / 1000.0)
    while time.time() < deadline:
        if (_get_value_by_label(page, "Corporation Name") or
            _get_value_by_label(page, "Filing #") or
            _get_value_by_label(page, "Date Filed")):
            return
        page.wait_for_timeout(150)
    raise TimeoutError("Modal did not populate expected fields in time.")

def _get_value_by_label(page, label_text):
    item = page.locator(f"li.list-group-item:has(div:has-text('{label_text}'))")
    if item.count() == 0:
        return None
    val = item.locator("div.d-flex.w-100.justify-content-between > div").last
    try:
        text = val.inner_text().strip()
        return text if text else None
    except Exception:
        return None

def _extract_modal(page):
    # helper to read text by selector
    def read_first(selector):
        loc = page.locator(selector)
        return loc.first.inner_text().strip() if loc.count() > 0 else None

    # Core fields
    name = read_first("#corp_name") or _get_value_by_label(page, "Corporation Name")
    filing = read_first("#filing-number") or _get_value_by_label(page, "Filing #")
    date = read_first("#date-filed") or _get_value_by_label(page, "Date Filed")

    # Additional fields
    entity_type = read_first("#filing-type") or _get_value_by_label(page, "Filing Type")
    status = read_first("#status") or _get_value_by_label(page, "Status")
    agent_address = read_first("#agent-address") or _get_value_by_label(page, "Agent Address")
    principal_address = _get_value_by_label(page, "Principal Address") or agent_address

    # Normalize statusActive flag
    status_active = status and status.strip().lower() in ["good standing", "current"]

    return {
        "entity_name": name,
        "registration_date": date,
        "entity_type": entity_type,
        "business_identification_number": filing,
        "entity_status": status,
        "statusActive": bool(status_active),
        "address": principal_address
    }

def _close_modal_if_open(page):
    if not _is_modal_open(page):
        return
    for sel in [
        "button:has-text('Close')",
        "a:has-text('Close')",
        "[data-bs-dismiss='modal']",
        "button[aria-label='Close']",
        ".modal-header button.close",
    ]:
        btn = page.locator(sel)
        if btn.count() > 0 and btn.first.is_visible():
            try:
                btn.first.click()
                break
            except Exception:
                pass
    else:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    try:
        page.locator("#modalBody, .modal-body").first.wait_for(state="hidden", timeout=5000)
    except TimeoutError:
        pass
