import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: '**/test-mobile.spec.ts',
  timeout: 60000,
  use: {
    headless: true,
    screenshot: 'on',
  },
  projects: [
    {
      name: 'Mobile Chrome',
      use: {
        ...devices['Pixel 7'],
        channel: 'chromium',
      },
    },
  ],
});
