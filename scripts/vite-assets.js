import { cpSync, createReadStream, existsSync, statSync } from 'node:fs';
import { resolve, extname, sep } from 'node:path';
import { cpus, totalmem, freemem, platform, arch } from 'node:os';

// Cesium's worker/texture files are served locally in development and copied
// alongside the production bundle. No ion token or CDN runtime is required.
export function studyAssets() {
  const cesium = resolve('node_modules/cesium/Build/Cesium');
  let output;
  return {
    name: 'study-assets',
    configResolved(config) { output = resolve(config.build.outDir); },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const pathname = new URL(req.url, 'http://localhost').pathname;
        if (pathname.endsWith('/__device')) {
          res.setHeader('Content-Type', 'application/json');
          res.setHeader('Cache-Control', 'no-store');
          res.end(JSON.stringify({ cpu:cpus()[0]?.model, logicalCores:cpus().length, totalMemory:totalmem(), freeMemory:freemem(), platform:platform(), arch:arch(), source:'Local development host' }));
          return;
        }
        const customPrefix='/models/scripture-qwen3-0.6b-v2/resolve/v2/';
        const custom=pathname.includes(customPrefix);
        const prefix = custom?customPrefix:'/cesium/';
        const directory=custom?resolve('.cache/training/qwen3-0.6b-v2/mlc-q4f16_1'):cesium;
        const start = pathname.indexOf(prefix);
        if (start < 0) return next();
        let file;
        try { file = resolve(directory, decodeURIComponent(pathname.slice(start + prefix.length))); } catch { return next(); }
        if (!file.startsWith(directory + sep) || !existsSync(file) || !statSync(file).isFile()) return next();
        const types = {'.js':'text/javascript','.json':'application/json','.css':'text/css','.wasm':'application/wasm','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml'};
        res.setHeader('Content-Type', types[extname(file)] || 'application/octet-stream');
        createReadStream(file).pipe(res);
      });
    },
    closeBundle() {
      for (const folder of ['Assets','ThirdParty','Workers','Widgets']) cpSync(resolve(cesium,folder),resolve(output,'cesium',folder),{recursive:true});
    },
  };
}
