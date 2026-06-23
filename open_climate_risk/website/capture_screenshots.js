const puppeteer = require('puppeteer');
const path = require('path');

const SECTIONS = [
  { name: '01_hero',         y: 0 },
  { name: '02_stats',        y: 900 },
  { name: '03_features',     y: 1087 },
  { name: '04_pipeline',     y: 2058 },
  { name: '05_architecture', y: 2689 },
  { name: '06_data',         y: 3677 },
  { name: '07_hazards',      y: 4361 },
  { name: '08_roadmap',      y: 5325 },
  { name: '09_references',   y: 6280 },
  { name: '10_cta',          y: 6968 },
];

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('http://localhost:8080', { waitUntil: 'networkidle0' });

  // Wait for fonts to load
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 1000));

  // Trigger all fade-in animations
  await page.evaluate(() => {
    document.querySelectorAll('.fade-in').forEach(el => el.classList.add('visible'));
  });

  const dir = path.join(__dirname, 'screenshots');

  for (const section of SECTIONS) {
    await page.evaluate(y => window.scrollTo(0, y), section.y);
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({
      path: path.join(dir, `${section.name}.png`),
      type: 'png',
    });
    console.log(`Captured ${section.name}`);
  }

  // Full page screenshot too
  await page.screenshot({
    path: path.join(dir, 'full_page.png'),
    fullPage: true,
    type: 'png',
  });
  console.log('Captured full_page');

  await browser.close();
  console.log('Done!');
})();
