const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const scrapeIowa = async (searchTerm, outputFilename) => {
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
            headless: false,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        const page = await browser.newPage();
        page.setDefaultTimeout(60000);
        await page.setViewport({ width: 1280, height: 927 });

        await page.goto('https://sos.iowa.gov/search/business/search.aspx', { waitUntil: 'networkidle2' });

        await page.waitForSelector('#txtName', { visible: true });
        await page.type('#txtName', searchTerm, { delay: 100 });

        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#frmSearch button')
        ]);

        const firstResultSelector = '#mainArticle > table > tbody > tr:nth-child(2) > td:nth-child(1) > a';
        await page.waitForSelector(firstResultSelector, { visible: true });

        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click(firstResultSelector)
        ]);
        
        const detailsHeaderSelector = '.table th';
        await page.waitForSelector(detailsHeaderSelector, { visible: true });

        const scrapedData = await page.evaluate(() => {
            const mainArticle = document.getElementById('mainArticle');
            if (!mainArticle) return null;

            const findValueByHeader = (headerText) => { const allThs = Array.from(mainArticle.querySelectorAll('.table th')); const headerTh = allThs.find(th => th.textContent.trim() === headerText); if (!headerTh) return null; const headerRow = headerTh.parentElement; const dataRow = headerRow.nextElementSibling; if (!dataRow) return null; const headerIndex = Array.from(headerRow.children).indexOf(headerTh); const dataCell = dataRow.children[headerIndex]; return dataCell ? dataCell.textContent.trim() : null; };
            const getAddress = () => { const agentHeader = Array.from(mainArticle.querySelectorAll('h2')).find(h => h.textContent.includes('Registered Agent')); if (!agentHeader) return ''; const agentTable = agentHeader.nextElementSibling; if (!agentTable) return ''; const address1 = agentTable.querySelector('tr:nth-of-type(4) > td:nth-of-type(1)')?.textContent.trim() || ''; const address2 = agentTable.querySelector('tr:nth-of-type(4) > td:nth-of-type(2)')?.textContent.trim() || ''; const cityStateZip = agentTable.querySelector('tr:nth-of-type(6) > td')?.textContent.trim() || ''; return [address1, address2, cityStateZip].filter(Boolean).join(', '); };
            
            const entity_status = findValueByHeader('Status');
            const filingDateText = findValueByHeader('Filing Date');
            const registration_date = filingDateText ? new Date(filingDateText.split(' ')[0]).toLocaleDateString('en-US') : "";
            
            return {
                entity_name: findValueByHeader('Legal Name'),
                registration_date: registration_date,
                entity_type: findValueByHeader('Type'),
                business_identification_number: findValueByHeader('Business No.'),
                entity_status: entity_status,
                statusActive: entity_status ? entity_status.toLowerCase() === 'active' : false,
                address: getAddress()
            };
        });

        fs.writeFileSync(outputFilename, JSON.stringify([scrapedData], null, 2));

    } catch (err) {
        console.error("An error occurred during IA automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `iowa_error_${Date.now()}.png`);
        try {
            if (browser) {
                const pages = await browser.pages();
                if (pages.length > 0 && !pages[0].isClosed()) {
                    await pages[0].screenshot({ path: screenshotPath, fullPage: true });
                    console.log(`✅ Screenshot saved to: ${screenshotPath}`);
                }
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
scrapeIowa(searchTerm, outputFilename);