// window.__luna_mcp.hasDebugger() -- reports whether pc.Debugger is present.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('hasDebugger', () => {
  test('returns "yes" when pc.Debugger exists', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      window.__mocks.createBasicScene();
      window.pc.Debugger = {};
    });
    expect(await call('hasDebugger')).toBe('yes');
  });

  test('returns "no" when pc.Debugger is null', async ({ page }) => {
    // createMockGlobals() defaults pc.Debugger to null.
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('hasDebugger')).toBe('no');
  });
});
