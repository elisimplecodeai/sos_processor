const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const scrapeNewHampshire = async (searchTerm, outputFilename) => {
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
            headless: false, // Set to 'new' for system integration
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        const page = await browser.newPage();
        page.setDefaultTimeout(60000);
        await page.setViewport({ width: 1280, height: 928 });

        await page.goto('https://quickstart.sos.nh.gov/online/BusinessInquire', { waitUntil: 'networkidle2' });

        // Use a direct, simple selector for the input field
        const businessNameInputSelector = '#txtBusinessName';
        await page.waitForSelector(businessNameInputSelector, { visible: true });
        await page.type(businessNameInputSelector, searchTerm, { delay: 100 });

        // Click search and wait for navigation
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#btnSearch')
        ]);

        // Wait for the first result and click it
        const firstResultSelector = '#xhtml_grid > tbody > tr:nth-child(1) > td:nth-child(1) > a';
        await page.waitForSelector(firstResultSelector, { visible: true });

        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click(firstResultSelector)
        ]);
        
        // Wait for a stable element on the details page before scraping
        await page.waitForSelector('.data_pannel', { visible: true });

        const scrapedData = await page.evaluate(() => {
            const getTextAfterLabel = (labelText) => {
                const allTds = Array.from(document.querySelectorAll('.data_pannel td'));
                const labelTd = allTds.find(td => td.innerText.trim() === labelText);
                if (labelTd && labelTd.nextElementSibling) {
                    return labelTd.nextElementSibling.innerText.trim();
                }
                return "";
            };

            const entity_status = getTextAfterLabel('Business Status:');
            const registrationDateStr = getTextAfterLabel('Business Creation Date:');
            
            return {
                entity_name: getTextAfterLabel('Business Name:').replace(/"/g, ''),
                registration_date: registrationDateStr,
                entity_type: getTextAfterLabel('Business Type:'),
                business_identification_number: getTextAfterLabel('Business ID:'),
                entity_status: entity_status,
                statusActive: entity_status.toLowerCase().includes('active'),
                address: getTextAfterLabel('Principal Office Address:')
            };
        });

        // Write the single result as an array for consistency
        fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));

    } catch (err) {
        console.error("An error occurred during NH automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `newhampshire_error_${Date.now()}.png`);
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
scrapeNewHampshire(searchTerm, outputFilename);