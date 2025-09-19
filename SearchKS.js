const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const vosk = require('vosk');
const axios = require('axios');

// --- Configuration ---
const VOSK_MODEL_PATH = path.join(__dirname, 'vosk-model-small-en-us-0.15');
const DOWNLOAD_PATH = path.resolve(__dirname, 'downloads');
const ERROR_PATH = path.resolve(__dirname, 'errors');
const AUDIO_MP3_PATH = path.join(DOWNLOAD_PATH, 'captcha_audio_ks.mp3');
const SAMPLE_RATE = 16000;

// --- Helper Functions ---
const transcribeAudio = (filePath) => { /* ... full transcribeAudio code ... */ return new Promise((resolve, reject) => { const wavFilePath = path.join(path.dirname(filePath), 'audio_ks.wav'); const ffmpegCommand = `ffmpeg -i "${filePath}" -ar ${SAMPLE_RATE} -ac 1 "${wavFilePath}" -y`; exec(ffmpegCommand, (error) => { if (error) return reject(`FFmpeg conversion error: ${error}`); const model = new vosk.Model(VOSK_MODEL_PATH); const rec = new vosk.Recognizer({ model: model, sampleRate: SAMPLE_RATE }); const stream = fs.createReadStream(wavFilePath); stream.on('data', (chunk) => rec.acceptWaveform(chunk)); stream.on('end', () => { const result = rec.finalResult(); rec.free(); model.free(); fs.unlinkSync(wavFilePath); resolve(result.text.trim()); }); stream.on('error', (err) => reject(`Error reading audio stream: ${err}`)); }); }); };
const randomDelay = (min = 600, max = 1800) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));

// --- Main Automation Logic as a Callable Function ---
const scrapeKansas = async (searchTerm, outputFilename) => {
    // --- Setup Directories ---
    if (!fs.existsSync(VOSK_MODEL_PATH)) {
        console.error(`[JS ERROR] Vosk model not found at: ${VOSK_MODEL_PATH}`);
        process.exit(1);
    }
    if (!fs.existsSync(DOWNLOAD_PATH)) fs.mkdirSync(DOWNLOAD_PATH);
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: null,
        args: ['--start-maximized', '--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);

    try {
        await page.goto('https://www.sos.ks.gov/eforms/BusinessEntity/Search.aspx', { waitUntil: 'networkidle2' });
        await page.type('#MainContent_txtSearchEntityName', searchTerm, { delay: 150 });
        
        const iframeSelector = 'iframe[src*="api2/anchor"]';
        await page.waitForSelector(iframeSelector, { visible: true });
        const anchorFrame = await (await page.$(iframeSelector)).contentFrame();
        await anchorFrame.click('#recaptcha-anchor');
        
        const bframeSelector = 'iframe[src*="api2/bframe"]';
        await page.waitForSelector(bframeSelector, { visible: true });
        const bframe = await (await page.$(bframeSelector)).contentFrame();
        await bframe.click('#recaptcha-audio-button');
        
        const audioLinkSelector = '.rc-audiochallenge-tdownload-link';
        await bframe.waitForSelector(audioLinkSelector, { visible: true });
        const audioUrl = await bframe.evaluate((sel) => document.querySelector(sel).href, audioLinkSelector);
        
        const response = await axios({ method: 'GET', url: audioUrl, responseType: 'stream' });
        const writer = fs.createWriteStream(AUDIO_MP3_PATH);
        response.data.pipe(writer);
        await new Promise((resolve, reject) => { writer.on('finish', resolve); writer.on('error', reject); });
        
        const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
        if (!solutionText) throw new Error("Transcription failed to produce text.");
        
        await bframe.type('#audio-response', solutionText, { delay: 100 });
        await bframe.click('#recaptcha-verify-button');
        
        await randomDelay(2000, 3000);
        
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click('#MainContent_btnSearchEntity')
        ]);

        const firstResultSelector = '#MainContent_gvSearchResults_btnAddEntity_0';
        await page.waitForSelector(firstResultSelector, { visible: true });
        
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            page.click(firstResultSelector)
        ]);
        
        await page.waitForSelector('#MainContent_pnlEntityData', { visible: true });

        const businessData = await page.evaluate(() => {
            const getTextById = (id) => { const element = document.getElementById(id); return element ? element.textContent.trim() : null; };
            const status = getTextById('MainContent_lblEntityStatus');
            const data = { entity_name: getTextById('MainContent_lblEntityName'), registration_date: getTextById('MainContent_lblFormationDate'), entity_type: getTextById('MainContent_lblEntityType'), business_identification_number: getTextById('MainContent_lblEntityID'), entity_status: status, statusActive: status ? (status.toLowerCase().includes('active') || status.toLowerCase().includes('good standing')) : false };
            const poAddress = getTextById('MainContent_lblPOAddress'); const poCity = getTextById('MainContent_lblPOAddressCity'); const poState = getTextById('MainContent_lblPOAddressState'); const poZip = getTextById('MainContent_lblPOAddressZip');
            if (poAddress && poCity && poState && poZip) { data.address = `${poAddress}, ${poCity}, ${poState} ${poZip}`; } else { data.address = null; }
            return data;
        });

        fs.writeFileSync(outputFilename, JSON.stringify([businessData], null, 2));

    } catch (err) {
        console.error("An error occurred during KS automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `kansas_error_${Date.now()}.png`);
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
        if (browser) await browser.close();
        if (fs.existsSync(AUDIO_MP3_PATH)) fs.unlinkSync(AUDIO_MP3_PATH);
    }
};

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeKansas(searchTerm, outputFilename);