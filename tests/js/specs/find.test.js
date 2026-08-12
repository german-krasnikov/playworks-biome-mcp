// window.__luna_mcp.findObjects(query) / findByComponent(componentType)
// Both return newline-joined full paths (relative to scene root, root itself
// excluded), or a literal 'no matches' string when nothing matches.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('findObjects', () => {
  test('finds objects by case-insensitive name substring', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('findObjects', 'cube')).toBe('Cube');
  });

  test('returns "no matches" when nothing matches', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('findObjects', 'zzz')).toBe('no matches');
  });

  test('returns error when no scene', async ({ page }) => {
    const { call } = await injectLunaHelpers(page);
    expect(await call('findObjects', 'cube')).toBe('error: no scene');
  });
});

test.describe('findByComponent', () => {
  test('finds nodes carrying a specific component type', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('findByComponent', 'Camera')).toBe('Cube/Camera');
  });
});
