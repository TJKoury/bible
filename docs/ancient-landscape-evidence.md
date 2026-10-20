# Landscape evidence and reconstruction coverage

The registry at `public/data/reconstructions/index.json` covers **all 1,342 places** in the current OpenBible-derived corpus, retaining **4,370 candidate reference points**. It does not claim an ancient reconstruction for every place. Seven places remain unlocated; none receive invented coordinates. The source corpus covers the Protestant canon and does not provide equivalent coverage for deuterocanonical books.

Run `python3 scripts/build_reconstructions.py` after changing geography, encyclopedia or study files. `--verify-only` checks the registry against those exact inputs and validates study references. The build is local and deterministic; source hashes make changes auditable.

## Registry contract

`places[existingPlaceId]` supplies `studyIds`, a plain coverage label, candidate reference geometry and attribution, and an encyclopedia pointer with revision and contributor-history links. `studies` supplies `{id,title,path,placeIds,periodIds,status,sha256}`. Article history links explain the source's editorial history; they are not ancient landscape geometry.

Every current candidate is retained. Source scores are historical source-weighted assessments, not probabilities or present archaeological consensus. A region or river represented by a point does not gain settlement-level precision. Missing numeric coordinate accuracy remains `null`.

New study files use the same contract as `bethsaida.json`: `periods`, `sites`, `claims`, `sources` and optional `waterLevelAlternatives`. Each claim cites sources and states uncertainty. `periodIds` refer to viewing intervals, not continuous occupation. `siteIds` link to modern reference points. A future imported footprint or shoreline needs its own surveyed geometry, date range, spatial/vertical reference, source, accuracy, method and reuse license. Update the registry's geometry coverage logic when such datasets are added; its present `hasDatedGeometry:false` is deliberate.

## First evidence study

The Northern Sea of Galilee study links Bethsaida's two source entries, the lake and Magdala. It distinguishes competing El-Araj and Et-Tell identifications and provides early Roman and Byzantine evidence. Excavation reports are linked with short original paraphrases; copyrighted article bodies and plans were not downloaded.

The lake-level alternatives are **inferred intervals, an upper bound, and one find elevation**, with their types preserved. The Roman wall elevation is not a lake-level preset. The open-access [Giaime and Artzy study](https://doi.org/10.1038/s41598-022-09768-8) and the [El-Araj team's report](https://www.bethsaida-julias.com/season2report) support different interpretations. The data does not settle that disagreement.

No openly reusable, georeferenced ancient shoreline, former Jordan channel or epoch-specific ground surface was found in the reviewed Galilee sources. This is a bounded research result. The [Beteiha Plain thesis](https://digitalcommons.unomaha.edu/studentwork/3393/) describes GIS-based research, but no separately licensed vector dataset was located. No historical coordinates were traced or fabricated.

For expansion beyond Galilee, the official [ASCSA Corinth GIS portal](https://www.ascsa.org/excavations/ancient-corinth/digital-corinth/maps-gis-data-and-archaeological-data-for-corinth-and-greece) advertises openly licensed archaeological layers. The registry records this as an external data lead; it does not mark those layers as imported, date them to Paul's visits or assign them unverified accuracy.

## Cesium terrain integration

| Provider | Access and actual data | Limits relevant to this app |
| --- | --- | --- |
| [Mapterhorn](https://mapterhorn.com/data-access/) | Public XYZ Terrarium WebP, 512 px: `https://tiles.mapterhorn.com/{z}/{x}/{y}.webp`; TileJSON at `https://tiles.mapterhorn.com/tilejson.json` | Modern elevation, not ancient ground. The current environment returned 403 for TileJSON, so runtime access must be checked. Retain [source-specific attribution](https://mapterhorn.com/attribution/). |
| [AWS Terrain Tiles / Tilezen](https://registry.opendata.aws/terrain-tiles/) | Public no-account Terrarium PNG, 256 px: `https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png` | A Galilee tile at `12/2453/1651` returned 200 and `Access-Control-Allow-Origin: *` on 2026-10-20. Resolution and age vary by source. Retain the [complete applicable credits](https://github.com/tilezen/joerd/blob/master/docs/attribution.md); the combined dataset is not uniformly CC0. |
| [Cesium World Terrain](https://cesium.com/learn/cesiumjs-learn/cesiumjs-terrain/) | Cesium ion account and access token; supported Cesium terrain integration | Modern terrain. Token and service terms apply; optional configuration rather than an assumed anonymous endpoint. |
| [Cesium ellipsoid](https://cesium.com/learn/cesiumjs/ref-doc/EllipsoidTerrainProvider.html) | No terrain service or token required | A geometric globe with no elevation. It is a fallback, not relief data. |

For both Terrarium sources, decode metres as `R × 256 + G + B / 256 − 32768`, following [Tilezen's format specification](https://github.com/tilezen/joerd/blob/master/docs/formats.md). A [CustomHeightmapTerrainProvider](https://cesium.com/learn/ion-sdk/ref-doc/CustomHeightmapTerrainProvider.html) must use a Web Mercator tiling scheme for XYZ tiles, a correctly oriented sampled height grid, explicit maximum detail and credits. It supplies neither historical bathymetry nor a water mask. Handle unavailable tiles without unbounded retries or refinement. Raster resolution is not coordinate or height accuracy.

### Vertical reference and interpretation

Cesium positions use heights relative to the WGS84 ellipsoid, while archaeology reports often use local or unspecified mean-sea-level references. Orthometric elevation needs an appropriate geoid transformation before quantitative comparison. [Cesium's terrain guidance](https://community.cesium.com/t/is-cesium-ion-global-terrain-and-then-sampling-reasonably-accurate/43590/8) explains the distinction.

Mapterhorn's [Israel source record](https://github.com/mapterhorn/mapterhorn/blob/main/source-catalog/isr10/metadata.json) describes a 10 m grid derived from ASTER. That does not establish 10 m survey accuracy: [NASA identifies native ASTER GDEM](https://data.nasa.gov/dataset/aster-global-digital-elevation-model-v003-7ede1) as approximately 30 m posting with WGS84/EGM96 reference. The project's [vertical-reference issue](https://github.com/mapterhorn/mapterhorn/issues/255) documents an unresolved concern about harmonization. This review did not establish a common vertical reference for the aggregate.

Any elevation color screen over today's DEM must therefore be labeled an **uncalibrated illustration** until datum compatibility is established. Even after calibration, a threshold is not a hydraulic flood model or ancient coastline: changed sediment, buried surfaces, tectonic movement, barriers and absent bathymetry matter. Do not fabricate shoreline polygons, buildings or detailed city models from an elevation threshold. Modern imagery and labels should remain explicitly modern if displayed alongside dated evidence.
