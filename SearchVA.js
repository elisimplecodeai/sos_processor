const puppeteer = require('puppeteer-core');
const fs = require('fs');

// --- START: ADVANCED ANTI-BOT SPOOFING ---
// This complex function helps the scraper appear more like a real browser.
const antiBotSpoofing = () => {
    Object.defineProperty(navigator, 'plugins', { get: () => [{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    delete navigator.__proto__.webdriver;
    try {
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Open Source Technology Center';
            if (parameter === 37446) return 'Mesa DRI Intel(R) Ivybridge Mobile';
            return getParameter(parameter);
        };
    } catch (e) {}
    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
};
// --- END: ADVANCED ANTI-BOT SPOOFING ---


// --- START: Human-like Helper Functions ---
// These functions add delays and use more human-like interaction methods.
const randomDelay = (min = 400, max = 900) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));

const domClick = async (page, selector) => {
    await page.waitForSelector(selector, { visible: true, timeout: 30000 });
    await page.evaluate((sel) => {
        const element = document.querySelector(sel);
        if (element) { element.click(); } 
        else { throw new Error(`Element with selector "${sel}" not found.`); }
    }, selector);
};

const humanlikeType = async (page, selector, text) => {
    await page.waitForSelector(selector, { visible: true });
    await domClick(page, selector);
    await randomDelay(300, 600);
    await page.type(selector, text, { delay: Math.random() * 150 + 50 });
};

const submitWithEnter = async (page) => {
    await page.keyboard.press('Enter');
};
// --- END: Human-like Helper Functions ---


const scrapeVirginia = async (searchTerm, outputFilename, executablePath) => {
    // Validate that all necessary arguments were passed from Python
    if (!searchTerm || !outputFilename || !executablePath) {
        console.error("Error: Missing searchTerm, outputFilename, or executablePath.");
        fs.writeFileSync(outputFilename, JSON.stringify([])); // Write empty array for consistency
        process.exit(1);
    }

    if (!fs.existsSync(executablePath)) {
        console.error(`ERROR: Chrome not found at path passed from Python: "${executablePath}".`);
        fs.writeFileSync(outputFilename, JSON.stringify([]));
        process.exit(1);
    }

    let browser;
    try {
        browser = await puppeteer.launch({
            executablePath,
            headless: false, // Use 'new' for integration, set to false for debugging
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled', '--window-size=1920,1080']
        });

        const page = await browser.newPage();
        await page.evaluateOnNewDocument(antiBotSpoofing);
        await page.setViewport({ width: 1920, height: 1080 });
        page.setDefaultTimeout(60000);

        await page.goto('https://cis.scc.virginia.gov/EntitySearch/Index', { waitUntil: 'networkidle2' });
        await randomDelay(2000, 3500);
        await humanlikeType(page, '#BusinessSearch_Index_txtBusinessName', searchTerm);
        await randomDelay(1000, 2000);
        await submitWithEnter(page);

        // --- START: MODIFIED SECTION ---
        // After submitting, a pop-up may appear. This handles that case.
        try {
            const popUpButtonSelector = 'body > div.sweet-alert.showSweetAlert.visible > div.sa-button-container > button';
            // Wait for the button to appear, but only for a short time.
            await page.waitForSelector(popUpButtonSelector, { visible: true, timeout: 5000 });
            await domClick(page, popUpButtonSelector);
        } catch (error) {
            // This is an expected error if the pop-up does not appear.
            // We can safely ignore it and continue with the script.
        }
        // --- END: MODIFIED SECTION ---
        
        const loadingSpinnerSelector = 'div.sweet-alert.show-sweet-alert .la-ball-circus';
        const resultsTableSelector = '#grid_businessList';
        const noResultsModalSelector = 'div.sa-icon-error';

        // Wait for one of the three possible outcomes: spinner, results, or no results
        await page.waitForSelector(`${loadingSpinnerSelector}, ${resultsTableSelector}, ${noResultsModalSelector}`);

        // If the loading spinner is present, wait for it to disappear
        if (await page.$(loadingSpinnerSelector)) {
            await page.waitForSelector(loadingSpinnerSelector, { hidden: true, timeout: 45000 });
        }
        
        // After spinner, check if the "no results" modal appeared
        if (await page.$(noResultsModalSelector)) {
            fs.writeFileSync(outputFilename, JSON.stringify([]));
        } else {
            // Otherwise, we expect the results table
            await page.waitForSelector(resultsTableSelector, { visible: true });
            const firstResultLinkSelector = '#grid_businessList tbody tr:first-child td:first-child a';
            
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'networkidle2' }),
                domClick(page, firstResultLinkSelector)
            ]);

            await page.waitForSelector('.EntitySearch', { visible: true });
            
            const scrapedData = await page.evaluate(() => {
                const getTextByLabel = (labelText) => {
                    const allLabels = Array.from(document.querySelectorAll('.data_pannel0 .text-right'));
                    const targetLabel = allLabels.find(el => el.textContent.trim().toLowerCase().includes(labelText.toLowerCase()));
                    return (targetLabel && targetLabel.nextElementSibling) ? targetLabel.nextElementSibling.textContent.trim() : 'N/A';
                };

                let entity_status = 'N/A';
                const statusLabel = Array.from(document.querySelectorAll('.data_pannel0 .text-right')).find(el => el.textContent.trim().toLowerCase() === 'entity status:');
                if (statusLabel && statusLabel.nextElementSibling) {
                    const statusElement = statusLabel.nextElementSibling.querySelector('strong');
                    entity_status = statusElement ? statusElement.textContent.trim() : statusLabel.nextElementSibling.textContent.trim();
                }

                let address = 'N/A';
                const addressLabel = Array.from(document.querySelectorAll('.data_pannel0 .text-right')).find(el => el.textContent.trim().toLowerCase() === 'address:');
                if (addressLabel && addressLabel.nextElementSibling) {
                    address = addressLabel.nextElementSibling.textContent.trim().replace(/\s\s+/g, ' ');
                }

                return {
                    entity_name: getTextByLabel('entity name:'),
                    registration_date: getTextByLabel('va qualification date:'),
                    entity_type: getTextByLabel('entity type:'),
                    business_identification_number: getTextByLabel('entity id:'),
                    entity_status: entity_status,
                    statusActive: entity_status.toLowerCase() === 'active',
                    address: address
                };
            });

            // Return the result as an array with one object for consistency
            fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));
        }

    } catch (err) {
        console.error("An error occurred during VA automation:", err.message);
        fs.writeFileSync(outputFilename, JSON.stringify([])); // Ensure empty array on error
    } finally {
        if (browser) {
            await browser.close();
        }
    }
};

// These arguments are passed in from the Python wrapper script
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
const executablePath = process.argv[4];

scrapeVirginia(searchTerm, outputFilename, executablePath);