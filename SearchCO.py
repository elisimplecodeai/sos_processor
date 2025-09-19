from playwright.async_api import async_playwright
import asyncio
import os

async def search_co(search_args):
    """
    Final async working version for Colorado, modified to only return the first result.
    It correctly uses 'await' for all async operations.
    """
    entity_name = search_args.get("entity_name")
    if not entity_name:
        return {"error": "Entity name is required for Colorado search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto("https://www.coloradosos.gov/biz/BusinessEntityCriteria.do", wait_until="load", timeout=60000)
            await page.fill("#searchCriteria", entity_name)
            
            async with page.expect_navigation(wait_until="domcontentloaded"):
                await page.click('input[type="submit"][value="Search"]')

            await page.wait_for_selector('table[width="100%"] caption', state="visible")
            
            first_link_locator = page.locator('//table[@width="100%"]/tbody/tr/td[2]/a').first
            if await first_link_locator.count() == 0:
                return []

            href = await first_link_locator.get_attribute("href")
            
            if "BusinessEntityDetail.do" not in href and "TradeNameSummary.do" not in href:
                return []

            full_url = f"https://www.coloradosos.gov/biz/{href}"
            await page.goto(full_url, wait_until="domcontentloaded")

            show_entity_selector = 'a:has-text("Show entity"):not(.leftnav)'
            if await page.locator(show_entity_selector).count() > 0:
                async with page.expect_navigation(wait_until="domcontentloaded"):
                    await page.locator(show_entity_selector).click()
                await page.wait_for_selector("th.entity_conf_column_header_medium", state="visible")

            async def get_text_by_header(header_texts):
                for text in header_texts:
                    header = page.locator(f'//th[normalize-space(.)="{text}"]').first
                    if await header.count() > 0:
                        value = header.locator("xpath=./following-sibling::td[1]")
                        if await value.count() > 0:
                            return await value.inner_text()
                return ""

            entity_status = await get_text_by_header(["Status"])
            scraped_data = {
                "entity_name": (await get_text_by_header(["Name", "Entity name", "Trade name"])).split(',')[0].strip(),
                "entity_status": entity_status,
                "registration_date": await get_text_by_header(["Formation date"]),
                "business_identification_number": await get_text_by_header(["ID number"]),
                "entity_type": await get_text_by_header(["Form"]),
                "address": await get_text_by_header(["Principal office street address"]),
            }
            scraped_data["statusActive"] = "good standing" in scraped_data.get("entity_status", "").lower()
            
            return [scraped_data]

        except Exception as e:
            error_dir = os.path.join(os.path.dirname(__file__), "errors")
            os.makedirs(error_dir, exist_ok=True)
            screenshot_path = os.path.join(error_dir, f"colorado_unexpected_error_{int(time.time())}.png")
            if page and not page.is_closed():
                await page.screenshot(path=screenshot_path, full_page=True)
            return {"error": "An unexpected error occurred in CO scraper.", "details": str(e)}

        finally:
            if browser:
                await browser.close()