// Injection helper: loads js/luna_helpers.js + all mock/fixture factories
// into a Playwright page, wires up a mock scene via sceneFn, then returns a
// thin call() shortcut for invoking window.__luna_mcp methods.
'use strict';

const fs = require('fs');
const path = require('path');

const HELPERS_PATH = path.resolve(__dirname, '../../../js/luna_helpers.js');
const HELPERS_SOURCE = fs.readFileSync(HELPERS_PATH, 'utf-8');

const MOCKS_DIR = path.resolve(__dirname, '../mocks');
const FIXTURES_DIR = path.resolve(__dirname, '../fixtures');

// Reads every *.js file in `dir` (each exporting { SOURCE }) and concatenates
// their source. New mock/fixture files need no changes here -- drop a file
// with `module.exports = { SOURCE: '...' }` into mocks/ or fixtures/ and it
// is picked up automatically.
function readDirSources(dir) {
    return fs.readdirSync(dir)
        .filter((f) => f.endsWith('.js'))
        .sort()
        .map((f) => require(path.join(dir, f)).SOURCE)
        .join('\n');
}

// mocks/ must be evaluated before fixtures/ -- fixtures call window.__mocks.*
// factories defined by the mocks.
const MOCK_FACTORIES_SOURCE = readDirSources(MOCKS_DIR) + '\n' + readDirSources(FIXTURES_DIR);

/**
 * Injects luna_helpers.js into `page` against a mock Luna scene.
 *
 * @param {import('@playwright/test').Page} page
 * @param {Function|string} [sceneFn] - evaluated inside the page AFTER mock
 *   factories are loaded. Responsible for setting window.$scene (and
 *   optionally window.UnityEngine / window.pc / window.Bridge). Typically
 *   `() => window.__mocks.createBasicScene()`. Omit to test the "no scene"
 *   path.
 * @returns {Promise<{ call: (method: string, ...args: any[]) => Promise<any> }>}
 */
async function injectLunaHelpers(page, sceneFn) {
    // Fresh injection guard: luna_helpers.js is a no-op IIFE if
    // window.__luna_mcp already exists.
    await page.evaluate(() => {
        delete window.__luna_mcp;
        window.__mocks = {};
    });

    await page.evaluate(MOCK_FACTORIES_SOURCE);

    if (sceneFn) {
        await page.evaluate(sceneFn);
    }

    await page.evaluate(HELPERS_SOURCE);

    return {
        call: (method, ...args) => page.evaluate(
            ({ m, a }) => {
                var fn = window.__luna_mcp && window.__luna_mcp[m];
                if (typeof fn !== 'function') throw new Error('unknown luna_mcp method: ' + m);
                return fn.apply(window.__luna_mcp, a);
            },
            { m: method, a: args }
        ),
    };
}

module.exports = { injectLunaHelpers, HELPERS_SOURCE, MOCK_FACTORIES_SOURCE };
