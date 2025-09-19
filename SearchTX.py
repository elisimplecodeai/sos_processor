from playwright.async_api import async_playwright
import asyncio
import re

async def extract_registration_details_async(page):
    details = {"entity_name": "N/A", "registration_date": "N/A", "entity_type": "N/A", "business_identification_number": "N/A", "entity_status": "N/A", "statusActive": False, "address": "N/A"}
    entity_name_element = page.locator("#content h2.uppercase").first
    details["entity_name"] = await entity_name_element.inner_text() if await entity_name_element.count() > 0 else "N/A"
    rows = await page.locator("#content div.row").all()
    for row in rows:
        if await row.locator("div.grey-blocks strong").count() > 0:
            label_text = (await row.locator("div.grey-blocks strong").inner_text()).strip().upper()
            value_text = (await row.locator("div.results-blocks").inner_text()).strip()
            if "EFFECTIVE SOS REGISTRATION DATE" in label_text: details["registration_date"] = value_text
            elif "ENTITY TYPE" in label_text: details["entity_type"] = value_text
            elif "TEXAS SOS FILE NUMBER" in label_text: details["business_identification_number"] = value_text
            elif "SOS REGISTRATION STATUS" in label_text:
                details["entity_status"] = value_text
                details["statusActive"] = "active" in value_text.lower() or "in existence" in value_text.lower()
            elif "PRINCIPAL OFFICE ADDRESS" in label_text or "MAILING ADDRESS" in label_text:
                details["address"] = re.sub(r'\s+', ' ', value_text).strip()
    return details

async def search_tx(search_args):
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Texas search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://comptroller.texas.gov/taxes/franchise/account-status/", timeout=30000)
            await page.fill("#name", entity_name)
            
            async with page.expect_navigation():
                await page.click("#submitBtn")

            details_page_selector = "#content h2.uppercase"
            results_table_selector = "#resultTable"
            
            await page.wait_for_selector(f"{details_page_selector}, {results_table_selector}", timeout=20000)

            if await page.locator(details_page_selector).count() > 0:
                return [await extract_registration_details_async(page)]

            first_result_link = page.locator(f"{results_table_selector} tbody tr a").first
            if await first_result_link.count() == 0: return []
            
            async with page.expect_navigation(wait_until="load"):
                await first_result_link.click()
            
            await page.wait_for_selector(details_page_selector, timeout=20000)
            return [await extract_registration_details_async(page)]
        except Exception as e:
            return {"error": f"An unexpected error occurred in TX scraper: {e}"}
        finally:
            await browser.close()