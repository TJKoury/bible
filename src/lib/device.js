import { assetUrl } from './data.js';

export async function inspectDevice() {
  const result = {
    checked:true, supported:false, f16:false,
    logicalCores:navigator.hardwareConcurrency || null,
    reportedMemoryGB:navigator.deviceMemory || null,
    storageAvailable:null, adapter:'Not available', maxBufferBytes:0, maxStorageBufferBytes:0,
    localHost:null,
  };
  if (import.meta.env?.DEV) {
    try { const response=await fetch(assetUrl('__device')); if(response.ok)result.localHost=await response.json(); } catch { /* Optional local host information. */ }
  }
  try { const storage=await navigator.storage?.estimate();if(storage?.quota)result.storageAvailable=storage.quota-(storage.usage || 0); } catch { /* Not exposed in every browser. */ }
  if (!navigator.gpu || !window.isSecureContext) return result;
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) return result;
  result.supported=true;result.f16=adapter.features.has('shader-f16');
  const info=adapter.info;
  result.adapter=[info?.vendor,info?.architecture,info?.description].filter(Boolean).join(' · ') || 'WebGPU adapter';
  result.maxBufferBytes=adapter.limits.maxBufferSize;
  result.maxStorageBufferBytes=adapter.limits.maxStorageBufferBindingSize;
  return result;
}

export function modelCompatibility(model, device) {
  if (!device?.checked) return {allowed:false,reason:'Checking this device…'};
  if (!device.supported || !device.f16) return {allowed:false,reason:'Requires WebGPU and shader-f16'};
  if (device.maxBufferBytes < 256*1024**2 || device.maxStorageBufferBytes < 128*1024**2) return {allowed:false,reason:'GPU buffer limits are too small'};
  const memory = device.localHost?.totalMemory / 1024**3 || device.reportedMemoryGB;
  if (memory && memory < model.memoryGB) return {allowed:false,reason:'Reported memory is below the model estimate'};
  if (device.storageAvailable !== null && device.storageAvailable < model.downloadGB*1024**3*1.15) return {allowed:false,reason:'Insufficient reported cache space'};
  return {allowed:true,reason:device.localHost?'Hardware checks passed; free GPU memory is not guaranteed':'GPU checks passed; available GPU memory is not exposed'};
}
