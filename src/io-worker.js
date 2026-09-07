'use strict';
importScripts('math.js', 'geometry.js', 'model.js', 'exchange.js', 'production.js');
self.onmessage = event => { const { id, action, payload, name } = event.data; try {
    const result = action === 'parse-dxf' ? Kestrel.Exchange.parseDXF(payload, name) : action === 'write-dxf' ? Kestrel.Exchange.writeDXF(payload) : null;
    if (result === null)
        throw Error('Unknown worker action.');
    self.postMessage({ id, result });
}
catch (error) {
    self.postMessage({ id, error: error.message });
} };
