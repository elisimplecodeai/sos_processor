// --- Dependencies ---
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const vosk = require('vosk');
const axios = require('axios');

// --- Configuration ---
const VOSK_MODEL_PATH = 'vosk-model-small-en-us-0.15'; 
const DOWNLOAD_PATH = path.resolve(__dirname, 'downloads');
const AUDIO_MP3_PATH = path.join(DOWNLOAD_PATH, 'captcha_audio_md.mp3');
const SAMPLE_RATE = 16000;
const ERROR_PATH = path.resolve(__dirname, 'errors');

// --- Helper Functions ---
const randomDelay = (min = 500, max = 1200) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));

const transcribeAudio = (filePath) => {
    return new Promise((resolve, reject) => {
        const wavFilePath = path.join(path.dirname(filePath), 'audio_md.wav');
        const ffmpegCommand = `ffmpeg -i "${filePath}" -ar ${SAMPLE_RATE} -ac 1 "${wavFilePath}" -y`;
        exec(ffmpegCommand, (error) => {
            if (error) return reject(`FFmpeg error: ${error}`);
            const model = new vosk.Model(VOSK_MODEL_PATH);
            const rec = new vosk.Recognizer({ model: model, sampleRate: SAMPLE_RATE });
            const stream = fs.createReadStream(wavFilePath);
            stream.on('data', (chunk) => rec.acceptWaveform(chunk));
            stream.on('end', () => {
                const result = rec.finalResult();
                rec.free(); model.free();
                fs.unlinkSync(wavFilePath);
                resolve(result.text.trim());
            });
            stream.on('error', (err) => reject(`Error reading audio stream: ${err}`));
        });
    });
};


// --- Main Automation Logic ---
const scrapeMaryland = async (searchTerm, outputFilename) => {
    if (!fs.existsSync(VOSK_MODEL_PATH)) {
        console.error(`[JS ERROR] Vosk model not found at path: ${VOSK_MODEL_PATH}`);
        fs.writeFileSync(outputFilename, JSON.stringify([]));
        return;
    }
    if (!fs.existsSync(DOWNLOAD_PATH)) fs.mkdirSync(DOWNLOAD_PATH);
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    let browser;
    // --- FIX: Declare page outside the try block for error handling ---
    let page;
    try {
        browser = await puppeteer.launch({
            headless: false,
            args: [
                '--no-sandbox', '--disable-setuid-sandbox', '--disable-infobars', '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled', '--start-maximized',
            ],
            ignoreDefaultArgs: ['--enable-automation']
        });

        page = await browser.newPage();
        page.setDefaultTimeout(60000);
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36');
        await page.setViewport({ width: 1920, height: 1080 });

        console.log("Navigating to the Business Entity Search page...");
        await page.goto('https://egov.maryland.gov/BusinessExpress/EntitySearch', { waitUntil: 'networkidle2' });
        await randomDelay();

        console.log(`Typing "${searchTerm}" into the search field...`);
        await page.type('#BusinessName', searchTerm, { delay: 100 });
        await randomDelay(300, 700);
        
        console.log("Clicking search...");
        await page.click('#searchBus1');

        console.log("Watching for page outcome (CAPTCHA or results)...");
        const captchaIframeSelector = 'iframe[title="reCAPTCHA"]';
        const resultsTableSelector = '#newTblBusSearch';
        const noResultsSelector = 'div.p-3';

        await page.waitForSelector(`${captchaIframeSelector}, ${resultsTableSelector}, ${noResultsSelector}`);

        if (await page.$(noResultsSelector)) {
            const noResultsText = await page.$eval(noResultsSelector, el => el.innerText);
            if (noResultsText.includes('No business filings were found')) {
                console.log("Search returned no results. Script finishing successfully.");
                fs.writeFileSync(outputFilename, JSON.stringify([]));
                await browser.close();
                return;
            }
        }
        
        if (await page.$(captchaIframeSelector)) {
            console.log("CAPTCHA detected. Starting solver...");
            
            // --- *** THE FIX IS HERE *** ---
            // Step 1: Get the iframe handle and its content frame.
            const anchorFrameHandle = await page.waitForSelector('iframe[src*="api2/anchor"]');
            const anchorFrame = await anchorFrameHandle.contentFrame();

            // Step 2: Explicitly wait for the checkbox to be visible *within that frame*.
            console.log("Waiting for CAPTCHA checkbox to render inside its iframe...");
            await anchorFrame.waitForSelector('#recaptcha-anchor', { visible: true, timeout: 10000 });
            
            // Step 3: Use the frame's own click method. This is the crucial part.
            console.log("Clicking CAPTCHA checkbox...");
            await anchorFrame.click('#recaptcha-anchor');
            await randomDelay(2000, 3000); // Wait for challenge to appear
            // --- *** END OF FIX *** ---

            try {
                const bframeHandle = await page.waitForSelector('iframe[src*="api2/bframe"]', { visible: true, timeout: 5000 });
                const bframe = await bframeHandle.contentFrame();
                
                await bframe.waitForSelector('#recaptcha-audio-button', { visible: true });
                await bframe.click('#recaptcha-audio-button');
                await randomDelay();

                const audioLinkSelector = '.rc-audiochallenge-tdownload-link';
                await bframe.waitForSelector(audioLinkSelector, { visible: true });
                
                const audioUrl = await bframe.$eval(audioLinkSelector, el => el.href);
                const response = await axios.get(audioUrl, { responseType: 'stream' });
                const writer = fs.createWriteStream(AUDIO_MP3_PATH);
                response.data.pipe(writer);
                await new Promise((resolve, reject) => { writer.on('finish', resolve); writer.on('error', reject); });
                
                const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
                if (!solutionText) throw new Error("Transcription failed.");
                console.log(`Transcription result: "${solutionText}"`);
                
                await bframe.type('#audio-response', solutionText, { delay: 100 });
                await randomDelay();
                
                await bframe.waitForSelector('#recaptcha-verify-button', { visible: true });
                await bframe.click('#recaptcha-verify-button');

                console.log("✅ CAPTCHA solved. Waiting for results...");
            } catch (e) {
                console.log("Instant verification or no challenge needed. Proceeding...");
            }
        } else {
            console.log("No CAPTCHA detected. Proceeding directly to results.");
        }
        
        await page.waitForSelector(resultsTableSelector, { visible: true, timeout: 30000 });
        console.log("Search results page loaded.");
        
        await randomDelay();
        const firstResultSelector = '#newTblBusSearch > tbody > tr:nth-child(1) > td:nth-child(2) > a';
        
        await page.waitForSelector(firstResultSelector, { visible: true, timeout: 10000 });
        const newPagePromise = browser.waitForTarget(target => target.opener() === page.target()).then(target => target.page());
        await page.click(firstResultSelector);
        const newPage = await newPagePromise;
        if (!newPage) { throw new Error("Could not find the new page/tab."); }
        
        await newPage.setDefaultTimeout(60000);
        await newPage.setViewport({ width: 1920, height: 1080 });
        
        const detailsContainerSelector = '.fp_formItemGroup';
        await newPage.waitForSelector(`${detailsContainerSelector} .fp_formItemLabel strong`, { visible: true });

        const businessData = await newPage.evaluate((containerSelector) => {
            const getTextByLabel = (label) => { const allLabels = Array.from(document.querySelectorAll(`${containerSelector} .fp_formItemLabel strong`)); const targetLabel = allLabels.find(l => l.textContent.trim() === label); if (targetLabel) { const dataElement = targetLabel.closest('.fp_formItem').querySelector('.fp_formItemData'); return dataElement ? dataElement.innerText.trim().replace(/\s\s+/g, ' ') : null; } return null; };
            const entity_status = getTextByLabel('Status:');
            const activeKeywords = ['ACTIVE', 'IN GOOD STANDING', 'INCORPORATED'];
            const statusActive = entity_status ? activeKeywords.some(keyword => entity_status.toUpperCase().includes(keyword)) : false;
            return {
                entity_name: getTextByLabel('Business Name:'),
                registration_date: getTextByLabel('Date of Formation/ Registration:'),
                entity_type: getTextByLabel('Business Type:'),
                business_identification_number: getTextByLabel('Department ID Number:'),
                entity_status: entity_status,
                statusActive: statusActive,
                address: getTextByLabel('Principal Office:')
            };
        }, detailsContainerSelector);

        await newPage.close();
        
        console.log("Scraping complete. Writing data to file.");
        fs.writeFileSync(outputFilename, JSON.stringify([businessData], null, 2));

    } catch (err) {
        const timestamp = new Date().getTime();
        const screenshotPath = path.join(ERROR_PATH, `error-maryland-${timestamp}.png`);
        console.error(`An error occurred: ${err.message}\n${err.stack}`);
        console.log(`Saving screenshot to ${screenshotPath}`);
        
        if(page && !page.isClosed()) {
            await page.screenshot({ path: screenshotPath, fullPage: true });
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

if (!searchTerm || !outputFilename) {
    console.error("Error: Missing searchTerm or outputFilename arguments.");
    if(outputFilename) fs.writeFileSync(outputFilename, JSON.stringify([]));
    process.exit(1);
}
console.log(`Starting Maryland scrape for term: "${searchTerm}"`);
scrapeMaryland(searchTerm, outputFilename);