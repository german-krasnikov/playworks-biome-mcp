// window.__luna_mcp.visualSummary(detail)
// Requires UnityEngine.Camera.main (throws/errors out otherwise). Projects
// each visible renderer's bounds.center through cam.WorldToScreenPoint into
// a 3x3 screen bucket (TL/T/TR/L/C/R/BL/B/BR). Compact format:
//   "Scene <W>x<H> @<fps>fps | <N> vis"
//   "<Name>: <bucket> | ..."   (only when >=1 visible object)
//   "no end-card | 0 errors"
// detail='full' additionally appends a "UI:" section from collectUICanvases.
// fps() prefers pc.app.stats.frame.dt, falling back to UnityEngine.Time.deltaTime.
const { test, expect } = require('@playwright/test');
const { injectLunaHelpers } = require('../helpers/inject');

// Every scene below installs the same camera stub: WorldToScreenPoint always
// projects to dead-center of an 800x1280 viewport, so any visible object's
// bucket is deterministically 'C'.

test.describe('visualSummary', () => {
  test('returns a formatted summary with object counts and buckets', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      var cube = mocks.createNode('Cube');
      mocks.addComponent(cube, 'MeshRenderer', { bounds: { center: { x: 0, y: 0, z: 0 } } });
      var ball = mocks.createNode('Ball');
      mocks.addComponent(ball, 'SpriteRenderer', { bounds: { center: { x: 0, y: 0, z: 0 } } });
      mocks.wireScene([cube, ball], { camera: mocks.createCameraStub() });
    });
    const result = await call('visualSummary');
    expect(result).toBe('Scene 800x1280 @60fps | 2 vis\nCube: C | Ball: C\nno end-card | 0 errors');
  });

  test('handles an empty scene (zero visible objects)', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      mocks.wireScene([], { camera: mocks.createCameraStub() });
    });
    const result = await call('visualSummary');
    expect(result).toBe('Scene 800x1280 @60fps | 0 vis\nno end-card | 0 errors');
  });

  test('includes FPS info, falling back to UnityEngine.Time.deltaTime when pc.app.stats is absent', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      mocks.wireScene([], { camera: mocks.createCameraStub() });
      window.UnityEngine.Time.deltaTime = 0.02; // -> 50fps
      delete window.pc.app.stats;
    });
    const result = await call('visualSummary');
    expect(result).toContain('@50fps');
  });

  test('detects UI canvases and their Button/Text children (detail="full")', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      var buttonText = mocks.createNode('ButtonText');
      mocks.addComponent(buttonText, 'Text', { text: 'Play' });
      var playButton = mocks.createNode('PlayButton', { children: [buttonText] });
      mocks.addComponent(playButton, 'Button', {});
      var uiCanvas = mocks.createNode('UICanvas', { children: [playButton] });
      mocks.addComponent(uiCanvas, 'Canvas', { renderMode: 0 });
      mocks.wireScene([uiCanvas], { camera: mocks.createCameraStub() });
    });
    const result = await call('visualSummary', 'full');
    expect(result).toContain('UICanvas (mode=0)');
    expect(result).toContain('  Button PlayButton');
    expect(result).toContain('  Text ButtonText "Play"');
  });

  test('returns "no main camera" when UnityEngine.Camera.main is missing', async ({ page }) => {
    const { call } = await injectLunaHelpers(page, () => {
      var mocks = window.__mocks;
      mocks.wireScene([]);
      window.UnityEngine.Camera = {}; // defined, but no .main
    });
    expect(await call('visualSummary')).toBe('no main camera');
  });
});
