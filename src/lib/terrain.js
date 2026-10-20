// Terrarium format: https://github.com/tilezen/joerd/blob/master/docs/formats.md
export function terrariumHeight(red, green, blue) {
  return red * 256 + green + blue / 256 - 32768;
}

export function sampleTerrarium(pixels, width, height, size = 65, region = [0,0,1,1]) {
  const result = new Float32Array(size * size);
  for (let y=0;y<size;y++) for (let x=0;x<size;x++) {
    const u = Math.max(0,Math.min(width-1,Math.round((region[0]+x/(size-1)*region[2])*(width-1))));
    const v = Math.max(0,Math.min(height-1,Math.round((region[1]+y/(size-1)*region[3])*(height-1))));
    const i = (v*width+u)*4;
    result[y*size+x] = terrariumHeight(pixels[i],pixels[i+1],pixels[i+2]);
  }
  return result;
}

export function terrainProvider(C, onStatus = () => {}) {
  const cache = new Map();
  const abort = new AbortController();
  let pending = 0;
  let stopped = false;
  async function tile(x,y,z) {
    const key = `${z}/${x}/${y}`;
    if (cache.has(key)) return cache.get(key);
    const promise = (async () => {
      let response;
      try { response = await fetch(`https://tiles.mapterhorn.com/${key}.webp`, {signal:abort.signal}); }
      catch (error) { if(abort.signal.aborted)throw error; }
      if (!response?.ok) {
        response = await fetch(`https://elevation-tiles-prod.s3.amazonaws.com/terrarium/${key}.png`, {signal:abort.signal});
      }
      if (!response.ok) throw new Error('Elevation tiles are unavailable.');
      const bitmap = await createImageBitmap(await response.blob(), {colorSpaceConversion:'none',premultiplyAlpha:'none'});
      const canvas = new OffscreenCanvas(bitmap.width,bitmap.height);
      const context = canvas.getContext('2d',{willReadFrequently:true});
      context.drawImage(bitmap,0,0); bitmap.close();
      const image = context.getImageData(0,0,canvas.width,canvas.height);
      return image;
    })();
    cache.set(key,promise);
    if (cache.size > 96) cache.delete(cache.keys().next().value);
    promise.catch(() => cache.delete(key));
    return promise;
  }
  const provider = new C.CustomHeightmapTerrainProvider({
    width:65,height:65,tilingScheme:new C.WebMercatorTilingScheme(),
    credit:new C.Credit('Elevation: <a href="https://mapterhorn.com/attribution/">Mapterhorn</a> · fallback <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a>',true),
    callback(x,y,level) {
      if (stopped || pending >= 8) return undefined;
      pending++;
      // Reuse higher-resolution samples of the last source tile at close zoom;
      // this does not add detail beyond the original elevation data.
      const sourceLevel = Math.min(level,13), factor = 2 ** (level-sourceLevel);
      const sx = Math.floor(x/factor), sy = Math.floor(y/factor);
      return tile(sx,sy,sourceLevel).then(image => {
        onStatus('ready');
        return sampleTerrarium(image.data,image.width,image.height,65,[(x%factor)/factor,(y%factor)/factor,1/factor,1/factor]);
      }).catch(error => {
        if (!stopped) onStatus('error');
        throw error;
      }).finally(() => pending--);
    },
  });
  return {provider,dispose(){stopped=true;abort.abort();cache.clear();}};
}
