import re
import asyncio
from playwright.async_api import async_playwright

async def extract_detail_table_async(page):
    details = {}
    rows = await page.query_selector_all("table.details-list tbody tr")
    for row in rows:
        label_el = await row.query_selector("td.label")
        value_el = await row.query_selector("td.value")
        if label_el and value_el:
            label = (await label_el.inner_text()).strip()
            value = (await value_el.inner_text()).strip()
            details[label] = value
    return details

def normalize_address(addr: str) -> str:
    return re.sub(r'\s*\n\s*', ', ', addr).strip() if addr else "N/A"

async def search_nd(search_args: dict) -> dict:
    entity_name_input = search_args.get("entity_name")
    if not entity_name_input:
        return {"error": "Entity name required for North Dakota search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto("https://firststop.sos.nd.gov/search/business", wait_until="domcontentloaded")
            search_input = await page.wait_for_selector('input.search-input', state="visible")
            await search_input.fill(entity_name_input)
            
            await page.wait_for_function('document.querySelector("button.search-button")?.getAttribute("aria-disabled") === "false"')
            await page.click("button.search-button")

            await page.wait_for_selector("div.table-wrapper, .alert-danger", timeout=15000)
            if await page.locator(".alert-danger").count() > 0:
                return {"error": await page.locator(".alert-danger").inner_text()}

            first_row = page.locator("div.table-wrapper table tbody tr").first
            if await first_row.count() == 0:
                return []

            await first_row.locator("td div[role='button']").click()
            await page.wait_for_selector("table.details-list", timeout=10000)

            details = await extract_detail_table_async(page)
            entity_status = details.get("Status", "N/A")
            
            return [{
                "entity_name": await first_row.locator("td:nth-child(1) > div > span.cell").inner_text(),
                "registration_date": details.get("Initial Filing Date", "N/A"),
                "entity_type": details.get("Filing Type", "N/A"),
                "business_identification_number": await first_row.locator("td:nth-child(2) > span.cell").inner_text(),
                "entity_status": entity_status,
                "statusActive": "active" in entity_status.lower(),
                "address": normalize_address(details.get("Principal Address", "N/A"))
            }]
        except Exception as e:
            return {"error": f"An unexpected error occurred in ND scraper: {e}"}
        finally:
            await browser.close()