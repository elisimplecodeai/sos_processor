const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const scrapeCalifornia = async (searchTerm, outputFilename) => {
    if (!searchTerm || !outputFilename) {
        console.error("Error: Missing searchTerm or outputFilename arguments.");
        fs.writeFileSync(outputFilename, JSON.stringify([]));
        process.exit(1);
    }
    
    const ERROR_PATH = path.resolve(__dirname, 'errors');
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    let browser = null;
    try {
        browser = await chromium.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
        });
        const context = await browser.newContext({
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport: { width: 1366, height: 768 }
        });
        const page = await context.newPage();
        page.setDefaultTimeout(30000);

        await page.goto('https://bizfileonline.sos.ca.gov/search/business');

        await page.locator('input[placeholder="Search by name or file number"]').fill(searchTerm);
        await page.locator("button.search-button").click();

        const firstResultLocator = page.locator("table > tbody > tr:first-child > td:first-child > div[role='button']");
        await firstResultLocator.waitFor({ state: 'visible', timeout: 15000 });
        await firstResultLocator.click();

        await page.locator("div.drawer.show table.details-list").waitFor({ state: 'visible' });
        await page.locator("div.title-box").waitFor({ state: 'visible' });
        
        const scrapedData = await page.evaluate(() => {
            const getDetail = (label) => { const allLabels = document.querySelectorAll('div.drawer.show td.label'); for (const el of allLabels) { if (el.innerText.trim().toUpperCase() === label.toUpperCase()) { const valueCell = el.nextElementSibling; return valueCell ? valueCell.innerText.trim().replace(/\s\s+/g, ' ') : null; } } return null; };
            const titleElement = document.querySelector('div.title-box h4');
            const fullTitle = titleElement ? titleElement.innerText.trim() : '';
            let entityName = fullTitle; let businessId = null;
            const match = fullTitle.match(/^(.*?)\s*\(([A-Za-z0-9]+)\)$/);
            if (match) { entityName = match[1].trim(); businessId = match[2].trim(); }
            if (!businessId) { businessId = getDetail("File Number"); }
            const entityStatus = getDetail("Status");
            const mailingAddress = getDetail("Mailing Address");
            const principalAddress = getDetail("Principal Address");
            return {
                "entity_name": entityName, "registration_date": getDetail("Initial Filing Date"), "entity_type": getDetail("Entity Type"),
                "business_identification_number": businessId, "entity_status": entityStatus,
                "statusActive": entityStatus ? entityStatus.toLowerCase().includes("active") : false,
                "address": mailingAddress || principalAddress,
            };
        });

        fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));

    } catch (e) {
        console.error("An error occurred during CA automation:", e.message);
        const screenshotPath = path.join(ERROR_PATH, `california_error_${Date.now()}.png`);
        try {
            if (page && !page.isClosed()) {
                await page.screenshot({ path: screenshotPath });
                console.log(`✅ Screenshot saved to: ${screenshotPath}`);
            }
        } catch (screenshotError) {
            console.error(`Failed to take screenshot: ${screenshotError.message}`);
        }
        fs.writeFileSync(outputFilename, JSON.stringify([]));
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeCalifornia(searchTerm, outputFilename);