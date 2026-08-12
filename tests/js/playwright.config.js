// Playwright config for luna_helpers.js browser tests.
// Chromium only, headless, single worker (tests mutate window.__luna_mcp globals).
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './specs',
  timeout: 10000,
  retries: 0,
  workers: 1,
  use: {
    browserName: 'chromium',
    headless: true,
  },
  reporter: [['list'], ['junit', { outputFile: 'test-results/junit.xml' }]],
});
