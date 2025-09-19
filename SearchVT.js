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
const AUDIO_MP3_PATH = path.join(DOWNLOAD_PATH, 'captcha_audio_vt.mp3');
const SAMPLE_RATE = 16000;

// --- Helper Functions ---
const transcribeAudio = (filePath) => {
    return new Promise((resolve, reject) => {
        const wavFilePath = path.join(path.dirname(filePath), 'audio_vt.wav');
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
                const transcribedText = result.text.replace('the','').trim();
                resolve(transcribedText);
            });
            stream.on('error', (err) => reject(`Error reading audio stream: ${err}`));
        });
    });
};

const randomDelay = (min = 500, max = 1500) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));
const humanlikeClick = async (page, frame, selector) => { const element = await (frame.waitForSelector ? frame : page).waitForSelector(selector, { visible: true }); const box = await element.boundingBox(); if (!box) throw new Error(`Could not find a clickable box for selector: ${selector}`); const clickX = box.x + box.width / 2 + (Math.random() * 20 - 10); const clickY = box.y + box.height / 2 + (Math.random() * 20 - 10); await page.mouse.move(clickX + (Math.random() * 30 - 15), clickY + (Math.random() * 30 - 15), { steps: 10 }); await randomDelay(100, 300); await page.mouse.move(clickX, clickY, { steps: 10 }); await randomDelay(200, 500); await page.mouse.down(); await randomDelay(50, 150); await page.mouse.up(); };
const humanlikeType = async (page, selector, text) => { const element = await page.waitForSelector(selector, { visible: true }); await element.type(text, { delay: Math.random() * 150 + 50 }); await element.dispose(); };


// --- Main Automation Logic (Single Result) ---
const scrapeVermont = async (searchTerm, outputFilename) => {
    // --- Setup ---
    if (!fs.existsSync(VOSK_MODEL_PATH)) { console.error(`[JS ERROR] Vosk model not found...`); process.exit(1); }
    if (!fs.existsSync(DOWNLOAD_PATH)) fs.mkdirSync(DOWNLOAD_PATH);
    if (!fs.existsSync(ERROR_PATH)) fs.mkdirSync(ERROR_PATH);

    const browser = await puppeteer.launch({ headless: false, defaultViewport: null, args: ['--start-maximized', '--no-sandbox'] });
    const page = await browser.newPage();
    page.setDefaultTimeout(90000);
    await page.setViewport({ width: 1920, height: 1080 });
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');

    try {
        // --- STEP 1: Search and Solve Initial CAPTCHA ---
        await page.goto('https://bizfilings.vermont.gov/business/businesssearch', { waitUntil: 'networkidle2' });
        await humanlikeType(page, '#businessName', searchTerm);
        await humanlikeClick(page, page, 'form button ::-p-text(Search)');
        
        // --- CAPTCHA SOLVER LOGIC ---
        console.log('[CAPTCHA] Checking for CAPTCHA dialog...');
        const dialogSelector = 'app-captcha-dialog';
        try {
            await page.waitForSelector(dialogSelector, { visible: true, timeout: 5000 });
            console.log('[CAPTCHA] Dialog found. Starting solver...');
            const iframeSelector = 'iframe[src*="api2/anchor"]';
            await page.waitForSelector(iframeSelector, { visible: true });
            const anchorFrame = await (await page.$(iframeSelector)).contentFrame();
            await humanlikeClick(page, anchorFrame, '#recaptcha-anchor');
// --- Start Replacement Here ---
            try {
                // --- NEW, LOOPING CAPTCHA LOGIC ---
                const bframeSelector = 'iframe[src*="api2/bframe"]';
                await page.waitForSelector(bframeSelector, { visible: true, timeout: 5000 });

                // Loop up to 3 times to solve multi-step audio CAPTCHAs
                for (let i = 0; i < 3; i++) {
                    const bframe = await (await page.$(bframeSelector)).contentFrame();
                    
                    // On the first attempt, click the audio button.
                    if (i === 0) {
                        await humanlikeClick(page, bframe, '#recaptcha-audio-button');
                    }
                    
                    const audioLinkSelector = 'a[href*="audio.mp3"]';
                    await bframe.waitForSelector(audioLinkSelector, { visible: true });
                    
                    const newPagePromise = new Promise(resolve => browser.once('targetcreated', target => resolve(target.page())));
                    await humanlikeClick(page, bframe, audioLinkSelector);
                    const audioPage = await newPagePromise;
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    const audioUrl = audioPage.url();
                    await audioPage.close();
                    
                    const response = await axios({ method: 'GET', url: audioUrl, responseType: 'stream' });
                    const writer = fs.createWriteStream(AUDIO_MP3_PATH);
                    response.data.pipe(writer);
                    await new Promise((resolve, reject) => { writer.on('finish', resolve); writer.on('error', reject); });
                    
                    const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
                    if (!solutionText) throw new Error("Transcription failed.");
                    console.log(`[CAPTCHA] Attempt ${i + 1}: Transcribed as "${solutionText}"`);
                    
                    const freshBframe = await (await page.$(bframeSelector)).contentFrame();
                    // Use page.evaluate to type because humanlikeType disposes the element handle
                    await freshBframe.evaluate((text) => {
                        const input = document.querySelector('#audio-response');
                        if (input) input.value = text;
                    }, solutionText);
                    await humanlikeClick(page, freshBframe, '#recaptcha-verify-button');
                    await randomDelay(2000, 3000);

                    const multipleSolutionsText = await freshBframe.evaluate(() => {
                        const errorElement = document.querySelector('.rc-audiochallenge-error-message');
                        return errorElement ? errorElement.innerText : null;
                    });

                    if (multipleSolutionsText && multipleSolutionsText.includes('Multiple correct solutions required')) {
                        console.log('[CAPTCHA] Multiple solutions required. Continuing...');
                        try {
                            // Some captchas have a play button for the next sound
                            await freshBframe.click('.rc-audiochallenge-play-button button');
                            await randomDelay(1000, 1500);
                        } catch(e) { /* No play button, just loop */ }
                    } else {
                        console.log('[CAPTCHA] Verification appears successful.');
                        break; 
                    }
                }
                // --- END OF NEW LOGIC ---
            } catch (error) { 
                console.log('[CAPTCHA] No full audio challenge presented or an error occurred in the loop.');
                // console.error(error); // Uncomment for detailed debugging if needed
            }
// --- End Replacement Here ---
            await randomDelay(1000, 2000);
            await humanlikeClick(page, page, 'app-captcha-dialog button ::-p-text(Submit)');
            console.log('[CAPTCHA] Solved and submitted.');
        } catch (e) {
            console.log('[CAPTCHA] No dialog found. Proceeding normally.');
        }

        // --- STEP 2: Find and Click the First Result ---
        await page.waitForSelector('table.mat-mdc-table', { visible: true });
        const rowCount = await page.$$eval('table.mat-mdc-table tbody tr', rows => rows.length);
        if (rowCount === 0) {
            console.log("No results found on the page.");
            fs.writeFileSync(outputFilename, JSON.stringify([]));
            await browser.close();
            return;
        }

        console.log("--- Processing the first result ---");
        const firstResultSelector = 'table.mat-mdc-table tbody tr:first-child a';
        
        // --- THIS IS THE ROBUST NAVIGATION FIX ---
        // Start waiting for navigation BEFORE the click to avoid a race condition.
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle2' }),
            humanlikeClick(page, page, firstResultSelector)
        ]);
        // --- END OF FIX ---
        
        // --- STEP 3: Scrape the Details Page ---
        await page.waitForSelector('p ::-p-text(Record Number)', { visible: true });
        
        const businessData = await page.evaluate(() => {
            const getTextByLabel = (label) => { const allParagraphs = Array.from(document.querySelectorAll('div.readonly p:first-child')); const labelElement = allParagraphs.find(p => p.textContent && p.textContent.trim() === label); if (labelElement) { const valueElement = labelElement.nextElementSibling; return valueElement ? valueElement.textContent.trim() : null; } return null; };
            const status = getTextByLabel('Business Status');
            return { entity_name: getTextByLabel('Business Name'), registration_date: getTextByLabel('Date of Formation'), entity_type: getTextByLabel('Business Type'), business_identification_number: getTextByLabel('Record Number'), entity_status: status, statusActive: status ? status.toLowerCase().includes('active') : false, address: getTextByLabel('Designated Office (Street Address)') };
        });
        
        // --- STEP 4: Save the single result ---
        fs.writeFileSync(outputFilename, JSON.stringify([businessData], null, 2));

    } catch (err) {
        console.error("An error occurred during VT automation:", err.message);
        const screenshotPath = path.join(ERROR_PATH, `vermont_error_${Date.now()}.png`);
        try { if (page && !page.isClosed()) await page.screenshot({ path: screenshotPath, fullPage: true }); console.log(`✅ Screenshot saved to: ${screenshotPath}`); } catch (e) { console.error(`Failed to take screenshot: ${e.message}`); }
        fs.writeFileSync(outputFilename, JSON.stringify([]));
    } finally {
        if (browser) await browser.close();
        if (fs.existsSync(AUDIO_MP3_PATH)) fs.unlinkSync(AUDIO_MP3_PATH);
        const wavPath = path.join(DOWNLOAD_PATH, 'audio_vt.wav');
        if (fs.existsSync(wavPath)) fs.unlinkSync(wavPath);
    }
};

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];
scrapeVermont(searchTerm, outputFilename);