import { chromium } from 'playwright';

interface ElementCounts {
  metaInHead: number;
  linksInHead: number;
  scriptsInHead: number;
  metaAfterHead: number;
  linksAfterHead: number;
  scriptsAfterHead: number;
  metaInBody: number;
  linksInBody: number;
}

async function checkPagesHTML(): Promise<void> {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const pages: string[] = [
    'https://dev.blackbook.reviews/safety',
    'https://dev.blackbook.reviews/providers',
    'https://dev.blackbook.reviews/reviews/submit',
    'https://dev.blackbook.reviews/explore',
    'https://dev.blackbook.reviews/policies/dmca',
  ];

  for (const url of pages) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`Checking: ${url}`);
    console.log('='.repeat(80));

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

      const html = await page.content();

      const headStart = html.indexOf('<head>');
      const headEnd = html.indexOf('</head>');
      const bodyStart = html.indexOf('<body');

      if (headStart === -1 || headEnd === -1 || bodyStart === -1) {
        console.log('❌ CRITICAL: Missing basic HTML structure tags');
        continue;
      }

      // Extract sections
      const headContent = html.substring(headStart, headEnd + 7);
      const afterHead = html.substring(headEnd + 7, bodyStart);
      const bodyContent = html.substring(bodyStart, html.indexOf('</body>') + 7);

      // Count elements
      const counts: ElementCounts = {
        metaInHead: (headContent.match(/<meta/g) || []).length,
        linksInHead: (headContent.match(/<link/g) || []).length,
        scriptsInHead: (headContent.match(/<script/g) || []).length,
        metaAfterHead: (afterHead.match(/<meta/g) || []).length,
        linksAfterHead: (afterHead.match(/<link/g) || []).length,
        scriptsAfterHead: (afterHead.match(/<script/g) || []).length,
        metaInBody: (bodyContent.match(/<meta/g) || []).length,
        linksInBody: (bodyContent.match(/<link/g) || []).length,
      };

      console.log('\n📊 Element Distribution:');
      console.log(`  In <head>:`);
      console.log(`    Meta tags: ${counts.metaInHead}`);
      console.log(`    Link tags: ${counts.linksInHead}`);
      console.log(`    Scripts: ${counts.scriptsInHead}`);

      console.log(`  Between </head> and <body>:`);
      console.log(`    Meta tags: ${counts.metaAfterHead} ${counts.metaAfterHead > 0 ? '❌ PROBLEM!' : '✓'}`);
      console.log(`    Link tags: ${counts.linksAfterHead} ${counts.linksAfterHead > 0 ? '❌ PROBLEM!' : '✓'}`);
      console.log(`    Scripts: ${counts.scriptsAfterHead} ${counts.scriptsAfterHead > 0 ? '❌ PROBLEM!' : '✓'}`);

      console.log(`  In <body>:`);
      console.log(`    Meta tags: ${counts.metaInBody} ${counts.metaInBody > 0 ? '❌ PROBLEM!' : '✓'}`);
      console.log(`    Link tags (stylesheets): ${counts.linksInBody} ${counts.linksInBody > 0 ? '❌ PROBLEM!' : '✓'}`);

      // Show problematic content if found
      if (counts.metaAfterHead > 0 || counts.linksAfterHead > 0 || counts.scriptsAfterHead > 0) {
        console.log('\n🔍 Content between </head> and <body>:');
        console.log(afterHead.substring(0, 1000));
      }

      if (counts.metaInBody > 0 || counts.linksInBody > 0) {
        console.log('\n🔍 Meta/Link tags found in body:');
        const bodyMetaMatches = bodyContent.match(/<meta[^>]*>/g) || [];
        const bodyLinkMatches = bodyContent.match(/<link[^>]*>/g) || [];
        [...bodyMetaMatches, ...bodyLinkMatches].forEach(match => {
          console.log(`    ${match}`);
        });
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.log(`❌ ERROR loading ${url}: ${errorMessage}`);
    }
  }

  await browser.close();
}

checkPagesHTML().catch(console.error);