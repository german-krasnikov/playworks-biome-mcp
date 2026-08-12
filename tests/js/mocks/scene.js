// Mock Luna scene graph factory. Exported as a SOURCE string -- it is never
// executed by Node. inject.js evaluates it inside the Playwright page context,
// where it attaches factories onto window.__mocks.
//
// Node shape mirrors what js/luna_helpers.js expects from a real Luna node:
//   _children, _parent, _activeSelf, _localPosition, _localEulerAngles,
//   _localScale, _layer, _guid, _unityComponents, transform
//
// Component shape mirrors Luna's transpiled components: a plain object with a
// single '__<Namespace.ClassName>' key whose value is the "unity object" (the
// object real helper code reads fields off via getUnityObject()).

const SOURCE = `
window.__mocks = window.__mocks || {};
(function() {
    var __guidCounter = 0;
    function nextGuid(name) {
        __guidCounter += 1;
        return 'guid-' + name + '-' + __guidCounter;
    }

    function createNode(name, opts) {
        opts = opts || {};
        return {
            name: name,
            _children: opts.children || [],
            _parent: null,
            _activeSelf: opts.activeSelf !== undefined ? opts.activeSelf : true,
            _localPosition: opts.position || { x: 0, y: 0, z: 0 },
            _localEulerAngles: opts.rotation || { x: 0, y: 0, z: 0 },
            _localScale: opts.scale || { x: 1, y: 1, z: 1 },
            _layer: opts.layer !== undefined ? opts.layer : 0,
            _guid: opts.guid || nextGuid(name),
            _unityComponents: {},
            transform: {}
        };
    }

    function linkParents(node) {
        var children = node._children || [];
        for (var i = 0; i < children.length; i++) {
            children[i]._parent = node;
            linkParents(children[i]);
        }
        return node;
    }

    function createScene(rootChildren) {
        var root = createNode('Root', { children: rootChildren || [] });
        linkParents(root);
        return { root: root };
    }

    // typeName may be short ('MeshRenderer') or fully-qualified
    // ('UnityEngine.MeshRenderer'). Short names default to the UnityEngine
    // namespace, matching the vast majority of built-in components.
    function addComponent(node, typeName, fields) {
        var shortName = typeName.indexOf('.') === -1 ? typeName : typeName.split('.').pop();
        var fullType = typeName.indexOf('.') === -1 ? 'UnityEngine.' + typeName : typeName;
        var unityObject = Object.assign({ _enabled: true }, fields || {});
        var comp = {};
        comp['__' + fullType] = unityObject;
        if (!node._unityComponents[shortName]) node._unityComponents[shortName] = [];
        node._unityComponents[shortName].push(comp);
        return comp;
    }

    // DRY convenience: builds a scene from rootChildren, derives mock globals
    // from it, and wires window.$scene/UnityEngine/pc/Bridge in one call --
    // replaces the 6-9 line boilerplate repeated across spec files. Returns
    // the scene for further customization (e.g. tweaking window.pc.app.stats).
    // opts.camera, if given, is installed as window.UnityEngine.Camera.main.
    function wireScene(rootChildren, opts) {
        opts = opts || {};
        var scene = createScene(rootChildren);
        var globals = window.__mocks.createMockGlobals(scene);
        window.$scene = scene;
        window.UnityEngine = globals.UnityEngine;
        window.pc = globals.pc;
        if (globals.Bridge) window.Bridge = globals.Bridge;
        if (opts.camera) window.UnityEngine.Camera = { main: opts.camera };
        return scene;
    }

    function createCameraStub(x, y, z) {
        return {
            pixelWidth: 800,
            pixelHeight: 1280,
            WorldToScreenPoint: function() { return { x: x || 400, y: y || 640, z: z || 5 }; }
        };
    }

    window.__mocks.createNode = createNode;
    window.__mocks.linkParents = linkParents;
    window.__mocks.createScene = createScene;
    window.__mocks.addComponent = addComponent;
    window.__mocks.wireScene = wireScene;
    window.__mocks.createCameraStub = createCameraStub;
})();
`;

module.exports = { SOURCE };
