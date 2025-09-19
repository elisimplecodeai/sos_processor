from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

FL_FEI_SEARCH_URL = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByFeiNumber"
FL_NAME_SEARCH_URL = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName"
FL_BASE_URL = "https://search.sunbiz.org"

def extract_detail_fields(page):
    """Extracts fields from Florida detail page. Returns dict with defaults."""
    def get_text(selector):
        try:
            return page.locator(selector).inner_text().strip()
        except:
            return "N/A"

    entity_name = get_text(".detailSection.corporationName p:nth-of-type(2)")
    # Improved: Capture the actual entity type
    entity_type = get_text(".detailSection.corporationName p:nth-of-type(1)")
    fei_ein = get_text("label[for='Detail_FeiEinNumber'] + span")
    registration_date = get_text("label[for='Detail_FileDate'] + span")
    status = get_text("label[for='Detail_Status'] + span")

    # Address (principal or mailing, choose principal if available)
    try:
        # This selector targets the "Principal Address" block specifically
        address_block = page.locator(".detailSection:has-text('Principal Address') span div").inner_text().strip().replace("\n", " ")
        # Clean up multiple spaces that can result from the replace
        address_block = ' '.join(address_block.split())
    except:
        address_block = "N/A"

    return {
        "entity_name": entity_name if entity_name else "N/A",
        "registration_date": registration_date if registration_date else "N/A",
        "entity_type": entity_type if entity_type else "N/A",
        "business_identification_number": fei_ein if fei_ein else "N/A",
        "entity_status": status if status else "N/A",
        "statusActive": status.upper() == "ACTIVE",
        "address": address_block if address_block else "N/A"
    }

def extract_multiple_results(page, fei_search=False):
    """Extracts top results (entity name and detail URL) from the results table."""
    rows = page.query_selector_all("table tbody tr")
    results = []
    for row in rows:
        try:
            # For both search types, the link containing the name is the most reliable way to get the detail URL
            link_element = row.query_selector("td.large-width a, td.small-width a")
            if not link_element:
                continue

            name = link_element.inner_text().strip()
            detail_link = link_element.get_attribute("href")
            full_url = FL_BASE_URL + detail_link if detail_link else None
            
            if full_url:
                results.append({
                    "entity_name": name,
                    "detail_url": full_url
                })
        except:
            continue
    return results

# Main Search Function (Modified to return only one full result)
def search_fl(search_args, headless=True):
    fei = search_args.get("state_filing_number", "").strip()
    entity_name = search_args.get("entity_name", "").strip()

    if not fei and not entity_name:
        return {"error": "Entity name or FEI/EIN is required for Florida search."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            # Determine which search to use
            if fei:
                page.goto(FL_FEI_SEARCH_URL)
                page.fill("input[name='SearchTerm']", fei)
            else:
                page.goto(FL_NAME_SEARCH_URL)
                page.fill("input[name='SearchTerm']", entity_name)

            page.click("input[type='submit'][value='Search Now']")
            page.wait_for_load_state("networkidle")

            # Check for No Results
            if page.is_visible("text=No records found"):
                return {"error": f"No results found for '{entity_name or fei}'."}

            target_result = None

            # If a results table appears, find the best match.
            if page.is_visible("table"):
                results = extract_multiple_results(page)
                if not results:
                    return {"error": "No valid results found in the results table."}

                # If searching by name, try to find an exact match first.
                if entity_name:
                    search_name_lower = entity_name.lower()
                    for r in results:
                        if r["entity_name"].lower() == search_name_lower:
                            target_result = r
                            break
                
                # If no exact match was found (or search was by FEI), default to the first result.
                if not target_result:
                    target_result = results[0]

            # If the search led directly to a detail page.
            else:
                target_result = {"detail_url": page.url}

            if not target_result or not target_result.get("detail_url"):
                return {"error": "Could not identify a result to scrape."}

            # Navigate to the chosen result's detail page and extract data.
            if page.url != target_result["detail_url"]:
                page.goto(target_result["detail_url"])
                page.wait_for_load_state("networkidle")

            detail_data = extract_detail_fields(page)
            return detail_data

        except PlaywrightTimeoutError:
            return {"error": f"Page timeout while searching for '{entity_name or fei}'."}
        except Exception as e:
            return {"error": str(e)}
        finally:
            browser.close()