from playwright.async_api import async_playwright
import asyncio
import html, re 

WY_SEARCH_URL = "https://wyobiz.wyo.gov/Business/FilingSearch.aspx"
WY_BASE_URL = "https://wyobiz.wyo.gov/Business/"

def format_address(principal, mailing):
    def clean(text):
        if not text: return ""
        text = html.unescape(text).replace("\n", ", ").replace("<br>", ", ")
        return re.sub(r'\s{2,}', ' ', text).strip(" ,")
    p_clean = clean(principal)
    return p_clean if p_clean else clean(mailing) or "N/A"

async def parse_detail_page_async(page):
    async def get_text(selector):
        element = page.locator(selector)
        return (await element.inner_text()).strip() if await element.count() > 0 else "N/A"
    async def get_html(selector):
        element = page.locator(selector)
        return (await element.inner_html()).strip() if await element.count() > 0 else ""
    status = await get_text("#txtStatus")
    return {
        "entity_name": await get_text("#txtFilingName2"),
        "registration_date": await get_text("#txtInitialDate"),
        "entity_type": await get_text("#txtFilingType"),
        "business_identification_number": await get_text("#txtFilingNum"),
        "entity_status": status,
        "statusActive": "active" in status.lower() or "good standing" in status.lower(),
        "address": format_address(await get_html("#txtOfficeAddresss"), await get_html("#txtMailAddress"))
    }

async def search_wy(search_args):
    entity_name = search_args.get("entity_name", "").strip()
    if not entity_name:
        return {"error": "Filing Name required for Wyoming search."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(WY_SEARCH_URL, wait_until="domcontentloaded")
            await page.locator("#MainContent_chkSearchStartWith").check()
            await page.locator("#MainContent_txtFilingName").fill(entity_name)
            
            async with page.expect_navigation():
                await page.locator("#MainContent_cmdSearch").click()

            if "No Results Found" in await page.locator("#MainContent_lblResultsHeader").inner_text():
                return []
            
            first_result_link = page.locator("ol#Ol1 li a").first
            href = await first_result_link.get_attribute("href")
            
            await page.goto(WY_BASE_URL + href, wait_until="domcontentloaded")
            return [await parse_detail_page_async(page)]
        except Exception as e:
            return {"error": f"An unexpected error occurred in WY scraper: {e}"}
        finally:
            await browser.close()