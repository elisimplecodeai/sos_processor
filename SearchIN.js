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
const AUDIO_MP3_PATH = path.join(DOWNLOAD_PATH, 'captcha_audio_in.mp3');
const SAMPLE_RATE = 16000;

// --- Helper Functions ---
const transcribeAudio = (filePath) => { /* ... full transcribeAudio code ... */ return new Promise((resolve, reject) => { const wavFilePath = path.join(path.dirname(filePath), 'audio_in.wav'); const ffmpegCommand = `ffmpeg -i "${filePath}" -ar ${SAMPLE_RATE} -ac 1 "${wavFilePath}" -y`; exec(ffmpegCommand, (error) => { if (error) return reject(`FFmpeg conversion error: ${error}`); const model = new vosk.Model(VOSK_MODEL_PATH); const rec = new vosk.Recognizer({ model: model, sampleRate: SAMPLE_RATE }); const stream = fs.createReadStream(wavFilePath); stream.on('data', (chunk) => rec.acceptWaveform(chunk)); stream.on('end', () => { const result = rec.finalResult(); rec.free(); model.free(); fs.unlinkSync(wavFilePath); resolve(result.text.trim()); }); stream.on('error', (err) => reject(`Error reading audio stream: ${err}`)); }); }); };
const randomDelay = (min = 600, max = 1300) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));
const humanlikeClick = async (page, selector, frame = null) => { const target = frame || page; await target.waitForSelector(selector, { visible: true }); await target.click(selector); };
const humanlikeType = async (page, selector, text) => { await page.waitForSelector(selector, { visible: true }); await page.type(selector, text, { delay: Math.random() * 120 + 50 }); };

// --- Main Automation Logic as a Callable Function ---
const scrapeIndiana = async (searchTerm, outputFilename) => {
    // --- Setup Directories ---
    if (!fs.existsSync(VOSK_MODEL_PATH)) {
        console.error(`[JS ERROR] Vosk model not found at: ${VOSK_MODEL_PATH}`);
        process.exit(1);
    }
    if (!fs.existsSync(DOWNLOAD_PATH)) fs.mkdirSync(DOWNLOAD_PATH);
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: 'new',
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled', '--start-maximized'],
            ignoreDefaultArgs: ['--enable-automation']
        });

        const page = await browser.newPage();
        page.setDefaultTimeout(60000);
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36');
        await page.setViewport({ width: 1920, height: 1080 });

        await page.goto('https://bsd.sos.in.gov/publicbusinesssearch', { waitUntil: 'networkidle2' });
        await humanlikeType(page, '#txtBusinessName', searchTerm);
        
        const captchaIframeSelector = 'iframe[title="reCAPTCHA"]';
        await page.waitForSelector(captchaIframeSelector, { visible: true });
        const anchorFrame = await (await page.$(captchaIframeSelector)).contentFrame();
        await humanlikeClick(page, '#recaptcha-anchor', anchorFrame);

        try {
            const bframeSelector = 'iframe[src*="api2/bframe"]';
            await page.waitForSelector(bframeSelector, { visible: true, timeout: 5000 });
            const bframe = await (await page.$(bframeSelector)).contentFrame();
            await humanlikeClick(page, '#recaptcha-audio-button', bframe);

            const audioLinkSelector = '.rc-audiochallenge-tdownload-link';
            await bframe.waitForSelector(audioLinkSelector, { visible: true });
            const audioUrl = await bframe.evaluate(sel => document.querySelector(sel).href, audioLinkSelector);

            const response = await axios.get(audioUrl, { responseType: 'stream' });
            const writer = fs.createWriteStream(AUDIO_MP3_PATH);
            response.data.pipe(writer);
            await new Promise((resolve, reject) => { writer.on('finish', resolve); writer.on('error', reject); });

            const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
            if (!solutionText) throw new Error("Transcription failed.");

            await bframe.type('#audio-response', solutionText, { delay: 110 });
            await humanlikeClick(page, '#recaptcha-verify-button', bframe);

        } catch (error) {
            // Instant verification or timeout, proceed.
        }

        await new Promise(resolve => setTimeout(resolve, 2000));
        await humanlikeClick(page, '#btnSearch');
        
        const firstResultSelector = '#grid_businessList tbody tr:first-child a';
        await page.waitForSelector(firstResultSelector, { visible: true });
        
        await humanlikeClick(page, firstResultSelector);

        const detailsPageSelector = 'td.font_grey:first-of-type';
        await page.waitForSelector(detailsPageSelector);

        const businessData = await page.evaluate(() => {
            const getTextByLabel = (labelText) => { const allTds = Array.from(document.querySelectorAll('.data_pannel:first-of-type td')); const labelTd = allTds.find(td => td.textContent.trim() === labelText); if (labelTd && labelTd.nextElementSibling) { const strongTag = labelTd.nextElementSibling.querySelector('strong'); if (strongTag) { return strongTag.textContent.trim(); } } return null; };
            const status = getTextByLabel('Business Status:');
            return {
                entity_name: getTextByLabel('Business Name:'), registration_date: getTextByLabel('Creation Date:'), entity_type: getTextByLabel('Entity Type:'),
                business_identification_number: getTextByLabel('Business ID:'), entity_status: status,
                statusActive: status ? status.toLowerCase().includes('active') : false, address: getTextByLabel('Principal Office Address:')
            };
        });
        
        fs.writeFileSync(outputFilename, JSON.stringify([businessData], null, 2));

    } catch (err) {
        console.error("An error occurred during IN automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `indiana_error_${Date.now()}.png`);
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
        if (browser) await browser.close();
        if (fs.existsSync(AUDIO_MP3_PATH)) fs.unlinkSync(AUDIO_MP3_PATH);
    }
};

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeIndiana(searchTerm, outputFilename);