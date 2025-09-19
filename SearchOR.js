const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const scrapeOregon = async (searchTerm, outputFilename) => {
    if (!searchTerm || !outputFilename) {
        console.error("Error: Missing searchTerm or outputFilename arguments.");
        fs.writeFileSync(outputFilename, JSON.stringify([])); // Write empty array for consistency
        process.exit(1);
    }

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null, // Set to 'new' for system integration
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);
    await page.setViewport({ width: 1200, height: 800 });

    try {
        // --- PART 1: Perform the Search ---
        await page.goto('https://sos.oregon.gov/business/pages/find.aspx', { waitUntil: 'networkidle0' });
        await page.waitForSelector('#busSearchInput', { visible: true });
        await page.type('#busSearchInput', searchTerm, { delay: 100 });

        const searchButtonSelectors = ['button.primary.button', 'div.sos-content-wrapper button'];
        const searchButton = await Promise.race(
            searchButtonSelectors.map(selector => page.waitForSelector(selector, { visible: true }))
        );
        if (!searchButton) { throw new Error("Could not find a clickable search button."); }

        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle0' }),
            searchButton.click()
        ]);

        // --- PART 2: Click the First Result ---
        const firstResultSelector = 'body > form > table:nth-child(3) > tbody > tr:nth-child(2) > td:nth-child(6) > a';
        await page.waitForSelector(firstResultSelector, { visible: true });
        
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle0' }),
            page.click(firstResultSelector)
        ]);

        // --- PART 3: Scrape Data from Details Page ---
        const businessData = await page.evaluate(() => {
            const getDataByLabel = (label) => { const element = Array.from(document.querySelectorAll('td, b')).find(el => el.textContent.trim() === label); return element ? element.closest('td').nextElementSibling.textContent.trim() : null; };
            const getMainInfoByIndex = (index) => { const selector = 'table[border="1"][cellspacing="0"][cellpadding="0"] > tbody > tr:nth-child(2)'; const row = document.querySelector(selector); return row ? row.children[index - 1].textContent.trim() : null; };
            const entityStatus = getMainInfoByIndex(3);
            let fullAddress = ''; const ppbHeader = Array.from(document.querySelectorAll('td')).find(el => el.textContent.trim() === 'PRINCIPAL PLACE OF BUSINESS');
            if (ppbHeader) {
                try {
                    const addressTable = ppbHeader.closest('table').nextElementSibling; const cszTable = addressTable.nextElementSibling;
                    const addr1 = addressTable.querySelector('td:nth-child(2)').textContent.trim(); const city = cszTable.querySelector('td:nth-child(2)').textContent.trim(); const state = cszTable.querySelector('td:nth-child(3)').textContent.trim(); const zip = cszTable.querySelector('td:nth-child(4)').textContent.trim(); const countryElement = cszTable.querySelector('td:nth-child(7)'); const country = countryElement ? countryElement.textContent.trim() : 'Not Found';
                    fullAddress = [addr1, city, state, zip, country].filter(val => val && val !== 'Not Found').join(', ');
                } catch (e) { fullAddress = 'Address could not be parsed.'; }
            }
            return {
                entity_name: getDataByLabel('Entity Name'), registration_date: getMainInfoByIndex(5), entity_type: getMainInfoByIndex(2),
                business_identification_number: getMainInfoByIndex(1), entity_status: entityStatus,
                statusActive: entityStatus ? entityStatus.toUpperCase().startsWith('ACT') : false, address: fullAddress || 'Not Found'
            };
        });

        // --- PART 4: Save Data to JSON File ---
        // Write the result as an array with one object for consistency with other scrapers.
        fs.writeFileSync(outputFilename, JSON.stringify([businessData], null, 2));

    } catch (err) {
        console.error("An error occurred during OR automation:", err.message);
        fs.writeFileSync(outputFilename, JSON.stringify([])); // Write empty array on error
    } finally {
        if (browser) {
            await browser.close();
        }
    }
};

// --- Script Execution ---
// These arguments are passed in from the Python wrapper
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeOregon(searchTerm, outputFilename);