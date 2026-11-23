"""Copernicus Marine Service (CMEMS) access for the Romanian Black Sea coast.

Everything here was checked live on 2026-11-23 with copernicusmarine 2.5.1 (see
docs/data_sources/copernicus.md for what was run and what came back).

What needs a (free) Copernicus Marine account
---------------------------------------------
* NO login:  catalogue metadata (``copernicusmarine.describe``) and WMTS map tiles
             (``wmts_layers`` / ``wmts_tile_url``), which are good for folium backgrounds.
* login:     every data read: ``open_dataset``/``subset``/``read_dataframe``/``get``, so
             ``fetch_timeseries``, ``fetch_field``, ``climatology``, ``fetch_insitu``,
             ``insitu_platforms``.
  Without credentials the toolbox *prompts for a username on stdin* (which blocks a web app)
  or, with stdin closed, silently returns None. We therefore check credentials first and
  raise ``CopernicusLoginRequired`` with instructions (see ``login_help()``).

Conventions (see sources/__init__.py): canonical variable names, DatetimeIndex UTC tz-naive,
df.attrs = meta(...), every network call cached under data/cache/copernicus.
"""

from __future__ import annotations

import logging
import math
import os
import re
import time as _time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import copernicusmarine  # noqa: F401  (imported first: its dictConfig would reset our log level below)
import requests
import xarray as xr

from . import BBOX_RO, CANONICAL, STATIONS, cache_key, cached_path, meta

SOURCE = "copernicus"
log = logging.getLogger(__name__)
# The toolbox logs a lot at INFO/WARNING (incl. version retirement notices); keep the app quiet.
logging.getLogger("copernicusmarine").setLevel(os.environ.get("MARINEKIT_CMEMS_LOGLEVEL", "ERROR"))


def _now() -> pd.Timestamp:
    return pd.Timestamp.now("UTC").tz_localize(None)

CITATION = (
    "Generated using E.U. Copernicus Marine Service Information; https://doi.org/{doi}"
)
LICENCE = "Copernicus Marine Service licence (free, open; attribution required): https://marine.copernicus.eu/user-corner/service-commitments-and-licence"

# Native units -> canonical units conversions
_KELVIN = {"kelvin", "K", "degK"}

# --------------------------------------------------------------------------------------------
# Catalogue. dataset_id may be a list: candidates tried in order (the 2026-11-24 13:00Z catalogue
# release retires some ocean-colour L3 MY datasets and adds L4 gap-free ones; see docs).
# vars: native -> canonical (names not in CANONICAL are lower-case extras).
# res_deg: nominal grid step (deg), used to size the small box around a point.
# method: default point extraction, "nearest" (nearest valid sea cell) or "box" (mean of cells
#         in the box, better for gappy L3 satellite data).
# clim: catalogue key used for the reference climatology; clim_years: default reference period.
# --------------------------------------------------------------------------------------------
CATALOG: dict[str, dict] = {
    # ---- Model analysis/forecast, physics: BLKSEA_ANALYSISFORECAST_PHY_007_001 (CMCC/NEMO, ~2.5 km, 121 z-levels)
    "phy_temp": dict(product="BLKSEA_ANALYSISFORECAST_PHY_007_001", dataset_id="cmems_mod_blk_phy-temp_anfc_2.5km_P1D-m",
                     vars={"thetao": "temp", "bottomT": "bottom_temp"}, origin="model", res_deg=0.025, depth=True,
                     freq="P1D", clim="rea_phy_temp", doi="10.48670/mds-00355",
                     description="Black Sea physics analysis+10-day forecast, daily mean potential temperature"),
    "phy_sal": dict(product="BLKSEA_ANALYSISFORECAST_PHY_007_001", dataset_id="cmems_mod_blk_phy-sal_anfc_2.5km_P1D-m",
                    vars={"so": "sal"}, origin="model", res_deg=0.025, depth=True, freq="P1D", clim="rea_phy_sal",
                    doi="10.48670/mds-00355", description="Black Sea physics analysis/forecast, daily salinity"),
    "phy_cur": dict(product="BLKSEA_ANALYSISFORECAST_PHY_007_001", dataset_id="cmems_mod_blk_phy-cur_anfc_2.5km_P1D-m",
                    vars={"uo": "current_u", "vo": "current_v"}, origin="model", res_deg=0.025, depth=True, freq="P1D",
                    clim="rea_phy_cur", doi="10.48670/mds-00355",
                    description="Black Sea physics analysis/forecast, daily currents"),
    "phy_ssh": dict(product="BLKSEA_ANALYSISFORECAST_PHY_007_001", dataset_id="cmems_mod_blk_phy-ssh_anfc_2.5km_P1D-m",
                    vars={"zos": "ssh"}, origin="model", res_deg=0.025, depth=False, freq="P1D", clim="rea_phy_ssh",
                    doi="10.48670/mds-00355", description="Black Sea physics analysis/forecast, daily sea surface height"),
    "phy_mld": dict(product="BLKSEA_ANALYSISFORECAST_PHY_007_001", dataset_id="cmems_mod_blk_phy-mld_anfc_2.5km_P1D-m",
                    vars={"mlotst": "mld"}, origin="model", res_deg=0.025, depth=False, freq="P1D", clim="rea_phy_mld",
                    doi="10.48670/mds-00355", description="Black Sea physics analysis/forecast, daily mixed layer depth"),
    "wav": dict(product="BLKSEA_ANALYSISFORECAST_WAV_007_003", dataset_id="cmems_mod_blk_wav_anfc_2.5km_PT1H-i",
                vars={"VHM0": "wave_height", "VTPK": "wave_period", "VMDR": "wave_dir"}, origin="model", res_deg=0.025,
                depth=False, freq="PT1H", doi="10.48670/mds-00360",
                description="Black Sea waves analysis/forecast, hourly instantaneous"),
    # ---- Model analysis/forecast, biogeochemistry: BLKSEA_ANALYSISFORECAST_BGC_007_010 (BAMHBI, ~2.5 km, 59 levels)
    "bgc_chl": dict(product="BLKSEA_ANALYSISFORECAST_BGC_007_010", dataset_id="cmems_mod_blk_bgc-pft_anfc_2.5km_P1D-m",
                    vars={"chl": "chl", "phyc": "phyc", "zooc": "zooc"}, origin="model", res_deg=0.025, depth=True, freq="P1D",
                    clim="rea_bgc_chl", doi="10.48670/mds-00354", description="Black Sea BGC analysis/forecast, daily chlorophyll / phyto- / zooplankton carbon"),
    "bgc_o2": dict(product="BLKSEA_ANALYSISFORECAST_BGC_007_010", dataset_id="cmems_mod_blk_bgc-pp-o2_anfc_2.5km_P1D-m",
                   vars={"o2": "o2", "o2b": "o2_bottom", "nppv": "npp"}, origin="model", res_deg=0.025, depth=True, freq="P1D",
                   clim="rea_bgc_o2", doi="10.48670/mds-00354", description="Black Sea BGC analysis/forecast, daily dissolved O2, bottom O2, net primary production"),
    "bgc_nut": dict(product="BLKSEA_ANALYSISFORECAST_BGC_007_010", dataset_id="cmems_mod_blk_bgc-nut_anfc_2.5km_P1D-m",
                    vars={"no3": "no3", "po4": "po4", "odu": "odu"}, origin="model", res_deg=0.025, depth=True, freq="P1D",
                    clim="rea_bgc_nut", doi="10.48670/mds-00354", description="Black Sea BGC analysis/forecast, daily nitrate, phosphate, oxygen demand units"),
    "bgc_car": dict(product="BLKSEA_ANALYSISFORECAST_BGC_007_010", dataset_id="cmems_mod_blk_bgc-car_anfc_2.5km_P1D-m",
                    vars={"ph": "ph", "dissic": "dic", "talk": "alk"}, origin="model", res_deg=0.025, depth=True, freq="P1D",
                    clim="rea_bgc_car", doi="10.48670/mds-00354", description="Black Sea BGC analysis/forecast, daily pH, DIC, alkalinity"),
    "bgc_optics": dict(product="BLKSEA_ANALYSISFORECAST_BGC_007_010", dataset_id="cmems_mod_blk_bgc-optics_anfc_2.5km_P1D-m",
                       vars={"kd": "kd", "lght": "light"}, origin="model", res_deg=0.025, depth=True, freq="P1D",
                       doi="10.48670/mds-00354", description="Black Sea BGC analysis/forecast, daily light attenuation (PAR, not Kd490) and light"),
    # ---- Multi-year reanalysis (reference / climatology)
    "rea_phy_temp": dict(product="BLKSEA_MULTIYEAR_PHY_007_004", dataset_id="cmems_mod_blk_phy-temp_my_2.5km_P1D-m",
                         vars={"thetao": "temp", "bottomT": "bottom_temp"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D",
                         clim_years=(1993, 2022), doi="10.48670/mds-00356", description="Black Sea physics reanalysis 1993-2025, daily temperature"),
    "rea_phy_sal": dict(product="BLKSEA_MULTIYEAR_PHY_007_004", dataset_id="cmems_mod_blk_phy-sal_my_2.5km_P1D-m",
                        vars={"so": "sal"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D", clim_years=(1993, 2022),
                        doi="10.48670/mds-00356", description="Black Sea physics reanalysis, daily salinity"),
    "rea_phy_cur": dict(product="BLKSEA_MULTIYEAR_PHY_007_004", dataset_id="cmems_mod_blk_phy-cur_my_2.5km_P1D-m",
                        vars={"uo": "current_u", "vo": "current_v"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D",
                        clim_years=(1993, 2022), doi="10.48670/mds-00356", description="Black Sea physics reanalysis, daily currents"),
    "rea_phy_ssh": dict(product="BLKSEA_MULTIYEAR_PHY_007_004", dataset_id="cmems_mod_blk_phy-ssh_my_2.5km_P1D-m",
                        vars={"zos": "ssh"}, origin="reanalysis", res_deg=0.025, depth=False, freq="P1D", clim_years=(1993, 2022),
                        doi="10.48670/mds-00356", description="Black Sea physics reanalysis, daily SSH"),
    "rea_phy_mld": dict(product="BLKSEA_MULTIYEAR_PHY_007_004", dataset_id="cmems_mod_blk_phy-mld_my_2.5km_P1D-m",
                        vars={"mlotst": "mld"}, origin="reanalysis", res_deg=0.025, depth=False, freq="P1D", clim_years=(1993, 2022),
                        doi="10.48670/mds-00356", description="Black Sea physics reanalysis, daily MLD"),
    "rea_bgc_chl": dict(product="BLKSEA_MULTIYEAR_BGC_007_005", dataset_id="cmems_mod_blk_bgc-plankton_my_2.5km_P1D-m",
                        vars={"chl": "chl", "phyc": "phyc"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D",
                        clim_years=(1993, 2022), doi="10.48670/mds-00372", description="Black Sea BGC reanalysis 1992-2024, daily chlorophyll"),
    "rea_bgc_o2": dict(product="BLKSEA_MULTIYEAR_BGC_007_005", dataset_id="cmems_mod_blk_bgc-bio_my_2.5km_P1D-m",
                       vars={"o2": "o2", "o2b": "o2_bottom", "nppv": "npp"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D",
                       clim_years=(1993, 2022), doi="10.48670/mds-00372", description="Black Sea BGC reanalysis, daily O2, bottom O2, NPP"),
    "rea_bgc_nut": dict(product="BLKSEA_MULTIYEAR_BGC_007_005", dataset_id="cmems_mod_blk_bgc-nut_my_2.5km_P1D-m",
                        vars={"no3": "no3", "po4": "po4"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D",
                        clim_years=(1993, 2022), doi="10.48670/mds-00372", description="Black Sea BGC reanalysis, daily nitrate & phosphate"),
    "rea_bgc_car": dict(product="BLKSEA_MULTIYEAR_BGC_007_005", dataset_id="cmems_mod_blk_bgc-car_my_2.5km_P1D-m",
                        vars={"ph": "ph", "dissic": "dic", "talk": "alk"}, origin="reanalysis", res_deg=0.025, depth=True, freq="P1D",
                        clim_years=(1993, 2022), doi="10.48670/mds-00372", description="Black Sea BGC reanalysis, daily pH / carbonate system"),
    # ---- Satellite ocean colour (CNR-GOS)
    "sat_chl_l4_nrt": dict(product="OCEANCOLOUR_BLK_BGC_L4_NRT_009_152", dataset_id="cmems_obs-oc_blk_bgc-plankton_nrt_l4-gapfree-multi-1km_P1D",
                           vars={"CHL": "chl"}, origin="satellite", res_deg=0.0125, depth=False, freq="P1D", clim="sat_chl_l4_my",
                           doi="10.48670/moi-00302", description="Satellite chl-a L4 gap-free daily, 1 km, NRT (rolling ~3 weeks; older dates are in sat_chl_l4_my)"),
    "sat_chl_l4_my": dict(product="OCEANCOLOUR_BLK_BGC_L4_MY_009_154", dataset_id="cmems_obs-oc_blk_bgc-plankton_my_l4-gapfree-multi-1km_P1D",
                          vars={"CHL": "chl"}, origin="satellite", res_deg=0.0125, depth=False, freq="P1D", clim_years=(1998, 2022),
                          doi="10.48670/moi-00304", description="Satellite chl-a L4 gap-free daily, 1 km, multi-year 1997-present (incl. interim, ~12 days latency)"),
    "sat_chl_l3_nrt": dict(product="OCEANCOLOUR_BLK_BGC_L3_NRT_009_151", dataset_id="cmems_obs-oc_blk_bgc-plankton_nrt_l3-olci-300m_P1D",
                           vars={"CHL": "chl"}, origin="satellite", res_deg=0.003, depth=False, freq="P1D", method="box", box_deg=0.02,
                           doi="10.48670/moi-00301", description="Satellite chl-a L3 daily (cloud gaps), Sentinel-3 OLCI 300 m, NRT (~2 weeks)"),
    "sat_chl_l3_my": dict(product="OCEANCOLOUR_BLK_BGC_L3_MY_009_153",
                          dataset_id=["cmems_obs-oc_blk_bgc-plankton_my_l3-multi-1km_P1D", "cmems_obs-oc_blk_bgc-plankton_my_l3-olci-300m_P1D"],
                          vars={"CHL": "chl"}, origin="satellite", res_deg=0.0125, depth=False, freq="P1D", method="box", box_deg=0.03,
                          doi="10.48670/moi-00303", description="Satellite chl-a L3 daily multi-sensor 1 km (fallback OLCI 300 m), multi-year"),
    # Phytoplankton SIZE classes (chl in micro / nano / pico, mg m-3). Size classes, not taxonomy: diatoms and large
    # dinoflagellates are both MICRO. Only the multi-sensor 1 km L3 datasets carry them (the L4 and OLCI 300 m sets have CHL only).
    "sat_pft_l3_my": dict(product="OCEANCOLOUR_BLK_BGC_L3_MY_009_153", dataset_id="cmems_obs-oc_blk_bgc-plankton_my_l3-multi-1km_P1D",
                          vars={"CHL": "chl", "MICRO": "micro", "NANO": "nano", "PICO": "pico"}, origin="satellite", res_deg=0.0125,
                          depth=False, freq="P1D", method="box", box_deg=0.05, clim_years=(1998, 2022), doi="10.48670/moi-00303",
                          description="Satellite L3 daily chl and phytoplankton size classes (micro / nano / pico chl), multi-sensor 1 km, multi-year"),
    "sat_pft_l3_nrt": dict(product="OCEANCOLOUR_BLK_BGC_L3_NRT_009_151", dataset_id="cmems_obs-oc_blk_bgc-plankton_nrt_l3-multi-1km_P1D",
                           vars={"CHL": "chl", "MICRO": "micro", "NANO": "nano", "PICO": "pico"}, origin="satellite", res_deg=0.0125,
                           depth=False, freq="P1D", method="box", box_deg=0.05, clim="sat_pft_l3_my", doi="10.48670/moi-00301",
                           description="Satellite L3 daily chl and phytoplankton size classes (micro / nano / pico chl), multi-sensor 1 km, NRT"),
    # Satellite net primary production (depth-integrated, g C m-2 d-1)
    "sat_pp_my": dict(product="OCEANCOLOUR_BLK_BGC_L4_MY_009_154", dataset_id="cmems_obs-oc_blk_bgc-pp_my_l4-multi-4km_P1D",
                      vars={"PP": "pp"}, origin="satellite", res_deg=0.04, depth=False, freq="P1D", clim_years=(1998, 2022),
                      doi="10.48670/moi-00304", description="Satellite primary production L4 daily, 4 km, multi-year (g C m-2 d-1)"),
    "sat_pp_nrt": dict(product="OCEANCOLOUR_BLK_BGC_L4_NRT_009_152", dataset_id="cmems_obs-oc_blk_bgc-pp_nrt_l4-multi-4km_P1D",
                       vars={"PP": "pp"}, origin="satellite", res_deg=0.04, depth=False, freq="P1D", clim="sat_pp_my",
                       doi="10.48670/moi-00302", description="Satellite primary production L4 daily, 4 km, NRT (g C m-2 d-1)"),
    "sat_kd490_my": dict(product="OCEANCOLOUR_BLK_BGC_L3_MY_009_153 / L4_MY_009_154",
                         dataset_id=["cmems_obs-oc_blk_bgc-transp_my_l3-multi-1km_P1D", "cmems_obs-oc_blk_bgc-transp_my_l4-gapfree-multi-1km_P1D-m",
                                     "cmems_obs-oc_blk_bgc-transp_my_l3-olci-300m_P1D"],
                         vars={"KD490": "kd490"}, origin="satellite", res_deg=0.0125, depth=False, freq="P1D", method="box", box_deg=0.03,
                         clim_years=(1998, 2022), doi="10.48670/moi-00303", description="Satellite Kd490 (transparency) daily, multi-year (L3 1 km until 2026-11-24, then L4 gap-free)"),
    "sat_kd490_nrt": dict(product="OCEANCOLOUR_BLK_BGC_L3_NRT_009_151 / L4_NRT_009_152",
                          dataset_id=["cmems_obs-oc_blk_bgc-transp_nrt_l4-gapfree-multi-1km_P1D-m", "cmems_obs-oc_blk_bgc-transp_nrt_l3-multi-1km_P1D"],
                          vars={"KD490": "kd490"}, origin="satellite", res_deg=0.0125, depth=False, freq="P1D", method="box", box_deg=0.03,
                          clim="sat_kd490_my", doi="10.48670/moi-00301", description="Satellite Kd490 daily NRT (L4 gap-free from 2026-11-24, else L3)"),
    "sat_hr_l3": dict(product="OCEANCOLOUR_BLK_BGC_HR_L3_NRT_009_206", dataset_id="cmems_obs_oc_blk_bgc_tur-spm-chl_nrt_l3-hr-mosaic_P1D-m",
                      vars={"CHL": "chl", "SPM": "spm", "TUR": "turb"}, origin="satellite", res_deg=0.001, depth=False, freq="P1D",
                      method="box", box_deg=0.01, doi="10.48670/moi-00086",
                      description="Sentinel-2/3 high-res (~100 m) coastal L3 daily: turbidity (FNU), SPM, chl, 2020-present"),
    "sat_hr_l4_month": dict(product="OCEANCOLOUR_BLK_BGC_HR_L4_NRT_009_212", dataset_id="cmems_obs-oc_blk_bgc-tur-spm-chl_nrt_l4-hr-mosaic_P1M-m",
                            vars={"CHL": "chl", "SPM": "spm", "TUR": "turb"}, origin="satellite", res_deg=0.001, depth=False, freq="P1M",
                            method="box", box_deg=0.01, doi="10.48670/moi-00087",
                            description="High-res (~100 m) coastal monthly turbidity / SPM / chl"),
    "sat_chl_clim_ref": dict(product="OCEANCOLOUR_BLK_BGC_L4_MY_009_154", dataset_id="cmems_obs-oc_blk_bgc-plankton_my_l4-multi-climatology-1km_P1D",
                             vars={"CHL_median": "chl_clim_median", "CHL_standard_deviation": "chl_clim_std"}, origin="satellite",
                             res_deg=0.0125, depth=False, freq="P1D", doi="10.48670/moi-00304",
                             description="Ready-made daily chl climatology (median, std) on a dummy year 2000"),
    # ---- Satellite SST (CNR)
    "sst_l4_nrt": dict(product="SST_BS_SST_L4_NRT_OBSERVATIONS_010_006", dataset_id="SST_BS_SST_L4_NRT_OBSERVATIONS_010_006_a_V2",
                       vars={"analysed_sst": "sst"}, origin="satellite", res_deg=0.0625, depth=False, freq="P1D", clim="sst_l4_rep",
                       doi="10.48670/moi-00159", description="Satellite SST L4 optimal interpolation, daily, 1/16 deg, NRT 2008-present"),
    "sst_l4_nrt_hr": dict(product="SST_BS_SST_L4_NRT_OBSERVATIONS_010_006", dataset_id="SST_BS_SST_L4_NRT_OBSERVATIONS_010_006_c_V2",
                          vars={"analysed_sst": "sst"}, origin="satellite", res_deg=0.01, depth=False, freq="P1D", clim="sst_l4_rep",
                          doi="10.48670/moi-00159", description="Satellite SST L4 ultra-high-res 0.01 deg, daily, NRT"),
    "sst_anom_nrt": dict(product="SST_BS_SST_L4_NRT_OBSERVATIONS_010_006", dataset_id="SST_BS_SSTA_L4_NRT_OBSERVATIONS_010_006_b",
                         vars={"sst_anomaly": "sst_anomaly"}, origin="satellite", res_deg=0.0625, depth=False, freq="P1D",
                         doi="10.48670/moi-00159", description="Satellite SST anomaly vs 1991-2020 climatology (ready-made), daily 1/16 deg"),
    "sst_l4_rep": dict(product="SST_BS_SST_L4_REP_OBSERVATIONS_010_022", dataset_id="cmems_SST_BS_SST_L4_REP_OBSERVATIONS_010_022",
                       vars={"analysed_sst": "sst"}, origin="satellite", res_deg=0.05, depth=False, freq="P1D", clim_years=(1991, 2020),
                       doi="10.48670/moi-00160", description="Satellite SST L4 reprocessed (CDR) daily 0.05 deg, 1982-present (~1 month latency)"),
    # ---- In situ TAC (moorings, coastal stations, tide gauges, wave buoys, profiles)
    "insitu_bs": dict(product="INSITU_BLK_PHYBGCWAV_DISCRETE_MYNRT_013_034", dataset_id="cmems_obs-ins_blk_phybgcwav_mynrt_na_irr",
                      vars={"TEMP": "temp", "PSAL": "sal", "DOXY": "o2", "OSAT": "o2_sat", "CPHL": "chl", "FLU2": "chl",
                            "TUR4": "turb", "NTRA": "no3", "PHOS": "po4", "PHPH": "ph", "SLEV": "sea_level",
                            "VHM0": "wave_height", "WSPD": "wind_speed", "EWCT": "current_u", "NSCT": "current_v", "HCSP": "current_speed"},
                      origin="in-situ", res_deg=None, depth=True, freq="irregular", doi="10.48670/moi-00033",
                      description="Copernicus In Situ TAC Black Sea: moorings/buoys/coastal stations/tide gauges/profiles, NRT + history"),
}

# Units of canonical names that are not in CANONICAL
_EXTRA_UNITS = {"bottom_temp": "°C", "phyc": "mmol/m³", "zooc": "mmol/m³", "o2_bottom": "mmol/m³", "npp": "mg C/m³/day",
                "odu": "mmol/m³", "dic": "mol/m³", "alk": "mol/m³", "kd": "1/m", "light": "W/m²", "wave_period": "s",
                "wave_dir": "deg", "sst_anomaly": "°C", "chl_clim_median": "mg/m³", "chl_clim_std": "mg/m³",
                "o2_sat": "%", "sea_level": "m", "current_speed": "m/s",
                "micro": "mg/m³", "nano": "mg/m³", "pico": "mg/m³", "pp": "g C/m²/day"}

# Interesting Romanian in-situ platforms (verified in index_platform / index_history on 2026-11-23)
INSITU_RO = {
    "EUXRoOB01": "EuroSea/RO offshore buoy 1 (44.71N 30.76E): T, S, chl fluo, O2, turbidity, met",
    "EUXRoOB02": "RO offshore buoy 2 (44.33N 30.41E): T, S, chl fluo, O2, turbidity, met",
    "EUXRoOB03": "RO offshore buoy 3 (43.98N 29.92E): T, S, chl fluo, O2, turbidity, met",
    "EUXRo01": "older offshore buoy 1 (2013-2022): T, S, chl fluo, O2, turbidity",
    "EUXRo02": "older offshore buoy 2 (2013-2023)",
    "EUXRo03": "older offshore buoy 3 (2013-2023)",
    "15480": "NIMH coastal station Constanta (44.2N 28.6E): SST, 6-hourly, live",
    "15360": "NIMH coastal station Sulina (45.2N 29.7E): SST, live",
    "15428": "NIMH coastal station Gura Portitei area (44.7N 29.0E): SST",
    "15499": "NIMH coastal station Mangalia (43.8N 28.6E): SST",
    "SPOT1622": "Grigore Antipa wave buoy off Constanta/Mamaia: T, waves",
    "SPOT1624": "Grigore Antipa wave buoy (44.23N 28.66E): T, waves, live",
    "SPOT1383": "Grigore Antipa wave buoy (43.9-44.06N): T, waves",
    "WAVEB04": "NIMH wave buoy S of Mangalia (43.54N 28.61E): T, waves, live",
    "EUXRoCB01": "GeoEcoMar coastal buoy Sulina (45.11N 29.78E): currents, met (+AWAC waves)",
    "EUXRoCB02": "GeoEcoMar coastal buoy Constanta (44.23N 28.68E): currents, met",
    "EUXRoCB03": "GeoEcoMar coastal buoy Mangalia (43.81N 28.61E): currents, met",
    "CG": "GeoEcoMar mooring Mangalia (2016-2023): T, chl fluo, O2, turbidity, currents",
    "IOC-csta2": "Tide gauge Constanta (sea level)",
    "IOC-mang": "Tide gauge Mangalia (sea level)",
}


class CopernicusLoginRequired(RuntimeError):
    """Raised instead of letting the toolbox prompt for a username on stdin."""


# --------------------------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------------------------
def _credentials_file() -> Path:
    d = os.environ.get("COPERNICUSMARINE_CREDENTIALS_DIRECTORY") or (Path.home() / ".copernicusmarine")
    return Path(d) / ".copernicusmarine-credentials"


def is_logged_in(check_online: bool = False) -> bool:
    """True if credentials are available (env vars or ~/.copernicusmarine credentials file).

    check_online=True also validates them against the auth server (~0.3 s, needs network).
    Never prints or returns the secrets.
    """
    env_ok = bool(os.environ.get("COPERNICUSMARINE_SERVICE_USERNAME")) and bool(os.environ.get("COPERNICUSMARINE_SERVICE_PASSWORD"))
    netrc = Path.home() / (".netrc" if os.name != "nt" else "_netrc")
    file_ok = _credentials_file().is_file() or (netrc.is_file() and "marine.copernicus.eu" in netrc.read_text(errors="ignore"))
    if not (env_ok or file_ok):
        return False
    if not check_online:
        return True
    try:
        import copernicusmarine as cm
        return bool(cm.login(check_credentials_valid=True))
    except Exception as e:  # network problems etc.
        log.warning("credential check failed: %s", e)
        return False


def login_help() -> str:
    return (
        "Copernicus Marine data downloads need a free account (catalogue metadata and WMTS map tiles do not).\n"
        "1. Register (free): https://data.marine.copernicus.eu/register\n"
        "2. Store the credentials once, in a terminal:\n"
        "     .venv/bin/copernicusmarine login\n"
        "   (asks for username + password, writes ~/.copernicusmarine/.copernicusmarine-credentials)\n"
        "   or non-interactively for a server / CI:\n"
        "     export COPERNICUSMARINE_SERVICE_USERNAME=<user>\n"
        "     export COPERNICUSMARINE_SERVICE_PASSWORD=<password>\n"
        "   (COPERNICUSMARINE_CREDENTIALS_DIRECTORY can point to another folder holding the credentials file)\n"
        "3. Check:  .venv/bin/copernicusmarine login --check-credentials-valid\n"
        "Cached data under data/cache/copernicus keeps working offline without login."
    )


def _require_login() -> None:
    if not is_logged_in():
        raise CopernicusLoginRequired(login_help())


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _entry(key: str) -> dict:
    try:
        return CATALOG[key]
    except KeyError:
        raise KeyError(f"unknown Copernicus catalogue key {key!r}; choose from {sorted(CATALOG)}") from None


def _ids(e: dict) -> list[str]:
    d = e["dataset_id"]
    return list(d) if isinstance(d, (list, tuple)) else [d]


def _units(canon: str) -> str:
    return CANONICAL.get(canon, (None, _EXTRA_UNITS.get(canon, "")))[1]


def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t


def _fresh(path: Path, end: pd.Timestamp | None, max_age_h: float | None) -> bool:
    """Cache validity: data ending >10 days ago never changes; recent/forecast data is refreshed."""
    if not path.exists():
        return False
    if max_age_h is None:
        if end is not None and end < _now() - pd.Timedelta(days=10):
            return True
        max_age_h = 12
    return (_time.time() - path.stat().st_mtime) < max_age_h * 3600


def _open(dataset_ids: list[str], **kw) -> tuple[xr.Dataset, str]:
    """copernicusmarine.open_dataset over candidate dataset ids; returns (ds, id used)."""
    import copernicusmarine as cm

    _require_login()
    errors = []
    for did in dataset_ids:
        try:
            ds = cm.open_dataset(dataset_id=did, **kw)
        except Exception as e:  # DatasetNotFound, VariableDoesNotExist, CoordinatesOutOfDatasetBounds, ...
            name = type(e).__name__
            if name in ("InvalidUsernameOrPassword", "CredentialsCannotBeNone"):
                raise CopernicusLoginRequired(f"{name}: {e}\n\n{login_help()}") from e
            errors.append(f"{did}: {name}: {str(e)[:300]}")
            continue
        if ds is None:  # toolbox swallowed an aborted username prompt
            raise CopernicusLoginRequired(login_help())
        return ds, did
    raise RuntimeError("Copernicus Marine request failed for all candidates:\n  " + "\n  ".join(errors))


def _std_coords(obj):
    ren = {k: v for k, v in {"latitude": "lat", "longitude": "lon"}.items() if k in obj.dims or k in obj.coords}
    return obj.rename(ren)


def _convert(da: xr.DataArray) -> xr.DataArray:
    u = str(da.attrs.get("units", ""))
    if u in _KELVIN:
        da = da - 273.15
        da.attrs["units"] = "°C"
    return da


def _depth_window(depth: float | None) -> tuple[float, float]:
    """Depth range to request; the exact level is chosen locally (the toolbox rejects [0, 0])."""
    if depth is None or depth <= 1:
        return 0.0, 3.0
    return max(0.0, depth * 0.8 - 2), depth * 1.2 + 2


def _bbox_kw(lat: float, lon: float, h: float) -> dict:
    return dict(minimum_latitude=lat - h, maximum_latitude=lat + h, minimum_longitude=lon - h, maximum_longitude=lon + h)


def _haversine_km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


# --------------------------------------------------------------------------------------------
# Gridded products: time series at a point
# --------------------------------------------------------------------------------------------
def fetch_timeseries(key: str, lat: float, lon: float, start, end, variables: Iterable[str] | None = None,
                     depth: float | None = None, method: str | None = None, box_deg: float | None = None,
                     max_age_h: float | None = None, **insitu_kw) -> pd.DataFrame:
    """Time series near (lat, lon) from a CATALOG entry, surface by default.

    variables: canonical or native names (default: all of the entry's variables).
    method: "nearest" = nearest grid cell with valid data (models, L4); "box" = mean over cells in
            a small box (default for gappy L3 satellite); box_deg = half-width of that box.
    Returns DataFrame (DatetimeIndex "time", canonical columns); df.attrs = meta(...) incl. the grid
    point actually used (grid_lat, grid_lon, distance_km) and depth_m.
    For key "insitu_bs" this delegates to fetch_insitu (pass platform="..." or it picks the nearest).
    """
    e = _entry(key)
    if e["origin"] == "in-situ":
        if insitu_kw.get("platform"):
            return fetch_insitu(insitu_kw["platform"], start, end, variables=variables, depth=depth, max_age_h=max_age_h)
        errs = []
        for platform in nearest_platforms(lat, lon, variables=variables, start=start, end=end, n=4):
            try:
                return fetch_insitu(platform, start, end, variables=variables, depth=depth, max_age_h=max_age_h)
            except ValueError as ex:
                errs.append(str(ex))
        raise ValueError("no nearby in-situ platform has data: " + "; ".join(errs))

    start, end = _ts(start), _ts(end)
    native = _select_vars(e, variables)
    method = method or e.get("method", "nearest")
    h = box_deg or e.get("box_deg") or max(2.5 * e["res_deg"], 0.03)
    ck = cache_key("ts", key, _ids(e), round(lat, 4), round(lon, 4), str(start), str(end), native, depth, method, h)
    path = cached_path(SOURCE, ck, "parquet")
    if _fresh(path, end, max_age_h):
        df = pd.read_parquet(path)
        df.attrs = _read_attrs(path)
        return df

    kw = dict(variables=native, start_datetime=start.isoformat(), end_datetime=end.isoformat())
    if e["depth"]:
        dmin, dmax = _depth_window(depth)
        kw.update(minimum_depth=dmin, maximum_depth=dmax)
    for attempt in range(2):  # retry once with a 3x bigger box if no valid sea cell was found
        ds, did = _open(_ids(e), **kw, **_bbox_kw(lat, lon, h))
        ds = _std_coords(ds)
        depth_used = None
        if "depth" in ds.dims:
            target = 0.0 if depth is None else depth
            ds = ds.sel(depth=target, method="nearest")
            depth_used = float(ds["depth"])
        ds = ds.load()
        valid = sum(ds[v].notnull() for v in native if v in ds)
        ok = valid.any("time") if "time" in valid.dims else valid
        if bool(ok.any()):
            break
        h *= 3
    else:
        raise ValueError(f"{key}: no valid data within {h:.2f} deg of ({lat}, {lon}) for {start.date()}..{end.date()}")

    if method == "box":
        cols = {e["vars"][v]: _convert(ds[v]).mean(("lat", "lon"), skipna=True) for v in native if v in ds}
        glat, glon, dist, ncell = float(ds.lat.mean()), float(ds.lon.mean()), 0.0, int(ds.lat.size * ds.lon.size)
    else:
        la, lo = xr.broadcast(ds.lat, ds.lon)
        d = xr.DataArray(_haversine_km(lat, lon, la.values, lo.values), dims=la.dims, coords=la.coords)
        d = d.where(ok)
        idx = np.unravel_index(int(np.nanargmin(d.values)), d.shape)
        sel = {d.dims[0]: idx[0], d.dims[1]: idx[1]}
        cell = ds.isel(sel)
        glat, glon, dist, ncell = float(cell.lat), float(cell.lon), float(d.values[idx]), 1
        cols = {e["vars"][v]: _convert(cell[v]) for v in native if v in cell}

    df = pd.DataFrame({k: v.to_series() for k, v in cols.items()})
    df.index = pd.to_datetime(df.index)
    df.index.name = "time"
    df = df.groupby(level=0).mean() if df.index.has_duplicates else df
    df.attrs = meta(SOURCE, did, e["origin"], {c: _units(c) for c in df.columns}, product=e["product"], key=key,
                    lat=lat, lon=lon, grid_lat=round(glat, 5), grid_lon=round(glon, 5), distance_km=round(dist, 2),
                    method=method, n_cells=ncell, box_deg=h, depth_m=depth_used, citation=CITATION.format(doi=e["doi"]),
                    retrieved=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _write(df, path)
    return df


def _select_vars(e: dict, variables) -> list[str]:
    if not variables:
        # default: the first (main) variable(s) - all except obvious extras
        return list(e["vars"])
    if isinstance(variables, str):
        variables = [variables]
    inv = {}
    for nat, can in e["vars"].items():
        inv.setdefault(can, nat)
    out = []
    for v in variables:
        if v in e["vars"]:
            out.append(v)
        elif v in inv:
            out.append(inv[v])
        else:
            raise KeyError(f"variable {v!r} not in {list(e['vars'].items())}")
    return list(dict.fromkeys(out))


def _write(df: pd.DataFrame, path: Path) -> None:
    import json
    df.to_parquet(path)
    path.with_suffix(".json").write_text(json.dumps(df.attrs, default=str, indent=1))


def _read_attrs(path: Path) -> dict:
    import json
    p = path.with_suffix(".json")
    return json.loads(p.read_text()) if p.exists() else {}


# --------------------------------------------------------------------------------------------
# Gridded products: map field
# --------------------------------------------------------------------------------------------
def fetch_field(key: str, bbox=BBOX_RO, time=None, variable: str | None = None, depth: float | None = None,
                max_age_h: float | None = None) -> xr.DataArray:
    """2-D map (dims time[1], lat, lon) of one variable for the time step nearest to `time` (default: latest
    available up to now). bbox = (lon_min, lat_min, lon_max, lat_max). Cached as NetCDF."""
    e = _entry(key)
    if e["origin"] == "in-situ":
        raise ValueError("in-situ data has no gridded field; use insitu_platforms() / fetch_insitu()")
    native = _select_vars(e, variable)[0] if variable else next(iter(e["vars"]))
    canon = e["vars"][native]
    t = _ts(time) if time is not None else _now().normalize()
    lon0, lat0, lon1, lat1 = bbox
    ck = cache_key("field", key, _ids(e), native, [round(x, 4) for x in bbox], str(t), depth)
    path = cached_path(SOURCE, ck, "nc")
    if _fresh(path, t, max_age_h):
        with xr.open_dataarray(path) as da:
            return da.load()

    kw = dict(variables=[native], minimum_longitude=lon0, maximum_longitude=lon1, minimum_latitude=lat0,
              maximum_latitude=lat1, start_datetime=(t - pd.Timedelta(days=_window_days(e))).isoformat(),
              end_datetime=t.isoformat())
    if e["depth"]:
        kw.update(zip(("minimum_depth", "maximum_depth"), _depth_window(depth)))
    ds, did = _open(_ids(e), **kw)
    ds = _std_coords(ds)
    da = ds[native]
    if "depth" in da.dims:
        da = da.sel(depth=0.0 if depth is None else depth, method="nearest")
    da = da.load()
    # nearest time step that has valid pixels (L3 satellite days can be fully clouded)
    order = np.argsort(np.abs(da.time.values - np.datetime64(t)))
    has = da.notnull().any([d for d in da.dims if d != "time"]).values
    pick = next((i for i in order if has[i]), order[0])
    da = da.isel(time=[int(pick)])
    da = _convert(da).rename(canon)
    da.attrs = {**{k: v for k, v in da.attrs.items() if isinstance(v, (str, int, float))},
                **{k: (str(v) if v is not None else "") for k, v in meta(
                    SOURCE, did, e["origin"], None, product=e["product"], key=key, variable=canon, units_canon=_units(canon),
                    depth_m=float(da["depth"]) if "depth" in da.coords else "", citation=CITATION.format(doi=e["doi"])).items()
                   if k != "units"}}
    da.to_netcdf(path)
    return da


def _window_days(e: dict) -> int:
    if e.get("method") == "box" and e["freq"] == "P1D":  # gappy L3: look further back for a cloud-free day
        return 16
    return {"P1M": 62, "PT1H": 1}.get(e["freq"], 6)


# --------------------------------------------------------------------------------------------
# Climatology / reference conditions
# --------------------------------------------------------------------------------------------
def climatology(key: str, lat: float, lon: float, variable: str | None = None, years: tuple[int, int] | None = None,
                freq: str = "doy", window: int = 11, smooth: int = 31, depth: float | None = None) -> pd.DataFrame:
    """Reference climatology at a point from the multi-year dataset behind `key`.

    key may be an NRT/forecast key (its 'clim' entry is used, e.g. phy_temp -> rea_phy_temp,
    sat_chl_l4_nrt -> sat_chl_l4_my, sst_l4_nrt -> sst_l4_rep) or a multi-year key.
    freq="doy": per day-of-year (1..365, Feb 29 folded into Feb 28) stats pooled over a centred
    `window`-day window, then smoothed with a circular `smooth`-day running mean (Hobday et al. 2016
    marine-heatwave style). freq="month": per calendar month.
    Columns: mean, std, p10, p50, p90, n. One point download of the whole period (~4-5 s), cached.
    """
    e0 = _entry(key)
    ckey = e0.get("clim", key)
    e = _entry(ckey)
    years = years or e.get("clim_years") or (1993, 2022)
    native = _select_vars(e, variable)[0] if variable else next(iter(e["vars"]))
    canon = e["vars"][native]
    ck = cache_key("clim", ckey, _ids(e), round(lat, 4), round(lon, 4), native, years, freq, window, smooth, depth)
    path = cached_path(SOURCE, ck, "parquet")
    if path.exists():
        out = pd.read_parquet(path)
        out.attrs = _read_attrs(path)
        return out

    ts = fetch_timeseries(ckey, lat, lon, f"{years[0]}-01-01", f"{years[1]}-12-31T23:59:59", variables=[native], depth=depth)
    s = ts[canon].dropna()
    if e["freq"] == "PT1H":
        s = s.resample("1D").mean().dropna()
    if freq == "month":
        g = s.groupby(s.index.month)
        out = pd.DataFrame({"mean": g.mean(), "std": g.std(), "p10": g.quantile(0.1), "p50": g.median(),
                            "p90": g.quantile(0.9), "n": g.size()})
        out.index.name = "month"
    else:
        doy = _doy365(s.index)
        vals, dd = s.values, doy
        rows = []
        half = window // 2
        for d in range(1, 366):
            dist = np.abs(dd - d)
            dist = np.minimum(dist, 365 - dist)
            v = vals[dist <= half]
            stats = [np.nanmean(v), np.nanstd(v, ddof=1), *np.nanpercentile(v, [10, 50, 90])] if len(v) > 1 else [np.nan] * 5
            rows.append((d, *stats, len(v)))
        out = pd.DataFrame(rows, columns=["doy", "mean", "std", "p10", "p50", "p90", "n"]).set_index("doy")
        if smooth and smooth > 1:
            k = smooth // 2
            for c in ["mean", "std", "p10", "p50", "p90"]:
                x = out[c].to_numpy()
                ext = np.concatenate([x[-k:], x, x[:k]])
                out[c] = pd.Series(ext).rolling(smooth, center=True, min_periods=1).mean().to_numpy()[k:-k]
    out.attrs = {**ts.attrs, "variable": canon, "units": {canon: _units(canon)}, "years": list(years), "freq": freq,
                 "window_days": window if freq == "doy" else None, "smooth_days": smooth if freq == "doy" else None,
                 "n_years": int(s.index.year.nunique())}
    _write(out, path)
    return out


def _doy365(idx: pd.DatetimeIndex) -> np.ndarray:
    doy = idx.day_of_year.to_numpy().copy()
    leap = idx.is_leap_year
    doy[leap & (doy > 59)] -= 1  # Feb 29 -> 59 (= Feb 28), Mar 1 -> 60, ...
    return doy


def anomalies(df: pd.DataFrame, clim: pd.DataFrame, variable: str | None = None) -> pd.DataFrame:
    """Join a daily series with its climatology: adds clim_mean, clim_p10, clim_p90, anomaly, zscore, and
    flag (+1 above p90, -1 below p10, 0 otherwise)."""
    variable = variable or clim.attrs.get("variable") or df.columns[0]
    s = df[variable]
    if clim.index.name == "month":
        c = clim.reindex(s.index.month)
    else:
        c = clim.reindex(_doy365(s.index))
    c.index = s.index
    out = pd.DataFrame({variable: s, "clim_mean": c["mean"], "clim_p10": c["p10"], "clim_p90": c["p90"]})
    out["anomaly"] = s - c["mean"]
    out["zscore"] = out["anomaly"] / c["std"]
    out["flag"] = np.select([s > c["p90"], s < c["p10"]], [1, -1], 0)
    out.loc[s.isna(), "flag"] = 0
    out.attrs = {**df.attrs, "climatology": {k: clim.attrs.get(k) for k in ("dataset", "years", "freq", "window_days", "smooth_days")}}
    return out


# --------------------------------------------------------------------------------------------
# In situ TAC
# --------------------------------------------------------------------------------------------
INSITU_DATASET = CATALOG["insitu_bs"]["dataset_id"]


def _read_index(path: Path) -> pd.DataFrame:
    import io
    lines = path.read_text(errors="ignore").splitlines()
    hdr = [l for l in lines if l.startswith("# ") and "," in l][-1][2:].split(",")
    body = "\n".join(l for l in lines if l and not l.startswith("#"))
    return pd.read_csv(io.StringIO(body), header=None, names=hdr, quotechar='"', on_bad_lines="skip")


def insitu_platforms(bbox=(28.0, 43.4, 31.0, 45.6), max_age_h: float = 24) -> pd.DataFrame:
    """Platforms of the Black Sea In Situ TAC product inside bbox (lon_min, lat_min, lon_max, lat_max).

    Built from the product's index files (index_platform.txt + index_history.txt, fetched with
    copernicusmarine.get(index_parts=True), needs login, ~1.5 MB, cached 24 h).
    Columns: platform_id, type (MO mooring/coastal station, TG tide gauge, PR profile, ...), lat, lon,
    institution, parameters, first_obs, last_obs, live (obs in last 7 days).
    """
    import copernicusmarine as cm

    d = cached_path(SOURCE, "insitu_index", "d")
    d.mkdir(exist_ok=True)
    files = {n: next(d.rglob(f"index_{n}.txt"), None) for n in ("platform", "history")}
    if any(f is None or (_time.time() - f.stat().st_mtime) > max_age_h * 3600 for f in files.values()):
        _require_login()
        r = cm.get(dataset_id=INSITU_DATASET, index_parts=True, output_directory=str(d), overwrite=True, disable_progress_bar=True)
        if r is None:
            raise CopernicusLoginRequired(login_help())
        files = {n: next(d.rglob(f"index_{n}.txt")) for n in ("platform", "history")}
    p = _read_index(files["platform"])
    h = _read_index(files["history"])
    h["type"] = h.file_name.str.extract(r"/[A-Z]{2}_([A-Z]{2})_[A-Z]{2}_")[0]
    h["platform_id"] = h.file_name.str.extract(r"/[A-Z]{2}_[A-Z]{2}_[A-Z]{2}_(.+?)(?:_\d{4,8})?\.nc")[0]
    hist = h.groupby("platform_id").agg(first_obs=("time_coverage_start", "min"), hist_end=("time_coverage_end", "max"),
                                        hist_type=("type", "first")).reset_index()
    p = p.rename(columns={"platform_code": "platform_id", "last_latitude_observation": "lat",
                          "last_longitude_observation": "lon", "last_date_observation": "last_obs"})
    p["platform_id"] = p["platform_id"].astype(str)
    p["type"] = p["data_source"].str.extract(r"^[A-Z]{2}_([A-Z]{2})_")[0]
    p["family"] = p["data_source"].str.extract(r"^[A-Z]{2}_[A-Z]{2}_([A-Z]{2})_")[0]
    p = p.merge(hist, on="platform_id", how="left")
    lon0, lat0, lon1, lat1 = bbox
    p = p[p.lat.between(lat0, lat1) & p.lon.between(lon0, lon1)].copy()
    for c in ("last_obs", "first_obs"):
        p[c] = pd.to_datetime(p[c], utc=True, errors="coerce").dt.tz_localize(None)
    p["live"] = p["last_obs"] > _now() - pd.Timedelta(days=7)
    p["parameters"] = p["parameters"].astype(str).str.strip()
    cols = ["platform_id", "type", "family", "lat", "lon", "institution", "parameters", "first_obs", "last_obs", "live"]
    p = p.sort_values(["live", "last_obs"], ascending=False).drop_duplicates("platform_id")[cols].reset_index(drop=True)
    p.attrs = meta(SOURCE, INSITU_DATASET, "in-situ", None, product=CATALOG["insitu_bs"]["product"], bbox=bbox)
    return p


def nearest_platform(lat: float, lon: float, variables=None, live_only: bool = False) -> str:
    """Nearest In Situ TAC platform (optionally carrying the requested canonical/native variables)."""
    return nearest_platforms(lat, lon, variables=variables, live_only=live_only, n=1)[0]


def nearest_platforms(lat: float, lon: float, variables=None, start=None, end=None, live_only: bool = False,
                      n: int = 5) -> list[str]:
    """Platforms sorted by distance, filtered by variables and by overlap with [start, end] (if given)."""
    p = insitu_platforms()
    if start is not None:
        p = p[p.last_obs.isna() | (p.last_obs >= _ts(start))]
    if end is not None:
        p = p[p.first_obs.isna() | (p.first_obs <= _ts(end))]
    if variables:
        e = CATALOG["insitu_bs"]
        nat = set()
        for v in ([variables] if isinstance(variables, str) else variables):
            nat |= {n for n, c in e["vars"].items() if c == v or n == v}
        p = p[p.parameters.apply(lambda s: bool(nat & set(s.split())))]
    if live_only:
        p = p[p.live]
    if p.empty:
        raise ValueError("no matching in-situ platform")
    d = _haversine_km(lat, lon, p.lat.to_numpy(), p.lon.to_numpy())
    return [str(x) for x in p.iloc[np.argsort(d)[:n]].platform_id]


def fetch_insitu(platform_id: str, start, end, variables: Iterable[str] | None = None, depth: float | None = None,
                 good_qc_only: bool = True, max_age_h: float | None = None) -> pd.DataFrame:
    """Time series of one In Situ TAC platform (e.g. "EUXRoOB02", "15480", "IOC-csta2").

    Uses copernicusmarine.read_dataframe(platform_ids=[...]) on the dataset parts 'history'
    (archive, up to the end of last month), 'monthly' and 'latest' (last 30 days), merged and de-duplicated.
    Values nearest to `depth` (default: shallowest) per variable; QC flags 1/2 (good / probably good) kept.
    Returns wide DataFrame (canonical columns). df.attrs incl. platform lat/lon, depth, institution, doi.
    """
    import copernicusmarine as cm

    e = CATALOG["insitu_bs"]
    start, end = _ts(start), _ts(end)
    if variables:
        want = {n for v in ([variables] if isinstance(variables, str) else variables) for n, c in e["vars"].items() if v in (n, c)}
        if not want:
            raise KeyError(f"no in-situ variable matches {variables}; known: {e['vars']}")
    else:
        want = set(e["vars"])
    ck = cache_key("insitu", platform_id, str(start), str(end), sorted(want), depth, good_qc_only)
    path = cached_path(SOURCE, ck, "parquet")
    if _fresh(path, end, max_age_h):
        df = pd.read_parquet(path)
        df.attrs = _read_attrs(path)
        return df

    _require_login()
    now = _now()
    parts = ["history"]
    if end >= now - pd.Timedelta(days=62):
        parts.append("monthly")
    if end >= now - pd.Timedelta(days=31):
        parts.append("latest")
    frames = []
    for part in parts:
        try:
            df = cm.read_dataframe(dataset_id=INSITU_DATASET, dataset_part=part, platform_ids=[str(platform_id)],
                                   variables=sorted(want), start_datetime=start.isoformat(), end_datetime=end.isoformat(),
                                   disable_progress_bar=True)
        except Exception as ex:
            name = type(ex).__name__
            if name in ("InvalidUsernameOrPassword", "CredentialsCannotBeNone"):
                raise CopernicusLoginRequired(login_help()) from ex
            log.info("insitu %s part %s: %s %s", platform_id, part, name, str(ex)[:200])
            continue
        if df is None:
            raise CopernicusLoginRequired(login_help())
        if len(df):
            frames.append(df)
    if not frames:
        raise ValueError(f"no in-situ data for platform {platform_id} {start.date()}..{end.date()} (vars {sorted(want)})")
    raw = pd.concat(frames, ignore_index=True)
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    raw = raw.drop_duplicates(["variable", "time", "depth"])
    if good_qc_only and "value_qc" in raw:
        raw = raw[raw["value_qc"].isin([1, 2])]
    raw = raw.dropna(subset=["value"])
    # one depth level per variable: nearest to the requested depth (default: shallowest)
    raw["depth"] = raw["depth"].fillna(raw.get("pressure"))
    target = 0.0 if depth is None else depth
    dsel = raw.groupby("variable")["depth"].apply(lambda d: d.iloc[int(np.argmin(np.abs(d.fillna(0).to_numpy() - target)))]
                                                  if d.notna().any() else np.nan)
    keep = raw.apply(lambda r: (pd.isna(dsel[r["variable"]]) or r["depth"] == dsel[r["variable"]]), axis=1)
    raw = raw[keep]
    raw["canon"] = raw["variable"].map(e["vars"]).fillna(raw["variable"].str.lower())
    wide = raw.pivot_table(index="time", columns="canon", values="value", aggfunc="mean").sort_index()
    wide.columns.name = None
    wide.index.name = "time"
    first = raw.iloc[0]
    wide.attrs = meta(SOURCE, INSITU_DATASET, "in-situ", {c: _units(c) for c in wide.columns}, product=e["product"],
                      key="insitu_bs", platform_id=str(platform_id), platform_type=str(first.get("platform_type")),
                      lat=float(raw["latitude"].median()), lon=float(raw["longitude"].median()),
                      depth_m={str(k): (None if pd.isna(v) else float(v)) for k, v in dsel.items()},
                      institution=str(first.get("institution")), doi=str(first.get("doi")),
                      native_vars=sorted(raw["variable"].unique()), parts=parts, good_qc_only=good_qc_only,
                      citation=CITATION.format(doi=e["doi"]), retrieved=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    _write(wide, path)
    return wide


# --------------------------------------------------------------------------------------------
# WMTS (no login needed)
# --------------------------------------------------------------------------------------------
WMTS_BASE = "https://wmts.marine.copernicus.eu/teroWmts"
_NS = {"w": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}


def wmts_layers(key: str | None = None, product_id: str | None = None, max_age_h: float = 12) -> list[dict]:
    """WMTS layers for a catalogue key (or a whole product). No login required.

    Each dict: layer (full id incl. dataset version), dataset, variable, title, styles, time_default,
    time_values, elevation_default, legend_url.
    """
    if key:
        e = _entry(key)
        product_id = e["product"].split(" ")[0]
        if not product_id.startswith(("BLKSEA", "OCEANCOLOUR", "SST", "INSITU")):
            raise ValueError(key)
    if not product_id:
        raise ValueError("give key or product_id")
    path = cached_path(SOURCE, f"wmts_{product_id}", "xml")
    if not _fresh(path, None, max_age_h):
        r = requests.get(f"{WMTS_BASE}/{product_id}", params={"service": "WMTS", "request": "GetCapabilities"}, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    root = ET.fromstring(path.read_bytes())
    ids = _ids(_entry(key)) if key else None
    out = []
    for L in root.iter(f"{{{_NS['w']}}}Layer"):
        lid = L.findtext("ows:Identifier", namespaces=_NS)
        if not lid:
            continue
        parts = lid.split("/")
        if len(parts) != 3:
            continue
        ds_ver, var = parts[1], parts[2]
        ds = re.sub(r"_\d{6}(--ext--.*)?$", "", ds_ver)
        if ids and ds not in ids:
            continue
        dims = {}
        for D in L.findall("w:Dimension", _NS):
            dims[D.findtext("ows:Identifier", namespaces=_NS)] = (D.findtext("w:Default", namespaces=_NS),
                                                                  [v.text for v in D.findall("w:Value", _NS)])
        styles = [S.findtext("ows:Identifier", namespaces=_NS) for S in L.findall("w:Style", _NS)]
        leg = L.find("w:Style/w:LegendURL", _NS)
        out.append(dict(layer=lid, dataset=ds, variable=var, title=L.findtext("ows:Title", namespaces=_NS),
                        styles=styles, time_default=dims.get("time", (None, []))[0], time_values=dims.get("time", (None, []))[1],
                        elevation_default=dims.get("elevation", (None, []))[0],
                        legend_url=leg.get("{http://www.w3.org/1999/xlink}href") if leg is not None else None))
    return out


def wmts_tile_url(key: str, variable: str | None = None, time=None, style: str | None = None,
                  elevation: float | None = None) -> str:
    """XYZ tile-URL template ({z}/{x}/{y} placeholders, EPSG:3857) for folium.TileLayer / leaflet.

    Example:  folium.TileLayer(tiles=wmts_tile_url("sat_chl_l4_nrt"), attr="Copernicus Marine", overlay=True)
    time: date/ISO string (default: the layer's default time). No login required.
    """
    e = _entry(key)
    native = _select_vars(e, variable)[0] if variable else next(iter(e["vars"]))
    layers = [l for l in wmts_layers(key) if l["variable"] == native]
    if not layers:
        raise ValueError(f"no WMTS layer for {key}/{native}")
    L = layers[0]
    q = {"SERVICE": "WMTS", "REQUEST": "GetTile", "VERSION": "1.0.0", "LAYER": L["layer"],
         "STYLE": style or (L["styles"][0] if L["styles"] else ""), "TILEMATRIXSET": "EPSG:3857", "FORMAT": "image/png"}
    if time is not None:
        q["TIME"] = _ts(time).strftime("%Y-%m-%dT%H:%M:%SZ")
    if elevation is not None:
        q["ELEVATION"] = str(-abs(elevation))
    from urllib.parse import urlencode
    return f"{WMTS_BASE}?{urlencode(q, safe=':/,')}&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}"


def wmts_legend_url(key: str, variable: str | None = None) -> str | None:
    e = _entry(key)
    native = _select_vars(e, variable)[0] if variable else next(iter(e["vars"]))
    for l in wmts_layers(key):
        if l["variable"] == native:
            return l["legend_url"]
    return None


def _tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def check_tile(key: str, variable: str | None = None, z: int = 6, lat: float = 44.17, lon: float = 28.72, time=None) -> dict:
    """Fetch one real tile; returns {'ok', 'status', 'content_type', 'bytes', 'url'}."""
    x, y = _tile_xy(lat, lon, z)
    url = wmts_tile_url(key, variable, time=time).format(z=z, x=x, y=y)
    r = requests.get(url, timeout=60)
    return dict(ok=r.ok and r.content[:8] == b"\x89PNG\r\n\x1a\n", status=r.status_code,
                content_type=r.headers.get("content-type"), bytes=len(r.content), url=url)


def describe_dataset(key: str) -> dict:
    """Live catalogue metadata for a key (no login): versions, time range, variables/units."""
    import copernicusmarine as cm
    out = {}
    for did in _ids(_entry(key)):
        try:
            c = cm.describe(dataset_id=did, disable_progress_bar=True)
        except Exception as ex:
            out[did] = f"ERR {type(ex).__name__}: {ex}"
            continue
        for p in c.products:
            for d in p.datasets:
                for v in d.versions:
                    for part in v.parts:
                        info = {"version": v.label, "part": part.name, "retired": str(part.retired_date), "variables": {}}
                        for s in part.services:
                            for var in s.variables:
                                info["variables"][var.short_name] = var.units
                                for co in var.coordinates:
                                    if co.coordinate_id == "time":
                                        info["time"] = (co.minimum_value, co.maximum_value, co.step)
                        out[did] = info
    return out


# --------------------------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import traceback

    pd.set_option("display.width", 200)
    lat, lon = STATIONS["Constanta"]
    today = _now().normalize()
    results = {}

    def step(name, fn):
        t0 = _time.time()
        try:
            r = fn()
            results[name] = f"OK ({_time.time() - t0:.1f}s) {r}"
        except Exception as ex:
            results[name] = f"FAIL ({_time.time() - t0:.1f}s) {type(ex).__name__}: {str(ex)[:300]}"
            if "-v" in sys.argv:
                traceback.print_exc()
        print(f"[{name}] {results[name]}", flush=True)

    print("logged in (local):", is_logged_in(), "| online check:", is_logged_in(check_online=True))
    step("describe(no login) phy_temp", lambda: {k: (v["version"], v.get("time")) if isinstance(v, dict) else v
                                                 for k, v in describe_dataset("phy_temp").items()})
    step("wmts tile sat_chl_l4_nrt", lambda: check_tile("sat_chl_l4_nrt"))
    step("wmts tile phy_temp", lambda: check_tile("phy_temp"))

    if not is_logged_in():
        print("\nNot logged in -> data steps skipped.\n" + login_help())
        sys.exit(0)

    short = (today - pd.Timedelta(days=20), today + pd.Timedelta(days=3))
    keys = [k for k in CATALOG if k != "insitu_bs"] if "--all" in sys.argv else [
        "phy_temp", "phy_sal", "phy_cur", "phy_mld", "bgc_chl", "bgc_o2", "bgc_nut", "bgc_car", "wav",
        "sat_chl_l4_nrt", "sat_chl_l3_nrt", "sat_kd490_nrt", "sst_l4_nrt", "sst_anom_nrt"]
    for k in keys:
        e = CATALOG[k]
        if e["origin"] == "reanalysis" or k in ("sst_l4_rep", "sat_chl_l4_my", "sat_kd490_my", "sat_chl_l3_my"):
            s, t = "2024-06-01", "2024-06-30"
        elif k == "sat_chl_clim_ref":
            s, t = "2000-06-01", "2000-06-30"
        elif k == "sat_hr_l4_month":
            s, t = "2026-01-01", "2026-10-31"
        else:
            s, t = short
        step(f"ts {k}", lambda k=k, s=s, t=t: (lambda df: f"{df.shape} {df.attrs['dataset']} grid=({df.attrs['grid_lat']},{df.attrs['grid_lon']}) "
                                                          f"d={df.attrs['distance_km']}km depth={df.attrs['depth_m']} "
                                                          f"last={df.index.max()} {df.iloc[:, 0].describe()[['mean', 'min', 'max']].round(3).to_dict()}")(
            fetch_timeseries(k, lat, lon, s, t)))
    step("field sst_l4_nrt", lambda: (lambda da: f"{dict(da.sizes)} t={str(da.time.values[0])[:10]} mean={float(da.mean()):.2f}")(
        fetch_field("sst_l4_nrt", BBOX_RO, today - pd.Timedelta(days=2), "sst")))
    step("field bgc_chl", lambda: (lambda da: f"{dict(da.sizes)} t={str(da.time.values[0])[:10]} mean={float(da.mean()):.2f}")(
        fetch_field("bgc_chl", BBOX_RO, today, "chl")))
    step("field sat_chl_l4_nrt", lambda: (lambda da: f"{dict(da.sizes)} t={str(da.time.values[0])[:10]} mean={float(da.mean()):.2f}")(
        fetch_field("sat_chl_l4_nrt", (28.5, 43.7, 29.5, 44.6), today - pd.Timedelta(days=3), "chl")))
    step("clim phy_temp (rea 1993-2022)", lambda: (lambda c: f"{c.shape} doy1={c.loc[1, ['mean', 'p10', 'p90']].round(2).to_dict()} "
                                                             f"doy327={c.loc[327, ['mean', 'p10', 'p90']].round(2).to_dict()}")(
        climatology("phy_temp", lat, lon, "temp")))
    step("clim sst (rep 1991-2020)", lambda: (lambda c: f"{c.shape} doy327={c.loc[327, ['mean', 'p10', 'p90']].round(2).to_dict()}")(
        climatology("sst_l4_nrt", lat, lon, "sst")))
    step("clim sat chl (1998-2022, monthly)", lambda: (lambda c: f"{c.round(2).to_dict('index')}")(
        climatology("sat_chl_l4_nrt", lat, lon, "chl", freq="month")))
    step("clim bgc o2 (rea)", lambda: (lambda c: f"{c.shape} doy327={c.loc[327, ['mean', 'p10', 'p90']].round(1).to_dict()}")(
        climatology("bgc_o2", lat, lon, "o2")))
    step("anomalies sst", lambda: (lambda a: a.tail(3).round(2).to_dict("index"))(
        anomalies(fetch_timeseries("sst_l4_nrt", lat, lon, *short), climatology("sst_l4_nrt", lat, lon, "sst"))))
    step("insitu platforms RO", lambda: (lambda p: f"{len(p)} platforms, live={int(p.live.sum())}: "
                                                   f"{p[p.live].platform_id.tolist()[:15]}")(insitu_platforms()))
    step("insitu 15480 Constanta TEMP (latest)", lambda: (lambda df: f"{df.shape} {df.attrs['depth_m']} last={df.index.max()} "
                                                                     f"{df.iloc[-3:].round(2).to_dict('list')}")(
        fetch_insitu("15480", today - pd.Timedelta(days=10), today + pd.Timedelta(days=1), ["temp"])))
    step("insitu EUXRoOB02 (history)", lambda: (lambda df: f"{df.shape} cols={list(df.columns)} {df.mean().round(2).to_dict()}")(
        fetch_insitu("EUXRoOB02", "2025-06-01", "2025-06-30")))
    step("insitu via fetch_timeseries nearest temp platform", lambda: (lambda df: f"{df.attrs['platform_id']} {df.shape}")(
        fetch_timeseries("insitu_bs", lat, lon, today - pd.Timedelta(days=5), today + pd.Timedelta(days=1), ["temp"])))

    n_fail = sum(v.startswith("FAIL") for v in results.values())
    print(f"\n{len(results) - n_fail}/{len(results)} steps OK")
