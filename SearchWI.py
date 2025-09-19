from playwright.async_api import async_playwright
import asyncio

WI_SEARCH_URL = "https://apps.dfi.wi.gov/apps/corpsearch/Search.aspx?"
WI_BASE = "https://apps.dfi.wi.gov/apps/corpsearch/"

async def extract_detail_data_async(page) -> dict:
    async def get_table_value(label_text: str) -> str:
        row = page.locator(f"tr:has(td.label:has-text('{label_text}')) td.data").first
        return await row.inner_text() if await row.count() > 0 else "N/A"
    
    raw_status = await get_table_value("Status")
    status_keywords = ["Incorporated", "Qualified", "Registered", "Organized", "Restored"]
    entity_status = "N/A"
    statusActive = False
    if raw_status != "N/A":
        entity_status = raw_status.split('/')[0].strip()
        statusActive = any(keyword.lower() in raw_status.lower() for keyword in status_keywords)

    return {
        "entity_name": await page.locator("#entityName").inner_text(),
        "registration_date": await get_table_value("Registered Effective Date"),
        "entity_type": await get_table_value("Entity Type"),
        "business_identification_number": await get_table_value("Entity ID"),
        "entity_status": entity_status,
        "statusActive": statusActive,
        "address": (await get_table_value("Principal Office")).replace('\n', ', '),
    }

async def search_wi(search_args: dict) -> dict:
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name required for Wisconsin search."}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(WI_SEARCH_URL, timeout=20000)
            await page.fill('input[name="ctl00$cpContent$txtSearchString"]', entity_name)
            
            async with page.expect_navigation():
                await page.click('input[name="ctl00$cpContent$btnSearch"]')
            
            if await page.locator("text='No matches found.'").count() > 0:
                return []

            first_row_link = page.locator("#results tbody tr td.nameAndTypeDescription span.name a").first
            if await first_row_link.count() == 0: return []
            
            href = await first_row_link.get_attribute("href")
            await page.goto(WI_BASE + href.lstrip('/'))
            
            return [await extract_detail_data_async(page)]
        except Exception as e:
            return {"error": f"An unexpected error occurred in WI scraper: {e}"}
        finally:
            await browser.close()