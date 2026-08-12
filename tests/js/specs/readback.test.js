// window.__luna_mcp.readBack(path, fieldPath)
// Unlike the rest of luna_helpers.js, readBack returns a JSON STRING:
// {ok, exists, value?} or {ok:false, err}. A resolveNode() failure (missing
// scene OR missing node) always yields {ok:true, exists:false} -- readBack
// deliberately does not distinguish "no scene" from "not found".
// Field resolution: fieldPath is dot-split; a leading "transform" segment is
// skipped (the node itself IS the transform context); the first real segment
// is tried against each component's `uc['get'+key]` getter before falling
// back to plain property lookup on the node.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('readBack', () => {
  test('returns the current value after a set', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('setTransform', 'Cube', 'position', 5, 6, 7)).toBe('ok');
    const result = JSON.parse(await call('readBack', 'Cube', '_localPosition'));
    expect(result).toEqual({ ok: true, exists: true, value: { x: 5, y: 6, z: 7 } });
  });

  test('handles a nonexistent path as {exists:false}', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = JSON.parse(await call('readBack', 'Nope', '_localPosition'));
    expect(result).toEqual({ ok: true, exists: false });
  });

  test('works for transform properties (direct node field lookup)', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var n = window.__mocks.createNode('Obj', { scale: { x: 2, y: 3, z: 4 } });
      window.__mocks.wireScene([n]);
    });
    const result = JSON.parse(await call('readBack', 'Obj', '_localScale'));
    expect(result).toEqual({ ok: true, exists: true, value: { x: 2, y: 3, z: 4 } });
  });

  test('works for component fields via a matching get<Field> accessor', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      var n = mocks.createNode('Obj');
      mocks.addComponent(n, 'CustomType', { getfoo: function() { return 42; } });
      mocks.wireScene([n]);
    });
    const result = JSON.parse(await call('readBack', 'Obj', 'foo'));
    expect(result).toEqual({ ok: true, exists: true, value: 42 });
  });
});
