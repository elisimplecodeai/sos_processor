const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const scrapeArizona = async (searchTerm, outputFilename) => {
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
            headless: 'new', // Set to 'new' for system integration
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        const page = await browser.newPage();
        page.setDefaultTimeout(60000); // 60-second timeout
        await page.setViewport({ width: 1365, height: 919 });

        await page.goto('https://ecorp.azcc.gov/EntitySearch/Index', { waitUntil: 'domcontentloaded' });

        await page.type('#quickSearch_BusinessName', searchTerm);

        // Click search button and wait for results grid
        await Promise.all([
            page.waitForSelector('#grid_resutList', { visible: true, timeout: 60000 }),
            page.click('#btn_Search')
        ]);

        // --- Conditional "Too many results" handling ---
        const okButtonSelector = 'button.confirm[tabindex="1"][style*="display: inline-block"]';
        try {
            // Use a short timeout just to check for the presence of the button
            await page.waitForSelector(okButtonSelector, { timeout: 2000 });
            // If found, it means too many results, so we output an error
            fs.writeFileSync(outputFilename, JSON.stringify({"error": "Too many results. Please refine your search."}, null, 2));
            await browser.close();
            return; // Exit script
        } catch (error) {
            // If waitForSelector times out, it means the OK button was NOT found (good path)
            // We just proceed.
        }
        // --- End conditional handling ---

        // Click the top search result
        const firstResultSelector = '#grid_resutList tbody tr:first-child a.BlueLink';
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle0' }),
            page.click(firstResultSelector)
        ]);

        // Scrape the details from the entity details page
        const scrapedData = await page.evaluate(() => {
            const data = {};
            const getLabelText = (labelText) => {
                const labelElement = Array.from(document.querySelectorAll('.search-label label'))
                    .find(label => label.textContent.trim().includes(labelText));
                if (labelElement) {
                    let valueElement = labelElement.parentElement.nextElementSibling;
                    if (labelText === 'Entity Status:') {
                        return valueElement ? valueElement.querySelector('strong')?.textContent.trim() || valueElement.textContent.trim() : null;
                    }
                    return valueElement ? valueElement.textContent.trim() : null;
                }
                return null;
            };
            data.entity_name = getLabelText('Entity Name:');
            data.registration_date = getLabelText('Formation Date:');
            data.entity_type = getLabelText('Entity Type:');
            data.business_identification_number = getLabelText('Entity ID:');
            data.entity_status = getLabelText('Entity Status:');
            data.statusActive = data.entity_status ? data.entity_status.toLowerCase().includes('active') : false;
            const agentAddressLabel = Array.from(document.querySelectorAll('.data_pannel1 .row label'))
                .find(label => label.textContent.includes('Address:') && label.getAttribute('for') === 'Agent_PrincipalAddress');
            if (agentAddressLabel) {
                const addressContainer = agentAddressLabel.closest('.row');
                const addressValue = addressContainer ? addressContainer.querySelector('.col-sm-6')?.textContent.trim() : null;
                data.address = addressValue ? addressValue.replace(/\s+/g, ' ') : null;
            } else {
                data.address = null;
            }
            return data;
        });

        fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));

    } catch (err) {
        console.error("An error occurred during AZ automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `arizona_error_${Date.now()}.png`);
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
scrapeArizona(searchTerm, outputFilename);