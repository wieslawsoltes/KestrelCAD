/* Real-hardware WebGPU functional checks. Not a mock, benchmark, or fallback test.
 * Run tests/webgpu.html from the supplied localhost server. */
'use strict';
(() => {
  const K = window.Kestrel, byId = id => document.getElementById(id);
  const checks = [], camera = new K.Camera();
  let renderer, report;
  const assert = (condition, message) => { if (!condition) throw Error(message); };
  const makeDrawing = entities => {
    const doc = new K.Drawing('WebGPU validation');
    entities.forEach(entity => doc.add(entity));
    return doc;
  };
  const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
  const finish = status => {
    report = {
      suite: 'Real Kestrel WebGPU pipelines and texture readback',
      status, date: new Date().toISOString(), userAgent: navigator.userAgent,
      secureContext: isSecureContext, backend: renderer?.backend || 'Not initialized',
      adapter: renderer?.adapterInfo || null,
      fallbackReason: renderer?.fallbackReason || null,
      passed: checks.filter(test => test.status === 'passed').length,
      failed: checks.filter(test => test.status === 'failed').length,
      tests: checks, validationErrors: renderer?.gpuErrors || [],
      note: 'Functional checks only. These are not GPU timing or throughput benchmarks.'
    };
    window.kestrelGPUReport = report;
    byId('report').textContent = JSON.stringify(report, null, 2);
    byId('status').textContent = `${status}: ${report.passed} passed, ${report.failed} failed.`;
    byId('download').disabled = false;
  };
  async function test(name, operation) {
    byId('status').textContent = name;
    let detail, failure, scopeError;
    const device = renderer.device;
    device.pushErrorScope('validation');
    try {
      detail = await operation();
      await device.queue.onSubmittedWorkDone();
      assert(renderer.backend === 'WebGPU', 'Device was lost or fallback became active.');
    } catch (error) { failure = error; }
    finally {
      try { scopeError = await device.popErrorScope(); }
      catch (error) { failure ||= error; }
    }
    if (scopeError) failure ||= scopeError;
    checks.push(failure
      ? { name, status: 'failed', error: String(failure.message || failure) }
      : { name, status: 'passed', detail: detail ?? null });
    byId('report').textContent = JSON.stringify(checks, null, 2);
  }
  // Render with the production renderer into an offscreen color texture, then
  // use a real GPU copy/map operation. This does not rely on canvas screenshots.
  async function pixels(doc) {
    const d = renderer.device, w = renderer.canvas.width, h = renderer.canvas.height;
    const rowBytes = Math.ceil(w * 4 / 256) * 256;
    const texture = d.createTexture({ label: 'Validation color readback', size: [w, h],
      format: renderer.format, usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC });
    const buffer = d.createBuffer({ label: 'Validation mapped pixels', size: rowBytes * h,
      usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const original = renderer.gpuContext;
    try {
      renderer.gpuContext = { getCurrentTexture: () => texture };
      renderer.render(doc);
      renderer.gpuContext = original;
      const encoder = d.createCommandEncoder();
      encoder.copyTextureToBuffer({ texture }, { buffer, bytesPerRow: rowBytes }, [w, h]);
      d.queue.submit([encoder.finish()]);
      await buffer.mapAsync(GPUMapMode.READ);
      const source = new Uint8Array(buffer.getMappedRange());
      const data = new Uint8Array(w * h * 4);
      for (let y = 0; y < h; y++) data.set(source.subarray(y * rowBytes, y * rowBytes + w * 4), y * w * 4);
      buffer.unmap();
      return { data, w, h };
    } finally {
      renderer.gpuContext = original;
      buffer.destroy(); texture.destroy();
    }
  }
  function changedPixels(a, b, tolerance = 8) {
    assert(a.data.length === b.data.length, 'Image dimensions differ.');
    let count = 0;
    for (let i = 0; i < a.data.length; i += 4) {
      if (Math.max(...[0, 1, 2].map(j => Math.abs(a.data[i + j] - b.data[i + j]))) > tolerance) count++;
    }
    return count;
  }
  async function run() {
    byId('run').disabled = true;
    if (!isSecureContext || !navigator.gpu) {
      checks.push({ name: 'WebGPU secure-context availability', status: 'unavailable',
        reason: !isSecureContext ? 'Open this page on localhost or HTTPS.' : 'navigator.gpu is unavailable in this browser.' });
      finish('UNAVAILABLE — not a WebGPU pass'); return;
    }
    renderer = new K.Renderer(byId('scene'), byId('overlay'), camera);
    renderer.grid = false;
    const backend = await renderer.init();
    if (backend !== 'WebGPU') {
      checks.push({ name: 'Adapter, shader and pipeline initialization', status: 'failed', error: renderer.fallbackReason });
      finish('FAILED — GPU initialization'); return;
    }
    checks.push({ name: 'Real WGSL compilation, bindings and all production pipelines', status: 'passed' });
    renderer.resize(640, 400); camera.setView('top');
    const empty = makeDrawing([]), simple = makeDrawing([
      { type: 'LINE', points: [[-60, -25, 0], [60, 25, 0]], color: '#ffae55' },
      { type: 'CIRCLE', center: [0, 0, 0], radius: 30, color: '#63d7eb' }
    ]);
    camera.target = [0, 0, 0]; camera.zoom = 3; camera.update();
    await test('Instanced antialiased lines produce actual pixels', async () => {
      renderer.style = 'wireframe'; const blank = await pixels(empty), image = await pixels(simple);
      const count = changedPixels(blank, image); assert(count > 100, 'Line geometry did not appear.');
      assert(renderer.buffers['scene-lines'].count > 10, 'Missing instanced curve segments.');
      return { changedPixels: count, lineInstances: renderer.buffers['scene-lines'].count };
    });
    await test('Geometry vertex buffers are retained across unchanged frames and camera pans', async () => {
      renderer.render(simple); const buffer = renderer.buffers['scene-lines'].buffer;
      renderer.render(simple); camera.pan(8, 5); renderer.render(simple);
      assert(renderer.buffers['scene-lines'].buffer === buffer, 'Unchanged geometry allocated a new buffer.');
      camera.pan(-8, -5);
    });
    const solid = makeDrawing([{ ...K.Geo.box([-25, -25, 0], 50, 50, 20), color: '#61bdcb' }]);
    await test('Shaded triangles and four-sample MSAA produce filled pixels', async () => {
      renderer.style = 'shaded'; camera.setView('iso'); camera.fit(solid.entities[0].vertices);
      const blank = await pixels(empty), image = await pixels(solid), count = changedPixels(blank, image);
      assert(count > 2000, 'No substantial shaded area was rendered.');
      assert(renderer.stats.triangles === 12, 'Unexpected box triangulation.');
      return { changedPixels: count, triangles: renderer.stats.triangles };
    });
    await test('Depth testing hides a line behind a solid but shows a line in front', async () => {
      camera.setView('top'); camera.target = [0, 0, 0]; camera.zoom = 4; camera.update();
      renderer.style = 'shaded'; const base = await pixels(solid);
      const back = solid.add({ type: 'LINE', points: [[-15, 0, -10], [15, 0, -10]], color: '#ff00ff' });
      solid.changed('GPU test geometry'); const hidden = await pixels(solid);
      solid.replace(back.id, { ...back, points: [[-15, 0, 30], [15, 0, 30]] });
      solid.changed('GPU test geometry'); const visible = await pixels(solid);
      assert(changedPixels(base, hidden) < 15, 'The back line was visible through an opaque solid.');
      assert(changedPixels(hidden, visible) > 60, 'The front line was not visible.');
      return { hiddenDifference: changedPixels(base, hidden), visibleDifference: changedPixels(hidden, visible) };
    });
    await test('Camera-relative GPU coordinates preserve geometry near world coordinate 1e9', async () => {
      renderer.style = 'shaded-edges'; camera.setView('iso');
      const baseDoc = makeDrawing([{ ...K.Geo.box([-20, -15, -10], 40, 30, 20), color: '#d5ac6e' }]);
      camera.fit(baseDoc.entities[0].vertices); const originalCamera = camera.serialize(), base = await pixels(baseDoc);
      const offset = [1e9, -1e9, 1e9];
      const shifted = makeDrawing(baseDoc.entities.map(e => K.Geo.transform(e, K.Math.M.translation(...offset))));
      camera.target = K.Math.V.add(camera.target, offset); camera.update(); const translated = await pixels(shifted);
      const fraction = changedPixels(base, translated, 16) / (base.w * base.h);
      assert(fraction < 0.035, 'Large coordinates changed too much of the rendered image.');
      camera.restore(originalCamera); return { differentPixelFraction: fraction };
    });
    await test('Wireframe, shaded, edged and x-ray pipelines submit without validation errors', async () => {
      for (const style of ['wireframe', 'shaded', 'shaded-edges', 'xray']) {
        renderer.style = style; await pixels(solid);
        assert(renderer.stats.drawCalls > 0, `${style} issued no draw calls.`);
      }
    });
    await test('Theme switch changes the actual render target', async () => {
      renderer.theme = 'dark'; const dark = await pixels(solid);
      renderer.theme = 'light'; const light = await pixels(solid);
      assert(changedPixels(dark, light) > 1000, 'Theme did not change GPU pixel output.'); renderer.theme = 'dark';
    });
    await test('Resize rebuilds multisample and depth attachments', async () => {
      renderer.resize(600, 360); await pixels(solid); renderer.resize(640, 400); await pixels(solid);
      assert(renderer.width === 640 && renderer.height === 400, 'Resize dimensions were not restored.');
    });
    await test('The real WebGPU canvas presents the completed scene', async () => {
      renderer.style = 'shaded-edges'; camera.setView('iso'); camera.fit(solid.entities[0].vertices);
      await frame(); renderer.render(solid); await renderer.device.queue.onSubmittedWorkDone();
      assert(renderer.canvas.getContext('webgpu') === renderer.gpuContext, 'Canvas WebGPU context mismatch.');
    });
    await new Promise(resolve => setTimeout(resolve, 100));
    finish(checks.some(t => t.status === 'failed') || renderer.gpuErrors.length ? 'FAILED' : 'PASSED');
  }
  byId('run').onclick = () => run().catch(error => {
    checks.push({ name: 'Test harness execution', status: 'failed', error: String(error.stack || error) });
    finish('FAILED');
  });
  byId('download').onclick = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'kestrel-webgpu-results.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  };
})();
