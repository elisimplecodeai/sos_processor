const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());
const fs = require('fs');

// --- Main function to handle the scraping logic ---
const scrapeLouisiana = async (searchTerm, outputFilename) => {
    if (!searchTerm || !outputFilename) {
        console.error("Error: Missing search term or output filename.");
        process.exit(1);
    }

    const browser = await puppeteer.launch({
        headless: false,
        args: [
            '--no-sandbox', '--disable-setuid-sandbox', '--disable-infobars',
            '--window-position=0,0', '--ignore-certificate-errors',
            '--ignore-certificate-errors-spki-list', '--start-maximized',
        ],
        defaultViewport: null,
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);

    try {
        await page.goto('https://coraweb.sos.la.gov/commercialsearch/commercialsearch.aspx', { waitUntil: 'networkidle2' });

        await page.type('#ctl00_cphContent_txtEntityName', searchTerm, { delay: 80 });

        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#btnSearch')
        ]);

        const resultsPageSelector = '#ctl00_cphContent_pnlSearchResults';
        const detailsPageSelector = '#ctl00_cphContent_lblName';
        const noResultsSelector = '#ctl00_cphContent_lblNoRecords';

        await page.waitForSelector(`${resultsPageSelector}, ${detailsPageSelector}, ${noResultsSelector}`);

        let scrapedData = {};

        if (await page.$(resultsPageSelector)) {
            // --- This script targets the VERY FIRST result on the list ---
            const firstResultSelector = '#ctl00_cphContent_grdSearchResults_EntityNameOrCharterNumber_ctl03_btnViewDetails';
            
            try {
                await page.waitForSelector(firstResultSelector, { visible: true, timeout: 10000 });
                await Promise.all([
                    page.waitForNavigation({ waitUntil: 'networkidle2' }),
                    // Use evaluate to click, bypassing potential overlays like reCAPTCHA badge
                    page.evaluate(selector => document.querySelector(selector).click(), firstResultSelector)
                ]);
            } catch (e) {
                // If the first result doesn't exist, it means no results were found.
                fs.writeFileSync(outputFilename, JSON.stringify([], null, 2)); // Write empty array
                await browser.close();
                return;
            }

        } else if (await page.$(noResultsSelector)) {
            fs.writeFileSync(outputFilename, JSON.stringify([], null, 2)); // Write empty array for no results
            await browser.close();
            return;
        }

        // Now we are on the details page (either directly or after clicking)
        await page.waitForSelector('#ctl00_cphContent_lblName', { visible: true });
        scrapedData = await page.evaluate(() => {
            const getText = (selector) => document.querySelector(selector)?.innerText.trim() || '';
            const entity_name = getText('#ctl00_cphContent_lblName');
            const registration_date = getText('#ctl00_cphContent_lblRegistrationDate');
            const entity_type = getText('#ctl00_cphContent_lblType');
            const business_identification_number = getText('#ctl00_cphContent_lblCharterNumber');
            const entity_status = getText('#ctl00_cphContent_lblStatus2');
            const address1 = getText('#ctl00_cphContent_lblAddress1');
            const address2 = getText('#ctl00_cphContent_lblCSZ');
            const address = `${address1} ${address2.replace(/\s\s+/g, ' ')}`.trim();
            return { entity_name, registration_date, entity_type, business_identification_number, entity_status, address };
        });

        // Write the single result as an array containing one object
        fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));

    } catch (err) {
        console.error("An error occurred during LA automation:", err);
        // On error, write an empty array to the output file so Python doesn't fail
        fs.writeFileSync(outputFilename, JSON.stringify([], null, 2)); 
    } finally {
        await browser.close();
    }
};

// --- Script execution starts here ---
// process.argv[2] is the first command-line argument (the search term)
// process.argv[3] is the second (the output filename)
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];

scrapeLouisiana(searchTerm, outputFilename).catch(err => {
    console.error(err);
    process.exit(1);
});