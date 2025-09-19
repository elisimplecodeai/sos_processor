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
const AUDIO_MP3_PATH = path.join(DOWNLOAD_PATH, 'captcha_audio_sd.mp3');
const SAMPLE_RATE = 16000;

// --- Helper Functions ---
const transcribeAudio = (filePath) => {
    return new Promise((resolve, reject) => {
        const wavFilePath = path.join(path.dirname(filePath), 'audio_sd.wav');
        const ffmpegCommand = `ffmpeg -i "${filePath}" -ar ${SAMPLE_RATE} -ac 1 "${wavFilePath}" -y`;
        exec(ffmpegCommand, (error) => {
            if (error) return reject(`FFmpeg conversion error: ${error}`);
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

const randomDelay = (min = 600, max = 1300) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));
const humanlikeClick = async (page, selector, frame = null) => { const target = frame || page; await target.waitForSelector(selector, { visible: true }); await target.click(selector); };
const humanlikeType = async (page, selector, text) => { await page.waitForSelector(selector, { visible: true }); await page.type(selector, text, { delay: Math.random() * 120 + 50 }); };


// --- Main Automation Logic ---
const scrapeSouthDakota = async (searchTerm, outputFilename) => {
    // --- Setup Directories ---
    if (!fs.existsSync(VOSK_MODEL_PATH)) { console.error(`[JS ERROR] Vosk model not found...`); process.exit(1); }
    if (!fs.existsSync(DOWNLOAD_PATH)) fs.mkdirSync(DOWNLOAD_PATH);
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: false, // Set to 'new' for system integration
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled', '--start-maximized'],
            ignoreDefaultArgs: ['--enable-automation']
        });

        const page = await browser.newPage();
        page.setDefaultTimeout(60000);
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36');
        await page.setViewport({ width: 1920, height: 1080 });

        await page.goto('https://sosenterprise.sd.gov/BusinessServices/Business/FilingSearch.aspx', { waitUntil: 'networkidle2' });
        await humanlikeType(page, '#ctl00_MainContent_txtSearchValue', searchTerm);
        
        const captchaIframeSelector = 'iframe[title="reCAPTCHA"]';
        try {
            await page.waitForSelector(captchaIframeSelector, { visible: true, timeout: 5000 });
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
                await new Promise((resolve, reject) => { response.data.pipe(writer); writer.on('finish', resolve); writer.on('error', reject); });
                const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
                if (!solutionText) throw new Error("Transcription failed.");
                await bframe.type('#audio-response', solutionText, { delay: 110 });
                await humanlikeClick(page, '#recaptcha-verify-button', bframe);
            } catch (error) { /* Instant verification */ }
        } catch (e) { /* No CAPTCHA on initial page */ }

        await randomDelay(1500, 2500);
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            humanlikeClick(page, '#ctl00_MainContent_SearchButton')
        ]);
        
        const firstResultSelector = '#DataTables_Table_0 tbody tr:first-child a';
        await page.waitForSelector(firstResultSelector, { visible: true });
        
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            humanlikeClick(page, firstResultSelector)
        ]);

        try {
            await page.waitForSelector(captchaIframeSelector, { visible: true, timeout: 7000 });
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
                await new Promise((resolve, reject) => { response.data.pipe(writer); writer.on('finish', resolve); writer.on('error', reject); });
                const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
                if (!solutionText) throw new Error("Transcription failed.");
                await bframe.type('#audio-response', solutionText, { delay: 110 });
                await humanlikeClick(page, '#recaptcha-verify-button', bframe);
            } catch (error) { /* Instant verification */ }
            
            await randomDelay(1500, 2500);
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'networkidle2' }),
                humanlikeClick(page, '#ctl00_MainContent_btnViewDetail')
            ]);
        } catch (e) { /* No CAPTCHA on details page */ }

        await page.waitForSelector('.formHeader', { visible: true });

        const businessData = await page.evaluate(() => {
            const status = document.getElementById('ctl00_MainContent_txtStatus')?.textContent.trim() || null;
            return {
                entity_name: document.getElementById('ctl00_MainContent_txtName')?.textContent.trim() || null,
                registration_date: document.getElementById('ctl00_MainContent_txtInitialDate')?.textContent.trim() || null,
                entity_type: document.getElementById('ctl00_MainContent_lblFilingType')?.textContent.trim() || null,
                business_identification_number: document.getElementById('ctl00_MainContent_txtBusinessID')?.textContent.trim() || null,
                entity_status: status,
                statusActive: status ? status.toLowerCase().includes('good standing') : false,
                address: document.getElementById('ctl00_MainContent_txtOfficeAddresss')?.innerHTML.replace(/<br\s*\/?>/gi, ', ').trim() || null
            };
        });
        
        fs.writeFileSync(outputFilename, JSON.stringify([businessData], null, 2));

    } catch (err) {
        console.error("An error occurred during SD automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `south_dakota_error_${Date.now()}.png`);
        try { if (browser) { const pages = await browser.pages(); if (pages.length > 0 && !pages[0].isClosed()) await pages[0].screenshot({ path: screenshotPath, fullPage: true }); console.log(`✅ Screenshot saved to: ${screenshotPath}`); } } catch (e) { console.error(`Failed to take screenshot: ${e.message}`); }
        fs.writeFileSync(outputFilename, JSON.stringify([]));
    } finally {
        if (browser) await browser.close();
        if (fs.existsSync(AUDIO_MP3_PATH)) fs.unlinkSync(AUDIO_MP3_PATH);
    }
};

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeSouthDakota(searchTerm, outputFilename);