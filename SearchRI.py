import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

def format_date_mmddyyyy(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%m-%d-%Y").strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return date_str

async def extract_detail_page_data_async(page) -> dict:
    async def safe_inner_text(selector):
        loc = page.locator(selector)
        return (await loc.inner_text()).strip() if await loc.count() > 0 else "N/A"
    
    charter_number_raw = (await safe_inner_text("#MainContent_lblIDNumberHeader") or await safe_inner_text("#MainContent_lblIDNumber"))
    charter_number = charter_number_raw.split(":", 1)[1].strip() if ":" in charter_number_raw else charter_number_raw

    is_inactive = await page.locator("#MainContent_lblInactiveDate").count() > 0 and bool(await page.locator("#MainContent_lblInactiveDate").inner_text())
    entity_status = "Inactive" if is_inactive else "Active"
    
    address_parts = [await safe_inner_text(f"#MainContent_lblPrinciple{part}") for part in ["Street", "City", "State", "Zip", "Country"]]
    address = ", ".join(part for part in address_parts if part and part != "N/A")

    return {
        "entity_name": await safe_inner_text("#MainContent_lblEntityName"),
        "registration_date": format_date_mmddyyyy(await safe_inner_text("#MainContent_lblOrganisationDate")),
        "entity_type": await safe_inner_text("#MainContent_lblEntityType"),
        "business_identification_number": charter_number,
        "entity_status": entity_status,
        "statusActive": not is_inactive,
        "address": address or "N/A"
    }

async def search_ri(search_args: dict) -> dict:
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Rhode Island search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://business.sos.ri.gov/CorpWeb/CorpSearch/CorpSearch.aspx", wait_until="load")
            await page.check("#MainContent_rdoByEntityName")
            await page.fill("#MainContent_txtEntityName", entity_name)
            
            async with page.expect_navigation():
                await page.click("#MainContent_btnSearch")

            if await page.locator("#MainContent_lblMessage:has-text('No records found')").count() > 0:
                return []
            
            first_row_link = page.locator("table#MainContent_SearchControl_grdSearchResultsEntity tbody tr:not(.GridHeader) td:first-child a.link").first
            async with page.expect_navigation(wait_until="load"):
                await first_row_link.click()
            
            return [await extract_detail_page_data_async(page)]
        except Exception as e:
            return {"error": f"An unexpected error occurred in RI scraper: {e}"}
        finally:
            await browser.close()