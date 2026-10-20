<script>
  import { onMount } from 'svelte';
  import 'cesium/Build/Cesium/Widgets/widgets.css';
  import { assetUrl } from './data.js';
  import { terrainProvider } from './terrain.js';
  import Icon from './Icon.svelte';
  let { points = [], theme = 'light', selected = '', selectedCandidate = '', onSelect = () => {}, reconstruction = false, evidenceSites = [], showEvidence = true, threshold = null } = $props();
  let container;
  let viewer, C, terrain, handler, resize;
  let ready = $state(false), failure = $state(''), terrainState = $state('loading');
  let lastBounds = null;
  let lastFocus = '';
  onMount(() => {
    let disposed = false;
    async function start() {
      try {
        window.CESIUM_BASE_URL = new URL(assetUrl('cesium/'),location.href).href;
        C = await import('cesium');
        if (disposed) return;
        C.Ion.defaultAccessToken = '';
        terrain = terrainProvider(C,status => { if (!disposed) terrainState = status; });
        viewer = new C.Viewer(container, {
          terrainProvider:terrain.provider, baseLayer:false, baseLayerPicker:false,
          geocoder:false, homeButton:false, sceneModePicker:false, navigationHelpButton:false,
          animation:false,timeline:false,fullscreenButton:false,infoBox:false,selectionIndicator:false,
          requestRenderMode:true,maximumRenderTimeChange:Infinity,scene3DOnly:true,
        });
        viewer.imageryLayers.addImageryProvider(new C.OpenStreetMapImageryProvider({url:'https://tile.openstreetmap.org/'}));
        viewer.scene.globe.depthTestAgainstTerrain = true;
        viewer.scene.globe.maximumScreenSpaceError = 3;
        viewer.scene.screenSpaceCameraController.minimumZoomDistance = 150;
        viewer.scene.screenSpaceCameraController.maximumZoomDistance = 16000000;
        viewer.resolutionScale = Math.min(1,1.5/(window.devicePixelRatio || 1));
        viewer.scene.renderError.addEventListener(() => { failure = 'The 3D view stopped rendering. Switch to 2D or reload this view.'; });
        handler = new C.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction(event => {
          const entity = viewer.scene.pick(event.position)?.id;
          const placeId = entity?.properties?.placeId?.getValue();
          if (placeId) onSelect(placeId, entity.id);
        },C.ScreenSpaceEventType.LEFT_CLICK);
        resize = new ResizeObserver(() => { viewer?.resize(); viewer?.scene.requestRender(); });
        resize.observe(container);
        ready = true;
      } catch (e) { if (!disposed) failure = `Cesium could not start: ${e.message || 'WebGL is unavailable'}. The 2D map remains available.`; }
    }
    start();
    return () => { disposed=true;resize?.disconnect();handler?.destroy();terrain?.dispose();if(viewer&&!viewer.isDestroyed())viewer.destroy(); };
  });
  $effect(() => {
    if (!ready || !viewer) return;
    const current = points, chosen = selected, chosenCandidate = selectedCandidate, sites = evidenceSites, display = showEvidence;
    viewer.entities.removeAll();
    for (const p of current) {
      const highlighted = chosenCandidate ? chosenCandidate === p.key : chosen === p.placeId;
      viewer.entities.add({
      id:p.key,position:C.Cartesian3.fromDegrees(p.lon,p.lat),
      properties:{placeId:p.placeId},
      point:{pixelSize:highlighted?16:9,color:C.Color.fromCssColorString(highlighted?'#e7b865':p.disputed?'#bb954f':'#466555'),outlineColor:C.Color.WHITE,outlineWidth:highlighted?3:2,heightReference:C.HeightReference.CLAMP_TO_GROUND,disableDepthTestDistance:Number.POSITIVE_INFINITY},
      label:{text:p.name || p.placeName,font:'13px sans-serif',fillColor:C.Color.WHITE,outlineColor:C.Color.fromCssColorString('#26382e'),outlineWidth:3,style:C.LabelStyle.FILL_AND_OUTLINE,pixelOffset:new C.Cartesian2(0,-22),heightReference:C.HeightReference.CLAMP_TO_GROUND,disableDepthTestDistance:Number.POSITIVE_INFINITY,distanceDisplayCondition:new C.DistanceDisplayCondition(0,150000)},
      });
    }
    if (reconstruction && display) for (const s of sites) {
      const coords = s.geometry?.coordinates;
      if (!coords || s.geometry?.type !== 'Point') continue;
      viewer.entities.add({id:`evidence-${s.id}`,position:C.Cartesian3.fromDegrees(...coords),
        point:{pixelSize:15,color:C.Color.fromCssColorString('#9569a6'),outlineColor:C.Color.WHITE,outlineWidth:2,heightReference:C.HeightReference.CLAMP_TO_GROUND,disableDepthTestDistance:Number.POSITIVE_INFINITY},
        label:{text:s.name,font:'13px sans-serif',pixelOffset:new C.Cartesian2(0,24),fillColor:C.Color.WHITE,outlineColor:C.Color.BLACK,outlineWidth:3,style:C.LabelStyle.FILL_AND_OUTLINE,heightReference:C.HeightReference.CLAMP_TO_GROUND,disableDepthTestDistance:Number.POSITIVE_INFINITY},
      });
    }
    const key = current.map(p=>`${p.key}:${p.lon}:${p.lat}`).join('|');
    const focused = current.find(p=>p.key===chosenCandidate);
    const nextFocus = focused ? `${focused.key}:${focused.lon}:${focused.lat}` : '';
    if (focused && (nextFocus!==lastFocus || key!==lastBounds)) fit([focused]);
    else if (key!==lastBounds) fit(current);
    lastBounds=key;
    lastFocus=nextFocus;
    viewer.scene.requestRender();
  });
  $effect(() => {
    if (!ready || !viewer) return;
    viewer.imageryLayers.get(0).show = !reconstruction;
    viewer.imageryLayers.get(0).brightness = theme==='dark'?0.65:0.95;
    viewer.scene.backgroundColor = C.Color.fromCssColorString(theme==='dark'?'#18211e':'#d4dfe0');
    viewer.scene.globe.baseColor = C.Color.fromCssColorString('#b2ad83');
    viewer.scene.globe.material = reconstruction ? new C.Material({fabric:{
      type:'StudyRelief',
      uniforms:{screenHeight:Number.isFinite(threshold)?threshold:-100000.0},
      // Heightmap terrain has no vertex normals. Screen-space derivatives of
      // actual terrain positions provide relief shading without invented detail.
      source:`czm_material czm_getMaterial(czm_materialInput materialInput) {
        czm_material material = czm_getDefaultMaterial(materialInput);
        float h = materialInput.height;
        vec3 color = mix(vec3(0.48,0.57,0.45),vec3(0.76,0.73,0.55),clamp((h+450.0)/1000.0,0.0,1.0));
        color = mix(color,vec3(0.91,0.87,0.76),clamp((h-550.0)/3000.0,0.0,1.0));
        if(h < screenHeight) color = vec3(0.30,0.55,0.61);
        vec3 normal = normalize(cross(dFdx(materialInput.positionToEyeEC),dFdy(materialInput.positionToEyeEC)));
        float shade = 0.45 + 0.55 * abs(dot(normal,normalize(vec3(-0.5,0.7,0.5))));
        material.diffuse = color * shade;
        material.alpha = 1.0;
        return material;
      }`,
    }}) : undefined;
    viewer.scene.requestRender();
  });
  function fit(current = points) {
    if (!viewer) return;
    if (!current.length) { viewer.camera.flyTo({destination:C.Cartesian3.fromDegrees(35,31,1500000),duration:0.7}); return; }
    const sphere = C.BoundingSphere.fromPoints(current.map(p=>C.Cartesian3.fromDegrees(p.lon,p.lat)));
    viewer.camera.flyToBoundingSphere(sphere,{duration:0.8,offset:new C.HeadingPitchRange(C.Math.toRadians(-12),C.Math.toRadians(-48),Math.max(3500,sphere.radius*3.5))});
  }
  function zoom(factor) { if(viewer){viewer.camera.zoomIn(viewer.camera.positionCartographic.height*factor);viewer.scene.requestRender();} }
  function north() { if(viewer){viewer.camera.setView({orientation:{heading:0,pitch:viewer.camera.pitch,roll:0}});viewer.scene.requestRender();} }
</script>

<div class="map-frame cesium-frame">
  <div bind:this={container} class="map-canvas" aria-label="Cesium 3D map"></div>
  {#if failure}<div class="map-notice" role="alert">{failure}</div>{:else if !ready}<div class="map-notice">Loading Cesium 3D…</div>{/if}
  {#if ready}
    <button class="map-fit" onclick={()=>fit()}><Icon name="expand" />Fit places</button>
    <div class="cesium-controls"><button aria-label="Zoom in" onclick={()=>zoom(0.35)}>+</button><button aria-label="Zoom out" onclick={()=>zoom(-0.5)}>−</button><button aria-label="Face north" onclick={north}>N</button></div>
    <div class="map-legend"><span>CesiumJS · 3D</span><span>{reconstruction?'Modern relief · historical overlays':'Modern terrain'}</span></div>
  {/if}
  {#if terrainState==='error'}<div class="tile-notice">Some elevation tiles could not load. Relief may be incomplete.</div>{/if}
</div>
<p class="map-instructions">Drag to pan · scroll to zoom · Ctrl + drag to tilt or rotate. Terrain elevations are approximate; no archaeological vertical calibration is applied.</p>
