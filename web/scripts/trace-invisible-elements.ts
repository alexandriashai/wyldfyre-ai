/**
 * Trace Invisible Elements - Find their parent and location
 */

import { chromium } from '@playwright/test';

interface TracedElement {
  path: string;
  tag: string;
  className: string;
  parentTag: string;
  parentClasses: string;
  grandParentTag: string;
  grandParentClasses: string;
  hasText: boolean;
  text: string;
  innerHTML: string;
}

const BASE_URL = 'https://dev.blackbook.reviews';

async function traceElements(url: string): Promise<void> {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  console.log(`\nAnalyzing: ${url}\n`);

  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);

  const traced = await page.evaluate((): TracedElement[] => {
    const elements = document.querySelectorAll('*');
    const found: TracedElement[] = [];

    elements.forEach((el) => {
      const style = window.getComputedStyle(el);
      const color = style.color;
      const bgColor = style.backgroundColor;

      if (color && bgColor && color === bgColor) {
        // Build a better selector
        const path: string[] = [];
        let current: Element | null = el;

        while (current && current !== document.body) {
          let selector = current.tagName.toLowerCase();

          if (current.id) {
            selector += `#${current.id}`;
            path.unshift(selector);
            break; // ID is unique, stop here
          }

          if (current.className && typeof current.className === 'string') {
            const classes = current.className
              .split(' ')
              .filter((c) => c.trim() && !c.includes(':'));
            if (classes.length > 0) {
              selector += `.${classes[0]}`;
            }
          }

          path.unshift(selector);
          current = current.parentElement;
        }

        const fullPath = path.join(' > ');
        const parent = el.parentElement;
        const parentClasses = parent?.className || '';
        const grandParent = parent?.parentElement;
        const grandParentClasses = grandParent?.className || '';

        found.push({
          path: fullPath,
          tag: el.tagName,
          className: el.className || '(none)',
          parentTag: parent?.tagName || '(none)',
          parentClasses: parentClasses || '(none)',
          grandParentTag: grandParent?.tagName || '(none)',
          grandParentClasses: grandParentClasses || '(none)',
          hasText: (el.textContent || '').trim().length > 0,
          text: (el.textContent || '').trim().substring(0, 50),
          innerHTML: el.innerHTML.substring(0, 200),
        });
      }
    });

    return found;
  });

  console.log(`Found ${traced.length} elements with matching color/bg:\n`);

  traced.forEach((el, i) => {
    console.log(`[${i + 1}] ${el.path}`);
    console.log(`    Parent: <${el.parentTag}> class="${el.parentClasses}"`);
    console.log(`    Grandparent: <${el.grandParentTag}> class="${el.grandParentClasses}"`);
    console.log(`    Has Text: ${el.hasText}`);
    if (el.hasText) {
      console.log(`    Text Content: "${el.text}"`);
    }
    console.log(`    Inner HTML: ${el.innerHTML || '(empty)'}...`);
    console.log('');
  });

  await browser.close();
}

async function main(): Promise<void> {
  const urls = [
    `${BASE_URL}/safety`,
    `${BASE_URL}/providers`, 
    `${BASE_URL}/reviews/submit`,
    `${BASE_URL}/explore`,
  ];

  for (const url of urls) {
    await traceElements(url);
  }
}

main().catch(console.error);