// Basic 3-branch scene fixture. Exported as a SOURCE string -- evaluated
// inside the Playwright page context by inject.js, AFTER mocks/scene.js and
// mocks/globals.js have been evaluated (so window.__mocks.createNode etc.
// already exist). Attaches createBasicScene() onto window.__mocks.
//
// Hierarchy:
//   Root
//     Cube [MeshRenderer, MeshFilter]
//       Camera [Camera]
//     UICanvas [Canvas]
//       PlayButton [Button, Image]
//         ButtonText [Text]

const SOURCE = `
window.__mocks = window.__mocks || {};
(function() {
    function build() {
        var mocks = window.__mocks;

        var camera = mocks.createNode('Camera');
        mocks.addComponent(camera, 'Camera', {
            _fieldOfView: 60,
            _nearClipPlane: 0.3,
            _farClipPlane: 1000
        });

        var cube = mocks.createNode('Cube', { children: [camera] });
        mocks.addComponent(cube, 'MeshRenderer', {
            getSharedMaterials: function() {
                return [{ name: 'CubeMat', shader: { name: 'Standard' } }];
            }
        });
        mocks.addComponent(cube, 'MeshFilter', { _mesh: 'CubeMesh' });

        var buttonText = mocks.createNode('ButtonText');
        mocks.addComponent(buttonText, 'Text', {
            text: 'Play',
            _text: 'Play',
            _fontSize: 24
        });

        var playButton = mocks.createNode('PlayButton', { children: [buttonText] });
        mocks.addComponent(playButton, 'Button', { _interactable: true });
        mocks.addComponent(playButton, 'Image', { _color: { r: 1, g: 1, b: 1, a: 1 } });

        var uiCanvas = mocks.createNode('UICanvas', { children: [playButton] });
        mocks.addComponent(uiCanvas, 'Canvas', { renderMode: 0, _renderMode: 0 });

        var scene = mocks.createScene([cube, uiCanvas]);
        var globals = mocks.createMockGlobals(scene);

        return {
            $scene: scene,
            UnityEngine: globals.UnityEngine,
            pc: globals.pc,
            Bridge: globals.Bridge
        };
    }

    // Builds the scene AND wires it onto window.$scene / window.UnityEngine /
    // window.pc / window.Bridge -- suitable for use directly as the sceneFn
    // argument to injectLunaHelpers(page, () => window.__mocks.createBasicScene()).
    function createBasicScene() {
        var result = build();
        window.$scene = result.$scene;
        window.UnityEngine = result.UnityEngine;
        window.pc = result.pc;
        if (result.Bridge) window.Bridge = result.Bridge;
        return result;
    }

    window.__mocks.createBasicScene = createBasicScene;
})();
`;

module.exports = { SOURCE };
