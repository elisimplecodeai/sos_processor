from playwright.async_api import async_playwright
import asyncio

async def search_ut(search_args):
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Utah search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto("https://secure.utah.gov/bes/", timeout=60000)
            await page.fill('input[name="name"]', entity_name)
            
            async with page.expect_navigation():
                await page.click('button:has-text("Search")')

            first_result_link = page.locator("table#entities > tbody > tr:first-child > td > a")
            if await first_result_link.count() == 0:
                return []

            async with page.expect_navigation():
                await first_result_link.click()

            await page.wait_for_selector("div#entity-details")

            async def get_detail(label):
                element = page.locator(f"//dt[normalize-space()='{label}']/following-sibling::dd[1]")
                return await element.inner_text() if await element.count() > 0 else None

            entity_status = await get_detail("Status:")
            scraped_data = {
                "entity_name": await page.locator("h2.title").inner_text(),
                "business_identification_number": await get_detail("Entity Number:"),
                "entity_type": await get_detail("Type:"),
                "address": await get_detail("Address:"),
                "registration_date": await get_detail("Registration Date:"),
                "entity_status": entity_status,
                "statusActive": "active" in entity_status.lower() if entity_status else False,
            }
            return [scraped_data]
        except Exception as e:
            return {"error": f"An unexpected error occurred in UT scraper: {e}"}
        finally:
            await browser.close()