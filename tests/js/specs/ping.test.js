// window.__luna_mcp.ping() -- trivial connectivity probe.
// Real behavior (js/luna_helpers.js): returns 'pong' when getScene() finds a
// scene, 'no scene' otherwise. No stats are included.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('ping', () => {
  test('returns "pong" when a scene exists', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('ping')).toBe('pong');
  });

  test('returns "no scene" when no scene is set', async ({ page }) => {
    const { call } = await injectLunaHelpers(page);
    expect(await call('ping')).toBe('no scene');
  });
});
