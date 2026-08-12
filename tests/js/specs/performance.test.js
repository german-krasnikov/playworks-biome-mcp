// window.__luna_mcp.getPerformanceMetrics()
// Every section is individually try/catch-wrapped, so missing pieces of the
// runtime (no pc.Application, no performance.memory, ...) are silently
// omitted rather than causing a failure -- 'PERFORMANCE:' + whatever the
// mock environment can supply is always returned.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('getPerformanceMetrics', () => {
  test('returns fps and timing data from UnityEngine.Time', async ({ page }) => {
    // createMockGlobals() default: UnityEngine.Time = { deltaTime: 0.016, timeScale: 1 }.
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getPerformanceMetrics');
    expect(result).toContain('PERFORMANCE:');
    expect(result).toContain('fps: 63 (GOOD)');
    expect(result).toContain('deltaTime: 16.0ms');
    expect(result).toContain('timeScale: 1');
  });

  test('handles a missing pc.Application/pc.app.stats gracefully (no drawCalls line)', async ({ page }) => {
    // The mock `pc` object only ever exposes `pc.app` (an instance), never
    // the legacy `pc.Application.getApplication()` static accessor that
    // getPerformanceMetrics reads drawCalls/materialSwitches from -- so that
    // whole section is always absent with our mocks, and must not throw.
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getPerformanceMetrics');
    expect(result).toContain('PERFORMANCE:');
    expect(result).not.toContain('drawCalls:');
  });

  test('includes memory info when performance.memory is available', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    await page.evaluate(() => {
      Object.defineProperty(performance, 'memory', {
        value: { usedJSHeapSize: 10 * 1048576, totalJSHeapSize: 20 * 1048576, jsHeapSizeLimit: 100 * 1048576 },
        configurable: true
      });
    });
    const result = await call('getPerformanceMetrics');
    expect(result).toContain('heap: 10.0MB / 20.0MB (limit 100MB)');
  });
});
