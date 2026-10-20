import test from 'node:test';
import assert from 'node:assert/strict';
import {terrariumHeight,sampleTerrarium} from '../src/lib/terrain.js';
import {modelCompatibility} from '../src/lib/device.js';
import {assetUrl} from '../src/lib/data.js';

test('Terrarium decoding preserves below-sea-level heights and fractional metres',()=>{
  assert.equal(terrariumHeight(128,0,0),0);
  assert.equal(terrariumHeight(127,47,0),-209);
  assert.equal(terrariumHeight(128,100,128),100.5);
  const rgba=new Uint8ClampedArray([128,0,0,255,128,10,0,255,127,47,0,255,128,100,128,255]);
  assert.deepEqual([...sampleTerrarium(rgba,2,2,2)],[0,10,-209,100.5]);
  assert.equal(sampleTerrarium(rgba,2,2,3)[4],(0+10-209+100.5)/4);
  assert.deepEqual([...sampleTerrarium(rgba,2,2,2,[1,1,0,0])],[100.5,100.5,100.5,100.5]);
});
test('model downloads require device checks, GPU features, and sufficient reported capacity',()=>{
  const model={memoryGB:1.5,downloadGB:0.4};
  const fit={checked:true,supported:true,f16:true,maxBufferBytes:256*1024**2,maxStorageBufferBytes:128*1024**2,reportedMemoryGB:8,storageAvailable:1024**3};
  assert.equal(modelCompatibility(model,null).allowed,false);
  assert.equal(modelCompatibility(model,{...fit,f16:false}).allowed,false);
  assert.equal(modelCompatibility(model,{...fit,reportedMemoryGB:1}).allowed,false);
  assert.equal(modelCompatibility(model,{...fit,storageAvailable:1024}).allowed,false);
  assert.equal(modelCompatibility(model,fit).allowed,true);
  assert.equal(modelCompatibility({...model,memoryGB:12},{...fit,localHost:{totalMemory:256*1024**3}}).allowed,true);
});
test('asset paths preserve source URLs and have a development fallback outside Vite',()=>{
  assert.equal(assetUrl('/data/catalog.json'),'/data/catalog.json');
  assert.equal(assetUrl('https://example.com/source'),'https://example.com/source');
});
