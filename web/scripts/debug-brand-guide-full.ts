import { chromium } from 'playwright';

interface ErrorInfo {
  success: boolean;
  status?: number;
  error?: string;
}

interface AlpineStatus {
  hasAlpine: boolean;
  hasLocationCascading: boolean;
}

async function debug(): Promise<void> {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Capture ALL console messages
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    console.log(`[${type.toUpperCase()}] ${text}`);
  });

  page.on('pageerror', (error: Error) => {
    console.error(`[PAGE ERROR] ${error.message}`);
  });

  console.log('Loading brand guide...\n');
  await page.goto('https://dev.blackbook.reviews/brand-guide', {
    waitUntil: 'networkidle',
    timeout: 30000,
  });

  await page.waitForTimeout(3000);

  // Check which scripts are loaded
  const scripts = await page.evaluate((): string[] => {
    const scriptTags = Array.from(document.querySelectorAll('script[src]'));
    return scriptTags.map(s => (s as HTMLScriptElement).src);
  });

  console.log('\n=== Loaded Scripts ===');
  scripts.forEach(src => {
    if (src.includes('brand-guide') || src.includes('location') || src.includes('cascading')) {
      console.log(`✓ ${src}`);
    }
  });

  // Check if Alpine is initialized
  const alpineStatus = await page.evaluate((): AlpineStatus => {
    const globalWindow = window as Window & typeof globalThis & {
      Alpine?: unknown;
      initLocationCascading?: unknown;
    };
    return {
      hasAlpine: typeof globalWindow.Alpine !== 'undefined',
      hasLocationCascading: typeof globalWindow.initLocationCascading !== 'undefined',
    };
  });

  console.log('\n=== JavaScript Status ===');
  console.log(`Alpine.js loaded: ${alpineStatus.hasAlpine}`);
  console.log(`Location cascading available: ${alpineStatus.hasLocationCascading}`);

  // Try to manually trigger the cascading init
  const manualInit = await page.evaluate(async (): Promise<ErrorInfo> => {
    try {
      // Check if countries.min.json is accessible
      const response = await fetch('/assets/countries.min.json');
      if (response.ok) {
        return {success: true, status: response.status};
      }
      return {success: false, status: response.status};
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return {success: false, error: errorMessage};
    }
  });

  console.log('\n=== Countries Data ===');
  console.log(`countries.min.json accessible: ${manualInit.success}`);
  if (!manualInit.success) {
    console.log(`Status/Error: ${manualInit.status || manualInit.error}`);
  }

  // Check dropdown options
  const countryOptions = await page.locator('[data-location-country] option').count();
  console.log(`\nCountry dropdown options: ${countryOptions}`);

  await browser.close();
}

debug().catch(console.error);