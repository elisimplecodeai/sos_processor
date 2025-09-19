const puppeteer = require('puppeteer'); // v23.0.0 or later

// Get the entity name from the command-line arguments
// process.argv[2] is the first argument passed to the script
const entityNameToSearch = process.argv[2];

if (!entityNameToSearch) {
    console.error(JSON.stringify({ error: "Entity name not provided to the Node.js script." }));
    process.exit(1);
}

(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    const timeout = 30000;
    page.setDefaultTimeout(timeout);

    {
        const targetPage = page;
        await targetPage.setViewport({
            width: 1916,
            height: 927
        })
    }
    {
        const targetPage = page;
        await targetPage.goto('https://apps3.web.maine.gov/nei-sos-icrs/ICRS?MainPage=x');
    }
    {
        const targetPage = page;
        await puppeteer.Locator.race([
            targetPage.locator('::-p-aria(Keyword from name to be searched: [role=\\"cell\\"]) >>>> ::-p-aria([role=\\"textbox\\"])'),
            targetPage.locator('tr:nth-of-type(4) input')
        ])
            .setTimeout(timeout)
            .click();
    }
    {
        const targetPage = page;
        await puppeteer.Locator.race([
            targetPage.locator('::-p-aria(Keyword from name to be searched: [role=\\"cell\\"]) >>>> ::-p-aria([role=\\"textbox\\"])'),
            targetPage.locator('tr:nth-of-type(4) input')
        ])
            .setTimeout(timeout)
            .fill(entityNameToSearch); // Use the variable passed from Python
    }
    {
        const targetPage = page;
        const promises = [];
        const startWaitingForEvents = () => {
            promises.push(targetPage.waitForNavigation());
        }
        await puppeteer.Locator.race([
            targetPage.locator('::-p-aria(Click Here to Search[role=\\"button\\"])'),
            targetPage.locator('button')
        ])
            .setTimeout(timeout)
            .on('action', () => startWaitingForEvents())
            .click();
        await Promise.all(promises);
    }
    {
        const targetPage = page;
        const promises = [];
        const startWaitingForEvents = () => {
            promises.push(targetPage.waitForNavigation());
        }
        await puppeteer.Locator.race([
            targetPage.locator('tr:nth-of-type(6) a'),
            targetPage.locator('::-p-xpath(/html/body/form/center/table/tbody/tr[3]/td/table[1]/tbody/tr[6]/td[4]/font/a)')
        ])
            .setTimeout(timeout)
            .on('action', () => startWaitingForEvents())
            .click();
        await Promise.all(promises);
    }

    const scrapedData = await page.evaluate(() => {
        // Helper function to safely query selectors
        const safeQuery = (selector) => {
            const element = document.querySelector(selector);
            return element ? element.innerText.trim() : '';
        };

        const entity_name = safeQuery('body > center > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(5) > td:nth-child(1)');
        const registration_date_raw = safeQuery('body > center > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(7) > td:nth-child(1)');
        
        let registration_date = '';
        if (registration_date_raw) {
            const [month, day, year] = registration_date_raw.split('/');
            registration_date = `${month.padStart(2, '0')}/${day.padStart(2, '0')}/${year}`;
        }
        
        const entity_type = safeQuery('body > center > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(5) > td:nth-child(3)');
        const business_identification_number = safeQuery('body > center > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(5) > td:nth-child(2)');
        const entity_status = safeQuery('body > center > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(5) > td:nth-child(4)');
        const statusActive = entity_status.toLowerCase().includes('active');
        const address = safeQuery('body > center > table > tbody > tr:nth-child(3) > td > table > tbody > tr:nth-child(11) > td:nth-child(1)').replace(/\n/g, ' ');

        return {
            entity_name,
            registration_date,
            entity_type,
            business_identification_number,
            entity_status,
            statusActive,
            address,
        };
    });

    // Output the final data as a JSON string to standard output
    console.log(JSON.stringify(scrapedData, null, 2));

    await browser.close();

})().catch(err => {
    // Output errors as a JSON string to standard error
    console.error(JSON.stringify({ error: err.message }));
    process.exit(1);
});