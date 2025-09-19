const puppeteer = require('puppeteer'); // Use standard Puppeteer
const fs = require('fs');
const path = require('path');

const search_wa = async (searchTerm, outputFilename) => {
    if (!searchTerm || !outputFilename) {
        console.error("Error: Missing searchTerm or outputFilename arguments.");
        fs.writeFileSync(outputFilename, JSON.stringify([]));
        process.exit(1);
    }

    const ERROR_PATH = path.resolve(__dirname, 'errors');
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: 'new',
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        const page = await browser.newPage();
        page.setDefaultTimeout(60000);
        await page.setViewport({ width: 1905, height: 919 });

        await page.goto('https://ccfs.sos.wa.gov/#/Home');

        await page.waitForSelector('::-p-aria(Business Name)', { visible: true });
        await page.type('::-p-aria(Business Name)', searchTerm, { delay: 100 });
        
        const searchButtonSelector = 'body > div > ng-include > div > div > main > div:nth-child(3) > div > div > div > div > div:nth-child(5) > div:nth-child(2) > button';
        await page.waitForSelector(searchButtonSelector, { visible: true });
        await page.click(searchButtonSelector);

        // --- Handle sticky search button ---
        await new Promise(resolve => setTimeout(resolve, 2000));
        try {
            // isVisible() is a Playwright method, so we use a different check for Puppeteer
            const button = await page.$(searchButtonSelector);
            if (button) {
                await page.click(searchButtonSelector);
            }
        } catch (error) {
            // Button is gone, which is the expected outcome.
        }
        
        const firstResultSelector = 'tr:nth-of-type(1) > td:nth-of-type(1) > a';
        await page.waitForSelector(firstResultSelector, { visible: true });
        await page.click(firstResultSelector);

        const detailsPageElementSelector = '[data-ng-bind="businessInfo.UBINumber"]';
        await page.waitForSelector(detailsPageElementSelector, { visible: true });

        const scrapedData = await page.evaluate(() => {
            const getElementText = (selector) => { const element = document.querySelector(selector); return element ? element.innerText.trim() : null; };
            const entity_status = getElementText('[data-ng-bind="businessInfo.BusinessStatus | uppercase"]');
            return {
                entity_name: getElementText('[data-ng-bind="businessInfo.BusinessName"]'),
                registration_date: getElementText('[data-ng-bind*="businessInfo.DateOfIncorporation"]'),
                entity_type: getElementText('[data-ng-bind="businessInfo.BusinessType"]'),
                business_identification_number: getElementText('[data-ng-bind="businessInfo.UBINumber"]'),
                entity_status: entity_status,
                statusActive: entity_status === 'ACTIVE',
                address: getElementText('[data-ng-bind*="businessInfo.PrincipalOffice.PrincipalStreetAddress.FullAddress"]')
            };
        });

        fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));

    } catch (err) {
        console.error("An error occurred during WA automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `washington_error_${Date.now()}.png`);
        try {
            if (page && !page.isClosed()) {
                await page.screenshot({ path: screenshotPath, fullPage: true });
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
};

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
search_wa(searchTerm, outputFilename);