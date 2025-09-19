import re
import asyncio
from playwright.async_api import async_playwright

def parse_entity_name(full_text: str) -> tuple[str, str]:
    state_id_match = re.search(r"\((\d+)\)$", full_text)
    state_id = state_id_match.group(1) if state_id_match else "N/A"
    entity_name_clean = re.sub(r"\s*\(\d+\)$", "", full_text).strip()
    return entity_name_clean, state_id

async def extract_pa_details_async(page) -> dict:
    details = {"registration_date": "N/A", "entity_type": "N/A", "entity_status": "N/A", "statusActive": False, "address": "N/A"}
    rows = await page.query_selector_all("table.details-list tbody tr.detail")
    for row in rows:
        label_td = await row.query_selector("td.label")
        value_td = await row.query_selector("td.value")
        if not label_td or not value_td: continue
        label = (await label_td.inner_text()).strip().upper()
        value = re.sub(r'\s+', ' ', await value_td.inner_text()).strip()
        if label == "INITIAL FILING DATE": details["registration_date"] = value
        elif label == "STATUS":
            details["entity_status"] = value
            details["statusActive"] = "active" in value.lower()
        elif label == "FILING TYPE": details["entity_type"] = value
        elif label in ["PRINCIPAL ADDRESS", "REGISTERED OFFICE"]:
             details["address"] = value
    return details

async def search_pa(search_args: dict) -> dict:
    entity_name_input = search_args.get("entity_name")
    if not entity_name_input:
        return {"error": "Entity name required for Pennsylvania search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto("https://file.dos.pa.gov/search/business", wait_until="domcontentloaded")
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

            full_entity_text = await first_row.locator("td:nth-child(1) > div > span.cell").inner_text()
            entity_name_clean, state_id = parse_entity_name(full_entity_text)
            
            await first_row.locator("td div[role='button']").click()
            await page.wait_for_selector("table.details-list", timeout=10000)

            details = await extract_pa_details_async(page)
            details["entity_name"] = entity_name_clean
            details["business_identification_number"] = state_id
            return [details]
        except Exception as e:
            return {"error": f"An unexpected error occurred in PA scraper: {e}"}
        finally:
            await browser.close()