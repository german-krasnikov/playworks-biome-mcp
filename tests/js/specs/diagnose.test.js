// window.__luna_mcp.diagnoseObject(path)
// Line-per-check report: exists / active-chain / position / scale / layer /
// renderer(+materials). NOTE the renderer section prints only the shader
// name per material ('[OK] material[0]: <shader>'), not the material name --
// that richer format belongs to the separate getMaterials()/collectMaterials
// helper, not diagnoseObject.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

test.describe('diagnoseObject', () => {
  test('reports an active, well-formed object as healthy', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var n = window.__mocks.createNode('Healthy');
      window.__mocks.wireScene([n]);
    });
    const result = await call('diagnoseObject', 'Healthy');
    expect(result).toBe(
      'DIAGNOSE: Healthy\n' +
      '[OK] exists\n' +
      '[OK] active (self + parents)\n' +
      '[OK] position: (0.0, 0.0, 0.0)\n' +
      '[OK] scale: (1.0, 1.0, 1.0)\n' +
      '[OK] layer: 0 (Default)\n' +
      '[--] no renderer component'
    );
  });

  test('detects an inactive ancestor in the chain', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      var child = mocks.createNode('Child');
      var parent = mocks.createNode('Parent', { children: [child], activeSelf: false });
      mocks.wireScene([parent]);
    });
    const result = await call('diagnoseObject', 'Parent/Child');
    expect(result).toContain('[!!] INACTIVE: parent "Parent" is inactive');
  });

  test('detects zero scale (all three axes near zero)', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var n = window.__mocks.createNode('ZeroScale', { scale: { x: 0, y: 0, z: 0 } });
      window.__mocks.wireScene([n]);
    });
    const result = await call('diagnoseObject', 'ZeroScale');
    expect(result).toContain('[!!] scale: (0.0, 0.0, 0.0) (ZERO SCALE)');
  });

  test('handles a missing object', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => window.__mocks.createBasicScene());
    expect(await call('diagnoseObject', 'Nope')).toBe('[!!] NOT FOUND: Nope');
  });

  test('reports renderer info (enabled state + shader per material)', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      var n = mocks.createNode('Rend');
      mocks.addComponent(n, 'MeshRenderer', {
        getSharedMaterials: function() {
          return [{ name: 'M1', shader: { name: 'Standard' } }];
        }
      });
      mocks.wireScene([n]);
    });
    const result = await call('diagnoseObject', 'Rend');
    expect(result).toContain('[OK] renderer: MeshRenderer (enabled)');
    expect(result).toContain('[OK] material[0]: Standard');
  });

  test('returns error when no scene is set', async ({ page }) => {
    const { call } = await injectLunaHelpers(page);
    expect(await call('diagnoseObject', 'X')).toBe('error: no scene');
  });
});
