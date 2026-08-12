// window.__luna_mcp.getTransform(path)
// Returns 'position: (x, y, z)\nrotation: (x, y, z)\nscale: (x, y, z)' using
// the node's OWN _localPosition/_localEulerAngles/_localScale -- always local
// values, never composed with a parent's transform (getTransform does not
// walk _parent at all).
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('getTransform', () => {
  test('returns position/rotation/scale for a valid path', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getTransform', 'Cube');
    expect(result).toBe(
      'position: (0.0, 0.0, 0.0)\n' +
      'rotation: (0.0, 0.0, 0.0)\n' +
      'scale: (1.0, 1.0, 1.0)'
    );
  });

  test('returns error for a nonexistent path', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('getTransform', 'Nope')).toBe('error: not found: Nope');
  });

  test('reports local values only, independent of the parent transform', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      var child = mocks.createNode('Child', {
        position: { x: 5, y: 10, z: -2 },
        rotation: { x: 0, y: 90, z: 0 },
        scale: { x: 2, y: 1, z: 0.5 }
      });
      // Parent has a wildly different transform -- must not leak into the
      // child's reported values.
      var parent = mocks.createNode('Parent', {
        children: [child],
        position: { x: 100, y: 200, z: 300 }
      });
      mocks.wireScene([parent]);
    });
    const result = await call('getTransform', 'Parent/Child');
    expect(result).toBe(
      'position: (5.0, 10.0, -2.0)\n' +
      'rotation: (0.0, 90.0, 0.0)\n' +
      'scale: (2.0, 1.0, 0.5)'
    );
  });

  test('returns error when no scene is set', async ({ page }) => {
    const { call } = await injectLunaHelpers(page);
    expect(await call('getTransform', 'X')).toBe('error: no scene');
  });
});
