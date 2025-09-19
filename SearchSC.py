import re
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

SC_SEARCH_URL = "https://businessfilings.sc.gov/BusinessFiling/Entity/Search"
SC_BASE_URL = "https://businessfilings.sc.gov"

async def parse_detail_page_async(page) -> dict:
    await page.wait_for_selector("fieldset.entityProfile legend", timeout=10000)
    
    async def get_text(selector):
        element = page.locator(selector)
        return (await element.inner_text()).strip() if await element.count() > 0 else "N/A"

    entity_status = await get_text("section.entityProfileInfo span.label:has-text('Status') + span.data")
    
    address_data_element = page.locator("div.profileContent:has(h2:has-text('Registered Agent')) span.label:has-text('Address') + span.data")
    address = "N/A"
    if await address_data_element.count() > 0:
        raw_html = await address_data_element.inner_html()
        text_with_commas = re.sub(r'<br\s*/?>', ', ', raw_html, flags=re.IGNORECASE)
        soup = BeautifulSoup(text_with_commas, 'html.parser')
        address = re.sub(r'\s+', ' ', soup.get_text()).strip()

    return {
        "entity_name": await get_text("fieldset.entityProfile legend"),
        "registration_date": await get_text("section.datesInfo span.label:has-text('Effective Date') + span.data"),
        "entity_type": await get_text("section.entityProfileInfo span.label:has-text('Entity Type') + span.data"),
        "business_identification_number": await get_text("section.entityProfileInfo span.label:has-text('Entity Id') + span.data"),
        "entity_status": entity_status,
        "statusActive": "good standing" in entity_status.lower() or "active" in entity_status.lower(),
        "address": address
    }

async def search_sc(search_args: dict) -> dict:
    entity_name = search_args.get("entity_name", "").strip()
    if not entity_name:
        return {"error": "Entity name is required for South Carolina search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(SC_SEARCH_URL, wait_until="domcontentloaded")
            await page.fill("input#SearchTextBox", entity_name)
            await page.select_option("select#EntitySearchTypeEnumId", value="3")
            
            async with page.expect_navigation():
                await page.click("button#EntitySearchButton")

            if await page.is_visible("p.alert.noResults"):
                return []

            first_row_link = page.locator("table#EntitySearchResultsTable tbody tr a").first
            href = await first_row_link.get_attribute("href")
            
            await page.goto(SC_BASE_URL + href, wait_until="domcontentloaded")
            
            record = await parse_detail_page_async(page)
            return [record]
        except Exception as e:
            return {"error": f"An unexpected error occurred in SC scraper: {e}"}
        finally:
            await browser.close()