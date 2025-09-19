const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const vosk = require('vosk');
const axios =require('axios');

// --- Configuration ---
const VOSK_MODEL_PATH = 'vosk-model-small-en-us-0.15';
const DOWNLOAD_PATH = path.resolve(__dirname, 'downloads');
const AUDIO_MP3_PATH = path.join(DOWNLOAD_PATH, 'captcha_audio.mp3');
const SAMPLE_RATE = 16000;

// --- Helper Functions ---
const transcribeAudio = (filePath) => {
    return new Promise((resolve, reject) => {
        const wavFilePath = path.join(path.dirname(filePath), 'audio.wav');
        // Convert MP3 to WAV format that Vosk can process
        const ffmpegCommand = `ffmpeg -i "${filePath}" -ar ${SAMPLE_RATE} -ac 1 "${wavFilePath}" -y`;

        exec(ffmpegCommand, (error) => {
            if (error) {
                return reject(`FFmpeg error: ${error}`);
            }

            const model = new vosk.Model(VOSK_MODEL_PATH);
            const rec = new vosk.Recognizer({ model: model, sampleRate: SAMPLE_RATE });
            const stream = fs.createReadStream(wavFilePath);

            stream.on('data', (chunk) => {
                rec.acceptWaveform(chunk);
            });

            stream.on('end', () => {
                const result = rec.finalResult();
                rec.free();
                model.free();
                // Clean up the transcribed text
                const transcribedText = result.text.replace('the', '').trim();
                resolve(transcribedText);
            });

            stream.on('error', (err) => {
                reject(`Error reading audio stream: ${err}`);
            });
        });
    });
};

const randomDelay = (min = 500, max = 1500) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));

const showClick = async (page, x, y) => {
    await page.evaluate((x, y) => {
        const dot = document.createElement('div');
        dot.style.position = 'absolute';
        dot.style.left = `${x - 5}px`;
        dot.style.top = `${y - 5}px`;
        dot.style.width = '10px';
        dot.style.height = '10px';
        dot.style.backgroundColor = 'red';
        dot.style.borderRadius = '50%';
        dot.style.zIndex = '999999';
        dot.id = 'debug-click-dot';
        document.body.appendChild(dot);
    }, x, y);
    await new Promise(resolve => setTimeout(resolve, 500));
    await page.evaluate(() => {
        document.getElementById('debug-click-dot')?.remove();
    });
};

const humanlikeClick = async (page, frame, selector) => {
    const element = await frame.waitForSelector(selector, { visible: true });
    const box = await element.boundingBox();
    if (!box) throw new Error(`Could not find a clickable box for selector: ${selector}`);
    const clickX = box.x + box.width / 2 + (Math.random() * 20 - 10);
    const clickY = box.y + box.height / 2 + (Math.random() * 20 - 10);
    await showClick(page, clickX, clickY);
    await page.mouse.move(clickX, clickY, { steps: 10 });
    await randomDelay(200, 500);
    await page.mouse.down();
    await randomDelay(50, 150);
    await page.mouse.up();
    await element.dispose();
};

const humanlikeType = async (frame, selector, text) => {
    const element = await frame.waitForSelector(selector, { visible: true });
    await element.type(text, { delay: Math.random() * 150 + 50 });
    await element.dispose();
};

// --- Main Automation Logic as a Callable Function ---
const scrapeNebraska = async (searchTerm, outputFilename) => {
    if (!fs.existsSync(VOSK_MODEL_PATH)) {
        console.error(`[JS ERROR] Vosk model not found at: ${VOSK_MODEL_PATH}`);
        process.exit(1);
    }
    if (!fs.existsSync(DOWNLOAD_PATH)) {
        fs.mkdirSync(DOWNLOAD_PATH);
    }

    const browser = await puppeteer.launch({
        headless: false, // Set to 'new' for integration, false for debugging
        defaultViewport: null,
        args: ['--start-maximized', '--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    page.setDefaultTimeout(60000);
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36');

    try {
        console.log("Navigating to the Nebraska SOS corporate search page...");
        await page.goto('https://www.nebraska.gov/sos/corp/corpsearch.cgi?nav=search', { waitUntil: 'networkidle2' });

        console.log("Entering search term and preparing for reCAPTCHA...");
        await humanlikeClick(page, page, '#searchform > div:nth-of-type(2) > div > div > div:nth-of-type(1) > label');
        await humanlikeType(page, '#corpname', searchTerm);

        console.log("Solving reCAPTCHA...");
        const anchorFrame = await (await page.$('iframe[src*="api2/anchor"]')).contentFrame();
        await humanlikeClick(page, anchorFrame, '#recaptcha-anchor');

        const bframe = await (await page.$('iframe[src*="api2/bframe"]')).contentFrame();
        await humanlikeClick(page, bframe, '#recaptcha-audio-button');

        const audioLinkSelector = 'a[href*="audio.mp3"]';
        await bframe.waitForSelector(audioLinkSelector, { visible: true });

        console.log("Downloading audio captcha...");
        const audioUrl = await bframe.$eval(audioLinkSelector, a => a.href);
        const response = await axios({ method: 'GET', url: audioUrl, responseType: 'stream' });
        const writer = fs.createWriteStream(AUDIO_MP3_PATH);
        response.data.pipe(writer);
        await new Promise((resolve, reject) => { writer.on('finish', resolve); writer.on('error', reject); });

        console.log("Transcribing audio to text...");
        const solutionText = await transcribeAudio(AUDIO_MP3_PATH);
        if (!solutionText) throw new Error("Transcription failed, no text returned.");
        console.log(`Transcription result: "${solutionText}"`);

        const freshBframe = await (await page.$('iframe[src*="api2/bframe"]')).contentFrame();
        await humanlikeType(freshBframe, '#audio-response', solutionText);
        await humanlikeClick(page, freshBframe, '#recaptcha-verify-button');

        console.log("Submitting search form...");
        await humanlikeClick(page, page, '#submit');
        await page.waitForNavigation({ waitUntil: 'networkidle2' });

        console.log("Scraping initial results from the table...");
        let scrapedData = await page.evaluate((tableSelector) => {
            const results = [];
            const table = document.querySelector(tableSelector);
            if (!table) return [];
            table.querySelectorAll('tbody tr').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length === 5) {
                    results.push({
                        name: cells[0]?.innerText.trim(),
                        accountNumber: cells[1]?.innerText.trim(),
                        type: cells[2]?.innerText.trim(),
                        status: cells[3]?.innerText.trim(),
                        details: {} // Placeholder for details to be added
                    });
                }
            });
            return results;
        }, 'table.table-condensed');

        const numToClick = Math.min(scrapedData.length, 1);
        console.log(`Found ${scrapedData.length} results. Will click details for the first ${numToClick}.`);

        // Loop through the first few results to click details and scrape
        // --- NEW, DIRECT SINGLE-RESULT LOGIC ---

        // Check if there are any results before proceeding
        if (scrapedData.length > 0) {
            console.log(`Processing details for the first result: ${scrapedData[0].name}`);
            const buttonSelector = `table.table-condensed tbody tr:nth-child(1) .btn-default`;

            // Click the "Details" button for the first result
            await page.waitForSelector(buttonSelector, { visible: true });
            await Promise.all([
                page.waitForNavigation({ waitUntil: 'networkidle2' }),
                page.click(buttonSelector)
            ]);

            // Scrape the details from the new page
            const businessData = await page.evaluate(() => {
                const getTextByLabel = (labelText) => {
                    const allLabels = Array.from(document.querySelectorAll('.bold'));
                    const targetLabel = allLabels.find(el => el.textContent.trim() === labelText);
                    if (targetLabel) {
                        const parentContainer = targetLabel.parentElement;
                        if (parentContainer) {
                            const fullText = parentContainer.innerText || "";
                            const labelTextOnly = targetLabel.innerText || "";
                            return fullText.replace(labelTextOnly, '').replace(/\n/g, ' ').replace(/\s\s+/g, ' ').trim();
                        }
                    }
                    return null;
                };

                const status = getTextByLabel('Status');

                return {
                    entity_name: document.querySelector('h4')?.textContent.trim() || null,
                    registration_date: getTextByLabel('Date Filed'),
                    entity_type: getTextByLabel('Entity Type'),
                    business_identification_number: getTextByLabel('SOS Account Number'),
                    entity_status: status,
                    statusActive: status ? !status.toLowerCase().includes('inactive') : false,
                    address: getTextByLabel('Contact')
                };
            });

            console.log(`Scraping complete. Writing data to ${outputFilename}...`);
            fs.writeFileSync(outputFilename, JSON.stringify(businessData, null, 2));
            console.log("File written successfully.");

        } else {
            console.log("No results found on the page to scrape.");
            fs.writeFileSync(outputFilename, JSON.stringify({}, null, 2)); // Write empty object if no results
        }
// --- END OF NEW LOGIC ---

    } catch (err) {
        console.error("An error occurred during NE automation:", err.message);
        fs.writeFileSync(outputFilename, JSON.stringify([], null, 2)); // Write empty array on error
    } finally {
        if (browser) {
            await browser.close();
            console.log("Browser closed.");
        }
    }
};

// --- Script Execution ---
const searchTerm = process.argv[2];
const outputFilename = process.argv[3];

if (!searchTerm || !outputFilename) {
    console.log("Usage: node your_script_name.js <'Search Term'> <output_filename.json>");
    process.exit(1);
}

scrapeNebraska(searchTerm, outputFilename);