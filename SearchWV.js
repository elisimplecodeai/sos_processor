const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');

puppeteer.use(StealthPlugin());

const scrapeWestVirginia = async (searchTerm, outputFilename) => {
    if (!searchTerm || !outputFilename) {
        console.error("Error: Missing search term or output filename arguments.");
        fs.writeFileSync(outputFilename, JSON.stringify([]));
        process.exit(1);
    }

    // --- TEMPORARY CHANGE FOR DEBUGGING ---
    const browser = await puppeteer.launch({
        headless: false, // Set to false to watch the browser in action
        slowMo: 50, // Slows down puppeteer operations by 50ms to make it easier to see
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--start-maximized']
    });
    // --- END OF CHANGE ---

    const page = await browser.newPage();
    page.setDefaultTimeout(90000);
    await page.setViewport({ width: 1920, height: 1080 });

    try {
        console.log('Navigating to WV Business Search...');
        await page.goto('https://apps.wv.gov/SOS/BusinessEntitySearch/', { waitUntil: 'networkidle2' });

        console.log(`Typing search term: "${searchTerm}"`);
        await page.type('#phMain_txtOrganizationName', searchTerm, { delay: 30 });

        console.log('Clicking search...');
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#phMain_btnSearch')
        ]);
        console.log('Search page loaded. Looking for results...');

        const resultsTableSelector = '#phMain_gvSearchResults';
        await page.waitForSelector(resultsTableSelector, { timeout: 15000 });
        console.log('Found results table.');

        // Check if there are any result rows. The selector targets the first data row.
        const firstResultRowSelector = `${resultsTableSelector} > tbody > tr:nth-child(2)`;
        const firstRow = await page.$(firstResultRowSelector);

        if (!firstRow) {
            console.log('Results table was found, but it contains 0 results.');
            fs.writeFileSync(outputFilename, JSON.stringify([]));
        } else {
            console.log('Scraping the first result...');
            
            // Scrape entity type from the first row
            const entityTypeSelector = `${firstResultRowSelector} > td.hidden-tablet.hidden-phone`;
            const entityType = await page.$eval(entityTypeSelector, el => el.innerText.trim());

            // Click the details link of the first result
            const detailLinkSelector = '#phMain_gvSearchResults_hpDetails_0';
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'networkidle2' }),
                page.click(detailLinkSelector)
            ]);

            const scrapedData = await page.evaluate(() => {
                const getText = (id) => document.getElementById(id)?.innerText.trim() || "";
                const entity_name = getText('phMain_ctrlMainDetails_lblBusinessName');
                const registration_date = getText('phMain_ctrlMainDetails_lblEffectiveDate');
                const business_identification_number = getText('phMain_ctrlMainDetails_lblBusinessId');
                const entity_status = getText('phMain_ctrlMainDetails_lblStatus');
                const statusActive = entity_status.toLowerCase().includes('active');

                const addressRow = Array.from(document.querySelectorAll('tr')).find(row => row.cells[0]?.innerText.trim() === 'Principal Office Address:');
                let address = "";
                if (addressRow) {
                    const addr1 = addressRow.cells[2]?.innerText.replace('Addr1:', '').trim() || "";
                    const addr2 = addressRow.cells[3]?.innerText.replace('Addr2:', '').trim() || "";
                    const city = addressRow.cells[4]?.innerText.replace('City:', '').trim() || "";
                    const state = addressRow.cells[5]?.innerText.replace('State:', '').trim() || "";
                    const zip = addressRow.cells[6]?.innerText.replace('Zip:', '').trim() || "";
                    address = `${addr1} ${addr2} ${city}, ${state} ${zip}`.replace(/\s+/g, ' ').trim();
                }

                return { entity_name, registration_date, business_identification_number, entity_status, statusActive, address };
            });

            // Combine the data and write it to the file (as an array with one item)
            const finalResult = { ...scrapedData, entity_type: entityType };
            fs.writeFileSync(outputFilename, JSON.stringify([finalResult], null, 2));
            console.log('Successfully scraped and saved the first result.');
        }

    } catch (err) {
        console.error("An error occurred during WV automation:", err);
        // Take a screenshot right when the error happens
        await page.screenshot({ path: 'wv_error_screenshot.png' });
        console.log("Error screenshot saved to wv_error_screenshot.png");
        fs.writeFileSync(outputFilename, JSON.stringify([]));
    } finally {
        // Keep the browser open for a few seconds to see the final state
        console.log('Closing browser in 10 seconds...');
        await new Promise(resolve => setTimeout(resolve, 10000));
        await browser.close();
    }
};

const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeWestVirginia(searchTerm, outputFilename);