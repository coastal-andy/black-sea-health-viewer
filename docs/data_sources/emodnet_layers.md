# GIS layers for the Sprint 1 pressure map (EMODnet + OSM)

Module: `src/marinekit/sources/emodnet_layers.py`. Cache: `data/cache/emodnet_layers/`.
Study box: `BBOX_RO = (28.4, 43.6, 30.6, 45.4)` (lon/lat, EPSG:4326). Every count below is for that box unless stated.
All checks were live HTTP requests on **2026-11-23**: WFS 1.0.0 GetFeature as `application/json`, WMS 1.1.1
GetMap PNG 400x330 (the "% non-transparent" value is the share of the PNG that has data), and the module smoke test
(`cd src && ../.venv/bin/python -m marinekit.sources.emodnet_layers`).

```python
from marinekit.sources.emodnet_layers import LAYERS, fetch_wfs, fetch_gdf, wms_tile_layer, wms_getmap, \
    depth_at, depth_profile, sector_layers, bathymetry_wcs_url
gj = fetch_wfs("bathing_waters")                 # GeoJSON dict + gj["meta"] (count, truncated, attribution...)
folium.raster_layers.WmsTileLayer(**wms_tile_layer("vessel_density_fishing")).add_to(m)
depth_at(44.17, 28.72)                           # 26.3 (m, positive down; negative = land elevation)
```

`wms_tile_layer()` works for WFS layers too (same GeoServer renders them with its default style). Verified
2026-11-23: `wms_getmap` returned a PNG for `bathing_waters` (2.7% of the image has data), `natura2000` (35%) and
`ports` (2.5%). `folium.raster_layers.WmsTileLayer(**wms_tile_layer("vessel_density_fishing"))` renders, and the
TIME parameter is passed through. Layers with a
default `cql` (port statistics, bathing waters, fishing effort) filter on the server by country/year and the bbox is
applied in the client, because GeoServer will not take both BBOX and CQL_FILTER. Pass `cql=""` to drop the filter or
`cql="..."` to pick another year.

## Endpoints

| Service | URL | Notes |
|---|---|---|
| EMODnet Human Activities WFS | `https://ows.emodnet-humanactivities.eu/wfs` | 159 feature types (`emodnet:*`) |
| EMODnet Human Activities WMS | `https://ows.emodnet-humanactivities.eu/wms` | 206 layers, incl. raster vessel/route density (TIME dim) |
| EMODnet Bathymetry WMS | `https://ows.emodnet-bathymetry.eu/wms` | `emodnet:mean_atlas_land`, `emodnet:mean_multicolour`, `emodnet:contours` |
| EMODnet Bathymetry WCS | `https://ows.emodnet-bathymetry.eu/wcs` | coverage `emodnet__mean` (GeoTIFF float32) |
| EMODnet Bathymetry REST | `https://rest.emodnet-bathymetry.eu/depth_sample?geom=POINT(lon lat)`, `/depth_profile?geom=LINESTRING(...)` | JSON |
| EMODnet Seabed Habitats WMS | `https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_view/wms` | **HTTP 503 all day on 2026-11-23** |
| EMODnet Geology WMS | `https://drive.emodnet-geology.eu/geoserver/gtk/wms` | seabed substrate (fallback for habitats) |
| EMODnet Biology WFS (VLIZ) | `https://geo.vliz.be/geoserver/Dataportal/wfs` | EurOBIS grids / occurrences |
| OBIS API | `https://api.obis.org/v3/occurrence?geometry=POLYGON(...)` | 325,159 records / 1,369 species in BBOX_RO |
| OSM Overpass | `https://overpass-api.de/api/interpreter` (+2 mirrors) | over capacity (HTTP 502) on 2026-11-23; module falls back to Nominatim |
| EEA discomap (Natura 2000, bathing water ArcGIS) | `bio.discomap.eea.europa.eu`, `water.discomap.eea.europa.eu` | **TCP timeout** on 2026-11-23. The same EEA data is served by EMODnet HA (below) |

## Layers by sector

Status column: **V** = verified 2026-11-23 (what was run and what came back), **NV** = not verified.

### (1) Ports & maritime logistics

| key | layer | kind | shows | RO coverage | status |
|---|---|---|---|---|---|
| `ports` | `emodnet:portlocations` | WFS | Eurostat/GISCO main ports | 4: Constanta, Midia, Mangalia, Tulcea | V: GetFeature bbox -> 4 features, Constanta at 28.657, 44.138 |
| `port_goods` | `emodnet:portgoods` | WFS | goods per port x year x cargo type x direction (`thousand_of_tonnes`), 1997-2025 | default `country='RO' AND year=2024`: 160 rows, 80 in bbox. Constanta 2024 (direction Total): dry bulk 29,036 kt, liquid bulk 17,125, containers 7,860, other 2,758 | V: ran CQL queries; 2025 covers only part of the year (dry bulk 5,930 kt), so 2024 is the default |
| `port_vessels` | `emodnet:portvessels` | WFS | vessel calls per type/tonnage (`nofvessels`, `gross_tonnage__gt_thousand`) | 2024 TOTAL: 34 rows, 24 in bbox | V: 24 features |
| `port_passengers` | `emodnet:portpassengers` | WFS | passengers per port/direction | 2024: 64 in bbox | V |
| `port_waste` | `emodnet:wasteatports` | WFS | ship waste delivered to port reception facilities (MARPOL annexes, m3/t) | 5 rows (Constanta, 2018...) | V: 5 features |
| `vessel_density_all` | `vesseldensity_allavg` | WMS | EMSA AIS vessel density (h/km2/month), 1 km, annual, TIME 2017-2024 (default 2024) | full coverage | V: GetMap PNG, 61% of image has data |
| `vessel_density_cargo` | `vesseldensity_09avg` | WMS | cargo ships | | V: PNG 57% |
| `vessel_density_tanker` | `vesseldensity_10avg` | WMS | tankers (oil-spill risk proxy) | | V: PNG 42% |
| `vessel_density_tug` | `vesseldensity_07avg` | WMS | tug & towing (port operations) | | V: PNG 13% |
| `route_density_all` | `routedensity_allavg` | WMS | EMSA route density, TIME 2019-2025 | | V: PNG 64% |

Other density layers on the same WMS: `vesseldensity_{00..12}avg` (00 other, 02 service, 06 high-speed, 11 military,
12 unknown), monthly `vesseldensity_XX` (TIME monthly), `routedensity_0{1..5}avg|seasonal`.

### (2) Shipyards & marine engineering

| key | layer | kind | shows | RO coverage | status |
|---|---|---|---|---|---|
| `shipyards_osm` | OSM `industrial=shipyard`/`landuse=shipyard` | Overpass, falls back to Nominatim | shipyard sites | 9 via Nominatim: Santierul Naval Constanta, GSP Shipyard Agigea, Santierul Naval Mangalia, Damen Shipyards Mangalia, Midia Ship Repair, Santierul Naval Midia, VARD Tulcea, Sulina, Mangalia Ship Repair | V (Nominatim fallback): Overpass returned 502 "at capacity" all day; the 9 features are cached. Galati (Damen) and Braila are west of the box, so pass a wider bbox to get them |
| `vessel_density_dredging` | `vesseldensity_03avg` | WMS | dredging / underwater-ops vessels (marine works) | | V: PNG 3% (port approaches) |
| `offshore_platforms_osm` | OSM `man_made=offshore_platform` | Overpass | oil/gas platforms on the shelf | none yet | **NV**: Overpass mirrors timed out; Nominatim has no usable hits |

EMODnet HA has **no shipyard layer**. Its `platforms`, `pipelines`, `hydrocarbons` (boreholes) and `dredging` layers
return 0 features for Romania (whole Black Sea: platforms 7 in BG/RU/UA, dredging 21 in BG only). Romanian dredging
and dumping are not in EMODnet.

### (3) Coastal & marine tourism

| key | layer | kind | shows | RO coverage | status |
|---|---|---|---|---|---|
| `bathing_waters` | `emodnet:bathingwaters` (EEA Bathing Water Directive) | WFS | site, `year`, `status` = **that season's class**, `class` = latest class repeated on every year (do not use `class` for history) | 49 RO coastal sites per year (2007-2024); default `countrycod='RO' AND year='2024'` -> 49. Per-year history: `bathing_water_history()` (matches EEA: 2022 45/4, 2023 34/15, 2024 41/8 Excellent/Good) | V: e.g. "PLAJA MAMAIA I ZONA 2 ENIGMA", 1 - Excellent, 2024 |
| `marinas_osm` | `emodnet:osmmarinas` | WFS | OSM marinas | 23 (20 RO, 2 UA, 1 BG) | V |
| `tourism_nuts3` | `emodnet:tourismnuts3` | WFS | tourism indicators per NUTS3 (nights, beds, blue flags, % excellent BW) | 21 polygons intersect the box. For RO223 Constanta most numbers are null; blue_flags=6, diversity_index=0.38 | V (attributes sparse) |
| `tourism_lau` | `emodnet:tourismlau` | WFS | nights spent per municipality | 75 LAU polygons | V |
| `vessel_density_passenger` | `vesseldensity_08avg` | WMS | passenger/cruise/ferry | | V: PNG 3% |
| `vessel_density_pleasure` | `vesseldensity_05avg` | WMS | pleasure craft | | V: PNG 1% |
| `vessel_density_sailing` | `vesseldensity_04avg` | WMS | sailing | | V: PNG 1% |

`emodnet:emodnetmarinas` (TransEurope) has no Black Sea data. `port_passengers` also covers cruise traffic.

### (4) Fishing

| key | layer | kind | shows | RO coverage | status |
|---|---|---|---|---|---|
| `vessel_density_fishing` | `vesseldensity_01avg` | WMS | AIS fishing-vessel density (only AIS-equipped vessels, mostly >15 m) | hot spot off Constanta/Midia and along the BG coast | V: PNG 7%, inspected visually |
| `route_density_fishing` | `routedensity_02avg` | WMS | fishing routes | | V: PNG 15% |
| `fishing_effort_ro` | `emodnet:gfcmsubareaeffortbycountry` | WFS | RO fleet effort per year in GSA 29: fishing days, kW-days, GT-days, hours | 12 rows (years). 2024: 4,000 fishing days, 211,467 kW-days | V. The polygon is the whole GSA 29, so this is a statistic, not a spatial pattern |
| `fishing_effort_gear` | `emodnet:gfcmsubareaeffort` | WFS | effort by gear (`fishtech`) and length class | 73 RO rows | V |
| `fish_sales` | `emodnet:fishsales` | WFS | EUMOFA first sales by landing place | 107 rows, **all Bulgarian** ports | V (no RO ports) |

The ICES/OSPAR fishing-intensity grids (`fishingbottomottertrawls`, `fishingsurface`, `fishingsubsurface`...) cover NE
Atlantic and Baltic only: 0 features in the Black Sea.

### (5) Aquaculture

| key | layer | kind | shows | RO coverage | status |
|---|---|---|---|---|---|
| `shellfish_production` | `emodnet:shellfish` | WFS | shellfish farms | **0 in RO**; 44 in the whole Black Sea, all Bulgarian | V (empty for RO) |
| `finfish_production` | `emodnet:finfish` | WFS | marine finfish farms | 0 in the Black Sea | V (empty) |
| `shellfish_licences` | `emodnet:shellfishlics` | WFS | licensed polygons | 0 in the Black Sea | V (empty) |

EMODnet has **no Romanian marine aquaculture**. `freshwater` and `macroalgae` also return 0 in the box. Other
sources are needed (see "Gaps" below).

### Context: protected areas

| key | layer | kind | shows | RO coverage | status |
|---|---|---|---|---|---|
| `natura2000` | `emodnet:natura2000areas` (EEA) | WFS | SCI/SAC (`sitetype` B), SPA (A), `mar_perc` marine share | 24 sites (20 RO). 10 fully marine (`mar_perc`=100): ROSAC0269 **Vama Veche - 2 Mai**, ROSCI0066 Delta Dunarii zona marina, ROSPA0076 Marea Neagra, ROSCI0311 Canionul Viteaz, ROSCI0413 Lobul sudic al Campului de Phyllophora al lui Zernov, ROSAC0094 Izvoarele sulfuroase submarine Mangalia, ROSAC0197 Plaja submersa Eforie, ROSAC0273 Capul Tuzla, ROSCI0281 Cap Aurora, ROSCI0293 Costinesti - 23 August | V |
| `nationally_designated` | `emodnet:nationallydesignatedareas` (CDDA) | WFS | national protected areas | 19 (15 RO, incl. "Vama Veche - 2 Mai" marine reserve, Dunele marine de la Agigea, Lacul Techirghiol) | V |
| `wdpa` | `emodnet:wdpaareas` | WFS | WDPA | 5, Ukrainian only (Danube Biosphere Reserve UA side) | V |

`emodnet:marineprotectedareas` (Regional Sea Convention MPAs) has no Black Sea data. The EEA's own Natura 2000 and
CDDA ArcGIS services (`bio.discomap.eea.europa.eu`) were unreachable: **NV**.

### Context: other pressures (land-based, energy, legacy)

| key | layer | RO coverage | status |
|---|---|---|---|
| `wastewater_plants` | `emodnet:treatmentplants` (UWWTD, `capacit_pe`) | 173 (e.g. RAJA Constanta Nord, 255,000 p.e.) | V |
| `discharge_points` | `emodnet:dischargepoints` | 142 | V |
| `wind_farms` | `emodnet:windfarms` | 3 planned RO projects (e.g. Black Sea 1, 500 MW) | V |
| `wrecks` | `emodnet:wwshipwrecks` (UKHO) | 23 | V |
| `lighthouses` | `emodnet:lighthouses` | 21 | V |
| `military_areas` | `emodnet:militaryareaspoly` | 1 (BG) | V |

Empty for RO, not in LAYERS: `munitions`/`munitionspoly` (3 points elsewhere in the Black Sea), `pipelines`,
`dredgespoil`, `aggregates`, `mspzoningpoly`. `telecablesactual` and `powercables` are WMS only, and their GetMap is
**fully transparent** over the box, so they have no RO data.

### Context: bathymetry, seabed, biology

| key | layer | kind | status |
|---|---|---|---|
| `depth_at()` | REST `depth_sample` | JSON | V: Constanta (44.17, 28.72) -> **26.3 m**. Mamaia 17.2, Midia 12.1, Mangalia 24.1, Sf. Gheorghe 28.6, Sulina 9.8, offshore (44.40, 29.50) 53.2. Land (44.40, 28.40) -> elevation +99 m, returned as -99. Near the coast the `reference` is GEBCO2024, i.e. infilled cells |
| `depth_profile()` | REST `depth_profile` | JSON | V: Constanta to 29.5E along 44.17N -> 1000 samples, 20.7 to 57.3 m |
| `bathymetry` | `emodnet:mean_atlas_land` | WMS | V: PNG, 100% has data |
| `bathymetry_colour` | `emodnet:mean_multicolour` | WMS | V: PNG 71% (sea only) |
| `depth_contours` | `emodnet:contours` | WMS | V: PNG 3% |
| `bathymetry_wcs_url()` | WCS `emodnet__mean` | GeoTIFF | V: GetCoverage 28.6-29.0E x 44.0-44.3N -> 384x288 float32 TIFF (442 kB). Reading it needs rasterio, which is not installed |
| `seabed_habitats` | `eusm2023_eunis2019_full` (EUSeaMap 2023) | WMS | **NV**: every request to ows.emodnet-seabedhabitats.eu (capabilities, GetMap, WFS) returned HTTP 503 after about 133 s, tried 3 times over the day. The layer name is unconfirmed: check GetCapabilities when the service is back |
| `seabed_substrate` | `seabed_substrate_250k` (EMODnet Geology, Folk) | WMS | V: PNG 55%. Use as the habitat proxy |
| `seabed_substrate_1m` | `seabed_substrate_1m` | WMS | V: PNG 71% |
| `biology_records_grid` | `Dataportal:eurobis_grid_15m-obisenv` | WFS | V: 68 cells of 0.25 deg with `RecordCount` (e.g. 1,793 records in the cell at 29.75-30.0E, 45.25-45.5N). This counts records (sampling effort), not abundance |

OBIS (`api.obis.org/v3`) is a good option for species points: `/statistics` over BBOX_RO gave 325,159 records,
1,369 species, 110 datasets, 1927-2026 (e.g. NIMRD zooplankton 1973-1980). Not wrapped in the module.

## Five sectors -> pressures -> indicators -> layers (proposal for the Sprint 1 map)

| Sector | Main pressures on the ecosystem | Indicator (what we map/score) | Layers (keys) | Gap / other source |
|---|---|---|---|---|
| 1 Ports & maritime logistics | ship traffic (noise, emissions, collision risk), oil/ballast spills, port waste, dredging of channels, NIS via ballast | vessel density h/km2 (all, cargo, tanker); route density; cargo throughput kt/yr per port; vessel calls; waste delivered | `vessel_density_all/_cargo/_tanker/_tug`, `route_density_all`, `ports`, `port_goods`, `port_vessels`, `port_waste` | Romanian dredging volumes / dumping sites are missing (ask APMC / Constanta Port Authority); oil-spill detections come from CleanSeaNet (EMSA, restricted) |
| 2 Shipyards & marine engineering | antifouling/TBT, metals, hull blasting, effluents, coastal works and underwater ops | shipyard locations (+buffer); dredging/underwater-ops vessel density; offshore platforms; planned wind farms | `shipyards_osm`, `vessel_density_dredging`, `offshore_platforms_osm` (Overpass down), `wind_farms` | shipyard sizes and emissions: E-PRTR / EU Industrial Emissions portal; Romanian offshore platforms (OMV Petrom, Black Sea Oil & Gas Midia) not in EMODnet |
| 3 Coastal & marine tourism | bathing-season sewage loads, beach works and nourishment, trampling, recreational boating, litter | % bathing sites Excellent/Good per year; nights spent per LAU; marina count; pleasure/passenger vessel density; WWTP capacity near beaches | `bathing_waters`, `tourism_lau`, `tourism_nuts3`, `marinas_osm`, `vessel_density_pleasure/_sailing/_passenger`, `wastewater_plants`, `discharge_points` | beach litter: EMODnet Chemistry beach-litter WMS (not covered here); INS TEMPO tourism statistics |
| 4 Fishing | bottom trawling (seabed disturbance), by-catch (dolphins, turbot gillnets), stock depletion | AIS fishing density h/km2; fishing routes; RO effort days and kW-days per year (GSA 29); effort by gear | `vessel_density_fishing`, `route_density_fishing`, `fishing_effort_ro`, `fishing_effort_gear` | small-scale coastal fishery (no AIS) is invisible, so landings by port need ANPA/INS data; Global Fishing Watch API (token) for gear-resolved effort |
| 5 Aquaculture | organic enrichment, escapes, disease, space use | farm locations/area, production t/yr | (EMODnet shellfish/finfish/licences: **0 RO features**) | Romanian mussel farms are not in EMODnet. Need ANPA register / Romanian MSP data, or digitise from imagery |
| Context | habitats, protected areas, depth, Danube influence | overlap of pressures with Natura 2000 marine sites; depth zones; substrate | `natura2000`, `nationally_designated`, `bathymetry`, `depth_contours`, `seabed_substrate`, `seabed_habitats` (503), `biology_records_grid` | Danube plume: use Copernicus Marine chl/SPM/salinity (other agent); river discharge: GRDC / Danube ICPDR |

Simple score for Sprint 1: rasterise each indicator onto one common grid (e.g. the 1 km EMSA grid, or the 0.05 deg
EMODnet DTM decimated), normalise each to 0-1 (log for densities), weight them per sector, then overlay `natura2000`
(marine share 100%) to rank "pressure inside protected areas". Vessel density PNGs carry colour only, not values. For
numeric values, download the EMSA density GeoTIFFs from the EMODnet HA download page; that was not tried here.

## Gaps and caveats

- **Aquaculture (sector 5) and Romanian shipyards/platforms (sector 2) are absent from EMODnet.** Shipyards come from
  OSM (Nominatim fallback, 9 sites). Platforms and aquaculture are still open.
- Seabed Habitats (EUSeaMap) returned 503 on 2026-11-23. EMODnet Geology substrate is the stand-in.
- EEA discomap was unreachable. EMODnet HA re-serves EEA Natura 2000, CDDA, bathing waters and UWWTD, so nothing is
  lost.
- Port statistics: one row per port x year x category. Filter on `direction='Total'` (goods) or `tonnage='TOTAL'`
  (vessels) before summing to avoid double counting. 2025 is a partial year.
- `fetch_wfs` caches the first successful answer per (key, bbox, cql). If shipyards were cached from the Nominatim
  fallback, call `fetch_wfs("shipyards_osm", refresh=True)` once Overpass recovers to get the fuller OSM tag query.
- EMODnet HA GeoServer is fast (1-10 s). Seabed Habitats and Overpass are the fragile services, so warm the cache
  before the demo.
