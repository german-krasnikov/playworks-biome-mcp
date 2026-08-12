// window.__luna_mcp.getComponents(path) / getComponent(path, componentType)
// getComponents: newline-joined short component type names, in registration
// order.
// getComponent: readComponentFields() walks 5 strategies (S1 pc.Debugger,
// S2 prototype getters, S3 Deserializers.fields, S4 Bridge.Reflection,
// S5 m_/_ prefix scan). Our mock components are plain objects with no
// pc.Debugger/Deserializers/Bridge wiring, so every field always resolves
// via the S5 fallback: only own properties starting with "_" (not "__") or
// "m_" are surfaced -- plain (non-prefixed) fields like `text` are skipped.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('getComponents', () => {
  test('lists all components on a node', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('getComponents', 'Cube')).toBe('MeshRenderer\nMeshFilter');
  });

  test('returns error for an invalid path', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('getComponents', 'Nope')).toBe('error: not found: Nope');
  });
});

test.describe('getComponent', () => {
  test('returns field values for a specific component', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getComponent', 'Cube/Camera', 'Camera');
    expect(result).toBe(
      '_enabled: true\n' +
      '_fieldOfView: 60\n' +
      '_nearClipPlane: 0.3\n' +
      '_farClipPlane: 1000'
    );
  });

  test('falls back to the S5 underscore-prefix scan, skipping non-prefixed fields', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    // Text component fields: { text: 'Play', _text: 'Play', _fontSize: 24 }.
    // Only the underscore-prefixed ones (plus the default _enabled) surface;
    // plain `text` is dropped by the S5 filter.
    const result = await call('getComponent', 'UICanvas/PlayButton/ButtonText', 'Text');
    expect(result).toBe('_enabled: true\n_text: Play\n_fontSize: 24');
  });

  test('returns error for a component not on the node', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('getComponent', 'Cube', 'AudioSource')).toBe('error: component not found: AudioSource');
  });
});
