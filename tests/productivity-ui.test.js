'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const K = {Productivity: {}, UI: {commands: [], groups: {}}, Production: {}};
vm.runInNewContext(fs.readFileSync(path.join(root, 'src/productivity-ui.js'), 'utf8'), {Kestrel: K});
class App {
    constructor() {
        this.doc = {entities: [], layers: [], selected: () => []};
        this.messages = [];
    }
    async run(id) { return 'original:' + id; }
    dialog(options) { this.lastDialog = options; }
    toast(message) { this.messages.push(message); }
}
const tests = [];
async function test(name, action) {
    try { await action(); tests.push({name, status: 'passed'}); console.log('PASS', name); }
    catch (error) { tests.push({name, status: 'failed', error: error.stack}); console.error(error); }
}
(async () => {
    await test('synchronous installation preserves Promise-returning unknown commands', async () => {
        K.installProductivityUI(App);
        const app = new App(), result = app.run('existing');
        assert.equal(typeof result.catch, 'function');
        assert.equal(await result, 'original:existing');
    });
    await test('ribbon dialog actions always return a Promise', async () => {
        const app = new App(), result = app.run('productivity-select');
        assert.equal(typeof result.catch, 'function');
        await result;
        assert.equal(app.lastDialog.title, 'Quick select');
    });
    await test('command aliases retain the same Promise contract', async () => {
        const app = new App(), result = app.run('QSELECT');
        assert.equal(typeof result.catch, 'function');
        await result;
        assert.equal(app.lastDialog.title, 'Quick select');
    });
    await test('invalid selection reports an error without rejecting unexpectedly', async () => {
        const app = new App(), result = app.run('productivity-lengthen');
        assert.equal(typeof result.catch, 'function');
        assert.equal(await result, false);
        assert.match(app.messages[0], /exactly one/);
    });
    await test('repeated installation does not wrap commands again', () => {
        const run = App.prototype.run;
        K.installProductivityUI(App);
        assert.equal(App.prototype.run, run);
    });
    const failed = tests.filter(t => t.status === 'failed').length;
    fs.mkdirSync(path.join(root, 'tests/results'), {recursive: true});
    fs.writeFileSync(path.join(root, 'tests/results/productivity-ui-results.json'), JSON.stringify({passed: tests.length - failed, failed, tests}, null, 2));
    process.exitCode = failed ? 1 : 0;
})();
