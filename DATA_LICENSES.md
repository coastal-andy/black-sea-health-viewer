# Data sources and licences

The code in this repository is the team's own work. The data it fetches or derives keeps its original licence:

| Source | Used for | Licence / attribution |
|---|---|---|
| Copernicus Marine Service (Black Sea MFC, OC-TAC, SST-TAC, INS-TAC) | model, reanalysis, satellite and in-situ series and maps | Copernicus Marine licence, free use with attribution: "Generated using E.U. Copernicus Marine Service Information"; dataset DOIs in `docs/data_sources/copernicus.md` |
| EMODnet Physics, Chemistry, Human Activities, Bathymetry, Geology, Biology | in-situ platforms, water samples, climatologies, ports, vessel and route density (EMSA AIS), bathing waters, Natura 2000, bathymetry | CC BY 4.0, "EMODnet [thematic lot]" |
| OpenStreetMap | beaches, marinas, shipyards, harbour areas in `data/zones/` | © OpenStreetMap contributors, ODbL 1.0. The zone files derived from OSM are a derivative database under ODbL. |
| NOAA CoastWatch / PIFSC ERDDAP, ESA OC-CCI | satellite SST and chlorophyll | public domain (NOAA); OC-CCI with citation |
| Open-Meteo (marine, ERA5, GloFAS flood API) | waves, wind, Danube discharge | CC BY 4.0, "Weather data by Open-Meteo.com" |
| OBIS / EurOBIS | species occurrences | per-dataset licences, mostly CC BY / CC0 |
| ANAR (rowater.ro), Romanian ministerial orders | aquaculture lease coordinates, fishing rules | public administrative information |
| EEA | bathing-water classification | EEA standard re-use policy, attribution |

The cached downloads (`data/cache/`) are not in the repository; `scripts/preload_cache.py` rebuilds them.
