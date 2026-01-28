/**
 * Accessibility Diagnostic Script - Exact Copy of Crawler Logic
 *
 * Runs the EXACT same checks as the crawler to identify issues.
 */

import { chromium, Page, Browser } from '@playwright/test';

const BASE_URL = 'https://dev.blackbook.reviews';

interface ViewportConfig {
  name: string;
  width: number;
  height: number;
  deviceScaleFactor: number;
  userAgent: string;
}

interface ImageDetails {
  src: string;
  alt: string;
  hasAlt: boolean;
  complete: boolean;
  naturalWidth: number;
  naturalHeight: number;
  className: string;
  parent: string;
}

interface InvisibleTextElement {
  tag: string;
  class: string;
  id: string;
  color: string;
  bgColor: string;
  text: string;
}

interface AccessibilityAnalysisResult {
  issues: string[];
  viewport: string;
}

const VIEWPORTS: ViewportConfig[] = [
  {
    name: 'mobile-portrait',
    width: 390,
    height: 844,
    deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
  },
  {
    name: 'desktop-1080p',
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
  },
];

async function analyzePageExact(page: Page, viewportName: string): Promise<AccessibilityAnalysisResult> {
  const issues: string[] = [];

  // EXACT copy of crawler logic
  const layoutIssues: string[] = await page.evaluate(() => {
    const problems: string[] = [];

    // Check for horizontal overflow
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth) {
      problems.push('Horizontal overflow detected');
    }

    // Check for images without alt text
    const imagesWithoutAlt = Array.from(document.images).filter((img: HTMLImageElement) => !img.alt);
    if (imagesWithoutAlt.length > 0) {
      problems.push(`${imagesWithoutAlt.length} images missing alt text`);
    }

    // Check for broken images
    const brokenImages = Array.from(document.images).filter(
      (img: HTMLImageElement) => !img.complete || img.naturalHeight === 0
    );
    if (brokenImages.length > 0) {
      problems.push(`${brokenImages.length} broken/unloaded images`);
    }

    // Check for invisible text (color too similar to background)
    const elements = document.querySelectorAll('*');
    let invisibleTextCount = 0;
    elements.forEach((el: Element) => {
      const style = window.getComputedStyle(el);
      const color = style.color;
      const bgColor = style.backgroundColor;
      const textContent = (el.textContent || '').trim();

      // Only flag elements that have text content
      if (color && bgColor && color === bgColor && textContent.length > 0) {
        invisibleTextCount++;
      }
    });
    if (invisibleTextCount > 0) {
      problems.push(`${invisibleTextCount} elements with invisible text`);
    }

    // Check for elements outside viewport
    const body = document.body;
    const bodyRect = body.getBoundingClientRect();
    let elementsOutside = 0;

    document.querySelectorAll('*').forEach((el: Element) => {
      const rect = el.getBoundingClientRect();
      if (rect.right > bodyRect.right + 10 || rect.left < bodyRect.left - 10) {
        elementsOutside++;
      }
    });

    if (elementsOutside > 5) {
      problems.push(`${elementsOutside} elements positioned outside viewport`);
    }

    return problems;
  });

  issues.push(...layoutIssues);
  return { issues, viewport: viewportName };
}

async function diagnoseURL(browser: Browser, url: string): Promise<void> {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Diagnosing: ${url}`);
  console.log(`${'='.repeat(80)}\n`);

  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: viewport.deviceScaleFactor,
      userAgent: viewport.userAgent,
    });

    const page = await context.newPage();

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(1000); // Let animations settle

      const result = await analyzePageExact(page, viewport.name);

      console.log(`${viewport.name} (${viewport.width}x${viewport.height}):`);
      if (result.issues.length === 0) {
        console.log('  ✓ No issues found');
      } else {
        result.issues.forEach((issue: string) => console.log(`  - ${issue}`));
      }
      console.log('');

      // Get detailed image info if there are image issues
      if (result.issues.some((i: string) => i.includes('images'))) {
        const imageDetails: ImageDetails[] = await page.evaluate(() => {
          const images = Array.from(document.images);
          return images.map((img: HTMLImageElement): ImageDetails => ({
            src: img.src,
            alt: img.alt,
            hasAlt: img.hasAttribute('alt'),
            complete: img.complete,
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight,
            className: img.className,
            parent: img.parentElement?.className || 'unknown',
          }));
        });

        const missingAlt = imageDetails.filter((img: ImageDetails) => !img.alt);
        const broken = imageDetails.filter((img: ImageDetails) => !img.complete || img.naturalHeight === 0);

        if (missingAlt.length > 0) {
          console.log(`  Missing alt text (${missingAlt.length}):`);
          missingAlt.forEach((img: ImageDetails, i: number) => {
            console.log(
              `    [${i + 1}] ${img.src.substring(0, 80)} (hasAlt: ${img.hasAlt}, class: ${img.className})`
            );
          });
          console.log('');
        }

        if (broken.length > 0) {
          console.log(`  Broken/unloaded (${broken.length}):`);
          broken.forEach((img: ImageDetails, i: number) => {
            console.log(
              `    [${i + 1}] ${img.src.substring(0, 80)} (${img.naturalWidth}x${img.naturalHeight}, complete: ${img.complete})`
            );
          });
          console.log('');
        }
      }

      // Get invisible text details
      if (result.issues.some((i: string) => i.includes('invisible text'))) {
        const invisibleDetails: InvisibleTextElement[] = await page.evaluate(() => {
          const elements = document.querySelectorAll('*');
          const invisible: InvisibleTextElement[] = [];

          elements.forEach((el: Element) => {
            const style = window.getComputedStyle(el);
            const color = style.color;
            const bgColor = style.backgroundColor;

            if (color && bgColor && color === bgColor) {
              invisible.push({
                tag: el.tagName,
                class: el.className,
                id: el.id,
                color,
                bgColor,
                text: (el.textContent || '').trim().substring(0, 50),
              });
            }
          });

          return invisible.slice(0, 10); // First 10 only
        });

        console.log(`  Invisible text elements (showing first 10):`);
        invisibleDetails.forEach((el: InvisibleTextElement, i: number) => {
          console.log(
            `    [${i + 1}] <${el.tag}> class="${el.class}" color=${el.color} text="${el.text}..."`
          );
        });
        console.log('');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      console.error(`  ✗ Error: ${errorMessage}`);
    } finally {
      await context.close();
    }
  }
}

async function main(): Promise<void> {
  const browser = await chromium.launch();

  try {
    // Test key pages
    const urlsToTest = [
      `${BASE_URL}/`,
      `${BASE_URL}/profile/1`,
      `${BASE_URL}/search`,
      `${BASE_URL}/reviews`,
    ];

    for (const url of urlsToTest) {
      await diagnoseURL(browser, url);
    }
  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
    console.error('Main execution error:', errorMessage);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

// Run the diagnostic
main().catch((error: unknown) => {
  const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
  console.error('Fatal error:', errorMessage);
  process.exit(1);
});