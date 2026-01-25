import { test, expect, devices } from '@playwright/test';

test.use({ ...devices['Pixel 7'] });

test('mobile terminal shows keyboard buttons', async ({ page }) => {
  // Login
  console.log('Navigating to login...');
  await page.goto('https://wyldfyre.ai/login');
  await page.fill('input[type="email"], input[name="email"]', 'admin@wyldfyre.ai');
  await page.fill('input[type="password"], input[name="password"]', '4638!Singing');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  console.log('Current URL after login:', page.url());
  await page.screenshot({ path: '/tmp/mobile-1-after-login.png' });

  // Navigate to workspace files
  console.log('Navigating to workspace/files...');
  await page.goto('https://wyldfyre.ai/workspace/files');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/tmp/mobile-2-workspace.png' });

  // Check if we need to select a project
  const noProjectText = await page.locator('text=Select a project').isVisible().catch(() => false);
  console.log('No project selected:', noProjectText);

  if (noProjectText) {
    console.log('Need to select a project...');

    // Click hamburger menu to open sidebar
    const hamburger = page.locator('button').filter({ has: page.locator('svg') }).first();
    await hamburger.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: '/tmp/mobile-3-sidebar.png' });

    // Look for project selector or project list
    const projectButton = page.locator('[data-project], button:has-text("Project"), button:has-text("WF")').first();
    if (await projectButton.isVisible().catch(() => false)) {
      console.log('Found project button, clicking...');
      await projectButton.click();
      await page.waitForTimeout(1000);
    }

    // Try to find any project in a dropdown or list
    const projectItem = page.locator('[role="option"], [role="menuitem"], button:has-text("Test")').first();
    if (await projectItem.isVisible().catch(() => false)) {
      console.log('Found project item, clicking...');
      await projectItem.click();
      await page.waitForTimeout(2000);
    }

    await page.screenshot({ path: '/tmp/mobile-4-after-project.png' });
  }

  // Get viewport width
  const viewport = await page.evaluate(() => window.innerWidth);
  console.log('Viewport width:', viewport);

  // Now look for the Terminal tab in bottom nav
  console.log('Looking for Terminal tab...');
  await page.screenshot({ path: '/tmp/mobile-5-looking-for-terminal.png' });

  // Find terminal tab by looking for button with Terminal icon/text
  const terminalTab = page.locator('button:has-text("Terminal")').first();
  const terminalVisible = await terminalTab.isVisible().catch(() => false);
  console.log('Terminal tab visible:', terminalVisible);

  if (terminalVisible) {
    await terminalTab.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/tmp/mobile-6-terminal.png' });

    // Check for keyboard buttons
    console.log('\n=== Checking for mobile keyboard toolbar ===');

    const tabButton = page.locator('button:has-text("Tab")');
    const ctrlCButton = page.locator('button:has-text("Ctrl+C")');
    const escButton = page.locator('button:has-text("Esc")');

    console.log('Tab button visible:', await tabButton.isVisible().catch(() => false));
    console.log('Ctrl+C button visible:', await ctrlCButton.isVisible().catch(() => false));
    console.log('Esc button visible:', await escButton.isVisible().catch(() => false));

    // Take final screenshot
    await page.screenshot({ path: '/tmp/mobile-7-terminal-final.png' });
  } else {
    console.log('Terminal tab still not found');

    // List all buttons
    const buttons = await page.locator('button').all();
    console.log('All buttons on page:', buttons.length);
    for (const btn of buttons) {
      const text = await btn.textContent().catch(() => '');
      if (text) console.log('  - Button:', text.substring(0, 50));
    }
  }
});
