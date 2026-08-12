// window.__luna_mcp.getHierarchy(depth, rootPath)
// Text tree: one line per node ("<indent><name> [Comp1, Comp2]"), 2-space
// indent per depth level, trailing " !" marker when node._activeSelf===false.
// depth caps recursion (traverseHierarchy bails before emitting anything past
// maxDepth, so deeper nodes are omitted entirely, not truncated in place).
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('getHierarchy', () => {
  test('returns full tree with component names', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getHierarchy');
    expect(result).toBe(
      'Cube [MeshRenderer, MeshFilter]\n' +
      '  Camera [Camera]\n' +
      'UICanvas [Canvas]\n' +
      '  PlayButton [Button, Image]\n' +
      '    ButtonText [Text]'
    );
  });

  test('respects depth limit (deeper nodes omitted entirely)', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getHierarchy', 1);
    expect(result).toBe('Cube [MeshRenderer, MeshFilter]\nUICanvas [Canvas]');
  });

  test('rootPath filters output to the named subtree', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    const result = await call('getHierarchy', null, 'UICanvas');
    expect(result).toBe('PlayButton [Button, Image]\n  ButtonText [Text]');
  });

  test('returns "error: no scene" without a scene', async ({ page }) => {
    const { call } = await injectLunaHelpers(page);
    expect(await call('getHierarchy')).toBe('error: no scene');
  });

  test('marks inactive objects with a trailing "!"', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var disabled = window.__mocks.createNode('Disabled', { activeSelf: false });
      window.__mocks.wireScene([disabled]);
    });
    expect(await call('getHierarchy')).toBe('Disabled !');
  });
});
