// Mock Luna/PlayCanvas/UnityEngine globals. Exported as a SOURCE string --
// evaluated inside the Playwright page context by inject.js (never run in
// Node). Attaches createMockGlobals() onto window.__mocks.

const SOURCE = `
window.__mocks = window.__mocks || {};
(function() {
    // scene is accepted for symmetry with createScene()/fixtures that may
    // want to derive globals from scene contents later; unused for now.
    function createMockGlobals(scene) {
        var UnityEngine = {
            Time: { deltaTime: 0.016, timeScale: 1 },
            Shader: {},
            Screen: { width: 1920, height: 1080 }
        };
        var pc = {
            app: {
                stats: { frame: { dt: 1 / 60 } },
                graphicsDevice: {}
            },
            Debugger: null
        };
        var Bridge = null; // Phase 2
        return { UnityEngine: UnityEngine, pc: pc, Bridge: Bridge };
    }

    window.__mocks.createMockGlobals = createMockGlobals;
})();
`;

module.exports = { SOURCE };
