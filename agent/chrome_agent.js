/**
 * StudyFrame Chrome Automation Agent
 * Uses Puppeteer to automate Meta AI image generation
 * Communicates with the FastAPI backend via WebSocket
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());

const WS_PORT = process.env.WS_PORT || 8765;
const META_AI_URL = 'https://www.meta.ai';
const IMAGES_OUTPUT_DIR = process.env.IMAGES_OUTPUT_DIR || './agent_images';
const REQUEST_DELAY_MS = 4000;  // Delay between requests to avoid rate limiting

// Ensure output directory exists
if (!fs.existsSync(IMAGES_OUTPUT_DIR)) {
    fs.mkdirSync(IMAGES_OUTPUT_DIR, { recursive: true });
}

let browser = null;
let page = null;

async function launchBrowser() {
    console.log('[Agent] Launching Chrome browser...');
    browser = await puppeteer.launch({
        headless: false,  // Set to true for background mode
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1280,900'
        ],
        defaultViewport: { width: 1280, height: 900 }
    });

    page = await browser.newPage();

    // Set realistic user agent
    await page.setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    );

    // Navigate to Meta AI
    console.log('[Agent] Navigating to Meta AI...');
    await page.goto(META_AI_URL, { waitUntil: 'networkidle2', timeout: 30000 });
    console.log('[Agent] Meta AI loaded. Ready to receive prompts.');
}

async function generateImage(prompt, sceneId, jobId) {
    /**
     * Automates Meta AI to generate an image from a text prompt.
     * Returns the local path of the saved JPEG.
     */
    const outputPath = path.join(
        IMAGES_OUTPUT_DIR,
        `${jobId}_${sceneId}.jpg`
    );

    try {
        console.log(`[Agent] Generating image for ${sceneId}: ${prompt.slice(0, 80)}...`);

        // Find the input box and type the prompt
        const inputSelector = 'div[contenteditable="true"], textarea[placeholder], input[type="text"]';
        await page.waitForSelector(inputSelector, { timeout: 15000 });

        // Clear and type prompt
        await page.click(inputSelector);
        await page.keyboard.down('Control');
        await page.keyboard.press('a');
        await page.keyboard.up('Control');
        await page.keyboard.press('Backspace');

        // Type with human-like delays
        const imagePrompt = `Generate an image: ${prompt}`;
        for (const char of imagePrompt) {
            await page.keyboard.type(char, { delay: Math.random() * 20 + 10 });
        }

        await page.keyboard.press('Enter');

        // Wait for image to appear (Meta AI typically takes 10-30 seconds)
        console.log(`[Agent] Waiting for image generation...`);
        const imageSelector = 'img[src*="scontent"], img[src*="fbcdn"], img.generated-image, .image-result img';

        await page.waitForSelector(imageSelector, { timeout: 90000 });
        await delay(2000);  // Extra wait for full render

        // Get the most recently added image
        const imageUrl = await page.evaluate((sel) => {
            const imgs = document.querySelectorAll(sel);
            const lastImg = imgs[imgs.length - 1];
            return lastImg ? lastImg.src : null;
        }, imageSelector);

        if (!imageUrl) {
            throw new Error('Could not find generated image on page');
        }

        // Download the image using page.goto trick
        const imageBuffer = await page.evaluate(async (url) => {
            const response = await fetch(url);
            const buffer = await response.arrayBuffer();
            return Array.from(new Uint8Array(buffer));
        }, imageUrl);

        fs.writeFileSync(outputPath, Buffer.from(imageBuffer));
        console.log(`[Agent] Image saved: ${outputPath}`);

        // Add delay before next request
        await delay(REQUEST_DELAY_MS);

        return { status: 'success', file_path: outputPath };

    } catch (error) {
        console.error(`[Agent] Image generation failed for ${sceneId}:`, error.message);
        return { status: 'error', error: error.message, file_path: null };
    }
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function startWebSocketServer() {
    /**
     * WebSocket server that listens for image generation requests from the FastAPI backend.
     */
    const wss = new WebSocket.Server({ port: WS_PORT });
    console.log(`[Agent] WebSocket server listening on ws://localhost:${WS_PORT}`);

    wss.on('connection', (ws) => {
        console.log('[Agent] Backend connected via WebSocket');

        ws.on('message', async (data) => {
            let request;
            try {
                request = JSON.parse(data.toString());
            } catch {
                ws.send(JSON.stringify({ status: 'error', error: 'Invalid JSON' }));
                return;
            }

            const { job_id, scene_id, prompt } = request;
            console.log(`[Agent] Received request: job=${job_id}, scene=${scene_id}`);

            const result = await generateImage(prompt, scene_id, job_id);
            ws.send(JSON.stringify(result));
        });

        ws.on('close', () => {
            console.log('[Agent] Backend disconnected');
        });
    });
}

async function main() {
    try {
        await launchBrowser();
        await startWebSocketServer();

        console.log('[Agent] StudyFrame Chrome Agent is ready.');
        console.log('[Agent] Waiting for image generation requests...');

        // Keep process alive
        process.on('SIGINT', async () => {
            console.log('[Agent] Shutting down...');
            if (browser) await browser.close();
            process.exit(0);
        });

    } catch (error) {
        console.error('[Agent] Fatal error:', error);
        if (browser) await browser.close();
        process.exit(1);
    }
}

main();
