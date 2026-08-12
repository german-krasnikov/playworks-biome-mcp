// Playworks Biome MCP helpers. Injected via CDP. All output TEXT (no JSON).
// Version 1.6.1
(function() {
    if (window.__luna_mcp) return;

    // Field caps for readComponentFields — keep in sync with js_field_caps.py
    var FIELD_CAP = 20;   // max fields per component
    var VALUE_CAP = 120;  // max chars per serialized value

    function getScene() {
        if (typeof $scene !== 'undefined') return $scene;
        var iframe = document.querySelector('iframe');
        if (iframe && iframe.contentWindow && iframe.contentWindow.$scene) {
            return iframe.contentWindow.$scene;
        }
        return null;
    }

    function getComponentTypeName(comp) {
        var keys = Object.keys(comp);
        for (var i = 0; i < keys.length; i++) {
            if (keys[i].indexOf('__') === 0) {
                var full = keys[i].substring(2);
                var parts = full.split('.');
                return parts[parts.length - 1]; // short name
            }
        }
        return comp.constructor && comp.constructor.name !== 'Object' ? comp.constructor.name : '?';
    }

    function getComponentFullType(comp) {
        var keys = Object.keys(comp);
        for (var i = 0; i < keys.length; i++) {
            if (keys[i].indexOf('__') === 0) return keys[i].substring(2);
        }
        return '?';
    }

    function getNodeComponents(node) {
        var result = [];
        var uc = node._unityComponents;
        if (!uc) return result;
        var categories = Object.keys(uc);
        for (var ci = 0; ci < categories.length; ci++) {
            var arr = uc[categories[ci]];
            if (!Array.isArray(arr)) continue;
            for (var j = 0; j < arr.length; j++) {
                result.push(arr[j]);
            }
        }
        return result;
    }

    function traverseHierarchy(node, depth, maxDepth, indent) {
        if (depth > maxDepth) return '';
        var comps = getNodeComponents(node);
        var compNames = [];
        for (var i = 0; i < comps.length; i++) {
            compNames.push(getComponentTypeName(comps[i]));
        }
        var line = indent + node.name;
        if (compNames.length) line += ' [' + compNames.join(', ') + ']';
        if (node._activeSelf === false) line += ' !';
        var result = line + '\n';
        var children = node._children || [];
        for (var c = 0; c < children.length; c++) {
            result += traverseHierarchy(children[c], depth + 1, maxDepth, indent + '  ');
        }
        return result;
    }

    function findByPath(root, path) {
        if (!path) return root;
        var parts = path.split('/');
        var node = root;
        for (var i = 0; i < parts.length; i++) {
            var found = null;
            var children = node._children || [];
            for (var c = 0; c < children.length; c++) {
                if (children[c].name === parts[i]) { found = children[c]; break; }
            }
            if (!found) return null;
            node = found;
        }
        return node;
    }

    function vec3str(v) {
        if (!v) return '(0, 0, 0)';
        return '(' + (v.x || 0).toFixed(1) + ', ' + (v.y || 0).toFixed(1) + ', ' + (v.z || 0).toFixed(1) + ')';
    }

    function serializeValue(val, depth) {
        if (val === null || val === undefined) return 'null';
        if (typeof val !== 'object') return String(val);
        if ('x' in val && 'y' in val) return vec3str(val);  // Vector
        if ('r' in val && 'g' in val && 'b' in val)
            return 'rgba(' + val.r.toFixed(2) + ',' + val.g.toFixed(2) + ',' + val.b.toFixed(2) + ',' + (val.a || 1).toFixed(2) + ')';
        if (Array.isArray(val) || typeof val.ToArray === 'function') {
            var arr = Array.isArray(val) ? val : val.ToArray();
            return '[' + arr.length + ' items]';
        }
        if (val.gameObject || val._guid) return '<ref:' + (val.name || '?') + '>';
        if (val.$id) return '<asset:' + (val.name || val.$id) + '>';
        if (depth > 1) return '{...}';
        var keys = Object.keys(val).filter(function(k) { return k.indexOf('$') !== 0 && k.indexOf('__') !== 0; });
        if (keys.length > 10) return '{' + keys.length + ' fields}';
        return '{' + keys.slice(0, 5).join(', ') + (keys.length > 5 ? '...' : '') + '}';
    }

    function flattenDebuggerField(f) {
        if (f.type === null) return null;
        if (f.type === 'number' || f.type === 'string' || f.type === 'boolean') return f.value;
        if (f.type === 'Vector') return f.value;
        if (f.type === 'Color') return f.value;
        if (f.type === 'ref') return f.value;
        // -1: pc.Debugger List fields[0] is the Size sentinel element
        if (f.type === 'List' && f.fields) return '[' + Math.max(0, f.fields.length - 1) + ' items]';
        if (f.fields) return '{' + f.fields.length + ' fields}';
        return f.value !== undefined ? f.value : '(complex)';
    }

    function readComponentFields(comp) {
        var dunder = Object.keys(comp).find(function(k) { return k.indexOf('__') === 0; });
        if (!dunder) return [];
        var uo = comp[dunder];
        var shortType = dunder.substring(2).split('.').pop();

        // S1: pc.Debugger delegation
        if (typeof pc !== 'undefined' && pc.Debugger && pc.Debugger.DataTypes && pc.Debugger.DataTypes.MonoBehaviour) {
            try {
                var result = pc.Debugger.DataTypes.MonoBehaviour(comp);
                if (result && result.fields && result.fields.length > 0) {
                    return result.fields.map(function(f) {
                        return { key: f.label, val: flattenDebuggerField(f) };
                    });
                }
            } catch(e) { /* fall through */ }
        }

        // S2: Prototype getters
        var proto = Object.getPrototypeOf(uo);
        var getters = Object.getOwnPropertyNames(proto).filter(function(k) {
            return k.indexOf('get') === 0 && k.indexOf('$') === -1;
        });
        if (getters.length > 0) {
            var fields = [];
            for (var g = 0; g < getters.length; g++) {
                try {
                    var val = uo[getters[g]]();
                    var propName = getters[g].substring(3);
                    if (typeof val !== 'function') {
                        fields.push({ key: propName, val: val });
                    }
                } catch(e) { /* skip */ }
            }
            if (fields.length > 0) return fields;
        }

        // S3: Deserializers.fields
        var dtoPrefix = 'Luna.Unity.DTO.UnityEngine.Components.';
        if (typeof Deserializers !== 'undefined' && Deserializers.fields) {
            var dtoFields = Deserializers.fields[dtoPrefix + shortType];
            if (dtoFields) {
                var fieldNames = Object.keys(dtoFields);
                if (fieldNames.length > 0) {
                    return fieldNames
                        .filter(function(k) { return k !== 'enabled' && k !== 'm_Enabled'; })
                        .map(function(k) { return { key: k, val: uo[k] }; });
                }
            }
        }

        // S4: Bridge.Reflection.getMembers
        if (typeof Bridge !== 'undefined' && Bridge.Reflection && comp.unityClass) {
            try {
                var members = Bridge.Reflection.getMembers(comp.unityClass, 4, 20);
                if (members && members.length > 0) {
                    return members.map(function(m) { return { key: m.n, val: uo[m.n] }; });
                }
            } catch(e) { /* fall through */ }
        }

        // S5: m_/_ prefix scan
        var own = Object.getOwnPropertyNames(uo).filter(function(k) {
            return (k.indexOf('m_') === 0 || (k.indexOf('_') === 0 && k.indexOf('__') !== 0))
                && k !== 'm_Enabled' && k !== '$init';
        });
        if (own.length > 0) {
            return own.map(function(k) { return { key: k, val: uo[k] }; });
        }

        return [];
    }

    function applyFieldCaps(fields) {
        // Truncate values and cap the total number of fields.
        var capped = fields.map(function(f) {
            var v = f.val;
            if (typeof v === 'string' && v.length > VALUE_CAP) {
                v = v.substring(0, VALUE_CAP) + '…'; // ellipsis
            }
            return { key: f.key, val: v };
        });
        if (capped.length > FIELD_CAP) {
            var extra = capped.length - FIELD_CAP;
            capped = capped.slice(0, FIELD_CAP);
            capped.push({ key: '+' + extra + ' more fields', val: '' });
        }
        return capped;
    }

    function getShaderName(mat) {
        if (!mat) return '(null material)';
        if (mat._shader && mat._shader._name) return mat._shader._name;
        if (mat.shader && mat.shader.name) return mat.shader.name;
        var s = typeof mat.getShader === 'function' ? mat.getShader() : null;
        if (s && s._name) return s._name;
        return '(unknown shader)';
    }

    function collectMaterials(node, lines, prefix) {
        var comps = getNodeComponents(node);
        for (var i = 0; i < comps.length; i++) {
            var t = getComponentTypeName(comps[i]);
            if (t !== 'MeshRenderer' && t !== 'SkinnedMeshRenderer' && t !== 'SpriteRenderer') continue;
            var uo = getUnityObject(comps[i]);
            if (!uo) continue;
            var mats = [];
            try { mats = uo.getSharedMaterials ? uo.getSharedMaterials() : (uo._materials || uo._sharedMaterials || []); } catch(e) {}
            if (!Array.isArray(mats)) try { mats = mats.ToArray ? mats.ToArray() : []; } catch(e) { mats = []; }
            var label = (prefix ? prefix + '/' : '') + node.name;
            lines.push((prefix ? '  ' : '') + t + ' (' + label + '):');
            for (var j = 0; j < mats.length; j++) {
                var sn = getShaderName(mats[j]);
                var flag = (sn.indexOf('Error') !== -1 || sn.indexOf('Internal') !== -1 || sn.indexOf('Hidden/') === 0) ? ' [!!FALLBACK]' : '';
                lines.push('    [' + j + '] ' + (mats[j] && mats[j].name ? mats[j].name : '?') + ' (Shader: ' + sn + ')' + flag);
            }
        }
    }

    function buildPath(node) {
        var parts = [];
        var n = node;
        while (n && n.name && n !== getScene().root) {
            parts.unshift(n.name);
            n = n._parent || n.parent;
        }
        return parts.join('/');
    }

    function resolveNode(path) {
        var scene = getScene();
        if (!scene) return { err: 'error: no scene' };
        var node = findByPath(scene.root, path);
        if (!node) return { err: 'error: not found: ' + path };
        return { node: node, scene: scene };
    }

    function requireDebugger(sub) {
        if (typeof pc === 'undefined' || !pc.Debugger) return 'error: requires Luna Debugger extension';
        if (sub && !pc.Debugger[sub]) return 'error: requires pc.Debugger.' + sub;
        return null;
    }

    function getUnityObject(comp) {
        var dk = Object.keys(comp).find(function(k) { return k.indexOf('__') === 0; });
        return dk ? comp[dk] : null;
    }

    function findAnimator(path) {
        var r = resolveNode(path);
        if (r.err) return { err: r.err };
        var comps = getNodeComponents(r.node);
        for (var i = 0; i < comps.length; i++) {
            if (getComponentTypeName(comps[i]) === 'Animator') {
                return { node: r.node, animator: comps[i] };
            }
        }
        return { err: 'error: no Animator on ' + path };
    }

    function walkScene(callback) {
        var scene = getScene();
        if (!scene) return;
        function walk(node, path) {
            var p = path ? path + '/' + node.name : node.name;
            callback(node, p);
            var ch = node._children || [];
            for (var i = 0; i < ch.length; i++) walk(ch[i], p);
        }
        var children = scene.root._children || [];
        for (var i = 0; i < children.length; i++) walk(children[i], '');
    }

    // ── Visual Summary helpers ────────────────────────────────────────────────

    function isActiveChain(node) {
        var n = node;
        while (n) {
            if (n._activeSelf === false) return false;
            n = n._parent || n.parent;
            if (!n || !n.name) break;
        }
        return true;
    }

    function isZeroScale(node) {
        var s = node._localScale;
        return s && (s.x === 0 || s.y === 0 || s.z === 0);
    }

    function findRenderer(comps) {
        for (var i = 0; i < comps.length; i++) {
            var t = getComponentTypeName(comps[i]);
            if (t === 'MeshRenderer' || t === 'SkinnedMeshRenderer' || t === 'SpriteRenderer' || t === 'ParticleSystemRenderer') {
                return comps[i];
            }
        }
        return null;
    }

    function getBounds(renderer) {
        try {
            var uo = getUnityObject(renderer);
            if (uo && uo.bounds) return uo.bounds;
            if (uo && uo.getBounds) return uo.getBounds();
        } catch(e) {}
        return null;
    }

    function kindOf(comps) {
        for (var i = 0; i < comps.length; i++) {
            var t = getComponentTypeName(comps[i]);
            if (t === 'ParticleSystem' || t === 'ParticleSystemRenderer') return 'particles';
            if (t === 'Canvas' || t === 'CanvasRenderer') return 'ui';
            if (t === 'SkinnedMeshRenderer') return 'skinned';
            if (t === 'SpriteRenderer') return 'sprite';
            if (t === 'MeshRenderer') return 'mesh';
        }
        return 'obj';
    }

    function animState(comps) {
        for (var i = 0; i < comps.length; i++) {
            if (getComponentTypeName(comps[i]) !== 'Animator') continue;
            try {
                var uo = getUnityObject(comps[i]);
                if (!uo) continue;
                // Try pc.Debugger path
                if (typeof pc !== 'undefined' && pc.Debugger && pc.Debugger.Animator) {
                    var info = pc.Debugger.Animator.getStateInfo(comps[i]);
                    if (info && info.name) return '[' + info.name + ' t=' + (info.normalizedTime || 0).toFixed(2) + ']';
                }
                // Fallback: current state hash
                if (uo.GetCurrentAnimatorStateInfo) {
                    var s = uo.GetCurrentAnimatorStateInfo(0);
                    if (s) return '[state:' + (s.shortNameHash || s.nameHash || '?') + ']';
                }
            } catch(e) {}
        }
        return '';
    }

    function bucket9(sx, sy) {
        var col = sx < 0.33 ? 'L' : (sx < 0.67 ? '' : 'R');
        var row = sy < 0.33 ? 'T' : (sy < 0.67 ? '' : 'B');
        return (row + col) || 'C';
    }

    function screenPct(cam, b, W, H) {
        // Returns {bucket, sizePct} or null if off-screen
        if (!b) return null;
        var center = b.center;
        if (!center) return null;
        var s;
        try {
            s = cam.WorldToScreenPoint(center);
        } catch(e) {
            // Fallback: manual MVP projection
            try {
                var vm = cam.worldToCameraMatrix, pm = cam.projectionMatrix;
                var vx = vm.m00*center.x + vm.m01*center.y + vm.m02*center.z + vm.m03;
                var vy = vm.m10*center.x + vm.m11*center.y + vm.m12*center.z + vm.m13;
                var vz = vm.m20*center.x + vm.m21*center.y + vm.m22*center.z + vm.m23;
                var cx = pm.m00*vx + pm.m02*vz, cy = pm.m11*vy + pm.m12*vz, cw = -vz;
                if (cw <= 0) return null;
                s = { x: (cx/cw + 1) * 0.5 * W, y: (cy/cw + 1) * 0.5 * H, z: cw };
                // TODO: frustum check for wide cameras (off-screen padding -0.1..1.1 may miss edge cases)
            } catch(e2) { return null; }
        }
        if (!s || s.z < 0) return null;
        var nx = s.x / W, ny = 1 - s.y / H;
        if (nx < -0.1 || nx > 1.1 || ny < -0.1 || ny > 1.1) return null;
        // Estimate screen size from bounds extents
        var sizePct = 0;
        try {
            var ext = b.extents || b.size;
            if (ext) {
                var sc = cam.WorldToScreenPoint({ x: center.x + ext.x, y: center.y, z: center.z });
                if (sc && sc.z > 0) sizePct = Math.round(Math.abs(sc.x - s.x) * 2 / H * 100);
            }
        } catch(e) {}
        return { bucket: bucket9(nx, ny), sizePct: sizePct };
    }

    function collectUICanvases() {
        var lines = [];
        walkScene(function(node) {
            var comps = getNodeComponents(node);
            for (var i = 0; i < comps.length; i++) {
                var t = getComponentTypeName(comps[i]);
                if (t !== 'Canvas') continue;
                if (!isActiveChain(node)) continue;
                var uo = getUnityObject(comps[i]);
                var mode = uo && uo.renderMode !== undefined ? uo.renderMode : '?';
                lines.push(node.name + ' (mode=' + mode + ')');
                // Collect Text/Button children
                var texts = [];
                walkScene(function(ch) {
                    if (!isActiveChain(ch)) return;
                    var cc = getNodeComponents(ch);
                    for (var j = 0; j < cc.length; j++) {
                        var ct = getComponentTypeName(cc[j]);
                        if (ct !== 'Text' && ct !== 'TextMeshProUGUI' && ct !== 'Button') continue;
                        var cuo = getUnityObject(cc[j]);
                        var label = '';
                        if (ct === 'Text' || ct === 'TextMeshProUGUI') label = cuo && (cuo.text || cuo.m_text) ? '"' + (cuo.text || cuo.m_text) + '"' : '';
                        texts.push('  ' + ct + ' ' + ch.name + (label ? ' ' + label : ''));
                    }
                });
                // Limit to first 5 to avoid verbose output
                for (var k = 0; k < Math.min(texts.length, 5); k++) lines.push(texts[k]);
                break;
            }
        });
        return lines;
    }

    function detectEndCard(visible, uiLines) {
        for (var i = 0; i < visible.length; i++) {
            if (/endcard|endscreen|final|end_card/i.test(visible[i].name)) return true;
        }
        for (var j = 0; j < uiLines.length; j++) {
            if (/endcard|endscreen|final|end_card/i.test(uiLines[j])) return true;
        }
        return false;
    }

    function fps() {
        try {
            if (typeof pc !== 'undefined' && pc.app && pc.app.stats && pc.app.stats.frame) return Math.round(1 / pc.app.stats.frame.dt) || 0;
        } catch(e) {}
        try { if (typeof UnityEngine !== 'undefined') return Math.round(1 / UnityEngine.Time.deltaTime) || 0; } catch(e) {}
        return 0;
    }

    function formatCompact(visible, uiLines, endCard, fpsVal, W, H) {
        var header = 'Scene ' + W + 'x' + H + ' @' + fpsVal + 'fps | ' + visible.length + ' vis';
        var parts = [];
        for (var i = 0; i < Math.min(visible.length, 8); i++) {
            var v = visible[i];
            var tok = v.name + ': ' + v.bucket;
            if (v.sizePct) tok += ' ' + v.sizePct + '%h';
            if (v.state) tok += ' ' + v.state;
            parts.push(tok);
        }
        var lines = [header];
        if (parts.length) lines.push(parts.join(' | '));
        lines.push((endCard ? 'end-card DETECTED' : 'no end-card') + ' | 0 errors');
        return lines.join('\n');
    }

    function formatUIOnly(uiLines, endCard) {
        var lines = ['UI overlay (Canvas/HUD):'];
        if (uiLines.length) for (var i = 0; i < uiLines.length; i++) lines.push('- ' + uiLines[i]);
        else lines.push('(no UI canvases)');
        lines.push(endCard ? 'end-card visible' : 'no end-card visible');
        return lines.join('\n');
    }

    function formatFull(visible, uiLines, endCard, fpsVal, W, H) {
        return formatCompact(visible, uiLines, endCard, fpsVal, W, H) +
            '\nUI:\n' + (uiLines.length ? uiLines.join('\n') : '(none)');
    }

    // LRU-ish visual snapshot cache (max 8 entries, ~5s TTL conceptually — caller tracks time)
    var __visualCache = {};
    var __visualCacheOrder = [];

    function cacheSet(key, val) {
        if (__visualCacheOrder.length >= 8) {
            var old = __visualCacheOrder.shift();
            delete __visualCache[old];
        }
        __visualCache[key] = val;
        __visualCacheOrder.push(key);
    }

    function diffSnapshots(prev, curr) {
        var pLines = prev.split('\n');
        var cLines = curr.split('\n');
        var added = [], removed = [], changed = [];
        for (var i = 0; i < cLines.length; i++) {
            if (pLines.indexOf(cLines[i]) === -1) added.push('+ ' + cLines[i]);
        }
        for (var j = 0; j < pLines.length; j++) {
            if (cLines.indexOf(pLines[j]) === -1) removed.push('- ' + pLines[j]);
        }
        if (!added.length && !removed.length) return 'no changes';
        var out = ['DIFF vs prev:'];
        for (var a = 0; a < added.length; a++) out.push(added[a]);
        for (var r = 0; r < removed.length; r++) out.push(removed[r]);
        // detect end-card change
        var pEc = /end-card DETECTED/.test(prev);
        var cEc = /end-card DETECTED/.test(curr);
        if (!pEc && cEc) out.push('end-card: NO -> YES');
        else if (pEc && !cEc) out.push('end-card: YES -> NO');
        return out.join('\n');
    }

    window.__luna_mcp = {
        version: '1.6.1',

        ping: function() {
            var scene = getScene();
            return scene ? 'pong' : 'no scene';
        },

        getHierarchy: function(depth, rootPath) {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var root = rootPath ? findByPath(scene.root, rootPath) : scene.root;
            if (!root) return 'error: root not found: ' + rootPath;
            var lines = '';
            var children = root._children || [];
            for (var i = 0; i < children.length; i++) {
                lines += traverseHierarchy(children[i], 1, depth || 99, '');
            }
            return lines.trimEnd();
        },

        getComponent: function(path, componentType) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            var comps = getNodeComponents(node);
            for (var i = 0; i < comps.length; i++) {
                var fullType = getComponentFullType(comps[i]);
                var shortType = getComponentTypeName(comps[i]);
                if (shortType === componentType || fullType === componentType) {
                    var fields = applyFieldCaps(readComponentFields(comps[i]));
                    if (!fields.length) return shortType + ': (no readable properties)';
                    var result = '';
                    for (var f = 0; f < fields.length; f++) {
                        result += fields[f].key + ': ' + serializeValue(fields[f].val, 0) + '\n';
                    }
                    return result.trimEnd();
                }
            }
            return 'error: component not found: ' + componentType;
        },

        getTransform: function(path) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            return 'position: ' + vec3str(node._localPosition) +
                '\nrotation: ' + vec3str(node._localEulerAngles) +
                '\nscale: ' + vec3str(node._localScale);
        },

        getComponents: function(path) {
            var r = resolveNode(path); if (r.err) return r.err;
            var comps = getNodeComponents(r.node);
            return comps.map(function(c) { return getComponentTypeName(c); }).join('\n') || '(none)';
        },

        getObjectDetail: function(path) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            var self = window.__luna_mcp;
            var out = '--- Transform ---\n' + self.getTransform(path);
            var comps = getNodeComponents(node);
            for (var i = 0; i < comps.length; i++) {
                var fullType = getComponentFullType(comps[i]);
                var shortType = getComponentTypeName(comps[i]);
                out += '\n\n--- ' + shortType + ' ---\n' + self.getComponent(path, fullType);
            }
            return out;
        },

        setProperty: function(path, componentType, prop, value) {
            var r = resolveNode(path); if (r.err) return r.err;
            var comps = getNodeComponents(r.node);
            for (var i = 0; i < comps.length; i++) {
                var fullType = getComponentFullType(comps[i]);
                var shortType = getComponentTypeName(comps[i]);
                if (shortType === componentType || fullType === componentType) {
                    var uc = getUnityObject(comps[i]);
                    if (!uc) return 'error: no unity object';
                    var setter = 'set' + prop;
                    if (typeof uc[setter] === 'function') {
                        uc[setter](value);
                        return 'ok';
                    }
                    return 'error: no setter for ' + prop;
                }
            }
            return 'error: component not found: ' + componentType;
        },

        setTransform: function(path, prop, x, y, z) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            var field = '_local' + prop.charAt(0).toUpperCase() + prop.slice(1);
            if (!node[field]) return 'error: unknown transform property: ' + prop;
            node[field].x = x;
            node[field].y = y;
            node[field].z = z;
            return 'ok';
        },

        readBack: function(path, fieldPath) {
            try {
                var r = resolveNode(path);
                if (r.err) return JSON.stringify({ok: true, exists: false});
                var parts = fieldPath.split('.');
                var cur = r.node;
                // skip 'transform' prefix — node IS the transform context
                var start = (parts[0] === 'transform') ? 1 : 0;
                for (var i = start; i < parts.length; i++) {
                    if (cur == null) return JSON.stringify({ok: true, exists: true, value: null});
                    var key = parts[i];
                    // try unity object getters first
                    if (i === start && key !== 'transform') {
                        var comps = getNodeComponents(cur);
                        for (var ci = 0; ci < comps.length; ci++) {
                            var uc = getUnityObject(comps[ci]);
                            if (uc && typeof uc['get' + key] === 'function') {
                                return JSON.stringify({ok: true, exists: true, value: uc['get' + key]()});
                            }
                        }
                    }
                    cur = cur[key];
                }
                return JSON.stringify({ok: true, exists: true, value: cur});
            } catch(e) {
                return JSON.stringify({ok: false, err: String(e)});
            }
        },

        findObjects: function(query) {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var results = [];
            var q = query.toLowerCase();
            function walk(node, path) {
                var p = path ? path + '/' + node.name : node.name;
                if (node.name.toLowerCase().indexOf(q) !== -1) results.push(p);
                var children = node._children || [];
                for (var i = 0; i < children.length; i++) walk(children[i], p);
            }
            var children = scene.root._children || [];
            for (var i = 0; i < children.length; i++) walk(children[i], '');
            return results.join('\n') || 'no matches';
        },

        findByComponent: function(componentType) {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var results = [];
            var ct = componentType.toLowerCase();
            function walk(node, path) {
                var p = path ? path + '/' + node.name : node.name;
                var comps = getNodeComponents(node);
                for (var i = 0; i < comps.length; i++) {
                    if (getComponentTypeName(comps[i]).toLowerCase() === ct ||
                        getComponentFullType(comps[i]).toLowerCase() === ct) {
                        results.push(p);
                        break;
                    }
                }
                var children = node._children || [];
                for (var c = 0; c < children.length; c++) walk(children[c], p);
            }
            var children = scene.root._children || [];
            for (var i = 0; i < children.length; i++) walk(children[i], '');
            return results.join('\n') || 'no matches';
        },

        discoverCustomComponents: function() {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var types = {};
            function walk(node) {
                var comps = getNodeComponents(node);
                for (var i = 0; i < comps.length; i++) {
                    var short = getComponentTypeName(comps[i]);
                    if (short === '?' || short === 'Transform' || short === 'RectTransform') continue;
                    if (typeof pc !== 'undefined' && pc.Debugger && pc.Debugger.Components && pc.Debugger.Components[short]) continue;
                    types[short] = getComponentFullType(comps[i]);
                }
                var children = node._children || [];
                for (var c = 0; c < children.length; c++) walk(children[c]);
            }
            var children = scene.root._children || [];
            for (var i = 0; i < children.length; i++) walk(children[i]);
            var keys = Object.keys(types);
            return keys.length ? keys.map(function(k) { return k + ': ' + types[k]; }).join('\n') : '(none)';
        },

        registerCustomComponents: function() {
            if (typeof pc === 'undefined' || !pc.Debugger || !pc.Debugger.DataTypes) {
                return 'error: pc.Debugger not available';
            }
            if (pc.Debugger.DataTypes.MonoBehaviour.__patched) return 'already patched';

            var orig = pc.Debugger.DataTypes.MonoBehaviour;
            var Field = pc.Debugger.DataTypes.Field;

            pc.Debugger.DataTypes.MonoBehaviour = function(comp, ctx) {
                var result = orig(comp, ctx);

                // Fix display: strip underscores so UI doesn't eat the prefix
                if (result && result.type) {
                    result.type = result.type.replace(/_/g, '');
                }

                // Enhance empty results with _ prefix field scan
                if (result && (!result.fields || result.fields.length === 0)) {
                    var n = comp.toUnityObject ? comp.toUnityObject() : comp;
                    if (n && n.code) n = n.code;
                    var own = Object.getOwnPropertyNames(n).filter(function(k) {
                        return (k.indexOf('_') === 0 && k.indexOf('__') !== 0)
                            && k !== '$init' && k !== '_enabled' && k !== '_destroyed';
                    });
                    if (own.length) {
                        result.fields = own.map(function(k) {
                            return Field(k, n[k]);
                        }).filter(function(f) { return !!f; });
                    }
                }

                return result;
            };
            pc.Debugger.DataTypes.MonoBehaviour.__patched = true;
            return 'patched MonoBehaviour (all components enhanced)';
        },

        pauseGame: function() {
            if (typeof UnityEngine === 'undefined') return 'error: no Unity runtime';
            UnityEngine.Time.timeScale = 0;
            return 'paused (timeScale=0)';
        },

        resumeGame: function() {
            if (typeof UnityEngine === 'undefined') return 'error: no Unity runtime';
            UnityEngine.Time.timeScale = 1;
            return 'resumed (timeScale=1)';
        },

        getGameState: function() {
            if (typeof UnityEngine === 'undefined') return 'error: no Unity runtime';
            var ts = UnityEngine.Time.timeScale;
            var editorCam = (typeof pc !== 'undefined' && pc.Debugger && pc.Debugger.GameState)
                ? pc.Debugger.GameState.inEditorMode
                : false;
            return 'timeScale: ' + ts + '\npaused: ' + (ts === 0) + '\neditorCamera: ' + editorCam;
        },

        getLayers: function() {
            var layers = [];
            var sorting = [];
            try {
                for (var i = 0; i < 32; i++) {
                    var n = UnityEngine.LayerMask.LayerToName(i);
                    if (n) layers.push(i + ': ' + n);
                }
            } catch(e) { layers.push('error: ' + e.message); }
            try {
                for (var i = 0; i < 32; i++) {
                    var n = UnityEngine.SortingLayer.GetLayerNameFromValue(i);
                    var id = UnityEngine.SortingLayer.GetLayerIDFromValue(i);
                    if (n && !sorting.find(function(s) { return s.indexOf(n) !== -1; }))
                        sorting.push(id + ': ' + n);
                }
            } catch(e) { sorting.push('error: ' + e.message); }
            return 'LAYERS:\n' + (layers.join('\n') || '(none)') +
                   '\n\nSORTING LAYERS:\n' + (sorting.join('\n') || '(none)');
        },

        diagnoseObject: function(path) {
            var r = resolveNode(path);
            if (r.err) return r.err.indexOf('not found') !== -1 ? '[!!] NOT FOUND: ' + path : r.err;
            var node = r.node; var scene = r.scene;
            var lines = ['DIAGNOSE: ' + path, '[OK] exists'];
            // Active chain
            var activeIssue = null;
            if (node._activeSelf === false) {
                activeIssue = 'self is inactive';
            } else {
                var parent = node._parent;
                while (parent && parent !== scene.root) {
                    if (parent._activeSelf === false) { activeIssue = 'parent "' + parent.name + '" is inactive'; break; }
                    parent = parent._parent;
                }
            }
            lines.push(activeIssue ? '[!!] INACTIVE: ' + activeIssue : '[OK] active (self + parents)');
            // Transform
            var pos = node._localPosition || {x:0,y:0,z:0};
            var scl = node._localScale || {x:1,y:1,z:1};
            lines.push((Math.abs(pos.x) > 9999 || Math.abs(pos.y) > 9999 || Math.abs(pos.z) > 9999)
                ? '[!!] position: ' + vec3str(pos) + ' (OFF-SCREEN?)'
                : '[OK] position: ' + vec3str(pos));
            lines.push((Math.abs(scl.x) < 0.001 && Math.abs(scl.y) < 0.001 && Math.abs(scl.z) < 0.001)
                ? '[!!] scale: ' + vec3str(scl) + ' (ZERO SCALE)'
                : '[OK] scale: ' + vec3str(scl));
            // Layer
            var layerName = '';
            try { layerName = UnityEngine.LayerMask.LayerToName(node._layer || 0); } catch(e) {}
            lines.push('[OK] layer: ' + (node._layer || 0) + ' (' + (layerName || 'Default') + ')');
            // Renderer
            var comps = getNodeComponents(node);
            var hasRenderer = false;
            for (var i = 0; i < comps.length; i++) {
                var t = getComponentTypeName(comps[i]);
                if (t === 'MeshRenderer' || t === 'SkinnedMeshRenderer' || t === 'SpriteRenderer') {
                    hasRenderer = true;
                    var uo = getUnityObject(comps[i]);
                    var enabled = uo ? (uo._enabled !== false) : true;
                    lines.push(enabled ? '[OK] renderer: ' + t + ' (enabled)' : '[!!] renderer: ' + t + ' (DISABLED)');
                    // Materials
                    var mats = [];
                    try { mats = uo && uo.getSharedMaterials ? uo.getSharedMaterials() : (uo && uo._materials || []); } catch(e) {}
                    if (!Array.isArray(mats)) try { mats = mats.ToArray ? mats.ToArray() : []; } catch(e) { mats = []; }
                    for (var j = 0; j < mats.length; j++) {
                        var sn = getShaderName(mats[j]);
                        var isFallback = sn.indexOf('Error') !== -1 || sn.indexOf('Internal') !== -1;
                        lines.push(isFallback ? '[!!] material[' + j + ']: ' + sn + ' (FALLBACK SHADER)' : '[OK] material[' + j + ']: ' + sn);
                    }
                }
            }
            if (!hasRenderer) lines.push('[--] no renderer component');
            return lines.join('\n');
        },

        getMaterials: function(path, includeChildren) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            var lines = ['MATERIALS: ' + path];
            collectMaterials(node, lines, '');
            if (includeChildren) {
                function walk(n, p) {
                    var children = n._children || [];
                    for (var i = 0; i < children.length; i++) {
                        collectMaterials(children[i], lines, p ? p + '/' + children[i].name : children[i].name);
                        walk(children[i], p ? p + '/' + children[i].name : children[i].name);
                    }
                }
                walk(node, '');
            }
            if (lines.length === 1) lines.push('(no renderers found)');
            return lines.join('\n');
        },

        getAnimatorState: function(path) {
            var de = requireDebugger('Animator'); if (de) return de;
            var fa = findAnimator(path); if (fa.err) return fa.err;
            var node = fa.node; var animator = fa.animator;
            var id = animator.handle ? animator.handle.$id : animator.$id;
            var guid = node._guid;
            var data = pc.Debugger.Animator.get({animator: {id: id, guid: guid}});
            if (!data) return 'error: animator data unavailable';
            var lines = ['ANIMATOR: ' + path];
            for (var li = 0; li < (data.layers || []).length; li++) {
                var layer = data.layers[li];
                lines.push('  layer[' + li + ']: ' + layer.name + ' (weight=' + layer.weight + ')');
            }
            var stateKeys = Object.keys(data.states || {});
            var activeStates = stateKeys.filter(function(k) { return data.states[k].normalizedTime !== undefined; });
            if (activeStates.length) {
                lines.push('  active states:');
                for (var si = 0; si < activeStates.length; si++) {
                    var s = data.states[activeStates[si]];
                    lines.push('    ' + s.name + ' t=' + (s.normalizedTime || 0).toFixed(2) + (s.isLooping ? ' (loop)' : ''));
                }
            }
            if (data.parameters) {
                var paramKeys = Object.keys(data.parameters);
                if (paramKeys.length) {
                    lines.push('  parameters:');
                    for (var pi = 0; pi < paramKeys.length; pi++)
                        lines.push('    ' + paramKeys[pi] + ': ' + data.parameters[paramKeys[pi]]);
                }
            }
            return lines.join('\n');
        },

        setAnimatorParam: function(path, paramName, value, isTrigger) {
            var de = requireDebugger('Animator'); if (de) return de;
            var fa = findAnimator(path); if (fa.err) return fa.err;
            var node = fa.node; var animator = fa.animator;
            var id = animator.handle ? animator.handle.$id : animator.$id;
            var guid = node._guid;
            var prefix = isTrigger ? 'triggers' : 'parameters';
            pc.Debugger.Animator.update({path: prefix + '/' + paramName, value: value, animator: {id: id, guid: guid}});
            return 'ok: ' + prefix + '/' + paramName + ' = ' + value;
        },

        toggleEditorCamera: function(enable) {
            var de = requireDebugger('GameState'); if (de) return de;
            var current = pc.Debugger.GameState.inEditorMode;
            if (enable === undefined) enable = !current;
            pc.Debugger.GameState.inEditorMode = enable;
            return enable
                ? 'editor camera ON (WASD=move, right-click+drag=look, Q/E=up/down, scroll=zoom)'
                : 'editor camera OFF (game cameras restored)';
        },

        hasDebugger: function() {
            return typeof pc !== 'undefined' && !!pc.Debugger ? 'yes' : 'no';
        },

        getShaderReport: function() {
            if (typeof UnityEngine === 'undefined') return 'error: no Unity runtime';
            var si = UnityEngine.Shader.shaderIndex;
            if (!si) return 'error: no shader index';
            var names = Object.keys(si);
            var lines = ['SHADERS (' + names.length + '):'];
            for (var i = 0; i < names.length; i++) {
                var entry = si[names[i]];
                if (!entry) continue;
                var passes = entry.passes ? entry.passes.length : 0;
                var errors = entry.compilationErrors ? entry.compilationErrors.length : 0;
                var line = (errors > 0 ? '[!!] ' : '[OK] ') + names[i] + ' | passes:' + passes;
                if (errors > 0) {
                    for (var j = 0; j < entry.compilationErrors.length; j++) {
                        var e = entry.compilationErrors[j];
                        line += '\n     ERR: ' + (e.message || e.error || String(e)).substring(0, 120);
                    }
                }
                lines.push(line);
            }
            // Also list common shaders that might be missing
            var expected = ['Standard', 'UI/Default', 'Sprites/Default', 'Particles/Standard Unlit',
                'Mobile/Particles/Alpha Blended', 'Mobile/Particles/Additive'];
            var missing = [];
            for (var i = 0; i < expected.length; i++) {
                try {
                    if (!UnityEngine.Shader.Find(expected[i])) missing.push(expected[i]);
                } catch(e) { missing.push(expected[i] + ' (error)'); }
            }
            if (missing.length) lines.push('\nMISSING COMMON SHADERS:\n  ' + missing.join('\n  '));
            return lines.join('\n');
        },

        showCollider: function(path) {
            var de = requireDebugger('GameState'); if (de) return de;
            var r = resolveNode(path); if (r.err) return r.err.replace('not found', 'object not found');
            var node = r.node;
            var comps = getNodeComponents(node);
            var colliderTypes = ['BoxCollider', 'SphereCollider', 'CapsuleCollider'];
            var collider = null;
            for (var i = 0; i < comps.length; i++) {
                var tn = getComponentTypeName(comps[i]);
                if (colliderTypes.indexOf(tn) !== -1) { collider = comps[i]; break; }
            }
            if (!collider) return 'error: no collider found on ' + path;
            var tn = getComponentTypeName(collider);
            pc.Debugger.GameState.selection = {
                type: 'GameObject',
                guid: node._guid,
                displayCollider: collider.$id
            };
            return 'showing collider: ' + tn + ' on ' + path;
        },

        hideCollider: function() {
            var de = requireDebugger('GameState'); if (de) return de;
            var sel = pc.Debugger.GameState.selection || {};
            pc.Debugger.GameState.selection = Object.assign({}, sel, { displayCollider: null });
            return 'collider hidden';
        },

        showColliderOverlay: function(path) {
            try {
                var r = resolveNode(path); if (r.err) return r.err;
                var node = r.node;
                var UE = UnityEngine;
                var comps = getNodeComponents(node);
                var count = 0;
                for (var i = 0; i < comps.length; i++) {
                    var comp = comps[i];
                    var tn = getComponentTypeName(comp);
                    var go = UE.GameObject.CreatePrimitive(UE.PrimitiveType.Cube);
                    go.name = '__dcol_' + count;
                    go.transform.parent = node.transform;
                    var mr = go.GetComponent(UE.MeshRenderer);
                    mr.material.shader = UE.Shader.Find('Sprites/Default');
                    if (tn === 'BoxCollider') {
                        var c = comp.center; var s = comp.size;
                        go.transform.localPosition = new UE.Vector3(c.x, c.y, c.z);
                        go.transform.localScale = new UE.Vector3(s.x, s.y, s.z);
                        mr.material.color = new UE.Color(0.2, 1.0, 0.3, 0.2);
                    } else if (tn === 'SphereCollider') {
                        var sc = comp.center; var sr = comp.radius * 2;
                        go.transform.localPosition = new UE.Vector3(sc.x, sc.y, sc.z);
                        go.transform.localScale = new UE.Vector3(sr, sr, sr);
                        mr.material.color = new UE.Color(0.2, 0.5, 1.0, 0.2);
                    } else if (tn === 'CapsuleCollider') {
                        var cc = comp.center; var cr = comp.radius * 2; var ch = comp.height;
                        go.transform.localPosition = new UE.Vector3(cc.x, cc.y, cc.z);
                        go.transform.localScale = new UE.Vector3(cr, ch, cr);
                        mr.material.color = new UE.Color(1.0, 0.8, 0.2, 0.2);
                    } else { UE.Object.Destroy(go); continue; }
                    var bc = go.GetComponent(UE.BoxCollider);
                    if (bc) bc.enabled = false;
                    count++;
                }
                return 'showing ' + count + ' colliders on ' + path;
            } catch(e) { return 'error: ' + e.message; }
        },

        showAllColliderOverlays: function(maxCount, skipGround) {
            try {
                var cap = Math.min(maxCount || 20, 50);
                var skip = skipGround !== false;
                var skipNames = ['Ground', 'ground', 'Floor', 'floor', 'Terrain'];
                var total = 0;
                var self = window.__luna_mcp;
                walkScene(function(node) {
                    if (total >= cap) return;
                    if (skip) {
                        for (var s = 0; s < skipNames.length; s++)
                            if (node.name.indexOf(skipNames[s]) !== -1) return;
                    }
                    var comps = getNodeComponents(node);
                    for (var i = 0; i < comps.length; i++) {
                        if (total >= cap) break;
                        var tn = getComponentTypeName(comps[i]);
                        if (tn !== 'BoxCollider' && tn !== 'SphereCollider' && tn !== 'CapsuleCollider') continue;
                        if (skip && tn === 'BoxCollider') {
                            try { var sz = getUnityObject(comps[i]).size; if (sz && (sz.x > 20 || sz.z > 20)) break; } catch(e) {}
                        }
                        self.showColliderOverlay(buildPath(node));
                        total++;
                        break;
                    }
                });
                return 'showing ' + total + ' collider overlays (green=box, blue=sphere, yellow=capsule)';
            } catch(e) { return 'error: ' + e.message; }
        },

        hideColliderOverlays: function() {
            try {
                var UE = UnityEngine;
                var count = 0;
                for (var i = 0; i < 200; i++) {
                    var go = UE.GameObject.Find('__dcol_' + i);
                    if (go) { UE.Object.Destroy(go); count++; }
                    else break;
                }
                return 'removed ' + count + ' collider overlays';
            } catch(e) { return 'error: ' + e.message; }
        },

        setField: function(path, component, field, value, fieldType) {
            var de = requireDebugger('Inspector'); if (de) return de;
            var r = resolveNode(path); if (r.err) return r.err.replace('not found', 'object not found');
            var comps = getNodeComponents(r.node);
            var comp = null;
            for (var i = 0; i < comps.length; i++) {
                if (getComponentTypeName(comps[i]) === component) { comp = comps[i]; break; }
            }
            if (!comp) return 'error: component not found: ' + component;
            var node = r.node;
            // Use castToUnityType when available for proper Vector/Color/Enum handling
            var castValue = value;
            if (pc.Debugger.Utils && pc.Debugger.Utils.castToUnityType) {
                try { castValue = pc.Debugger.Utils.castToUnityType(value, fieldType); } catch(e) {}
            }
            // Use __setValueAt for deep property path when available
            var uo = getUnityObject(comp);
            if (uo && typeof uo.__setValueAt === 'function' && field.indexOf('/') !== -1) {
                uo.__setValueAt(field, castValue);
                return 'ok: ' + path + '/' + component + '/' + field + ' = ' + value;
            }
            pc.Debugger.Inspector.update({
                path: node._guid + '/' + component + '/' + comp.$id + '/' + field,
                value: castValue,
                type: fieldType
            });
            return 'ok: ' + path + '/' + component + '/' + field + ' = ' + value;
        },

        toggleProfiler: function(enable) {
            var de = requireDebugger('GameState'); if (de) return de;
            var current = pc.Debugger.GameState.isProfiling;
            if (enable === undefined) enable = !current;
            pc.Debugger.GameState.isProfiling = enable;
            return enable ? 'profiler ON (FPS/ms/memory overlay)' : 'profiler OFF';
        },

        getEnums: function(filter) {
            if (typeof pc === 'undefined' || !pc.Debugger || !pc.Debugger.Utils || !pc.Debugger.Utils.getEnumData)
                return 'error: pc.Debugger not available';
            if (typeof Bridge === 'undefined') return 'error: Bridge not available';
            var R = Bridge.Reflection;
            var assemblies = ['UnityEngine', 'UnityEngine.UI', 'Assembly-CSharp'];
            var result = '';
            for (var a = 0; a < assemblies.length; a++) {
                try {
                    var types = R.getAssemblyTypes(R.load(assemblies[a]));
                    for (var i = 0; i < types.length; i++) {
                        var t = types[i];
                        if (t.$kind !== 'enum' && t.$kind !== 6) continue;
                        var name = t.$$name ? t.$$name.split('.').pop() : '?';
                        if (filter && name.toLowerCase().indexOf(filter.toLowerCase()) === -1) continue;
                        var data = pc.Debugger.Utils.getEnumData(t);
                        var vals = Object.keys(data).map(function(k) { return k + '=' + data[k]; }).join(', ');
                        result += name + ': ' + vals + '\n';
                    }
                } catch(e) { /* assembly not found, skip */ }
            }
            return result.trimEnd() || 'no enums found';
        },

        getTypeInfo: function(typeName) {
            if (typeof Bridge === 'undefined') return 'error: Bridge not available';
            var R = Bridge.Reflection;
            var assemblies = ['UnityEngine', 'UnityEngine.UI', 'Assembly-CSharp'];
            var type = null;
            for (var a = 0; a < assemblies.length; a++) {
                try {
                    var types = R.getAssemblyTypes(R.load(assemblies[a]));
                    for (var i = 0; i < types.length; i++) {
                        var n = types[i].$$name || '';
                        if (n === typeName || n.split('.').pop() === typeName) { type = types[i]; break; }
                    }
                } catch(e) {}
                if (type) break;
            }
            if (!type) return 'error: type not found: ' + typeName;
            var out = 'type: ' + (type.$$name || '?') + '\nkind: ' + (type.$kind || '?') + '\n';
            try { var base = R.getBaseType(type); if (base) out += 'inherits: ' + (base.$$name || '?') + '\n'; } catch(e) {}
            try { if (R.isValueType && R.isValueType(type)) out += 'valueType: true\n'; } catch(e) {}
            try { var ifaces = R.getInterfaces(type); if (ifaces && ifaces.length) out += 'interfaces: ' + ifaces.map(function(i) { return i.$$name || '?'; }).join(', ') + '\n'; } catch(e) {}
            var members = R.getMembers(type, 0, 28);
            if (!members || !members.length) return out + '(no members)';
            var fields = [], props = [], methods = [];
            for (var m = 0; m < members.length; m++) {
                var mem = members[m];
                if (mem.t === 4) fields.push(mem.n);
                else if (mem.t === 16) props.push(mem.n);
                else if (mem.t === 8) methods.push(mem.n);
            }
            if (fields.length) out += 'fields: ' + fields.join(', ') + '\n';
            if (props.length) out += 'props: ' + props.join(', ') + '\n';
            if (methods.length) out += 'methods: ' + methods.join(', ') + '\n';
            return out.trimEnd();
        },

        getAssemblies: function() {
            if (typeof Bridge === 'undefined') return 'error: Bridge not available';
            var names = Object.keys(Bridge.$assemblies || {});
            return names.join('\n') || 'no assemblies';
        },

        selectObject: function(path) {
            if (typeof pc === 'undefined' || !pc.Debugger) return 'error: pc.Debugger not available';
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            if (!node._guid) return 'error: no guid on node';
            pc.Debugger.GameState.selection = { type: 'GameObject', guid: node._guid };
            return 'selected: ' + path;
        },

        getSelection: function() {
            if (typeof pc === 'undefined' || !pc.Debugger) return 'error: pc.Debugger not available';
            var sel = pc.Debugger.GameState && pc.Debugger.GameState.selection;
            if (!sel) return 'none';
            if (sel.type === 'GameObject' && sel.guid) {
                var app = pc.Application.getApplication();
                var node = app && app.root.findByGuid(sel.guid);
                var path = node ? (function getPath(n) {
                    var parts = [];
                    while (n && n.name) { parts.unshift(n.name); n = n._parent; }
                    return parts.join('/');
                })(node) : '(unknown)';
                return 'type: GameObject\npath: ' + path + '\nguid: ' + sel.guid;
            }
            return 'type: ' + (sel.type || '?');
        },

        // ── Phase 12: Luna Debugger Deep Integration ─────────────────────────

        getDeepProperty: function(path, componentType, fieldPath) {
            var r = resolveNode(path); if (r.err) return r.err;
            var comps = getNodeComponents(r.node);
            for (var i = 0; i < comps.length; i++) {
                var shortType = getComponentTypeName(comps[i]);
                var fullType = getComponentFullType(comps[i]);
                if (shortType !== componentType && fullType !== componentType) continue;
                var uo = getUnityObject(comps[i]);
                if (!uo) return 'error: no unity object';
                if (typeof uo.__getValueAt === 'function') {
                    var val = uo.__getValueAt(fieldPath);
                    return val !== undefined ? String(serializeValue(val, 0)) : 'undefined';
                }
                // Fallback: manual path traversal
                var parts = fieldPath.split('/');
                var cur = uo;
                for (var p = 0; p < parts.length; p++) {
                    if (cur === null || cur === undefined) return 'error: path not found at: ' + parts[p];
                    cur = cur[parts[p]];
                }
                return serializeValue(cur, 0);
            }
            return 'error: component not found: ' + componentType;
        },

        editAnimatorState: function(path, stateHash, prop, value) {
            if (typeof pc === 'undefined' || !pc.Debugger || !pc.Debugger.Inspector ||
                !pc.Debugger.Inspector.AnimatorState)
                return 'error: requires Luna Debugger extension';
            var fa = findAnimator(path); if (fa.err) return fa.err;
            var animId = fa.animator.handle ? fa.animator.handle.$id : fa.animator.$id;
            pc.Debugger.Inspector.AnimatorState.update({
                path: animId + '/' + stateHash + '/' + prop,
                value: value
            });
            return 'ok: ' + prop + '=' + value;
        },

        logObject: function(path) {
            var de = requireDebugger('Log'); if (de) return de;
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            if (!node._guid) return 'error: no guid';
            pc.Debugger.Log.create({ gameObject: node._guid });
            return 'logged to console: ' + path;
        },

        logComponent: function(path, componentType) {
            var de = requireDebugger('Log'); if (de) return de;
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            if (!node._guid) return 'error: no guid';
            var comps = getNodeComponents(node);
            var comp = null;
            for (var i = 0; i < comps.length; i++) {
                if (getComponentTypeName(comps[i]) === componentType) { comp = comps[i]; break; }
            }
            if (!comp) return 'error: component not found: ' + componentType;
            pc.Debugger.Log.create({ gameObject: node._guid, component: comp.$id });
            return 'logged to console: ' + path + '/' + componentType;
        },

        enumerateDebugger: function() {
            if (typeof pc === 'undefined' || !pc.Debugger) return 'error: no debugger';
            try {
                var lines = [];
                var ns = Object.keys(pc.Debugger);
                for (var i = 0; i < ns.length; i++) {
                    var n = ns[i];
                    var obj = pc.Debugger[n];
                    if (!obj || typeof obj !== 'object') continue;
                    var fns = Object.keys(obj).filter(function(k) { return typeof obj[k] === 'function'; });
                    if (fns.length) lines.push(n + ': ' + fns.join(', '));
                }
                return lines.length ? lines.join('\n') : '(no namespaces)';
            } catch(e) { return 'error: ' + e.message; }
        },

        invokeDebugger: function(type, name, paramsJson) {
            return window.__luna_mcp.sendDebuggerMessage(type, name, paramsJson);
        },

        sendDebuggerMessage: function(type, name, paramsJson) {
            if (typeof pc === 'undefined' || !pc.Debugger) return 'error: no debugger';
            var params;
            try { params = JSON.parse(paramsJson || '{}'); } catch(e) { return 'error: invalid JSON params'; }
            var id = Math.floor(Math.random() * 999999999);
            return new Promise(function(resolve) {
                function handler(e) {
                    if (e.data && e.data.$$id === id) {
                        window.removeEventListener('message', handler);
                        resolve(e.data.response || 'null');
                    }
                }
                window.addEventListener('message', handler);
                window.postMessage({$$origin: 'LunaDebugger', $$id: id, type: type, name: name, params: params}, '*');
                setTimeout(function() { window.removeEventListener('message', handler); resolve('timeout'); }, 5000);
            });
        },

        getComponentFields: function(componentType) {
            if (typeof pc === 'undefined' || !pc.Debugger || !pc.Debugger.Components)
                return 'error: pc.Debugger not available';
            var def = pc.Debugger.Components[componentType];
            if (!def) return 'error: not found: ' + componentType;
            try {
                var fields = def.fields ? def.fields() : [];
                if (!fields || !fields.length) return '(no fields defined)';
                return fields.map(function(f) {
                    return f.label + ': ' + (f.type || '?') + (f.$$unsupportedField ? ' [unsupported]' : '');
                }).join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        getDeepLink: function(path, component) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            if (!node._guid) return 'error: no guid';
            if (!component) return 'gameobject:guid&' + node._guid;
            var comps = getNodeComponents(node);
            for (var i = 0; i < comps.length; i++) {
                if (getComponentTypeName(comps[i]) === component) {
                    return 'component:guid&' + node._guid + '&component&' + comps[i].$id;
                }
            }
            return 'error: component not found: ' + component;
        },

        auditMaterials: function() {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var issues = [];
            var ok = 0;
            function check(node, path) {
                var p = path ? path + '/' + node.name : node.name;
                var comps = getNodeComponents(node);
                for (var i = 0; i < comps.length; i++) {
                    var tn = getComponentTypeName(comps[i]);
                    if (tn.indexOf('Renderer') === -1) continue;
                    var uo = getUnityObject(comps[i]);
                    if (!uo) continue;
                    var mats = uo.sharedMaterials || uo.materials;
                    if (!mats) continue;
                    var items = mats._items || mats;
                    var count = mats._size !== undefined ? mats._size : items.length;
                    for (var m = 0; m < count; m++) {
                        var mat = items[m];
                        if (!mat) { issues.push('[!!] ' + p + ' | slot ' + m + ': NULL material'); continue; }
                        var shader = mat.shader;
                        var sn = shader ? getShaderName(shader) : 'NO SHADER';
                        if (!shader || sn === 'Hidden/InternalErrorShader') {
                            issues.push('[!!] ' + p + ' | ' + (mat.name || '?') + ' -> ' + sn);
                        } else { ok++; }
                    }
                }
                var ch = node._children || [];
                for (var c = 0; c < ch.length; c++) check(ch[c], p);
            }
            var children = scene.root._children || [];
            for (var i = 0; i < children.length; i++) check(children[i], '');
            if (!issues.length) return 'All materials OK (' + ok + ' checked)';
            return 'MATERIAL ISSUES (' + issues.length + '/' + (issues.length + ok) + '):\n' + issues.join('\n');
        },

        // Batch B: Scene Analysis
        raycast: function(x, y) {
            try {
                var cam = UnityEngine.Camera.main;
                if (!cam) return 'no camera';
                var ray = cam.ScreenPointToRay(new UnityEngine.Vector3(x, y, 0));
                var hit = new UnityEngine.RaycastHit.$ctor();
                if (UnityEngine.Physics.Raycast$4(ray, hit)) {
                    return buildPath(hit.collider.gameObject);
                }
                return 'no hit';
            } catch(e) { return 'error: ' + e.message; }
        },

        getCanvasInfo: function(path) {
            try {
                var scene = getScene();
                if (!scene) return 'no scene';
                var node = findByPath(scene.root, path);
                if (!node) return 'not found: ' + path;
                var comps = getNodeComponents(node);
                var lines = [];
                for (var i = 0; i < comps.length; i++) {
                    var c = comps[i];
                    var t = getComponentTypeName(c);
                    if (t === 'RectTransform') {
                        var ap = c.anchoredPosition; var sd = c.sizeDelta;
                        var amin = c.anchorMin; var amax = c.anchorMax; var piv = c.pivot;
                        lines.push('anchoredPosition: (' + (ap ? ap.x+', '+ap.y : '?') + ')');
                        lines.push('sizeDelta: (' + (sd ? sd.x+', '+sd.y : '?') + ')');
                        lines.push('anchorMin: (' + (amin ? amin.x+', '+amin.y : '?') + ')');
                        lines.push('anchorMax: (' + (amax ? amax.x+', '+amax.y : '?') + ')');
                        lines.push('pivot: (' + (piv ? piv.x+', '+piv.y : '?') + ')');
                    } else if (t === 'Canvas') {
                        lines.push('renderMode: ' + c.renderMode);
                        lines.push('sortingOrder: ' + c.sortingOrder);
                    }
                }
                return lines.length ? lines.join('\n') : '(no RectTransform/Canvas on ' + path + ')';
            } catch(e) { return 'error: ' + e.message; }
        },

        compareObjects: function(path1, path2) {
            try {
                var scene = getScene();
                if (!scene) return 'no scene';
                var n1 = findByPath(scene.root, path1);
                var n2 = findByPath(scene.root, path2);
                if (!n1) return 'not found: ' + path1;
                if (!n2) return 'not found: ' + path2;
                var lines = ['--- Transform ---'];
                var t1 = n1._transform; var t2 = n2._transform;
                function fv3(v) { return v ? '('+v.x.toFixed(2)+','+v.y.toFixed(2)+','+v.z.toFixed(2)+')' : '?'; }
                if (t1 && t2) {
                    lines.push('position: ' + fv3(t1.position) + ' vs ' + fv3(t2.position));
                    lines.push('rotation: ' + fv3(t1.eulerAngles) + ' vs ' + fv3(t2.eulerAngles));
                    lines.push('scale: ' + fv3(t1.lossyScale) + ' vs ' + fv3(t2.lossyScale));
                }
                var c1 = getNodeComponents(n1).map(getComponentTypeName);
                var c2 = getNodeComponents(n2).map(getComponentTypeName);
                lines.push('--- Components ---');
                var all = {};
                c1.forEach(function(k){ all[k]=1; }); c2.forEach(function(k){ all[k]=1; });
                Object.keys(all).forEach(function(k) {
                    var in1 = c1.indexOf(k) >= 0; var in2 = c2.indexOf(k) >= 0;
                    if (in1 && !in2) lines.push('- ' + k + ' (only in ' + path1 + ')');
                    else if (!in1 && in2) lines.push('+ ' + k + ' (only in ' + path2 + ')');
                });
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        // Batch D: Utility
        getAudioSources: function() {
            try {
                var scene = getScene();
                if (!scene) return 'no scene';
                var results = [];
                function walk(node, prefix) {
                    var p = prefix ? prefix + '/' + node.name : node.name;
                    var comps = getNodeComponents(node);
                    for (var i = 0; i < comps.length; i++) {
                        if (getComponentTypeName(comps[i]) === 'AudioSource') {
                            var a = comps[i];
                            var clip = a.clip ? (a.clip.name || 'clip') : 'none';
                            results.push(p + ': clip=' + clip + ' playing=' + (a.isPlaying||false) + ' vol=' + (a.volume||0).toFixed(1) + ' loop=' + (a.loop||false));
                        }
                    }
                    var ch = node._children || [];
                    for (var c = 0; c < ch.length; c++) walk(ch[c], p);
                }
                var children = scene.root._children || [];
                for (var i = 0; i < children.length; i++) walk(children[i], '');
                return results.length ? results.join('\n') : '(no AudioSource found)';
            } catch(e) { return 'error: ' + e.message; }
        },

        getPhysicsSettings: function() {
            try {
                var g = UnityEngine.Physics.gravity;
                var lines = ['gravity: (' + g.x.toFixed(2) + ', ' + g.y.toFixed(2) + ', ' + g.z.toFixed(2) + ')'];
                lines.push('fixedDeltaTime: ' + UnityEngine.Time.fixedDeltaTime.toFixed(4));
                lines.push('bounceThreshold: ' + UnityEngine.Physics.bounceThreshold);
                lines.push('defaultContactOffset: ' + UnityEngine.Physics.defaultContactOffset);
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        // Batch C: State Management
        watchProperty: function(path, comp, prop, interval, count) {
            return new Promise(function(resolve) {
                try {
                    var scene = getScene();
                    if (!scene) { resolve('no scene'); return; }
                    var node = findByPath(scene.root, path);
                    if (!node) { resolve('not found: ' + path); return; }
                    var comps = getNodeComponents(node);
                    var c = null;
                    for (var i = 0; i < comps.length; i++) {
                        if (getComponentTypeName(comps[i]) === comp) { c = comps[i]; break; }
                    }
                    if (!c) { resolve('component not found: ' + comp); return; }
                    var results = []; var idx = 0; var t0 = performance.now();
                    var id = setInterval(function() {
                        var val = c[prop];
                        results.push(Math.round(performance.now() - t0) + 'ms: ' + val);
                        if (++idx >= count) { clearInterval(id); resolve(results.join('\n')); }
                    }, interval);
                } catch(e) { resolve('error: ' + e.message); }
            });
        },

        snapshotState: function(name, path) {
            try {
                var scene = getScene();
                if (!scene) return 'no scene';
                var node = findByPath(scene.root, path);
                if (!node) return 'not found: ' + path;
                var t = node._transform;
                var snap = { path: path };
                // Use __createCopy() for deeper cloning when available
                if (t && typeof t.__createCopy === 'function') {
                    snap.transform = t.__createCopy();
                } else {
                    function fv3(v) { return v ? {x:v.x, y:v.y, z:v.z} : null; }
                    snap.transform = {
                        position: fv3(t && t.position), rotation: fv3(t && t.eulerAngles), scale: fv3(t && t.lossyScale)
                    };
                }
                window.__luna_snapshots = window.__luna_snapshots || {};
                window.__luna_snapshots[name] = snap;
                return 'saved: ' + name + ' (' + path + ')';
            } catch(e) { return 'error: ' + e.message; }
        },

        restoreState: function(name) {
            try {
                var snap = (window.__luna_snapshots || {})[name];
                if (!snap) return 'not found: ' + name;
                var scene = getScene();
                if (!scene) return 'no scene';
                var node = findByPath(scene.root, snap.path);
                if (!node) return 'object gone: ' + snap.path;
                var t = node._transform;
                if (t && snap.transform) {
                    var p = snap.transform.position;
                    var r = snap.transform.rotation;
                    if (p) t.position = new UnityEngine.Vector3(p.x, p.y, p.z);
                    if (r) t.eulerAngles = new UnityEngine.Vector3(r.x, r.y, r.z);
                    var s = snap.transform.scale;
                    if (s) t.localScale = new UnityEngine.Vector3(s.x, s.y, s.z);
                }
                return 'restored: ' + name;
            } catch(e) { return 'error: ' + e.message; }
        },

        // ── Phase 13: Performance & rendering tools ─────────────────────────

        getPerformanceMetrics: function() {
            try {
                var lines = ['PERFORMANCE:'];
                try {
                    var dt = UnityEngine.Time.deltaTime;
                    var fps = dt > 0 ? Math.round(1 / dt) : 0;
                    var rating = fps >= 30 ? 'GOOD' : fps >= 15 ? 'FAIR' : 'POOR';
                    lines.push('fps: ' + fps + ' (' + rating + ')');
                    lines.push('deltaTime: ' + (dt * 1000).toFixed(1) + 'ms');
                    lines.push('frameCount: ' + UnityEngine.Time.frameCount);
                    lines.push('timeScale: ' + UnityEngine.Time.timeScale);
                } catch(e) { lines.push('fps: unavailable'); }
                try {
                    var mem = performance.memory;
                    if (mem) {
                        var used = (mem.usedJSHeapSize / 1048576).toFixed(1);
                        var total = (mem.totalJSHeapSize / 1048576).toFixed(1);
                        var limit = (mem.jsHeapSizeLimit / 1048576).toFixed(0);
                        var warn = parseFloat(used) > 256 ? ' [!!]' : '';
                        lines.push('heap: ' + used + 'MB / ' + total + 'MB (limit ' + limit + 'MB)' + warn);
                    }
                } catch(e) {}
                try {
                    var t = performance.timing;
                    if (t && t.loadEventEnd > 0) {
                        var loadMs = t.loadEventEnd - t.navigationStart;
                        var lr = loadMs < 1200 ? 'GOOD' : loadMs < 3000 ? 'FAIR' : 'SLOW';
                        lines.push('loadTime: ' + loadMs + 'ms (' + lr + ')');
                    }
                } catch(e) {}
                try {
                    var app = pc.Application.getApplication();
                    if (app && app.stats && app.stats.frame) {
                        var f = app.stats.frame;
                        lines.push('drawCalls: ' + (f.drawCalls || 0));
                        lines.push('materialSwitches: ' + (f.materialSwitches || 0));
                    }
                } catch(e) {}
                try {
                    var _app2 = pc.Application.getApplication();
                    var _counters = _app2 && _app2.counters;
                    var _prev = _counters && _counters.previous;
                    if (_prev) {
                        var _times = _prev.times;
                        var _totalFrame = (_prev.frame || 0) * 1000;
                        var readTime = function(t, key) {
                            if (!t) return 0;
                            if (typeof Map !== 'undefined' && t instanceof Map) return (t.get(key) || 0) * 1000;
                            if (t[key] !== undefined) return (t[key] || 0) * 1000;
                            var syms = Object.getOwnPropertySymbols ? Object.getOwnPropertySymbols(t) : [];
                            for (var _si = 0; _si < syms.length; _si++) {
                                if (syms[_si].description === key) return (t[syms[_si]] || 0) * 1000;
                            }
                            return 0;
                        };
                        var _bdKeys = ['render','scripts','animations','animators','physics2d','physics'];
                        var _bdLines = ['frameBreakdown (last frame, ' + (_totalFrame || 0).toFixed(2) + 'ms):'];
                        for (var _bdi = 0; _bdi < _bdKeys.length; _bdi++) {
                            var _bdk = _bdKeys[_bdi];
                            var _bdv = readTime(_times, _bdk);
                            var _pct = _totalFrame > 0 ? Math.round(_bdv / _totalFrame * 100) : 0;
                            _bdLines.push('  ' + _bdk + ': ' + _bdv.toFixed(2) + 'ms (' + _pct + '%)');
                        }
                        _bdLines.push('  drawCalls: ' + (_prev.drawCalls || 0));
                        lines.push(_bdLines.join('\n'));
                    }
                } catch(e) {}
                try {
                    var si = UnityEngine.Shader.shaderIndex;
                    if (si) {
                        var count = Object.keys(si).length;
                        var sw = count > 20 ? ' [!!]' : '';
                        lines.push('shaderCount: ' + count + sw);
                    }
                } catch(e) {}
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        diagnoseRendering: function() {
            try {
                var lines = ['RENDERING DIAGNOSTICS:'];
                try {
                    var canvas = document.querySelector('canvas') ||
                        document.querySelector('iframe').contentDocument.querySelector('canvas');
                    if (canvas) {
                        var gl = canvas.getContext('webgl2');
                        if (gl) {
                            lines.push('webgl: 2.0');
                            lines.push('renderer: ' + gl.getParameter(gl.RENDERER));
                            lines.push('maxTextureSize: ' + gl.getParameter(gl.MAX_TEXTURE_SIZE));
                        } else {
                            gl = canvas.getContext('webgl');
                            lines.push('webgl: 1.0' + (gl ? '' : ' (no context!)'));
                            if (gl) {
                                lines.push('renderer: ' + gl.getParameter(gl.RENDERER));
                                lines.push('maxTextureSize: ' + gl.getParameter(gl.MAX_TEXTURE_SIZE));
                            }
                        }
                    } else { lines.push('webgl: no canvas found'); }
                } catch(e) { lines.push('webgl: error - ' + e.message); }
                try {
                    var si = UnityEngine.Shader.shaderIndex;
                    if (si) {
                        var names = Object.keys(si);
                        var errorCount = 0;
                        for (var i = 0; i < names.length; i++) {
                            var entry = si[names[i]];
                            if (entry && entry.compilationErrors && entry.compilationErrors.length) errorCount++;
                        }
                        var sw = names.length > 20 ? ' [!! >20 slows load]' : '';
                        lines.push('shaders: ' + names.length + sw);
                        if (errorCount) lines.push('shaderErrors: ' + errorCount + ' [!!]');
                    }
                } catch(e) {}
                try {
                    var app = pc.Application.getApplication();
                    if (app && app.stats && app.stats.frame)
                        lines.push('drawCalls: ' + (app.stats.frame.drawCalls || 0));
                } catch(e) {}
                try {
                    var scene = getScene();
                    if (scene) {
                        var camCount = 0, canvasCount = 0, lightCount = 0;
                        var _LIGHT_BUDGET = 4;
                        function countComps(node) {
                            var comps = getNodeComponents(node);
                            for (var i = 0; i < comps.length; i++) {
                                var tn = getComponentTypeName(comps[i]);
                                if (tn === 'Camera') camCount++;
                                if (tn === 'Canvas') canvasCount++;
                                if (tn === 'Light') lightCount++;
                            }
                            var ch = node._children || [];
                            for (var c = 0; c < ch.length; c++) countComps(ch[c]);
                        }
                        var ch = scene.root._children || [];
                        for (var i = 0; i < ch.length; i++) countComps(ch[i]);
                        lines.push('cameras: ' + camCount);
                        lines.push('canvases: ' + canvasCount);
                        var lw = lightCount > _LIGHT_BUDGET ? ' [!! light budget]' : '';
                        lines.push('lightCount: ' + lightCount + lw);
                    }
                } catch(e) {}
                try {
                    var _ai = UnityEngine.RenderSettings.ambientIntensity;
                    lines.push('ambientIntensity: ' + _ai);
                } catch(e) { lines.push('ambientIntensity: n/a'); }
                try {
                    lines.push('fog: ' + (UnityEngine.RenderSettings.fog ? 'on' : 'off'));
                } catch(e) { lines.push('fog: n/a'); }
                try {
                    lines.push('pixelLightCount: ' + UnityEngine.QualitySettings.pixelLightCount);
                } catch(e) { lines.push('pixelLightCount: n/a'); }
                try {
                    lines.push('shadowDistance: ' + UnityEngine.QualitySettings.shadowDistance);
                } catch(e) { lines.push('shadowDistance: n/a'); }
                try {
                    lines.push('vSyncCount: ' + UnityEngine.QualitySettings.vSyncCount);
                } catch(e) { lines.push('vSyncCount: n/a'); }
                try {
                    var w = UnityEngine.Screen.width, h = UnityEngine.Screen.height;
                    lines.push('screenRes: ' + w + 'x' + h);
                    var cv = document.querySelector('canvas') ||
                        document.querySelector('iframe').contentDocument.querySelector('canvas');
                    if (cv) {
                        lines.push('canvasRes: ' + cv.width + 'x' + cv.height);
                        if (cv.width !== w || cv.height !== h) lines.push('resMismatch: yes [!!]');
                    }
                } catch(e) {}
                try {
                    lines.push('antiAliasing: ' + UnityEngine.QualitySettings.antiAliasing + 'x');
                } catch(e) {}
                lines.push('(use get_console level=E for rendering errors)');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        auditTextures: function() {
            try {
                var scene = getScene();
                if (!scene) return 'error: no scene';
                var seen = {}, textures = [];
                function extractTextures(mat) {
                    if (!mat) return;
                    var dk = Object.keys(mat).find(function(k) { return k.indexOf('__') === 0; });
                    var uo = dk ? mat[dk] : mat;
                    var keys = Object.keys(uo);
                    for (var i = 0; i < keys.length; i++) {
                        try {
                            var val = uo[keys[i]];
                            if (val && val.width && val.height && val.name !== undefined) {
                                var id = val.$id || (val.GetInstanceID && val.GetInstanceID()) || keys[i];
                                if (seen[id]) continue;
                                seen[id] = true;
                                var w = val.width, h = val.height;
                                var fmt = val.format !== undefined ? val.format : '?';
                                var bpp = (typeof fmt === 'number' && fmt > 10) ? 2 : 4;
                                var memKB = Math.round(w * h * bpp / 1024);
                                var npot = (w & (w-1)) !== 0 || (h & (h-1)) !== 0;
                                textures.push({ name: val.name || '(unnamed)', w: w, h: h,
                                    fmt: fmt, memKB: memKB, warn: ((w > 1024 || h > 1024) ? ' [!!]' : '') + (npot ? ' [NPOT]' : '') });
                            }
                        } catch(e) {}
                    }
                }
                function walk(node) {
                    var comps = getNodeComponents(node);
                    for (var i = 0; i < comps.length; i++) {
                        if (getComponentTypeName(comps[i]).indexOf('Renderer') === -1) continue;
                        var uo = getUnityObject(comps[i]);
                        if (!uo) continue;
                        var mats = uo.sharedMaterials || uo.materials;
                        if (!mats) continue;
                        var items = mats._items || mats;
                        var count = mats._size !== undefined ? mats._size : items.length;
                        for (var m = 0; m < count; m++) extractTextures(items[m]);
                    }
                    var ch = node._children || [];
                    for (var c = 0; c < ch.length; c++) walk(ch[c]);
                }
                var ch = scene.root._children || [];
                for (var i = 0; i < ch.length; i++) walk(ch[i]);
                if (!textures.length) return 'no textures found (renderers may use procedural materials)';
                textures.sort(function(a, b) { return b.memKB - a.memKB; });
                var totalKB = 0, oversized = 0;
                var lines = ['TEXTURES (' + textures.length + '):'];
                for (var i = 0; i < textures.length; i++) {
                    var t = textures[i];
                    totalKB += t.memKB;
                    if (t.warn) oversized++;
                    lines.push(t.w + 'x' + t.h + ' ' + t.memKB + 'KB ' + t.name + ' fmt:' + t.fmt + t.warn);
                }
                lines.push('---');
                lines.push('total: ' + (totalKB / 1024).toFixed(1) + 'MB est.');
                if (oversized) lines.push('oversized (>1024): ' + oversized + ' [!!]');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        getRenderStats: function() {
            try {
                var app = pc.Application.getApplication();
                if (!app || !app.stats) return 'error: pc.app.stats not available';
                var f = app.stats.frame;
                var lines = [];
                lines.push('FPS: ' + (f.fps || 0));
                lines.push('triangles: ' + (f.triangles || 0));
                lines.push('vertices: ' + (f.vertices || f.otherPrimitives || 0));
                lines.push('draw calls: ' + (f.drawCalls || 0));
                lines.push('material switches: ' + (f.materialSwitches || 0));
                lines.push('shaders compiled: ' + (f.shaders || 0));
                lines.push('materials: ' + (f.materials || 0));
                lines.push('cameras: ' + (f.cameras || 0));
                lines.push('shadow updates: ' + (f.shadowMapUpdates || 0));
                lines.push('shadow casters: ' + (f.shadowDrawCalls || 0));
                lines.push('skinned meshes: ' + (f.skinDrawCalls || 0));
                lines.push('forward time: ' + (f.forwardTime || 0).toFixed(1) + 'ms');
                lines.push('sort time: ' + (f.sortTime || 0).toFixed(1) + 'ms');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        getVramUsage: function() {
            try {
                var gd = pc.Application.getApplication().graphicsDevice;
                var vram = gd._vram || {};
                var total = (vram.tex || 0) + (vram.vb || 0) + (vram.ib || 0) + (vram.ub || 0);
                var mb = function(b) { return (b / 1048576).toFixed(1) + 'MB'; };
                var lines = [];
                lines.push('VRAM total: ' + mb(total));
                lines.push('  textures: ' + mb(vram.tex || 0));
                lines.push('  vertex buffers: ' + mb(vram.vb || 0));
                lines.push('  index buffers: ' + mb(vram.ib || 0));
                if (vram.ub) lines.push('  uniform buffers: ' + mb(vram.ub));
                lines.push('GPU: ' + (gd.webgl2 ? 'WebGL 2' : 'WebGL 1'));
                lines.push('max texture: ' + gd.maxTextureSize);
                lines.push('precision: ' + (gd.precision || 'unknown'));
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        getGpuInfo: function() {
            try {
                var gd = pc.Application.getApplication().graphicsDevice;
                var gl = gd.gl;
                var dbg = gl.getExtension('WEBGL_debug_renderer_info');
                var lines = [];
                lines.push('WebGL: ' + (gd.webgl2 ? '2.0' : '1.0'));
                if (dbg) {
                    lines.push('vendor: ' + gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL));
                    lines.push('renderer: ' + gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL));
                }
                lines.push('max texture: ' + gd.maxTextureSize);
                lines.push('max textures: ' + gd.maxTextures);
                lines.push('float textures: ' + !!gd.extTextureFloat);
                lines.push('precision: ' + (gd.precision || 'unknown'));
                lines.push('canvas: ' + gd.width + 'x' + gd.height);
                lines.push('pixel ratio: ' + gd.maxPixelRatio);
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        stepFrame: function() {
            if (typeof UnityEngine === 'undefined') return 'error: no Unity runtime';
            UnityEngine.Time.timeScale = 1;
            return new Promise(function(resolve) {
                requestAnimationFrame(function() {
                    requestAnimationFrame(function() {
                        UnityEngine.Time.timeScale = 0;
                        resolve('stepped 1 frame (frame ' + UnityEngine.Time.frameCount + ')');
                    });
                });
            });
        },

        toggleActive: function(path) {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var node = findByPath(scene.root, path);
            if (!node) return 'error: not found: ' + path;
            node._activeSelf = !node._activeSelf;
            return (node._activeSelf ? 'activated' : 'deactivated') + ': ' + path;
        },

        moveCamera: function(x, y, z) {
            var cam = null;
            if (typeof UnityEngine !== 'undefined') {
                cam = UnityEngine.GameObject.Find('$$EditorCamera');
                if (!cam) cam = UnityEngine.Camera.main ? UnityEngine.Camera.main.gameObject : null;
            }
            if (!cam) return 'error: no camera found';
            cam.transform.position = new UnityEngine.Vector3(x, y, z);
            return 'camera moved to (' + x + ', ' + y + ', ' + z + ')';
        },

        auditBuildSize: function() {
            try {
                var entries = performance.getEntriesByType('resource');
                var scripts = [], images = [], audio = [], other = [];
                var imgExts = /\.(png|jpg|jpeg|webp|ktx|basis)(\?|$)/i;
                var audioExts = /\.(mp3|ogg|wav|aac)(\?|$)/i;
                var jsExt = /\.js(\?|$)/i;

                entries.forEach(function(e) {
                    var kb = Math.round((e.transferSize || e.encodedBodySize || 0) / 1024);
                    var name = e.name.split('/').pop().split('?')[0];
                    var item = {name: name, kb: kb, url: e.name};
                    if (jsExt.test(e.name)) scripts.push(item);
                    else if (imgExts.test(e.name)) images.push(item);
                    else if (audioExts.test(e.name)) audio.push(item);
                    else other.push(item);
                });

                scripts.sort(function(a, b) { return b.kb - a.kb; });

                function sumKB(arr) { return arr.reduce(function(s, i) { return s + i.kb; }, 0); }
                function fmtMB(kb) { return (kb / 1024).toFixed(1) + 'MB'; }

                var totalKB = sumKB(scripts) + sumKB(images) + sumKB(audio) + sumKB(other);
                var lines = ['BUILD SIZE: ' + fmtMB(totalKB) + ' total'];

                var scriptKB = sumKB(scripts);
                lines.push('SCRIPTS (' + fmtMB(scriptKB) + '):');
                scripts.forEach(function(s) {
                    var flag = s.kb > 1000 ? '[!!]' : '[OK]';
                    lines.push(flag + ' ' + s.name + '  ' + s.kb + 'KB');
                });

                lines.push('IMAGES (' + fmtMB(sumKB(images)) + ', ' + images.length + ' files)');
                lines.push('AUDIO (' + fmtMB(sumKB(audio)) + ', ' + audio.length + ' files)');
                if (other.length) lines.push('OTHER (' + fmtMB(sumKB(other)) + ', ' + other.length + ' files)');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        auditUnusedModules: function() {
            try {
                var entries = performance.getEntriesByType('resource');
                var scene = getScene();

                // count component types in scene
                function countComponents(typePart) {
                    if (!scene) return 0;
                    var count = 0;
                    walkScene(function(node) {
                        getNodeComponents(node).forEach(function(c) {
                            var t = getComponentTypeName(c);
                            if (t.indexOf(typePart) !== -1) count++;
                        });
                    });
                    return count;
                }

                var MODULES = [
                    {pat: /TextMeshPro/i, check: 'TMP', desc: 'TMP_Text/TMP_InputField'},
                    {pat: /physics2d/i, check: '2D', desc: '2D physics (Rigidbody2D, Collider2D)'},
                    {pat: /physics3d/i, check: '3D', desc: '3D physics (Rigidbody, Collider)'},
                    {pat: /particle[-_]system/i, check: 'Particle', desc: 'ParticleSystem'},
                    {pat: /DOTween/i, check: 'Tween', desc: 'DOTween'},
                    {pat: /mecanim/i, check: 'Animator', desc: 'Animator'},
                    {pat: /UniversalRenderPipeline/i, check: 'URP', desc: 'URP'},
                ];

                // group multi-part modules (e.g. physics2d-0.js + physics2d-1.js)
                var groups = {};
                entries.forEach(function(e) {
                    if (!/\.js(\?|$)/i.test(e.name)) return;
                    var kb = Math.round((e.transferSize || e.encodedBodySize || 0) / 1024);
                    var name = e.name.split('/').pop().split('?')[0];
                    MODULES.forEach(function(m) {
                        if (m.pat.test(name)) {
                            var key = m.check;
                            if (!groups[key]) groups[key] = {m: m, files: [], totalKB: 0};
                            groups[key].files.push(name);
                            groups[key].totalKB += kb;
                        }
                    });
                });

                var lines = ['MODULE USAGE ANALYSIS:'];
                var savingsKB = 0;

                Object.keys(groups).forEach(function(key) {
                    var g = groups[key];
                    var count = countComponents(key);
                    var fileList = g.files.join(' + ');
                    var kb = g.totalKB;
                    if (count === 0) {
                        lines.push('[!!] ' + fileList + ' (' + kb + 'KB) — NO ' + g.m.desc + '. REMOVE to save ' + (kb/1024).toFixed(1) + 'MB');
                        savingsKB += kb;
                    } else {
                        lines.push('[OK] ' + fileList + ' (' + kb + 'KB) — ' + count + ' ' + g.m.desc + ' active');
                    }
                });

                if (!Object.keys(groups).length) lines.push('(no known engine modules detected in resources)');
                lines.push('');
                var totalKB = entries.reduce(function(s, e) { return s + Math.round((e.transferSize || 0)/1024); }, 0);
                var pct = totalKB ? Math.round(savingsKB / totalKB * 100) : 0;
                lines.push('POTENTIAL SAVINGS: ' + (savingsKB/1024).toFixed(1) + 'MB (' + pct + '% of build)');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        auditUnusedAssets: function() {
            try {
                var entries = performance.getEntriesByType('resource');
                var scene = getScene();

                var usedTextures = {}, usedAudio = {}, usedFonts = {};

                if (scene) {
                    walkScene(function(node) {
                        getNodeComponents(node).forEach(function(c) {
                            // textures via material
                            if (c._material && c._material._texture) {
                                var t = c._material._texture;
                                if (t && t.name) usedTextures[t.name] = true;
                            }
                            // audio clips
                            if (c._clip && c._clip.name) usedAudio[c._clip.name] = true;
                            // fonts
                            if (c._font && c._font.name) usedFonts[c._font.name] = true;
                        });
                    });
                }

                var imgExts = /\.(png|jpg|jpeg|webp|ktx|basis)(\?|$)/i;
                var audioExts = /\.(mp3|ogg|wav|aac)(\?|$)/i;
                var fontExts = /\.(woff2?|ttf|otf)(\?|$)/i;

                var unusedLines = [], usedTex = 0, usedAud = 0, usedFont = 0;
                var unusedKB = 0;

                entries.forEach(function(e) {
                    var name = e.name.split('/').pop().split('?')[0];
                    var kb = Math.round((e.transferSize || e.encodedBodySize || 0) / 1024);
                    var baseName = name.replace(/\.[^.]+$/, '');

                    if (imgExts.test(name)) {
                        if (usedTextures[baseName] || usedTextures[name]) { usedTex++; }
                        else { unusedLines.push('[!!] ' + name + ' (' + kb + 'KB) — not referenced by any renderer material'); unusedKB += kb; }
                    } else if (audioExts.test(name)) {
                        if (usedAudio[baseName] || usedAudio[name]) { usedAud++; }
                        else { unusedLines.push('[!!] ' + name + ' (' + kb + 'KB) — not referenced by any AudioSource'); unusedKB += kb; }
                    } else if (fontExts.test(name)) {
                        if (usedFonts[baseName] || usedFonts[name]) { usedFont++; }
                        else { unusedLines.push('[!!] ' + name + ' (' + kb + 'KB) — not referenced by any Text/TMP component'); unusedKB += kb; }
                    }
                });

                var lines = ['UNUSED ASSETS:'];
                if (unusedLines.length) unusedLines.forEach(function(l) { lines.push(l); });
                else lines.push('(none detected)');
                lines.push('USED: ' + usedTex + ' textures, ' + usedAud + ' audio clips, ' + usedFont + ' fonts');
                lines.push('POTENTIALLY UNUSED: ' + unusedLines.length + ' assets (' + unusedKB + 'KB total)');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        diagnoseBottlenecks: function() {
            try {
                var lines = ['PERFORMANCE BOTTLENECK ANALYSIS:'];
                var issues = [];
                // 1. Frame stats
                try {
                    var app = pc.Application.getApplication();
                    var f = app.stats.frame;
                    var gd = app.graphicsDevice;
                    var fps = f.fps || 0;
                    var dc = f.drawCalls || 0;
                    var tri = f.triangles || 0;
                    var verts = f.vertices || 0;
                    var matSw = f.materialSwitches || 0;
                    var shaderSw = gd._shaderSwitchesPerFrame || 0;
                    var cams = f.cameras || 0;
                    var shadows = f.shadowMapUpdates || 0;
                    lines.push('FPS: ' + fps + ' | draw calls: ' + dc + ' | triangles: ' + tri + ' | mat switches: ' + matSw);
                    // Thresholds from Luna docs + PlayCanvas best practices
                    if (fps < 30) issues.push('[CRITICAL] FPS ' + fps + ' < 30 — target is 30+ for playable ads');
                    if (dc > 100) issues.push('[HIGH] Draw calls ' + dc + ' > 100 — batch materials, use texture atlases, enable static batching');
                    if (dc > 50 && dc <= 100) issues.push('[MEDIUM] Draw calls ' + dc + ' — consider material merging for <50 target');
                    if (tri > 100000) issues.push('[HIGH] Triangles ' + tri + ' > 100K — simplify meshes, use LOD, try Luna Mesh Simplification tool');
                    if (matSw > 100) issues.push('[HIGH] Material switches ' + matSw + ' > 100 — sort by material, use shared materials, texture atlases');
                    if (matSw > 50 && matSw <= 100) issues.push('[MEDIUM] Material switches ' + matSw + ' — reduce unique materials');
                    if (cams > 2) issues.push('[MEDIUM] ' + cams + ' cameras — each camera = extra render pass. Merge or disable unused.');
                    if (shadows > 0) issues.push('[INFO] ' + shadows + ' shadow updates/frame — shadows are expensive on mobile. Consider baked.');
                } catch(e) {}
                // 2. Shaders
                try {
                    var si = UnityEngine.Shader.shaderIndex;
                    if (si) {
                        var count = Object.keys(si).length;
                        if (count > 20) issues.push('[HIGH] ' + count + ' shaders > 20 max — replace heavy shaders with Mobile/SimpleLit');
                        else if (count > 15) issues.push('[MEDIUM] ' + count + ' shaders — approaching 20 limit');
                    }
                } catch(e) {}
                // 3. Memory
                try {
                    var mem = performance.memory;
                    if (mem) {
                        var usedMB = mem.usedJSHeapSize / 1048576;
                        if (usedMB > 256) issues.push('[HIGH] JS heap ' + usedMB.toFixed(0) + 'MB > 256MB — optimize textures, reduce scene complexity');
                        else if (usedMB > 150) issues.push('[MEDIUM] JS heap ' + usedMB.toFixed(0) + 'MB — monitor for growth');
                    }
                } catch(e) {}
                // 4. Textures
                try {
                    var gd2 = pc.Application.getApplication().graphicsDevice;
                    var vram = gd2._vram || {};
                    var texMB = (vram.tex || 0) / 1048576;
                    if (texMB > 50) issues.push('[HIGH] Texture VRAM ' + texMB.toFixed(0) + 'MB > 50MB — compress textures, reduce sizes to 512x512');
                    else if (texMB > 30) issues.push('[MEDIUM] Texture VRAM ' + texMB.toFixed(0) + 'MB — consider JPEG/WebP compression');
                } catch(e) {}
                // 5. Load time
                try {
                    var t = performance.timing;
                    if (t && t.loadEventEnd > 0) {
                        var loadMs = t.loadEventEnd - t.navigationStart;
                        if (loadMs > 3000) issues.push('[HIGH] Load time ' + loadMs + 'ms > 3s — reduce build size, optimize shader compilation');
                        else if (loadMs > 1200) issues.push('[MEDIUM] Load time ' + loadMs + 'ms > 1.2s target');
                    }
                } catch(e) {}
                // Sort by severity
                var order = {'[CRITICAL]': 0, '[HIGH]': 1, '[MEDIUM]': 2, '[INFO]': 3};
                issues.sort(function(a, b) { return (order[a.substring(0,10)] || 9) - (order[b.substring(0,10)] || 9); });
                if (issues.length) {
                    lines.push('');
                    for (var i = 0; i < issues.length; i++) lines.push((i+1) + '. ' + issues[i]);
                    lines.push('');
                    lines.push('SUMMARY: ' + issues.filter(function(x){return x.indexOf('[CRITICAL]')===0}).length + ' critical, ' +
                        issues.filter(function(x){return x.indexOf('[HIGH]')===0}).length + ' high, ' +
                        issues.filter(function(x){return x.indexOf('[MEDIUM]')===0}).length + ' medium');
                } else {
                    lines.push('No bottlenecks detected. Performance looks good.');
                }
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        visualSummary: function(detail) {
            try {
                var cam = UnityEngine.Camera.main;
                if (!cam) return 'no main camera';
                var W = cam.pixelWidth || 800, H = cam.pixelHeight || 1280;
                var visible = [];
                walkScene(function(node) {
                    if (!isActiveChain(node) || isZeroScale(node)) return;
                    var comps = getNodeComponents(node);
                    var r = findRenderer(comps);
                    if (!r) return;
                    var uo = getUnityObject(r);
                    if (uo && uo.enabled === false) return;
                    var b = getBounds(r);
                    var sp = screenPct(cam, b, W, H);
                    if (!sp) return;
                    visible.push({ name: node.name, bucket: sp.bucket, sizePct: sp.sizePct, kind: kindOf(comps), state: animState(comps) });
                });
                var ui = collectUICanvases();
                var endCard = detectEndCard(visible, ui);
                if (detail === 'ui_only') return formatUIOnly(ui, endCard);
                if (detail === 'full') return formatFull(visible, ui, endCard, fps(), W, H);
                return formatCompact(visible, ui, endCard, fps(), W, H);
            } catch(e) { return 'error: ' + e.message; }
        },

        visualDiff: function(prevId) {
            try {
                var snap = this.visualSummary('compact');
                var key = prevId || 'last';
                var prev = __visualCache[key];
                cacheSet('last', snap);
                if (prevId) cacheSet(prevId, snap);
                if (!prev) return 'no prev: ' + snap;
                return diffSnapshots(prev, snap);
            } catch(e) { return 'error: ' + e.message; }
        },

        getBuildRecommendations: function() {
            try {
                var self = window.__luna_mcp;
                var buildReport = self.auditBuildSize();
                var moduleReport = self.auditUnusedModules();
                var assetReport = self.auditUnusedAssets();

                var lines = ['BUILD OPTIMIZATION RECOMMENDATIONS:'];
                var idx = 1;

                // Extract [!!] lines from module report
                moduleReport.split('\n').forEach(function(l) {
                    if (l.indexOf('[!!]') === 0) {
                        lines.push(idx++ + '. [CRITICAL] ' + l.substring(5));
                    }
                });

                // Extract [!!] lines from asset report
                assetReport.split('\n').forEach(function(l) {
                    if (l.indexOf('[!!]') === 0) {
                        lines.push(idx++ + '. [WARNING] ' + l.substring(5));
                    }
                });

                // Extract oversized scripts
                buildReport.split('\n').forEach(function(l) {
                    if (l.indexOf('[!!]') === 0) {
                        lines.push(idx++ + '. [INFO] Large script: ' + l.substring(5));
                    }
                });

                // Total size warning
                var sizeMatch = buildReport.match(/BUILD SIZE: ([\d.]+)MB/);
                if (sizeMatch) {
                    var mb = parseFloat(sizeMatch[1]);
                    if (mb > 5) lines.push(idx++ + '. [INFO] Build is ' + mb + 'MB — exceeds 5MB limit for most ad networks');
                }

                if (lines.length === 1) lines.push('No issues found. Build looks optimized.');
                return lines.join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        collectInteractiveRects: function(maxN) {
            // Returns "path|x|y|w|h|kind\n..." for interactive objects in scene.
            // Detects: Button, Toggle, Slider, EventTrigger, Collider2D (raycast), custom onClick.
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var maxCount = maxN || 20;
            var out = [];

            // iframe offset for coordinate mapping
            var iframeOffX = 0, iframeOffY = 0, scaleX = 1, scaleY = 1;
            try {
                var iframe = document.querySelector('iframe');
                if (iframe) {
                    var r = iframe.getBoundingClientRect();
                    iframeOffX = r.left; iframeOffY = r.top;
                    scaleX = iframe.offsetWidth > 0 ? r.width / iframe.offsetWidth : 1;
                    scaleY = iframe.offsetHeight > 0 ? r.height / iframe.offsetHeight : 1;
                }
            } catch(e) {}

            function detectKind(comps) {
                for (var i = 0; i < comps.length; i++) {
                    var t = getComponentTypeName(comps[i]);
                    if (t === 'Button') return 'Button';
                    if (t === 'Toggle') return 'Toggle';
                    if (t === 'Slider') return 'Slider';
                    if (t === 'EventTrigger') return 'EventTrigger';
                    if (t === 'Collider2D' || t === 'BoxCollider2D' || t === 'CircleCollider2D' || t === 'PolygonCollider2D') {
                        try { if (comps[i].raycastTarget !== false) return 'Collider2D'; } catch(e) { return 'Collider2D'; }
                    }
                }
                // custom onClick / onPointerDown check
                for (var j = 0; j < comps.length; j++) {
                    var c = comps[j];
                    if (c && (c.onClick !== undefined || c.onPointerDown !== undefined || c.OnPointerClick !== undefined)) return 'Custom';
                }
                return null;
            }

            function computeRect(node, comps) {
                // Try RectTransform (UI)
                for (var i = 0; i < comps.length; i++) {
                    var t = getComponentTypeName(comps[i]);
                    if (t !== 'RectTransform') continue;
                    try {
                        var rt = comps[i];
                        var uo = rt[Object.keys(rt).find(function(k) { return k.indexOf('__') === 0; })];
                        if (!uo) break;
                        // GetWorldCorners via rect + transform
                        var corners = [];
                        if (uo.GetWorldCorners) {
                            var c4 = [null, null, null, null];
                            uo.GetWorldCorners(c4);
                            corners = c4;
                        } else if (uo.rect && uo.localToWorldMatrix) {
                            var rec = uo.rect; var m = uo.localToWorldMatrix;
                            corners = [
                                {x: rec.x, y: rec.y, z: 0},
                                {x: rec.x, y: rec.yMax, z: 0},
                                {x: rec.xMax, y: rec.yMax, z: 0},
                                {x: rec.xMax, y: rec.y, z: 0},
                            ].map(function(p) {
                                return {x: m.m00*p.x+m.m01*p.y+m.m03, y: m.m10*p.x+m.m11*p.y+m.m13, z: 0};
                            });
                        }
                        if (!corners || !corners[0]) break;
                        var cam = UnityEngine.Camera.main;
                        var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                        var sw = window.screen ? window.screen.width : 800;
                        var sh = window.screen ? window.screen.height : 600;
                        for (var ci = 0; ci < 4; ci++) {
                            var sp;
                            if (cam && cam.WorldToScreenPoint) {
                                sp = cam.WorldToScreenPoint(corners[ci]);
                            } else {
                                sp = {x: corners[ci].x, y: corners[ci].y, z: 0};
                            }
                            var px = (sp.x + iframeOffX / scaleX) * scaleX;
                            var py = (sh - sp.y + iframeOffY / scaleY) * scaleY;
                            if (px < minX) minX = px; if (px > maxX) maxX = px;
                            if (py < minY) minY = py; if (py > maxY) maxY = py;
                        }
                        if (maxX > minX && maxY > minY) return {x: Math.round(minX), y: Math.round(minY), w: Math.round(maxX-minX), h: Math.round(maxY-minY)};
                    } catch(e) {}
                    break;
                }
                // Fallback: try Renderer bounds
                try {
                    var cam2 = UnityEngine.Camera.main;
                    if (!cam2) return null;
                    var go = node.gameObject || node;
                    var rend = go.GetComponent && go.GetComponent('Renderer');
                    if (!rend) return null;
                    var b = rend.bounds;
                    var c8 = [
                        {x:b.min.x,y:b.min.y,z:b.min.z},{x:b.max.x,y:b.min.y,z:b.min.z},
                        {x:b.min.x,y:b.max.y,z:b.min.z},{x:b.max.x,y:b.max.y,z:b.min.z},
                        {x:b.min.x,y:b.min.y,z:b.max.z},{x:b.max.x,y:b.min.y,z:b.max.z},
                        {x:b.min.x,y:b.max.y,z:b.max.z},{x:b.max.x,y:b.max.y,z:b.max.z},
                    ];
                    var sh2 = window.screen ? window.screen.height : 600;
                    var mnX = Infinity, mnY = Infinity, mxX = -Infinity, mxY = -Infinity;
                    for (var bi = 0; bi < 8; bi++) {
                        var sp2 = cam2.WorldToScreenPoint(c8[bi]);
                        if (sp2.z < 0) continue;
                        var px2 = sp2.x * scaleX + iframeOffX;
                        var py2 = (sh2 - sp2.y) * scaleY + iframeOffY;
                        if (px2 < mnX) mnX = px2; if (px2 > mxX) mxX = px2;
                        if (py2 < mnY) mnY = py2; if (py2 > mxY) mxY = py2;
                    }
                    if (mxX > mnX && mxY > mnY) return {x: Math.round(mnX), y: Math.round(mnY), w: Math.round(mxX-mnX), h: Math.round(mxY-mnY)};
                } catch(e) {}
                return null;
            }

            function visit(node, parentPath) {
                if (!node || node._activeSelf === false) return;
                var path = parentPath ? parentPath + '/' + node.name : node.name;
                var comps = getNodeComponents(node);
                var kind = detectKind(comps);
                if (kind) {
                    var rect = computeRect(node, comps);
                    if (rect) out.push(path + '|' + rect.x + '|' + rect.y + '|' + rect.w + '|' + rect.h + '|' + kind);
                }
                var children = node._children || [];
                for (var ci = 0; ci < children.length; ci++) visit(children[ci], path);
            }

            try {
                visit(scene.root, '');
            } catch(e) { return 'error: ' + e.message; }
            return out.slice(0, maxCount).join('\n');
        },

        sampleMotionTimeline: function(path, durMs, samples) {
            var r = resolveNode(path);
            if (r.err) return JSON.stringify({error: r.err});
            var node = r.node;
            var animator = null, ps = null;
            var comps = getNodeComponents(node);
            for (var i = 0; i < comps.length; i++) {
                var t = getComponentTypeName(comps[i]);
                if (t.indexOf('Animator') >= 0) animator = comps[i];
                if (t.indexOf('ParticleSystem') >= 0) ps = comps[i];
            }
            var out = [];
            var start = performance.now();
            var step = Math.max(1, durMs / samples);
            return new Promise(function(resolve) {
                function tick(i) {
                    var t = ((performance.now() - start) / 1000).toFixed(2);
                    var pos = node._localPosition || (node.transform && node.transform.localPosition) || {x:0,y:0,z:0};
                    var nt = null;
                    if (animator && animator.GetCurrentAnimatorStateInfo) {
                        try { var info = animator.GetCurrentAnimatorStateInfo(0); nt = info && info.normalizedTime; } catch(e) {}
                    }
                    var pcount = (ps && ps.particleCount != null) ? ps.particleCount : null;
                    out.push('t=' + t + ' p=(' + (+pos.x||0).toFixed(1) + ',' + (+pos.y||0).toFixed(1) + ') nt=' + (nt!==null?nt.toFixed(2):'-') + ' pc=' + (pcount===null?'-':pcount));
                    if (i >= samples) {
                        var positions = out.map(function(line) { var m = line.match(/p=\((\-?[\d.]+),(\-?[\d.]+)\)/); return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0,0]; });
                        var ys = positions.map(function(p) { return p[1]; });
                        var dY = Math.max.apply(null, ys) - Math.min.apply(null, ys);
                        resolve(out.join('\n') + '\nSUMMARY: dY=' + dY.toFixed(1));
                        return;
                    }
                    setTimeout(function(){ tick(i+1); }, step);
                }
                tick(1);
            });
        },
        getSourceForClass: function(className) {
            // Search loaded scripts in the iframe for class/function definition matching className.
            // Returns matched source block (≤4000 chars) or empty string if not found.
            try {
                var w = (typeof $scene !== 'undefined') ? window :
                    (document.querySelector('iframe') && document.querySelector('iframe').contentWindow) || window;
                var scripts = w.document ? Array.from(w.document.querySelectorAll('script')) : [];
                for (var i = 0; i < scripts.length; i++) {
                    var src = scripts[i].textContent || '';
                    var idx = src.indexOf(className);
                    if (idx < 0) continue;
                    // Return surrounding context (~2000 chars each side)
                    var start = Math.max(0, idx - 200);
                    var end = Math.min(src.length, idx + 3800);
                    return src.slice(start, end);
                }
                return '';
            } catch(e) { return 'error: ' + e.message; }
        },
        diagnoseText: function(path) {
            try {
                var r = resolveNode(path);
                if (r.err) return 'error: ' + r.err;
                var node = r.node;
                var comps = getNodeComponents(node);
                var TMP_TYPES = {'TextMeshProUGUI': 1, 'TextMeshPro': 1, 'TMP_Text': 1};
                var comp = null;
                for (var i = 0; i < comps.length; i++) {
                    if (TMP_TYPES[getComponentTypeName(comps[i])]) { comp = comps[i]; break; }
                }
                if (!comp) return 'error: no TMP component on ' + path;
                var t = getUnityObject(comp);
                try { t.ForceMeshUpdate(false, false); } catch(_e) {}
                var text = '';
                try { text = t.text; } catch(_e) {}
                var overflow = false, overflowIdx = -1, overflowMode = '?';
                try { overflow = !!t.isTextOverflowing; } catch(_e) {}
                try { overflowIdx = t.firstOverflowCharacterIndex; } catch(_e) {}
                try { overflowMode = t.overflowMode; } catch(_e) {}
                var richText = false;
                try { richText = !!t.richText; } catch(_e) {}
                var prefW = 0, prefH = 0;
                try { prefW = t.preferredWidth; prefH = t.preferredHeight; } catch(_e) {}
                var fontName = '?';
                try { var fa = t.m_fontAsset; fontName = fa && fa.name ? fa.name : '?'; } catch(_e) {}
                var missing = [];
                try {
                    var fa2 = t.m_fontAsset;
                    if (fa2 && text) {
                        for (var ci = 0; ci < text.length && missing.length < 20; ci++) {
                            var code = text.charCodeAt(ci);
                            if (code < 32) continue;
                            try { if (!fa2.HasCharacter(code, true)) { var ch = text[ci]; if (missing.indexOf(ch) < 0) missing.push(ch); } } catch(_e) {}
                        }
                    }
                } catch(_e) {}
                var parts = [path + ' | text=' + (text.length > 40 ? text.slice(0,40)+'…' : text)];
                parts.push('overflow=' + overflow + ' overflowMode=' + overflowMode + ' richText=' + richText);
                parts.push('prefSize=' + prefW.toFixed(1) + 'x' + prefH.toFixed(1) + ' font=' + fontName);
                if (missing.length) parts.push('missing=' + missing.join(','));
                return parts.join(' | ');
            } catch(e) { return 'error: ' + e.message; }
        },

        particleAudit: function() {
            try {
                var rows = [];
                walkScene(function(node) {
                    var uc = node._unityComponents;
                    if (!uc || uc.particlesystem === undefined) return;
                    var arr = uc.particlesystem;
                    if (!Array.isArray(arr)) arr = [arr];
                    for (var i = 0; i < arr.length; i++) {
                        try {
                            var ps = arr[i] && arr[i]._particleSystem;
                            if (!ps) continue;
                            var alive = ps.particleCount || 0;
                            var maxP = (ps.main && ps.main.maxParticles) || 0;
                            var ratio = maxP > 0 ? alive / maxP : 0;
                            var rate = 0;
                            try {
                                var rot = ps.emission && ps.emission.rateOverTime;
                                if (rot) rate = rot.constant !== undefined ? rot.constant : (rot.constantMax || 0);
                            } catch(_e) {}
                            rows.push({
                                path: buildPath(node),
                                alive: alive, max: maxP, ratio: ratio,
                                play: !!ps.isPlaying, emit: !!ps.isEmitting,
                                paused: !!ps.isPaused, rate: rate,
                                t: ps.time !== undefined ? ps.time.toFixed(2) : '?'
                            });
                        } catch(_e) {}
                    }
                });
                if (!rows.length) return 'no particle systems found';
                rows.sort(function(a, b) { return b.ratio - a.ratio; });
                return rows.map(function(r) {
                    return r.path + ' | ' + r.alive + '/' + r.max +
                        ' play=' + r.play + ' emit=' + r.emit +
                        ' rate=' + r.rate + ' t=' + r.t;
                }).join('\n');
            } catch(e) { return 'error: ' + e.message; }
        },

        physicsProbe: function() {
            var goblin = (typeof Goblin !== 'undefined' && !!Goblin.World) || false;
            var adapter = window.app && window.app.app && window.app.app.systems && window.app.app.systems.physics && window.app.app.systems.physics.adapter;
            var adapterName = (adapter && adapter.constructor && adapter.constructor.name) || '';
            var verlet = (typeof VerletWorld !== 'undefined') || /verlet/i.test(adapterName);
            var baked = (typeof BakedPhysicsAdapter !== 'undefined') || /baked/i.test(adapterName);
            var unified = (typeof CustomPhysicsWorld !== 'undefined') || /unified|custom/i.test(adapterName);
            var goblin_bodies = 0, verlet_particles = 0, baked_entries = 0;
            try { if (goblin && Goblin.World) goblin_bodies = (Goblin.World._instances || []).length; } catch(e) {}
            try { if (typeof VerletWorld !== 'undefined' && VerletWorld.particles) verlet_particles = VerletWorld.particles.length; } catch(e) {}
            try { if (typeof BakedPhysicsAdapter !== 'undefined' && BakedPhysicsAdapter._dynamicList) baked_entries = BakedPhysicsAdapter._dynamicList.length; } catch(e) {}
            return 'goblin=' + goblin + ' verlet=' + verlet + ' baked=' + baked + ' unified=' + unified +
                   ' goblin.bodies=' + goblin_bodies + ' verlet.particles=' + verlet_particles + ' baked.entries=' + baked_entries;
        },

        // S2.1 — pi insights state
        piState: function() {
            if (typeof window.pi === 'function') return 'pi-not-initialized';
            if (typeof window.pi !== 'object' || !window.pi) return 'pi-absent';
            var lines = [];
            try {
                var esn = window.pi.eventSequenceNumbers || {};
                var keys = Object.keys(esn);
                for (var i = 0; i < keys.length; i++) {
                    lines.push(keys[i] + ':' + esn[keys[i]]);
                }
            } catch(e) {}
            try { lines.push('totalEvents:' + (window.pi.totalEvents || 0)); } catch(e) {}
            return lines.join('\n') || 'pi-ready';
        },

        // S2.1 — install ring-buffer recorder on window.pi.logEvent
        installInsightsRecorder: function() {
            if (typeof window.pi !== 'function' && (typeof window.pi !== 'object' || !window.pi)) return 'pi-absent';
            if (window.pi.__luna_rec) return 'already';
            var buf = [];
            var seq = 0;
            var CAP = 512;
            var origLog = window.pi.logEvent;
            window.pi.logEvent = function(name, reset, opts) {
                buf.push({name: name, reset: reset, opts: opts, seq: ++seq, t: performance.now()});
                if (buf.length > CAP) buf.shift();
                if (origLog) origLog.apply(window.pi, arguments);
            };
            window.pi.__luna_rec = buf;
            return 'installed';
        },

        // S2.1 — drain ring buffer to text
        getInsightEvents: function() {
            if (!window.pi || !window.pi.__luna_rec) return 'no recorder installed';
            var buf = window.pi.__luna_rec;
            var lines = [];
            for (var i = 0; i < buf.length; i++) {
                var e = buf[i];
                var optsStr = JSON.stringify(e.opts || {});
                if (optsStr.length > 120) optsStr = optsStr.slice(0, 120) + '…}';
                lines.push(e.seq + '|' + e.t.toFixed(1) + '|' + (e.name || '') + '|' + optsStr);
            }
            return lines.join('\n') || 'empty';
        },

        // S2.2 — why is a UI element not tappable?
        whyNotTappable: function(path) {
            var r = resolveNode(path); if (r.err) return r.err;
            var node = r.node;
            var comps = getNodeComponents(node);
            var lines = [];
            // Check Selectable subclass
            var selectable = null;
            for (var i = 0; i < comps.length; i++) {
                var t = getComponentTypeName(comps[i]);
                if (t === 'Button' || t === 'Toggle' || t === 'Slider' || t === 'Selectable') {
                    selectable = comps[i]; break;
                }
            }
            if (selectable) {
                try { lines.push('IsInteractable: ' + selectable.IsInteractable()); } catch(e) {
                    try { lines.push('IsInteractable: ' + selectable.interactable); } catch(e2) { lines.push('IsInteractable: unknown'); }
                }
                try { lines.push('enabled: ' + selectable.enabled); } catch(e) {}
            } else {
                lines.push('no Selectable component found');
            }
            try { lines.push('activeSelf: ' + node._activeSelf); } catch(e) {}
            // Check graphic raycastTarget
            for (var j = 0; j < comps.length; j++) {
                try {
                    var rt = comps[j].raycastTarget;
                    if (rt === false) { lines.push('raycastTarget: false (blocks raycast)'); break; }
                } catch(e2) {}
            }
            // Walk parent chain for blocking CanvasGroup
            var cur = node._parent;
            while (cur) {
                var curComps = getNodeComponents(cur);
                for (var k = 0; k < curComps.length; k++) {
                    var ct = getComponentTypeName(curComps[k]);
                    if (ct === 'CanvasGroup') {
                        try {
                            var cg = curComps[k];
                            if (cg.ignoreParentGroups) { cur = null; break; }
                            if (cg.interactable === false) { lines.push('BlockedBy: CanvasGroup at ' + (cur.name || '?') + ' (interactable=false)'); }
                            if (cg.blocksRaycasts === false) { lines.push('BlockedBy: CanvasGroup at ' + (cur.name || '?') + ' (blocksRaycasts=false)'); }
                        } catch(e) {}
                    }
                }
                if (!cur) break;
                cur = cur._parent;
            }
            return lines.join('\n') || 'ok: no blocking issues found';
        },

        // S2.3 — full animator graph dump
        getAnimatorGraph: function(path) {
            var de = requireDebugger('Animator'); if (de) return de;
            var fa = findAnimator(path); if (fa.err) return fa.err;
            var node = fa.node; var animator = fa.animator;
            var id = animator.handle ? animator.handle.$id : animator.$id;
            var guid = node._guid;
            var data = pc.Debugger.Animator.get({animator: {id: id, guid: guid}});
            if (!data) return 'error: animator data unavailable';
            var lines = ['ANIMATOR_GRAPH: ' + path];
            var layerKeys = Object.keys(data.layers || []);
            for (var li = 0; li < layerKeys.length; li++) {
                var layer = (data.layers || [])[layerKeys[li]];
                var lname = '?', lweight = 0;
                try { lname = layer.name; } catch(e) {}
                try { lweight = layer.weight; } catch(e) {}
                lines.push('  layer[' + li + ']: ' + lname + ' (weight=' + lweight + ')');
            }
            var stateKeys = Object.keys(data.states || {});
            for (var si = 0; si < stateKeys.length && lines.length < 55; si++) {
                try {
                    var s = data.states[stateKeys[si]];
                    var skeys = Object.keys(s);
                    var sname = '', snt = '', sloop = false, sspeed = 1;
                    for (var ski = 0; ski < skeys.length; ski++) {
                        if (skeys[ski] === 'name') sname = s.name;
                        else if (skeys[ski] === 'normalizedTime') snt = s.normalizedTime;
                        else if (skeys[ski] === 'isLooping') sloop = s.isLooping;
                        else if (skeys[ski] === 'speed') sspeed = s.speed;
                    }
                    lines.push('  state: ' + sname + (snt !== '' ? ' t=' + (+snt).toFixed(2) : '') + (sloop ? ' (loop)' : '') + ' speed=' + sspeed);
                } catch(e) {}
            }
            if (data.parameters) {
                var paramKeys = Object.keys(data.parameters);
                for (var pi = 0; pi < paramKeys.length && lines.length < 58; pi++) {
                    try { lines.push('  param: ' + paramKeys[pi] + '=' + data.parameters[paramKeys[pi]]); } catch(e) {}
                }
            }
            if (data.transitions) {
                var txKeys = Object.keys(data.transitions);
                for (var ti = 0; ti < txKeys.length && lines.length < 60; ti++) {
                    try { lines.push('  transition: ' + txKeys[ti]); } catch(e) {}
                }
            }
            return lines.join('\n');
        },

        // S2.4 — Luna performance counters (read .previous, not .current)
        getLunaCounters: function() {
            var c = window.app && window.app.app && window.app.app.counters;
            if (!c || !c.previous) return 'error: app.counters not available';
            var p = c.previous;
            var lines = [];
            var always = ['drawCalls','materialSwitches','verticesCount','trianglesCount',
                          'particleSystems','particles','animators','animatorLayers',
                          'activeBlendStates','uiElements'];
            for (var i = 0; i < always.length; i++) {
                try { lines.push(always[i] + ': ' + p[always[i]]); } catch(e) {}
            }
            var devOnly = ['totalSkinnedMeshes','visibleSkinnedMeshes',
                           'offscreenUpdatedSkinnedMeshes','shadowCasters'];
            for (var j = 0; j < devOnly.length; j++) {
                try {
                    var val = c.advancedMode ? p[devOnly[j]] : '[dev-only:n/a]';
                    lines.push(devOnly[j] + ': ' + val);
                } catch(e) {}
            }
            return lines.join('\n');
        },

        // S2.5 — runtime environment info with per-property try/catch
        getEnvironment: function() {
            if (typeof UnityEngine === 'undefined') return 'error: no Unity runtime';
            var lines = [];
            try { lines.push('creativeName: ' + UnityEngine.Application.creativeName); } catch(e) { lines.push('creativeName: n/a'); }
            try { lines.push('lunaVersion: ' + UnityEngine.Application.lunaVersion); } catch(e) { lines.push('lunaVersion: n/a'); }
            try { lines.push('lunaSHA: ' + UnityEngine.Application.lunaSHA); } catch(e) { lines.push('lunaSHA: n/a'); }
            try { lines.push('targetFrameRate: ' + UnityEngine.Application.targetFrameRate); } catch(e) { lines.push('targetFrameRate: n/a'); }
            try { lines.push('systemLanguage: ' + String(UnityEngine.Application.systemLanguage)); } catch(e) { lines.push('systemLanguage: n/a'); }
            try { lines.push('internetReachability: ' + String(UnityEngine.Application.internetReachability)); } catch(e) { lines.push('internetReachability: n/a'); }
            try { lines.push('platform: ' + String(UnityEngine.Application.platform)); } catch(e) { lines.push('platform: n/a'); }
            try { lines.push('androidStoreLink: ' + UnityEngine.Application.androidStoreLink); } catch(e) { lines.push('androidStoreLink: n/a'); }
            try { lines.push('iosStoreLink: ' + UnityEngine.Application.iosStoreLink); } catch(e) { lines.push('iosStoreLink: n/a'); }
            try { lines.push('minifyEnabled: ' + UnityEngine.Application.minifyEnabled); } catch(e) { lines.push('minifyEnabled: n/a'); }
            try { lines.push('isForceUncompressed: ' + UnityEngine.Application.isForceUncompressed); } catch(e) { lines.push('isForceUncompressed: n/a'); }
            try { lines.push('deviceModel: ' + UnityEngine.SystemInfo.deviceModel); } catch(e) { lines.push('deviceModel: n/a'); }
            try { lines.push('systemMemorySize: ' + UnityEngine.SystemInfo.systemMemorySize); } catch(e) { lines.push('systemMemorySize: n/a'); }
            try { lines.push('maxTextureSize: ' + UnityEngine.SystemInfo.maxTextureSize); } catch(e) { lines.push('maxTextureSize: n/a'); }
            try { lines.push('screenWidth: ' + UnityEngine.Screen.width); } catch(e) { lines.push('screenWidth: n/a'); }
            try { lines.push('screenHeight: ' + UnityEngine.Screen.height); } catch(e) { lines.push('screenHeight: n/a'); }
            try { lines.push('dpi: ' + UnityEngine.Screen.dpi); } catch(e) { lines.push('dpi: n/a'); }
            try {
                var sa = UnityEngine.Screen.safeArea;
                lines.push('safeArea: x=' + sa.x + ' y=' + sa.y + ' width=' + sa.width + ' height=' + sa.height);
            } catch(e) { lines.push('safeArea: n/a'); }
            try { lines.push('devicePixelRatio: ' + (window.devicePixelRatio || 1)); } catch(e) {}
            return lines.join('\n');
        },

        // S3.3 — Lifecycle waiter
        waitForLunaEvent: function(name, timeoutMs) {
            var ts = (window.lunaStartup && window.lunaStartup.timestamps) || {};
            if (ts[name] > 0) return 'already:' + ts[name];
            var done = false;
            return new Promise(function(resolve) {
                function h(e) {
                    if (done) return;
                    done = true;
                    window.removeEventListener(name, h);
                    resolve('fired:' + (performance.now() | 0));
                }
                window.addEventListener(name, h);
                setTimeout(function() {
                    if (done) return;
                    done = true;
                    window.removeEventListener(name, h);
                    resolve('timeout:' + (timeoutMs > 0 ? timeoutMs : 10000));
                }, timeoutMs > 0 ? timeoutMs : 10000);
            });
        },

        tapLifecycle: function() {
            if (window.__luna_lc_hooked) return 'already';
            window.__luna_lc_hooked = true;
            if (!window.__luna_lc_buf) window.__luna_lc_buf = [];
            var buf = window.__luna_lc_buf;
            var names = ['OnStart','GameStarted','GameEnded','OnPause','OnResume','OnLevelLoad','HapticTriggered'];
            // Path A: Luna.Unity.LifeCycle wrapping
            try {
                if (window.Luna && Luna.Unity && Luna.Unity.LifeCycle) {
                    for (var i = 0; i < names.length; i++) {
                        (function(n) {
                            try {
                                var orig = Luna.Unity.LifeCycle[n];
                                Luna.Unity.LifeCycle[n] = function() {
                                    buf.push({t: performance.now(), name: n});
                                    if (buf.length > 64) buf.shift();
                                    if (typeof orig === 'function') orig.apply(this, arguments);
                                };
                            } catch(e) {}
                        })(names[i]);
                    }
                }
            } catch(e) {}
            // Path B: window addEventListener for luna:* events
            for (var j = 0; j < names.length; j++) {
                (function(n) {
                    try {
                        window.addEventListener('luna:' + n.toLowerCase(), function() {
                            buf.push({t: performance.now(), name: n});
                            if (buf.length > 64) buf.shift();
                        });
                    } catch(e) {}
                })(names[j]);
            }
            return 'hooked';
        },

        getLifecycleEvents: function(sinceTs) {
            var buf = window.__luna_lc_buf || [];
            var since = sinceTs || 0;
            var lines = [];
            for (var i = 0; i < buf.length; i++) {
                if (buf[i].t > since) lines.push(buf[i].name + '|' + (buf[i].t | 0));
            }
            return lines.join('\n');
        },

        // S3.2 — DOTween inventory and control
        tweenList: function() {
            if (typeof DG === 'undefined' || !DG.Tweening || !DG.Tweening.Core || !DG.Tweening.Core.TweenManager) return 'DOTween not present in this build';
            var TM = DG.Tweening.Core.TweenManager;
            if (TM.totActiveTweens <= 0) return 'no active tweens';
            if (!TM._activeTweens) return 'DOTween internal state unavailable';
            if (TM._requiresActiveReorganization) TM.ReorganizeActiveTweens();
            var lines = [];
            for (var i = 0; i <= TM._maxActiveLookupId; i++) {
                var t = TM._activeTweens[i];
                if (!t) continue;
                var dur, pos, loops, playing, complete, target;
                try { dur = t.duration; } catch(e) { dur = '?'; }
                try { pos = t.position; } catch(e) { pos = '?'; }
                try { loops = t.loops; } catch(e) { loops = '?'; }
                try { playing = t.isPlaying; } catch(e) { playing = '?'; }
                try { complete = t.isComplete; } catch(e) { complete = '?'; }
                try { target = t.target && (t.target.name || '?'); } catch(e) { target = '?'; }
                lines.push(i + ' | dur=' + dur + ' | pos=' + pos + ' | loops=' + loops + ' | playing=' + playing + ' | complete=' + complete + ' | target=' + target);
            }
            return lines.length ? lines.join('\n') : 'no active tweens';
        },

        tweenControl: function(action) {
            if (typeof DG === 'undefined' || !DG.Tweening || !DG.Tweening.Core || !DG.Tweening.Core.TweenManager) return 'DOTween not present in this build';
            if (action === 'pause') { DG.Tweening.DOTween.PauseAll(); return 'paused all'; }
            if (action === 'play') { DG.Tweening.DOTween.PlayAll(); return 'playing all'; }
            if (action === 'kill') { DG.Tweening.DOTween.KillAll(); return 'killed all'; }
            if (action === 'complete') { DG.Tweening.DOTween.CompleteAll(); return 'completed all'; }
            return 'unknown action: ' + action;
        },

        // S3.4 — Physics forensics
        rigidbodyDump: function(path) {
            var scene = getScene();
            if (!scene) return 'error: no scene';
            var lines = [];
            function visitRb(node) {
                var comps = getNodeComponents(node);
                for (var i = 0; i < comps.length; i++) {
                    var t = getComponentTypeName(comps[i]);
                    if (t.indexOf('Rigidbody') < 0) continue;
                    var rb = comps[i];
                    var name = (node && node.name) || '?';
                    var vel, ang, mass, kin, grav, sleep, isStat, pos;
                    try { vel = rb.velocity; vel = '(' + vel.x.toFixed(2) + ',' + vel.y.toFixed(2) + ',' + vel.z.toFixed(2) + ')'; } catch(e) { vel = '?'; }
                    try { ang = rb.angularVelocity; ang = '(' + ang.x.toFixed(2) + ',' + ang.y.toFixed(2) + ',' + ang.z.toFixed(2) + ')'; } catch(e) { ang = '?'; }
                    try { mass = rb.mass; } catch(e) { mass = '?'; }
                    try { kin = rb.isKinematic; } catch(e) { kin = '?'; }
                    try { grav = rb.useGravity; } catch(e) { grav = '?'; }
                    try { sleep = rb.IsSleeping(); } catch(e) { try { sleep = rb.isSleeping; } catch(e2) { sleep = '?'; } }
                    try { isStat = rb.isStatic; } catch(e) { isStat = '?'; }
                    try { pos = rb.position; pos = '(' + pos.x.toFixed(2) + ',' + pos.y.toFixed(2) + ',' + pos.z.toFixed(2) + ')'; } catch(e) { pos = '?'; }
                    lines.push(name + ' vel=' + vel + ' ang=' + ang + ' mass=' + mass + ' kin=' + kin + ' grav=' + grav + ' sleep=' + sleep + ' static=' + isStat + ' pos=' + pos);
                }
                var children = node._children || [];
                for (var j = 0; j < children.length; j++) visitRb(children[j]);
            }
            var root = path ? findByPath(scene.root, path) : scene.root;
            if (!root) return 'error: node not found: ' + path;
            visitRb(root);
            return lines.length ? lines.join('\n') : '(no rigidbodies)';
        },

        listBodies2d: function(maxN) {
            var a = pc.app && pc.app.systems && pc.app.systems.physics2D && pc.app.systems.physics2D.adapter;
            if (!a) return 'error: no physics2D';
            var lines = [];
            var cap = maxN || 40;
            try {
                var b = a.world.GetBodyList();
                while (b && lines.length < cap) {
                    try {
                        var comp = a.getBodyComponentForBody(b);
                        var ename = (comp && comp.entity && comp.entity.name) || '?';
                        var btype = b.GetType();
                        var awake = b.IsAwake();
                        var bpos = b.GetPosition();
                        var bvel = b.GetLinearVelocity();
                        var px = bpos.x, py = bpos.y, vx = bvel.x, vy = bvel.y;
                        lines.push(ename + ' type=' + btype + ' awake=' + awake + ' pos=(' + px.toFixed(2) + ',' + py.toFixed(2) + ') vel=(' + vx.toFixed(2) + ',' + vy.toFixed(2) + ')');
                    } catch(e) { lines.push('(error: ' + e.message + ')'); }
                    b = b.GetNext();
                }
            } catch(e) { return 'error: ' + e.message; }
            return lines.length ? lines.join('\n') : '(no 2d bodies)';
        },

        raycast2d: function(ox, oy, dx, dy, dist) {
            var a = pc.app && pc.app.systems && pc.app.systems.physics2D && pc.app.systems.physics2D.adapter;
            if (!a) return 'error: no physics2D';
            try {
                var hit = pc.Physics2DSystem.raycast(ox, oy, dx, dy, dist || 1e9);
                if (!hit) return 'no hit';
                var colliderName = '?';
                try {
                    var code = hit.collider;
                    if (typeof code === 'number') {
                        var cols = a._colliders || [];
                        for (var i = 0; i < cols.length; i++) {
                            if (cols[i] && cols[i].code === code) { colliderName = (cols[i].entity && cols[i].entity.name) || String(code); break; }
                        }
                        if (colliderName === '?') colliderName = String(code);
                    } else {
                        colliderName = (hit.collider && hit.collider.name) || String(hit.collider);
                    }
                } catch(e) { colliderName = String(hit.collider); }
                return 'hit collider=' + colliderName + ' point=(' + (hit.point && hit.point.x || 0).toFixed(2) + ',' + (hit.point && hit.point.y || 0).toFixed(2) + ')';
            } catch(e) { return 'error: ' + e.message; }
        },

        overlapPoint2d: function(x, y) {
            var a = pc.app && pc.app.systems && pc.app.systems.physics2D && pc.app.systems.physics2D.adapter;
            if (!a) return 'error: no physics2D';
            try {
                var hit = pc.Physics2DSystem.overlapPoint(x, y);
                if (!hit) return 'no overlap';
                return 'overlap collider=' + (hit.name || String(hit));
            } catch(e) { return 'error: ' + e.message; }
        },

        contactPairs: function() {
            var a = pc.app && pc.app.systems && pc.app.systems.physics2D && pc.app.systems.physics2D.adapter;
            if (!a) return 'error: no physics2D';
            try {
                var w = a.world;
                var n = 0;
                try { n = w._contacts ? w._contacts.length : (w.GetContactCount ? w.GetContactCount() : 0); } catch(e) {}
                return 'contacts: ' + n + ' (names unavailable on this backend)';
            } catch(e) { return 'error: ' + e.message; }
        },

        // S2.6 — Unity shader variant report (counts only, no log strings)
        getUnityShaderReport: function() {
            if (typeof pc === 'undefined' || !pc.UnityShader) return 'error: no pc.UnityShader';
            var r;
            try { r = pc.UnityShader.generateReport(); } catch(e) { return 'error: ' + e.message; }
            if (!r) return 'error: empty report';
            var lines = [];
            var countFields = ['unityShaders','totalVariants','compiled','exported',
                               'excluded','missing','vertexShaders','fragmentShaders'];
            for (var i = 0; i < countFields.length; i++) {
                try { lines.push(countFields[i] + ': ' + r[countFields[i]]); } catch(e) {}
            }
            return lines.join('\n') || 'ok: no data';
        }
    };
})();
