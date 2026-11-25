"""Romanian for marinekit text other than the indicator cards.

Covers: marinekit.validation (source_summary), marinekit.seasonal (gate reasons, cycle and trend sentences),
marinekit.methods (uncertainty primer and texts for every profile, measurement needs), marinekit.datahub (trust reasons,
platform notes, source labels, notes in attrs, obs_vs_model note), in-situ trust notes, the pressure-zone files in
data/zones (activities, buffers, feature names and sources, sector sites, overlap areas) and the SHORTLIST.md sections
shown on the Methods page (indicator table, rule chain, data quality register, investigate table).

Order matters (see viewer.i18n_data): specific templates first; the generic list template ("a, b") is the very last.
Threshold labels OFFICIAL-RO / OFFICIAL-EU / OURS, dataset IDs, station codes, product names and file paths stay as they
are. NIMRD is written INCDM and MSFD is written DCSMM, as in the rest of the viewer.
"""
from viewer.i18n_data import EXACT, E, T


def _ee(d: dict):
    """Register whole strings. A string the cards table (i18n_ro_cards, loaded first) already translates keeps that
    wording, so a label reads the same on the cards and on the Methods page."""
    for k, v in d.items():
        if k not in EXACT:
            E(k, v)


def _keep(names):
    for n in names:
        E(n, n)


# =================================================================================================== single words, codes
_ee({
    # confidence words (as in viewer.i18n DATA_RO) and cost levels
    "high": "ridicată", "medium": "medie", "low": "scăzută", "none": "fără",
    "yes": "da", "no": "nu", "True": "da", "False": "nu", "n/a": "n/a",
    # trust flags (datahub, seasonal gate, viewer platform register)
    "good": "bună", "usable": "utilizabilă", "indicative": "orientativă", "untrusted": "nesigură",
    "not_usable_absolute": "neutilizabilă ca valori absolute", "under_qc": "în verificare (QC)",
    "context": "context", "not_assessed": "neevaluată", "unknown": "necunoscută",
    # trend levels
    "climate": "climatică",
    # origins and source ids
    "satellite": "satelit", "model": "model", "in-situ": "in situ", "in situ": "in situ", "insitu": "in situ",
    "reanalysis": "reanaliză", "derived": "derivat", "measured": "măsurat", "buoy": "geamandură",
    "bottles": "probe de apă", "coastal buoy": "geamandură costieră", "station 15480": "stația 15480",
    "open-meteo": "open-meteo", "era5": "ERA5", "glofas": "GloFAS",
    # sectors
    "ports": "porturi", "shipyards": "șantiere navale", "tourism": "turism", "fishing": "pescuit",
    "aquaculture": "acvacultură", "management": "administrare",
    # zone confidence
    "official": "oficial", "mapped": "cartografiat", "assumed": "presupus",
    # comparison pairs
    "in situ vs model": "in situ vs model", "in situ vs satellite": "in situ vs satelit",
    "satellite vs model": "satelit vs model",
    # units
    "mg/L": "mg/L", "PSU": "PSU", "mg/m³": "mg/m³", "mmol/m³": "mmol/m³", "log10 mg/m³": "log10 mg/m³",
    "log10(mg/m³)": "log10(mg/m³)", "z (unitless)": "z (fără unitate)", "m/s": "m/s",
    "°C per decade": "°C pe deceniu", "PSU per decade": "PSU pe deceniu", "mg/L per decade": "mg/L pe deceniu",
    "log10(mg/m³) per decade": "log10(mg/m³) pe deceniu",
    # place used as a station in the validation tables
    "Constanta bottles": "Constanța (probe de apă)",
    "this point": "acest punct",
})
# variable ids, station codes and need ids stay as they are
_keep(["sst", "chl", "sal", "o2", "o2_bottom", "o2_sat", "no3", "po4", "si", "nh4", "kd490", "mld", "ph",
       "wave_height", "wind_speed", "discharge", "bottom_temp",
       "EUXRoOB01", "EUXRoOB02", "EUXRoOB03", "EUXRo02", "EUXRo03", "EUXRoCB01", "EUXRoCB02", "EUXRoCB03",
       "EUXRoOB01-03", "EUXRoCB01-03", "EUXRoCB0x",
       "chl_buoys", "o2_coast", "o2_bottom", "chl_plume", "nutrients", "sal_buoys", "buoy_continuity",
       "lat", "lon", "OURS", "OFFICIAL-RO", "OFFICIAL-EU", "Spearman", "RMSE"])

# =================================================================================================== table column names
_ee({
    # validation pairs (researcher table) and summary_table
    "station": "stație", "pair": "pereche", "start": "început", "end": "sfârșit", "bias": "bias", "rmse": "RMSE",
    "ubrmse": "RMSE fără bias", "r2": "R²", "r2_anom": "R² anomalii", "slope": "pantă", "spearman": "Spearman",
    "headline": "principal", "median_ratio": "raport median", "space": "spațiu",
    "variable": "variabilă", "title": "titlu", "trusted_source": "sursă de referință",
    "trusted_label": "sursă de referință (detaliu)", "uncertainty": "incertitudine",
    "uncertainty_value": "valoare incertitudine", "error_unit": "unitatea erorii", "stations": "stații",
    "confidence": "încredere", "reading": "interpretare",
    # seasonal gate table
    "source": "sursă", "trust": "încredere", "r2_adj": "R² ajustat", "cycle_show": "ciclu afișat",
    "n_years": "ani compleți", "trend_level": "nivel tendință", "trend_show": "tendință afișată",
    "cycle_reason": "motiv ciclu", "trend_reason": "motiv tendință",
    # measurement needs
    "rank": "loc", "need_id": "cod nevoie", "what": "ce", "where": "unde", "why": "de ce", "how": "cum",
    "who": "cine", "cost": "cost", "sectors": "sectoare", "n_reasons": "nr. motive", "reasons": "motive",
    "evidence": "dovezi", "concerns_you": "te privește", "hand_set": "setat manual", "label": "etichetă",
    "disagree": "surse în dezacord", "no_trusted_insitu": "fără senzor in situ de încredere",
    "untrusted_sensor": "senzor nesigur", "time_gap": "lipsă în timp", "decision_at_stake": "prag oficial în joc",
})

# =================================================================================================== validation
_ee({
    # titles (also the capitalised seasonal names)
    "Sea surface temperature": "Temperatura apei la suprafață",
    "Chlorophyll-a (surface)": "Clorofila-a (la suprafață)",
    "Surface salinity": "Salinitatea la suprafață",
    "Surface dissolved oxygen": "Oxigenul dizolvat la suprafață",
    "Nitrate (shape only)": "Nitrați (doar forma sezonieră)",
    "Phosphate (shape only)": "Fosfați (doar forma sezonieră)",
    # trusted labels
    "Satellite SST (Copernicus L4 analysis)": "SST din satelit (analiza Copernicus L4)",
    "Satellite chlorophyll (Copernicus L4 gap-free, 1 km)": "Clorofilă din satelit (Copernicus L4 fără goluri, 1 km)",
    "Model salinity (Copernicus Black Sea physics, 2.5 km)":
        "Salinitate din model (fizica Copernicus pentru Marea Neagră, 2,5 km)",
    "Model O2 (Copernicus BGC) for the seasonal cycle and areas without buoys; offshore buoys after QC where available":
        "O2 din model (Copernicus BGC) pentru ciclul sezonier și zonele fără geamanduri; geamandurile din larg, după QC, "
        "acolo unde există",
    "Bottle samples and the DIVAnd climatology": "Probe de apă și climatologia DIVAnd",
    "Not assessed": "Neevaluat", "not assessed": "neevaluat",
    # uncertainty
    "about 0.45 °C for a daily value at a point, bias under 0.15 °C (indicative)":
        "aproximativ 0,45 °C pentru o valoare zilnică într-un punct, bias sub 0,15 °C (orientativ)",
    "about 1 PSU for a daily coastal value (indicative)":
        "aproximativ 1 PSU pentru o valoare zilnică la coastă (orientativ)",
    "about 1 mg/L offshore and 2 mg/L at the coast; bias not known to better than +/- 0.7 mg/L (indicative)":
        "aproximativ 1 mg/L în larg și 2 mg/L la coastă; bias-ul nu este cunoscut mai precis de ±0,7 mg/L (orientativ)",
    "model not usable as absolute values; seasonal shape only (Spearman 0.41)":
        "modelul nu poate fi folosit pentru valori absolute; doar forma sezonieră (Spearman 0,41)",
    "model not usable, even for the seasonal shape (Spearman 0.01)":
        "modelul nu poate fi folosit nici măcar pentru forma sezonieră (Spearman 0,01)",
    "not quantified against trusted measurements; at least a factor of about 1.6 (indicative)":
        "necuantificată față de măsurători de încredere; cel puțin un factor de aproximativ 1,6 (orientativ)",
    # readings
    "Satellite SST is within about 0.45 °C of the offshore buoys on a typical day, and reads less than 0.15 °C cooler "
    "on average.":
        "SST din satelit diferă de geamandurile din larg cu aproximativ 0,45 °C într-o zi obișnuită și indică în medie "
        "o temperatură cu mai puțin de 0,15 °C mai mică.",
    "Satellite chlorophyll is the working reference, but its error is not known: it agrees with the model within a "
    "factor of about 1.6, and no trusted measurement exists offshore to check either.":
        "Clorofila din satelit este referința de lucru, dar eroarea ei nu este cunoscută: concordă cu modelul în limita "
        "unui factor de aproximativ 1,6, iar în larg nu există nicio măsurătoare de încredere care să le verifice.",
    "Model salinity is within about 1 PSU of coastal bottle samples on a typical day; it follows the Danube plume "
    "episodes but smooths them.":
        "Salinitatea din model diferă de probele de apă de la coastă cu aproximativ 1 PSU într-o zi obișnuită; urmărește "
        "episoadele penei Dunării, dar le netezește.",
    "Model surface O2 is within about 1 mg/L of the offshore buoys (2 mg/L at the coast) and its bias is uncertain by "
    "about +/- 0.7 mg/L; it gets the seasons right, not day-to-day changes.":
        "O2 la suprafață din model diferă de geamandurile din larg cu aproximativ 1 mg/L (2 mg/L la coastă), iar bias-ul "
        "său este incert cu aproximativ ±0,7 mg/L; redă corect anotimpurile, nu și variațiile de la o zi la alta.",
    "Model nitrate only gets the broad seasonal pattern (peak in February, while the bottles peak in April); use bottle "
    "samples and the climatology for levels.":
        "Nitrații din model redau doar tiparul sezonier general (maxim în februarie, în timp ce probele de apă au maximul "
        "în aprilie); pentru niveluri folosește probele de apă și climatologia.",
    "Model phosphate does not match the bottle samples even in shape; do not use it at the coast.":
        "Fosfații din model nu se potrivesc cu probele de apă nici măcar ca formă; nu îi folosi la coastă.",
    "No hand-written reading for this variable yet; see the pair metrics.":
        "Încă nu există o interpretare scrisă pentru această variabilă; vezi statisticile pe perechi.",
    # caveats
    "Satellite and model agree with each other as closely as each agrees with the buoys; the model very probably "
    "assimilates satellite SST (inferred), so only the buoys are an independent check.":
        "Satelitul și modelul concordă între ele la fel de bine cum concordă fiecare cu geamandurile; modelul asimilează "
        "foarte probabil SST din satelit (dedus), deci doar geamandurile sunt o verificare independentă.",
    "At the Constanta coast the scatter is larger (RMSE about 0.9 °C, 43 bottle days 1993-2021).":
        "La coasta Constanței împrăștierea este mai mare (RMSE aproximativ 0,9 °C, 43 de zile cu probe de apă, "
        "1993-2021).",
    "R² near 1 comes mostly from the shared seasonal cycle; with monthly means removed it is about 0.9.":
        "Un R² apropiat de 1 vine mai ales din ciclul sezonier comun; după eliminarea mediilor lunare este de "
        "aproximativ 0,9.",
    "By season both read cooler than the buoys in winter (satellite -0.2 °C, model -0.3 °C).":
        "Pe anotimpuri: iarna, ambele indică temperaturi mai mici decât geamandurile (satelit -0,2 °C, model -0,3 °C).",
    "Headline numbers are satellite vs model (consistency, not accuracy), in log10 space: 0.2 log10 is a factor of "
    "about 1.6.":
        "Cifrele principale compară satelitul cu modelul (coerență, nu acuratețe), în spațiul log10: 0,2 log10 înseamnă "
        "un factor de aproximativ 1,6.",
    "Bottle samples at the coast give only 3 chlorophyll days, too few to compare.":
        "Probele de apă de la coastă oferă doar 3 zile cu clorofilă, prea puține pentru o comparație.",
    "Based on 41 bottle days at Constanta (1993-2021): small sample.":
        "Pe baza a 41 de zile cu probe de apă la Constanța (1993-2021): eșantion mic.",
    "Offshore, buoy salinity is not reliable, so the model cannot be checked there (R² 0.00-0.17 against the buoys, "
    "EUXRo03 included).":
        "În larg, salinitatea de la geamanduri nu este de încredere, deci modelul nu poate fi verificat acolo (R² "
        "0,00-0,17 față de geamanduri, inclusiv EUXRo03).",
    "The sign of the bias depends on the buoy generation: model higher than OB01-03 (+0.5 to +0.7 mg/L), lower than "
    "EUXRo03 (-0.5 mg/L); the pooled mean bias hides this.":
        "Semnul bias-ului depinde de generația geamandurii: modelul este mai mare decât OB01-03 (între +0,5 și "
        "+0,7 mg/L) și mai mic decât EUXRo03 (-0,5 mg/L); bias-ul mediu cumulat ascunde acest lucru.",
    "With monthly means removed, R² is 0.00-0.10: no day-to-day skill.":
        "După eliminarea mediilor lunare, R² este 0,00-0,10: modelul nu redă variațiile de la o zi la alta.",
    "At the coast the model is 1.5 mg/L lower than the bottles (RMSE 2.3 mg/L, 41 days).":
        "La coastă modelul este cu 1,5 mg/L sub probele de apă (RMSE 2,3 mg/L, 41 de zile).",
    "Says nothing about bottom O2 (hypoxia): no bottom sensor in this check.":
        "Nu spune nimic despre O2 de la fund (hipoxie): în această verificare nu există niciun senzor la fund.",
    "35 bottle days at Constanta (1993-1999); compared as standardised values (z-scores).":
        "35 de zile cu probe de apă la Constanța (1993-1999); comparate ca valori standardizate (scoruri z).",
    "38 bottle days at Constanta (1993-1999); compared as standardised values (z-scores).":
        "38 de zile cu probe de apă la Constanța (1993-1999); comparate ca valori standardizate (scoruri z).",
    # sources not used and why
    "Buoy chlorophyll (fluorescence) EUXRoOB01-03": "Clorofila de la geamandurile EUXRoOB01-03 (fluorescență)",
    "Buoy chlorophyll (fluorescence) EUXRo03": "Clorofila de la geamandura EUXRo03 (fluorescență)",
    "Buoy salinity EUXRoOB01-03": "Salinitatea de la geamandurile EUXRoOB01-03",
    "Coastal buoys EUXRoCB01-03": "Geamandurile costiere EUXRoCB01-03",
    "Model chlorophyll (Copernicus BGC)": "Clorofila din model (Copernicus BGC)",
    "Model nitrate (Copernicus BGC) as absolute values": "Nitrații din model (Copernicus BGC) ca valori absolute",
    "Model phosphate (Copernicus BGC)": "Fosfații din model (Copernicus BGC)",
    "Shore station 15480 (NIMH)": "Stația de țărm 15480 (ANM)",
    "Untrusted by repo rule (CLAUDE.md, SHORTLIST.md); not used in the check.":
        "Nesigure conform regulii proiectului (CLAUDE.md, SHORTLIST.md); nefolosite în verificare.",
    "Untrusted by repo rule; not used in the check.":
        "Nesigură conform regulii proiectului; nefolosită în verificare.",
    "Reads 2 to 3 times more than both satellite and model (median ratio 0.36-0.51), autumn values up to about "
    "100 mg/m³; likely factory calibration, quenching, biofouling (inferred).":
        "Indică de 2-3 ori mai mult decât satelitul și modelul (raport median 0,36-0,51), cu valori de toamnă de până la "
        "aproximativ 100 mg/m³; cauze probabile: calibrarea din fabrică, stingerea fluorescenței (quenching), "
        "murdărirea biologică (biofouling) (dedus).",
    "Flat bands that jump between levels; R² with the satellite 0.00.":
        "Benzi plate care sar între niveluri; R² față de satelit 0,00.",
    "Indicative only: shares part of the satellite variability but has no in situ check.":
        "Doar orientativ: redă o parte din variabilitatea satelitului, dar nu are nicio verificare in situ.",
    "Drops to 13-15 PSU lasting weeks to months that end in steps (e.g. OB02 Oct 2025 - Mar 2026); matches "
    "conductivity-cell fouling (inferred).":
        "Scăderi la 13-15 PSU care durează săptămâni sau luni și se încheie în trepte (de ex. OB02 oct. 2025 - "
        "mar. 2026); corespund colmatării celulei de conductivitate (dedus).",
    "Repo rule: not usable as absolute values; at most for the timing of the winter maximum.":
        "Regula proiectului: nu se folosește pentru valori absolute; cel mult pentru momentul maximului de iarnă.",
    "Repo rule: not usable as absolute values; no agreement in shape either (Spearman 0.01).":
        "Regula proiectului: nu se folosește pentru valori absolute; nici forma nu concordă (Spearman 0,01).",
})
# "source: reason" list items of the researcher text
_UNTRUSTED = {
    "Coastal buoys EUXRoCB01-03": "Geamandurile costiere EUXRoCB01-03",
    "Shore station 15480 (NIMH)": "Stația de țărm 15480 (ANM)",
    "Buoy chlorophyll (fluorescence) EUXRoOB01-03": "Clorofila de la geamandurile EUXRoOB01-03 (fluorescență)",
    "Buoy chlorophyll (fluorescence) EUXRo03": "Clorofila de la geamandura EUXRo03 (fluorescență)",
    "Model chlorophyll (Copernicus BGC)": "Clorofila din model (Copernicus BGC)",
    "Buoy salinity EUXRoOB01-03": "Salinitatea de la geamandurile EUXRoOB01-03",
    "Model nitrate (Copernicus BGC) as absolute values": "Nitrații din model (Copernicus BGC) ca valori absolute",
    "Model phosphate (Copernicus BGC)": "Fosfații din model (Copernicus BGC)",
}
for _en, _ro in _UNTRUSTED.items():
    T(_en + ": {r:l}", _ro + ": {r}")

# =================================================================================================== seasonal (gate, texts)
_ee({
    "sea surface temperature": "temperatura apei la suprafață",
    "chlorophyll-a (log10)": "clorofila-a (log10)",
    "surface salinity": "salinitatea la suprafață",
    "surface dissolved oxygen": "oxigenul dizolvat la suprafață",
    "Chlorophyll-a (log10)": "Clorofila-a (log10)",
    "Indicative trend": "Tendință orientativă", "Climate trend": "Tendință climatică",
    "Not significant: year-to-year variability is as large as the change.":
        "Nesemnificativă statistic: variabilitatea de la un an la altul este la fel de mare ca schimbarea.",
    "no cycle could be fitted": "nu s-a putut ajusta niciun ciclu",
    "no trend computed": "nicio tendință calculată",
    "no complete year": "niciun an complet",
    "datahub.get_series attrs": "atributele datahub.get_series",
    "1 Jan of the first year": "1 ian. din primul an",
    # source labels (also datahub SOURCES, below)
    "Nearest offshore buoy (measured O2)": "Cea mai apropiată geamandură din larg (O2 măsurat)",
})
T("passes the gate: trust {t:t}, cycle p {p:s}, adjusted R2 {r:n} (thresholds OURS)",
  "trece filtrul: încredere {t}, ciclu p {p}, R² ajustat {r} (praguri OURS)")
T("source trust is '{t:t}' (needs good or usable): the cycle of this source is not shown",
  "încrederea în sursă este „{t}” (trebuie să fie bună sau utilizabilă): ciclul acestei surse nu este afișat")
T("no significant seasonal cycle (p = {p:n}, needs < {q:n}, OURS)",
  "niciun ciclu sezonier semnificativ (p = {p}, necesar < {q}, OURS)")
T("the seasonal cycle explains too little of the variation (adjusted R2 {r:n}, needs >= {q:n}, OURS): the usual-range "
  "band would be misleading",
  "ciclul sezonier explică prea puțin din variație (R² ajustat {r}, necesar >= {q}, OURS): banda intervalului "
  "obișnuit ar induce în eroare")
T("source '{s:k}' has no seasonal analysis (use satellite, model, buoy)",
  "sursa „{s}” nu are analiză sezonieră (folosește satelit, model sau geamandură)")
T("no cached {s:t} record at this point ({e:k})", "nu există în cache o serie de la {s} în acest punct ({e})")
T("record too short for a seasonal fit (1 weeks, needs 2 years)",
  "serie prea scurtă pentru o ajustare sezonieră (o singură săptămână, sunt necesari 2 ani)")
T("record too short for a seasonal fit ({n:c} weeks, needs 2 years)",
  "serie prea scurtă pentru o ajustare sezonieră ({n} săptămâni, sunt necesari 2 ani)")
T("Seasonal cycle not shown: {r:t}.", "Ciclul sezonier nu este afișat: {r}.")
T("source trust is '{t:t}' (needs good or usable): no trend shown",
  "încrederea în sursă este „{t}” (trebuie să fie bună sau utilizabilă): nu se afișează nicio tendință")
T("not enough years yet: 0 complete year(s), a trend needs at least {m:c} (OURS)",
  "încă niciun an complet; o tendință are nevoie de cel puțin {m} ani (OURS)")
T("not enough years yet: 1 complete year(s), a trend needs at least {m:c} (OURS)",
  "încă un singur an complet; o tendință are nevoie de cel puțin {m} ani (OURS)")
T("not enough years yet: {n:c} complete year(s), a trend needs at least {m:c} (OURS)",
  "încă doar {n} ani compleți; o tendință are nevoie de cel puțin {m} ani (OURS)")
T("{n:c} complete years: climate trend (thresholds OURS)", "{n} ani compleți: tendință climatică (praguri OURS)")
T("{n:c} complete years: climate trend; not significant (p = {p:n}) (thresholds OURS)",
  "{n} ani compleți: tendință climatică; nesemnificativă statistic (p = {p}) (praguri OURS)")
T("{n:c} complete years: indicative (fewer than {m:c} years) (thresholds OURS)",
  "{n} ani compleți: tendință orientativă (sub {m} ani) (praguri OURS)")
T("{n:c} complete years: indicative (fewer than {m:c} years); not significant (p = {p:n}) (thresholds OURS)",
  "{n} ani compleți: tendință orientativă (sub {m} ani); nesemnificativă statistic (p = {p}) (praguri OURS)")
T("only 1 complete year(s) (need {m:c}): trend not meaningful",
  "un singur an complet (sunt necesari {m}): tendința nu are sens")
T("only {n:c} complete year(s) (need {m:c}): trend not meaningful",
  "doar {n} ani compleți (sunt necesari {m}): tendința nu are sens")
T("Long-term trend not shown: {r:t}.", "Tendința pe termen lung nu este afișată: {r}.")
T("weekly means {a:d} to {b:d}", "medii săptămânale {a} – {b}")
T("fit +- {z:n} x weekly residual sd (about p10-p90; OURS)",
  "ajustare ± {z} × abaterea standard a reziduurilor săptămânale (aproximativ p10-p90; OURS)")
T("day {d:i} of a {p:i}-d cycle counted from 1 Jan {y:i}",
  "ziua {d} a unui ciclu cu perioada de {p} de zile, numărată de la 1 ian. {y}")
T("day {d:i} of a {p:i}-d cycle counted from 1 Jan of the first year",
  "ziua {d} a unui ciclu cu perioada de {p} de zile, numărată de la 1 ian. din primul an")
T("fitted on the fly (periods from {s:k} in peaks.csv)", "ajustat pe loc (perioade de la {s} din peaks.csv)")
T("datahub register (get_series failed: {e:k})", "registrul datahub (get_series a eșuat: {e})")
# cycle sentence; chlorophyll first (its name contains brackets, and its amplitude is a factor). The date of the maximum
# comes before the end of the Romanian sentence, so the month abbreviation ("aug.") never meets the final full stop.
T("Chlorophyll-a (log10) ({o:t}) follows a yearly cycle of about a factor {f:n} above / below the mean (log10 amplitude "
  "{a:n}) around its mean (95 % CI {lo:n} to {hi:n}), highest around {d:t}, with a half-year component of a factor "
  "{f2:n} above / below the mean (log10 amplitude {a2:n}).",
  "Clorofila-a (log10) ({o}) urmează un ciclu anual cu maximul în jurul datei de {d}, de aproximativ {f} ori peste / "
  "sub medie (amplitudine log10 {a}; interval de încredere 95 %: {lo} – {hi}), și o componentă semianuală de {f2} ori "
  "peste / sub medie (amplitudine log10 {a2}).")
T("Chlorophyll-a (log10) ({o:t}) follows a yearly cycle of about a factor {f:n} above / below the mean (log10 amplitude "
  "{a:n}) around its mean (95 % CI {lo:n} to {hi:n}), highest around {d:t}.",
  "Clorofila-a (log10) ({o}) urmează un ciclu anual cu maximul în jurul datei de {d}, de aproximativ {f} ori peste / "
  "sub medie (amplitudine log10 {a}; interval de încredere 95 %: {lo} – {hi}).")
T("{nm:t} ({o:t}) follows a yearly cycle of about {a:t} around its mean (95 % CI {lo:n} to {hi:n}), highest around "
  "{d:t}, with a half-year component of {b:t}.",
  "{nm} ({o}) urmează un ciclu anual cu maximul în jurul datei de {d} și cu amplitudinea de aproximativ {a} față de "
  "medie (interval de încredere 95 %: {lo} – {hi}), plus o componentă semianuală de {b}.")
T("{nm:t} ({o:t}) follows a yearly cycle of about {a:t} around its mean (95 % CI {lo:n} to {hi:n}), highest around "
  "{d:t}.",
  "{nm} ({o}) urmează un ciclu anual cu maximul în jurul datei de {d} și cu amplitudinea de aproximativ {a} față de "
  "medie (interval de încredere 95 %: {lo} – {hi}).")
T("The cycle explains {p:i}% of the weekly variation ({w:t}, {s:t}).",
  "Ciclul explică {p}% din variația săptămânală ({w}, {s}).")
T("a factor {f:n} above / below the mean (log10 amplitude {a:n})",
  "de {f} ori peste / sub medie (amplitudine log10 {a})")
# trend sentence
T("{w:t} of chlorophyll-a (log10) ({o:t}, {y0:i}-{y1:i}, {n:c} complete years): {s:n} {u:t} (95 % CI {a:n} to {b:n}, "
  "p = {p:n}).",
  "{w} pentru clorofila-a (log10) ({o}, {y0}-{y1}, {n} ani compleți): {s} {u} (interval de încredere 95 %: {a} – "
  "{b}; p = {p}).")
T("{w:t} of {nm:t} ({o:t}, {y0:i}-{y1:i}, {n:c} complete years): {s:n} {u:t} (95 % CI {a:n} to {b:n}, p = {p:n}).",
  "{w} pentru {nm} ({o}, {y0}-{y1}, {n} ani compleți): {s} {u} (interval de încredere 95 %: {a} – {b}; p = {p}).")
T("Fewer than {n:c} years: read it as indicative, not as a climate trend.",
  "Mai puțin de {n} ani: citește-o ca tendință orientativă, nu ca tendință climatică.")

# =================================================================================================== methods: primers
_ee({
    "Every value on this site comes from one of three places: a **measurement** (a buoy or a water sample), a "
    "**satellite** (sees only the surface), or a **computer model** (fills the gaps). None is perfect. Next to each "
    "value we say how far you can trust it: *reliable*, *fairly reliable* or *rough guide only*.":
        "Fiecare valoare de pe acest site vine din una dintre trei surse: o **măsurătoare** (o geamandură sau o probă "
        "de apă), un **satelit** (vede doar suprafața) sau un **model numeric** (completează golurile). Niciuna nu este "
        "perfectă. Lângă fiecare valoare îți spunem cât te poți baza pe ea: *de încredere*, *destul de sigur* sau "
        "*doar orientativ*.",
    "Every value comes from a **measurement** (buoy, water sample), a **satellite** (surface only) or a **model** "
    "(computed everywhere). To know how wrong a value can be, we compare the sources on the same day at the same "
    "place. The typical difference (RMSE) and the average offset (bias) are the uncertainty; where no measurement "
    "exists, the uncertainty is unknown, not zero.":
        "Fiecare valoare provine dintr-o **măsurătoare** (geamandură, probă de apă), de la un **satelit** (doar "
        "suprafața) sau dintr-un **model** (calculat peste tot). Ca să aflăm cât de greșită poate fi o valoare, "
        "comparăm sursele în aceeași zi și în același loc. Diferența tipică (RMSE) și abaterea medie (bias) reprezintă "
        "incertitudinea; acolo unde nu există nicio măsurătoare, incertitudinea este necunoscută, nu zero.",
    "Every value comes from a measurement, a satellite or a model, and each has an error. For each indicator we say "
    "what that error means for your decision: whether a 'watch' or 'alert' can be acted on directly, or first needs a "
    "measurement on site.":
        "Fiecare valoare provine dintr-o măsurătoare, de la un satelit sau dintr-un model și fiecare are o eroare. "
        "Pentru fiecare indicator spunem ce înseamnă această eroare pentru decizia ta: dacă pe baza unei „atenții” sau "
        "a unei „alerte” se poate acționa direct sau este nevoie mai întâi de o măsurătoare la fața locului.",
    "Uncertainty is estimated by matching in-situ, satellite and model daily values at the offshore buoys "
    "(EUXRoOB01-03 2024-2026, EUXRo03 2013-2023) and coastal bottle samples (Constanta, 1993-2021), reporting bias, "
    "RMSE, unbiased RMSE, R², R² of anomalies, slope and Spearman. Sensors that fail the check are flagged in "
    "`marinekit.datahub` and never used as the automatic source. Seasonal cycles and trends are shown only behind a "
    "quality gate. Thresholds labelled OURS are our proposals; all uncertainties are indicative (point values, few "
    "stations).":
        "Incertitudinea este estimată prin împerecherea valorilor zilnice in situ, satelitare și din model la "
        "geamandurile din larg (EUXRoOB01-03 2024-2026, EUXRo03 2013-2023) și la probele de apă de la coastă "
        "(Constanța, 1993-2021), cu raportarea bias-ului, a RMSE, a RMSE fără bias, a R², a R² al anomaliilor, a pantei "
        "și a corelației de rang Spearman. Senzorii care nu trec verificarea sunt marcați în `marinekit.datahub` și nu "
        "sunt folosiți niciodată ca sursă automată. Ciclurile sezoniere și tendințele sunt afișate doar după un filtru "
        "de calitate. Pragurile etichetate OURS sunt propunerile noastre; toate incertitudinile sunt orientative "
        "(valori punctuale, puține stații).",
})

# =================================================================================================== methods: uncertainty texts
_ee({
    # confidence leads (public / stakeholder)
    "Reliable.": "De încredere.", "Fairly reliable.": "Destul de sigur.", "Rough guide only.": "Doar orientativ.",
    "Uncertain.": "Incert.",
    "Reliable for decisions.": "De încredere pentru decizii.",
    "Fairly reliable for decisions.": "Destul de sigur pentru decizii.",
    "Rough guide only for decisions.": "Doar orientativ pentru decizii.",
    # public
    "The satellite temperature is usually within about half a degree (0.45 °C) of what the buoys measure.":
        "Temperatura din satelit diferă de obicei cu cel mult o jumătate de grad (0,45 °C) de ce măsoară geamandurile.",
    "The map shows where there is more or less algae, but the exact amount can be off by half or double. Buoy readings "
    "are not used because they read 2 to 3 times too high.":
        "Harta arată unde sunt mai multe sau mai puține alge, dar cantitatea exactă poate fi de două ori mai mică sau de "
        "două ori mai mare. Citirile geamandurilor nu sunt folosite, pentru că arată de 2-3 ori prea mult.",
    "Salinity comes from a computer model that is usually within about 1 unit (PSU) of water samples at the coast. The "
    "offshore buoy sensors give wrong readings and are not used.":
        "Salinitatea vine dintr-un model numeric care diferă de obicei cu aproximativ 1 unitate (PSU) de probele de apă "
        "de la coastă. Senzorii geamandurilor din larg dau citiri greșite și nu sunt folosiți.",
    "Surface oxygen from the model is usually within about 1 mg/L of the buoys offshore (2 mg/L at the coast). Oxygen "
    "near the seabed, where fish and mussels can suffocate, is not measured near the coast.":
        "Oxigenul de la suprafață din model diferă de obicei cu aproximativ 1 mg/L de geamandurile din larg (2 mg/L la "
        "coastă). Oxigenul de lângă fundul mării, unde peștii și midiile se pot sufoca, nu este măsurat lângă coastă.",
    "Nutrient values come from past water samples, not from today: the model is not used for them.":
        "Valorile nutrienților provin din probe de apă mai vechi, nu de azi: modelul nu este folosit pentru ele.",
    "No sensor measures oxygen near the seabed along the coast. The value shown is a computer-model estimate, and "
    "different models differ by about 2 mg/L.":
        "Niciun senzor nu măsoară oxigenul de lângă fundul mării de-a lungul coastei. Valoarea afișată este o estimare "
        "dintr-un model numeric, iar modelele diferă între ele cu aproximativ 2 mg/L.",
    # student
    "Two numbers describe the error.": "Două numere descriu eroarea.",
    "*RMSE* (root mean square error) is the typical size of the difference between two sources on one day.":
        "*RMSE* (eroarea pătratică medie) este mărimea tipică a diferenței dintre două surse într-o zi.",
    "*Bias* is the average difference: a constant offset that could be corrected.":
        "*Bias*-ul (abaterea sistematică) este diferența medie: un decalaj constant care ar putea fi corectat.",
    "Why a high R² can mislead.": "De ce un R² mare poate înșela.",
    "Agreement is about RMSE and bias, not only R².": "Concordanța se judecă după RMSE și bias, nu doar după R².",
    "Chlorophyll spans more than 100 times from clear to bloom water, so errors are computed on a logarithmic scale: a "
    "difference of 0.2 in log10 means a factor of 10^0.2, about 1.6.":
        "Clorofila variază de peste 100 de ori între apa limpede și apa cu înflorire algală, așa că erorile se calculează "
        "pe o scară logaritmică: o diferență de 0,2 în log10 înseamnă un factor de 10^0,2, adică aproximativ 1,6.",
    "Satellite and model agree within about that factor.": "Satelitul și modelul concordă cam în limita acestui factor.",
    "The buoys read 2 to 3 times more (median ratio satellite / buoy 0.36-0.51).":
        "Geamandurile indică de 2-3 ori mai mult (raportul median satelit / geamandură 0,36-0,51).",
    "Agreement is not accuracy.": "Concordanța nu înseamnă acuratețe.",
    "Two sources that agree can both be wrong; here no trusted measurement exists offshore to check either, so the "
    "true error is not known.":
        "Două surse care concordă pot greși amândouă; aici, în larg, nu există nicio măsurătoare de încredere care să le "
        "verifice, deci eroarea reală nu este cunoscută.",
    "Offshore, the buoy salinity shows long drops that look like a dirty sensor; against it the model has R² "
    "0.00-0.17.":
        "În larg, salinitatea de la geamanduri are scăderi lungi care arată ca un senzor murdar; față de ea, modelul are "
        "R² 0,00-0,17.",
    "A bad reference makes a good source look bad.": "O referință proastă face ca o sursă bună să pară proastă.",
    "Before blaming the model, check the measurement.": "Înainte să dai vina pe model, verifică măsurătoarea.",
    "An average can hide opposite errors.": "O medie poate ascunde erori de semn opus.",
    "The pooled bias looks small because positive and negative offsets cancel.":
        "Bias-ul cumulat pare mic pentru că abaterile pozitive și negative se anulează.",
    "With the monthly means removed, R² is near 0: the model gets the seasons right, not the day-to-day changes.":
        "După eliminarea mediilor lunare, R² este aproape 0: modelul redă corect anotimpurile, nu și variațiile de la o "
        "zi la alta.",
    "For nutrients the model values are on a different scale from the samples, so both are standardised (z-scores) and "
    "only the shape is compared, with a rank correlation (Spearman): 0.41 for nitrate, enough for the broad seasonal "
    "pattern only.":
        "Pentru nutrienți, valorile din model sunt pe altă scară decât probele, așa că ambele sunt standardizate "
        "(scoruri z) și se compară doar forma, cu o corelație de rang (Spearman): 0,41 pentru nitrați, suficient doar "
        "pentru tiparul sezonier general.",
    "For nutrients the model values are on a different scale from the samples, so both are standardised (z-scores) and "
    "only the shape is compared, with a rank correlation (Spearman): 0.01 for phosphate: no agreement at all.":
        "Pentru nutrienți, valorile din model sunt pe altă scară decât probele, așa că ambele sunt standardizate "
        "(scoruri z) și se compară doar forma, cu o corelație de rang (Spearman): 0,01 pentru fosfați, deci nicio "
        "concordanță.",
    "That is why the model is not used for nutrient levels.":
        "De aceea modelul nu este folosit pentru nivelurile de nutrienți.",
    "What we can and cannot say.": "Ce putem și ce nu putem spune.",
    "To know how wrong a value can be, we compare it with a measurement at the same place and day. For bottom oxygen "
    "there is no measurement near the coast, so the error cannot be computed at all. What we have is the spread between "
    "two model systems, about 2 mg/L: that is a lower limit on the uncertainty, not the error itself. Compare it with "
    "the classes: below 2 mg/L is hypoxia, 2-4 mg/L is stress, so a 2 mg/L spread can move a site across a whole "
    "class.":
        "Ca să știm cât de greșită poate fi o valoare, o comparăm cu o măsurătoare din același loc și din aceeași zi. "
        "Pentru oxigenul de la fund nu există nicio măsurătoare lângă coastă, deci eroarea nu poate fi calculată deloc. "
        "Avem doar diferența dintre două sisteme de modelare, de aproximativ 2 mg/L: aceasta este o limită inferioară a "
        "incertitudinii, nu eroarea propriu-zisă. Compar-o cu clasele: sub 2 mg/L înseamnă hipoxie, 2-4 mg/L înseamnă "
        "stres, deci o diferență de 2 mg/L poate muta un loc dintr-o clasă în alta.",
    # stakeholder
    "Good enough for planning: an error of about 0.45 °C rarely changes a decision; near the coast allow about "
    "0.9 °C.":
        "Suficient de bun pentru planificare: o eroare de aproximativ 0,45 °C schimbă rareori o decizie; lângă coastă "
        "ia în calcul aproximativ 0,9 °C.",
    "Temperature maps for where fish gather are reliable offshore (about 0.45 °C); at the coast allow about 0.9 °C.":
        "Hărțile de temperatură care arată unde se adună peștii sunt de încredere în larg (aproximativ 0,45 °C); la "
        "coastă ia în calcul aproximativ 0,9 °C.",
    "Heat-stress alerts based on temperature are reliable; at the farm, near the coast, allow about 0.9 °C.":
        "Alertele de stres termic bazate pe temperatură sunt de încredere; la fermă, lângă coastă, ia în calcul "
        "aproximativ 0,9 °C.",
    "Bathing temperature is reliable to about half a degree offshore and about 1 °C at the beach.":
        "Temperatura apei pentru îmbăiere este de încredere cu o precizie de aproximativ o jumătate de grad în larg și "
        "de aproximativ 1 °C la plajă.",
    "Reliable for work planning and corrosion checks to about half a degree.":
        "De încredere pentru planificarea lucrărilor și verificările de coroziune, cu o precizie de aproximativ o "
        "jumătate de grad.",
    "Reliable to about half a degree; temperature is rarely the limiting factor for port operations.":
        "De încredere cu o precizie de aproximativ o jumătate de grad; temperatura este rareori factorul limitativ "
        "pentru operațiunile portuare.",
    "Use it as a reason to look, not as a measurement: the amount can be off by a factor of 1.6 or more.":
        "Folosește-o ca motiv de verificare, nu ca măsurătoare: cantitatea poate fi greșită cu un factor de 1,6 sau mai "
        "mult.",
    "A bloom shown near the beaches or the Danube plume can be overstated by river sediment. Check with a water sample "
    "before warning bathers.":
        "O înflorire algală afișată lângă plaje sau în pana Dunării poate fi exagerată de sedimentele aduse de fluviu. "
        "Verifică printr-o probă de apă înainte de a avertiza turiștii.",
    "A bloom alert near the farms is a reason to take a water sample and a toxin test, not a confirmed harmful bloom.":
        "O alertă de înflorire algală lângă ferme este un motiv pentru o probă de apă și un test de toxine, nu o "
        "înflorire dăunătoare confirmată.",
    "Use it as a broad sign of productive waters, not as an exact value.":
        "Folosește-o ca semn general al apelor productive, nu ca valoare exactă.",
    "Not decision-grade for ports; context only.":
        "Nu este suficient de precisă pentru decizii în porturi; doar context.",
    "Not decision-grade for shipyards; context only.":
        "Nu este suficient de precisă pentru decizii în șantierele navale; doar context.",
    "Offshore salinity comes from the model only; an error of about 1 PSU is fine for most uses.":
        "Salinitatea din larg vine doar din model; o eroare de aproximativ 1 PSU este acceptabilă pentru majoritatea "
        "utilizărilor.",
    "The model smooths the low-salinity Danube pulses: a short freshwater event at a farm can be missed or shown "
    "weaker than it is.":
        "Modelul netezește pulsurile de apă mai dulce venite de la Dunăre: un episod scurt de apă dulce la o fermă poate "
        "fi ratat sau arătat mai slab decât este.",
    "Good enough for corrosion planning (about 1 PSU).":
        "Suficient de bun pentru planificarea protecției la coroziune (aproximativ 1 PSU).",
    "Good enough for operations; salinity is rarely limiting.":
        "Suficient de bun pentru operațiuni; salinitatea este rareori un factor limitativ.",
    "An oxygen 'watch' or 'alert' is a reason to measure, not a confirmed event: surface oxygen is about 1 mg/L "
    "uncertain offshore, 2 mg/L at the coast, and bottom oxygen is not measured.":
        "O „atenție” sau o „alertă” de oxigen este un motiv să măsori, nu un eveniment confirmat: oxigenul de la "
        "suprafață are o incertitudine de aproximativ 1 mg/L în larg și 2 mg/L la coastă, iar oxigenul de la fund nu "
        "este măsurat.",
    "Mussel deaths depend on bottom oxygen, which nobody measures near the farms. The model value is uncertain by "
    "about 2 mg/L, as wide as the gap between 'stress' (4 mg/L) and 'hypoxia' (2 mg/L). Before acting on an alert, "
    "lower an oxygen probe at the farm.":
        "Mortalitatea midiilor depinde de oxigenul de la fund, pe care nu îl măsoară nimeni lângă ferme. Valoarea din "
        "model are o incertitudine de aproximativ 2 mg/L, cât toată distanța dintre „stres” (4 mg/L) și „hipoxie” "
        "(2 mg/L). Înainte de a acționa pe baza unei alerte, coboară o sondă de oxigen la fermă.",
    "Low bottom oxygen drives fish off the shelf; the map shows where it may happen, not where it did.":
        "Oxigenul scăzut la fund alungă peștii de pe platforma continentală; harta arată unde se poate întâmpla, nu unde "
        "s-a întâmplat.",
    "Surface oxygen is a background indicator for beaches; fish kills are rare and would be reported by the "
    "authorities first.":
        "Oxigenul de la suprafață este un indicator de fond pentru plaje; mortalitățile în masă ale peștilor sunt rare "
        "și ar fi anunțate mai întâi de autorități.",
    "Historical only: useful to explain long-term blooms, not to act this week.":
        "Doar istoric: util pentru a explica înfloririle algale pe termen lung, nu pentru a acționa săptămâna aceasta.",
    # researcher
    "**Method.** Daily means matched on the same day; satellite and model taken at the nearest pixel or grid cell to "
    "the station; chlorophyll compared in log10; nutrients as z-scores. Headline RMSE is pooled, n-weighted: sqrt(sum "
    "n*RMSE^2 / sum n). R² of anomalies uses monthly means removed, so it measures day-to-day agreement beyond the "
    "shared seasonal cycle; R² alone overstates agreement. Satellite and model are not independent for SST (the model "
    "very probably assimilates satellite SST, inferred); only in-situ data are an independent check.":
        "**Metodă.** Medii zilnice împerecheate pe aceeași zi; satelitul și modelul sunt luate din pixelul sau celula "
        "de grilă cea mai apropiată de stație; clorofila este comparată în log10, nutrienții ca scoruri z. RMSE "
        "principal este cumulat și ponderat cu n: sqrt(sum n*RMSE^2 / sum n). R² al anomaliilor se calculează după "
        "eliminarea mediilor lunare, deci măsoară concordanța de la o zi la alta dincolo de ciclul sezonier comun; R² "
        "singur supraestimează concordanța. Pentru SST, satelitul și modelul nu sunt independente (modelul asimilează "
        "foarte probabil SST din satelit, dedus); doar datele in situ sunt o verificare independentă.",
    "**Autocorrelation.** Daily values are autocorrelated, so the effective sample size is much smaller than n; RMSE "
    "and bias are fine as descriptions, but any confidence interval computed from n would be too narrow. Seasonal fits "
    "use Newey-West (HAC) errors; trends use annual means without an autocorrelation correction, so their uncertainty "
    "is a lower bound.":
        "**Autocorelație.** Valorile zilnice sunt autocorelate, deci mărimea efectivă a eșantionului este mult mai mică "
        "decât n; RMSE și bias-ul sunt bune ca descriere, dar orice interval de încredere calculat din n ar fi prea "
        "îngust. Ajustările sezoniere folosesc erori Newey-West (HAC); tendințele folosesc medii anuale fără corecție "
        "pentru autocorelație, deci incertitudinea lor este o limită inferioară.",
    "**Quality gate** (OURS): source trust good or usable; cycle p < 0.05 (HAC) and adjusted R² >= 0.5 on weekly "
    "means; trend from 8 complete years (indicative below 20, climate from 20).":
        "**Filtru de calitate** (OURS): încrederea în sursă bună sau utilizabilă; ciclu cu p < 0,05 (HAC) și R² ajustat "
        ">= 0,5 pe medii săptămânale; tendință de la 8 ani compleți (orientativă sub 20, climatică de la 20).",
    "**Caveats.**": "**Limitări.**", "Caveats.": "Limitări.",
    "**Not used.**": "**Surse nefolosite.**", "Not used.": "Surse nefolosite.",
    "**Bottom O2: no validation possible.** No bottom sensor exists within the study area in the matched data; the "
    "Copernicus BGC model systems (reanalysis vs analysis/forecast) disagree by about 2 mg/L at the bottom "
    "(docs/indicators/SHORTLIST.md section 4). The oxygen card therefore has low confidence; D5C5 (OFFICIAL-RO) cannot "
    "be assessed from data here.":
        "**O2 la fund: nicio validare posibilă.** În datele împerecheate nu există niciun senzor la fund în zona de "
        "studiu; sistemele de modelare Copernicus BGC (reanaliză vs analiză/prognoză) diferă cu aproximativ 2 mg/L la "
        "fund (docs/indicators/SHORTLIST.md, secțiunea 4). Prin urmare, fișa de oxigen are încredere scăzută; D5C5 "
        "(OFFICIAL-RO) nu poate fi evaluat aici din date.",
    "Surface O2, for reference:": "O2 la suprafață, ca referință:",
})
T("For temperature the satellite differs from the buoys by about {r:n} °C on a typical day (RMSE, {n:c} matched days "
  "at {k:c} offshore buoys) and reads {b:n} °C cooler on average (bias).",
  "Pentru temperatură, satelitul diferă de geamanduri cu aproximativ {r} °C într-o zi obișnuită (RMSE, {n} zile "
  "împerecheate la {k} geamanduri din larg) și indică în medie o temperatură cu {b} °C mai mică (bias).")
T("R² (how much of the variation one source explains in the other) is {a:n}-{b:n}, almost perfect, but most of it is "
  "the seasons that both sources share: winter cold and summer warm.",
  "R² (cât din variația unei surse este explicată de cealaltă) este {a}-{b}, aproape perfect, dar cea mai mare parte "
  "vine din anotimpurile comune ambelor surse: iarna rece și vara caldă.")
T("With the monthly means removed, R² drops to {a:n}-{b:n}.", "După eliminarea mediilor lunare, R² scade la {a}-{b}.")
T("The model is within about {r:n} PSU of coastal water samples ({n:c} sample days).",
  "Modelul diferă cu aproximativ {r} PSU de probele de apă de la coastă ({n} zile cu probe).")
T("Model surface oxygen differs from the offshore buoys by about {r:n} mg/L on a typical day.",
  "Oxigenul de suprafață din model diferă de geamandurile din larg cu aproximativ {r} mg/L într-o zi obișnuită.")
T("Its bias is {a:n} to {b:n} mg/L depending on the buoy: higher than the newer buoys, lower than the older one.",
  "Bias-ul său este între {a} și {b} mg/L, în funcție de geamandură: mai mare decât la geamandurile noi, mai mic decât "
  "la cea veche.")
T("**{t:t}**: trusted source {s:t}; uncertainty {u:t}; confidence {c:t}.",
  "**{t}**: sursa de referință: {s}; incertitudine: {u}; încredere {c}.")
T("Metrics ({u:t}; bias = second source minus first):", "Statistici ({u}; bias = a doua sursă minus prima):")
T("Long satellite record at the buoys: {s:n} °C per decade (95 % CI {a:n} to {b:n}, {y0:i}-{y1:i}, satellite, {n:c} "
  "complete years).",
  "Seria lungă din satelit la geamanduri: {s} °C pe deceniu (interval de încredere 95 %: {a} – {b}, {y0}-{y1}, satelit, "
  "{n} ani compleți).")
T("Basis: {f:k}; run {d:d}. All numbers indicative.", "Bază: {f}; rularea din {d}. Toate cifrele sunt orientative.")

# =================================================================================================== methods: measurement needs
_ee({
    # what
    "Chlorophyll-a in bottle samples, to calibrate the buoy fluorometers":
        "Clorofilă-a în probe de apă, pentru calibrarea fluorimetrelor de pe geamanduri",
    "Surface dissolved oxygen from a checked coastal sensor":
        "Oxigen dizolvat la suprafață, de la un senzor costier verificat",
    "Bottom dissolved oxygen, about 1 m above the seabed, May to September":
        "Oxigen dizolvat la fund, la aproximativ 1 m deasupra fundului mării, din mai până în septembrie",
    "Nearshore chlorophyll-a in bottle samples, with suspended matter to check the satellite":
        "Clorofilă-a lângă țărm în probe de apă, împreună cu materiile în suspensie, pentru verificarea satelitului",
    "Nitrate, nitrite, ammonium and phosphate (DIN, PO4) in bottle samples":
        "Nitrați, nitriți, amoniu și fosfați (DIN, PO4) în probe de apă",
    "Surface salinity from a clean conductivity cell": "Salinitate la suprafață, de la o celulă de conductivitate curată",
    "Keep the offshore buoys measuring oxygen and temperature":
        "Geamandurile din larg trebuie să măsoare în continuare oxigenul și temperatura",
    "Nothing new for sea surface temperature": "Nimic nou pentru temperatura apei la suprafață",
    # where
    "Offshore buoys EUXRoOB01-03": "Geamandurile din larg EUXRoOB01-03",
    "Coastal waters, Constanta - Mamaia": "Ape costiere, Constanța - Mamaia",
    "North-western shelf bottom water, 20-40 m, including the mussel farms Mangalia - 2 Mai (May to September)":
        "Apa de la fund pe platforma continentală de nord-vest, 20-40 m, inclusiv fermele de midii Mangalia - 2 Mai "
        "(mai-septembrie)",
    "Nearshore strip within 20 km of the coast, Danube plume from Sulina to Constanta":
        "Fâșia de 20 km de lângă țărm, pana Dunării de la Sulina la Constanța",
    "Coastal stations Constanta, Mamaia, Eforie": "Stațiile costiere Constanța, Mamaia, Eforie",
    "Whole coast (satellite) and offshore buoys": "Întreaga coastă (satelit) și geamandurile din larg",
    # how
    "Take a surface bottle sample for chlorophyll extraction at every buoy service visit (monthly if possible); compare "
    "it with the night-time fluorescence (avoids daytime quenching); clean the optical window.":
        "La fiecare vizită de service a geamandurii, prelevă o probă de apă de suprafață pentru extracția clorofilei "
        "(lunar, dacă se poate); compar-o cu fluorescența din timpul nopții (evită stingerea fluorescenței din timpul "
        "zilei); curăță fereastra optică.",
    "Confirm the oxygen units and the quality control of the coastal buoys EUXRoCB01-03 (question 4 for NIMRD), then "
    "check them against Winkler bottle samples at each service visit.":
        "Confirmă unitățile de măsură pentru oxigen și controlul calității la geamandurile costiere EUXRoCB01-03 "
        "(întrebarea 4 pentru INCDM), apoi verifică-le cu probe de apă analizate prin metoda Winkler la fiecare vizită "
        "de service.",
    "A bottom oxygen sensor (optode) on a mooring at the mussel farms, or monthly CTD casts with an oxygen sensor at 20, "
    "30 and 40 m depth from May to September.":
        "Un senzor de oxigen la fund (optodă) pe o ancorare la fermele de midii sau profile CTD lunare cu senzor de "
        "oxigen la 20, 30 și 40 m adâncime, din mai până în septembrie.",
    "A monthly bottle transect along the coast from Sulina to Constanta (stations 1, 5 and 20 km from shore), with "
    "chlorophyll extraction and suspended matter.":
        "Un transect lunar de probe de apă de-a lungul coastei, de la Sulina la Constanța (stații la 1, 5 și 20 km de "
        "țărm), cu extracția clorofilei și materii în suspensie.",
    "Ask NIMRD for their monitoring data after 2021 (question 1); then monthly bottles at Constanta, Mamaia and "
    "Eforie.":
        "Cere de la INCDM datele de monitorizare de după 2021 (întrebarea 1); apoi probe de apă lunare la Constanța, "
        "Mamaia și Eforie.",
    "Clean or replace the conductivity cell at EUXRoOB01-03; take a bottle salinity sample at each service visit to "
    "check the sensor.":
        "Curăță sau înlocuiește celula de conductivitate la EUXRoOB01-03; prelevă o probă de apă pentru salinitate la "
        "fiecare vizită de service, pentru verificarea senzorului.",
    "No new sensor: maintain EUXRoOB01-03 so the record reaches the 8 complete years a trend needs; EUXRoOB02 data "
    "stop at the end of July 2026, check its status.":
        "Niciun senzor nou: întreține EUXRoOB01-03 ca seria să ajungă la cei 8 ani compleți necesari pentru o tendință; "
        "datele EUXRoOB02 se opresc la sfârșitul lui iulie 2026, verifică-i starea.",
    "No new measurement needed: keep the existing buoys as the independent check of the satellite.":
        "Nu e nevoie de nicio măsurătoare nouă: păstrează geamandurile existente ca verificare independentă a "
        "satelitului.",
    # why
    "The buoys read 2 to 3 times more chlorophyll than the satellite and the model, so offshore algae levels cannot be "
    "checked against any trusted measurement.":
        "Geamandurile indică de 2-3 ori mai multă clorofilă decât satelitul și modelul, așa că nivelul algelor din larg "
        "nu poate fi verificat cu nicio măsurătoare de încredere.",
    "At the coast the model reads about 1.5 mg/L less oxygen than the water samples, and the new coastal buoys are not "
    "yet trusted, so coastal oxygen has no reliable check.":
        "La coastă modelul indică cu aproximativ 1,5 mg/L mai puțin oxigen decât probele de apă, iar noile geamanduri "
        "costiere nu sunt încă de încredere, așa că oxigenul de la coastă nu are nicio verificare sigură.",
    "Oxygen near the seabed is where fish and mussels can suffocate, and no sensor measures it near the coast: the "
    "dashboard relies on models that disagree with each other.":
        "Lângă fundul mării peștii și midiile se pot sufoca, iar acolo, lângă coastă, niciun senzor nu măsoară "
        "oxigenul: aplicația se bazează pe modele care nu concordă între ele.",
    "Near the coast river sediment can make the satellite overstate chlorophyll, and only 3 water samples exist to "
    "check it.":
        "Lângă coastă, sedimentele aduse de fluviu pot face satelitul să supraestimeze clorofila și există doar 3 probe "
        "de apă pentru verificare.",
    "The model cannot be used for nutrient levels and the water samples we have end years ago, so the nutrient status "
    "today is unknown.":
        "Modelul nu poate fi folosit pentru nivelurile de nutrienți, iar probele de apă pe care le avem s-au oprit acum "
        "câțiva ani, așa că starea actuală a nutrienților este necunoscută.",
    "The buoy salinity drops for weeks to months in a way that looks like a dirty sensor, so offshore salinity comes "
    "from the model only.":
        "Salinitatea de la geamanduri scade timp de săptămâni sau luni într-un fel care arată ca un senzor murdar, așa "
        "că salinitatea din larg vine doar din model.",
    "The buoys are the only offshore oxygen measurement, the model misses day-to-day changes, and the record is still "
    "too short to show a trend.":
        "Geamandurile sunt singura măsurătoare de oxigen din larg, modelul ratează variațiile de la o zi la alta, iar "
        "seria este încă prea scurtă pentru a arăta o tendință.",
    "Satellite temperature is within about half a degree of the buoys and covers 44 years.":
        "Temperatura din satelit diferă cu cel mult o jumătate de grad de geamanduri și acoperă 44 de ani.",
    # who
    "GeoEcoMar (buoy operator), NIMRD laboratory": "GeoEcoMar (operatorul geamandurilor), laboratorul INCDM",
    "NIMRD, GeoEcoMar": "INCDM, GeoEcoMar",
    "NIMRD, aquaculture operators": "INCDM, operatorii de acvacultură",
    "NIMRD": "INCDM",
    "GeoEcoMar (buoy operator)": "GeoEcoMar (operatorul geamandurilor)",
    # reasons (methods.CRITERIA)
    "sources disagree": "sursele nu concordă",
    "no trusted in-situ sensor": "niciun senzor in situ de încredere",
    "sensor exists but is not trusted": "senzorul există, dar nu este de încredere",
    "gap in time": "lipsă de date în timp",
    "an official threshold depends on it": "de ea depinde un prag oficial",
    # evidence parts
    "not testable: no matched in-situ data": "netestabil: nu există date in situ împerecheate",
    "no in-situ sensor for this variable here": "aici nu există niciun senzor in situ pentru această variabilă",
    "no sensor here": "niciun senzor aici",
    "no sensor with trust good or usable reporting here":
        "aici niciun senzor cu încredere bună sau utilizabilă nu transmite date",
    "no flagged sensor": "niciun senzor marcat",
    "no in-situ time series": "nicio serie temporală in situ",
    "no official threshold": "niciun prag oficial",
    "Copernicus BGC bottom O2: model systems disagree by about 2 mg/L (docs/indicators/SHORTLIST.md section 4); no "
    "measurement to compare":
        "Copernicus BGC, O2 la fund: sistemele de modelare diferă cu aproximativ 2 mg/L (docs/indicators/SHORTLIST.md, "
        "secțiunea 4); nicio măsurătoare pentru comparație",
    # thresholds named in the evidence (marinekit.indicators.T)
    "A: RO MSFD 2024 D5C5; B, C: ours; D: Diaz & Rosenberg 2008 (OFFICIAL-RO)":
        "A: DCSMM RO 2024 D5C5; B, C: ale noastre; D: Diaz & Rosenberg 2008 (OFFICIAL-RO)",
    "May-Sep P75 chl, coastal waters (RO MSFD 2024 D5C2)": "P75 chl mai-sep., ape costiere (DCSMM RO 2024 D5C2)",
    "May-Sep mean chl, marine waters south (RO MSFD 2024)": "media chl mai-sep., ape marine, sud (DCSMM RO 2024)",
    "May-Sep P10 Secchi depth, coastal waters (RO MSFD 2024)":
        "P10 adâncime Secchi mai-sep., ape costiere (DCSMM RO 2024)",
    "RO MSFD 2024 (NIMRD), D5C5": "DCSMM RO 2024 (INCDM), D5C5",
    "DIN P75, marine waters (RO MSFD 2024)": "DIN P75, ape marine (DCSMM RO 2024)",
    "PO4 P75, marine waters (RO MSFD 2024)": "PO4 P75, ape marine (DCSMM RO 2024)",
    "DIN P75, coastal waters RO-CT (RO MSFD 2024)": "DIN P75, ape costiere RO-CT (DCSMM RO 2024)",
    "PO4 P75, coastal waters RO-CT (RO MSFD 2024)": "PO4 P75, ape costiere RO-CT (DCSMM RO 2024)",
    "Bathing Water Directive 2006/7/EC": "Directiva privind apele de îmbăiere 2006/7/CE",
})
T("Criteria, ranking and thresholds OURS; evidence from the validation and seasonal results of {d:d}; all numbers "
  "indicative",
  "Criterii, clasament și praguri OURS; dovezi din rezultatele validării și ale analizei sezoniere din {d}; toate "
  "cifrele sunt orientative")
T("disagree: {a:t} | no_trusted_insitu: {b:t} | untrusted_sensor: {c:t} | time_gap: {d:t} | decision_at_stake: {e:t}",
  "surse în dezacord: {a} | fără senzor in situ de încredere: {b} | senzor nesigur: {c} | lipsă în timp: {d} | "
  "prag oficial în joc: {e}")
T("yes ({x:t})", "da ({x})")
T("no ({x:t})", "nu ({x})")
T("{v:t} {p:t}: bias {b:t} (typical error {u:n}), R2 of anomalies {r:t} (disagree below {q:n})",
  "{v} {p}: bias {b} (eroare tipică {u}), R² al anomaliilor {r} (dezacord sub {q})")
T("{v:t} Spearman {s:t} (disagree below {q:n})", "{v}: Spearman {s} (dezacord sub {q})")
T("trusted and reporting: {l:t}", "de încredere și cu date recente: {l}")
T("flagged in datahub: {l:t}", "marcate în datahub: {l}")
for _en, _ro in (("satellite", "satelitul"), ("model", "modelul"), ("buoy", "geamandura")):
    T(_en + " passes the trend gate ({n:c} complete years, climate)",
      _ro + " trece filtrul pentru tendință ({n} ani compleți, tendință climatică)")
    T(_en + " passes the trend gate ({n:c} complete years, indicative)",
      _ro + " trece filtrul pentru tendință ({n} ani compleți, tendință orientativă)")
T("no trusted source passes the trend gate here; longest buoy record 0 complete year(s), a trend needs {m:c} (OURS)",
  "aici nicio sursă de încredere nu trece filtrul pentru tendință; nicio geamandură nu are un an complet de date, "
  "iar o tendință are nevoie de {m} ani (OURS)")
T("no trusted source passes the trend gate here; longest buoy record 1 complete year(s), a trend needs {m:c} (OURS)",
  "aici nicio sursă de încredere nu trece filtrul pentru tendință; cea mai lungă serie de la o geamandură are un "
  "singur an complet, iar o tendință are nevoie de {m} ani (OURS)")
T("no trusted source passes the trend gate here; longest buoy record {n:c} complete year(s), a trend needs {m:c} "
  "(OURS)",
  "aici nicio sursă de încredere nu trece filtrul pentru tendință; cea mai lungă serie de la o geamandură are {n} ani "
  "compleți, iar o tendință are nevoie de {m} ani (OURS)")
T("in-situ record ended {d:d} ({n:c} sample days)", "seria in situ s-a încheiat la {d} ({n} zile cu probe)")
T("{x:t} (OFFICIAL-RO)", "{x} (OFFICIAL-RO)")
T("{x:t} (OFFICIAL-EU)", "{x} (OFFICIAL-EU)")
# "EUXRoOB01 chl: indicative: <reason>" (datahub notes) and "EUXRoOB01 sst: good" (evidence lists)
T("EUXRo{p:k} {v:t}: {t:t}: {w:t}", "EUXRo{p} {v}: {t}: {w}")
T("EUXRo{p:k} {v:t}: {t:t}", "EUXRo{p} {v}: {t}")

# =================================================================================================== datahub
_ee({
    # VARIABLE_TRUST reasons
    "buoy chlorophyll is fluorescence, not calibrated against bottles: reads 2-3x satellite and model at EUXRoOB01-03 "
    "(2024-2026), R2 0.00 against satellite at EUXRo03 (2013-2023); comparison only":
        "clorofila de la geamandură este fluorescență, necalibrată cu probe de apă: indică de 2-3 ori mai mult decât "
        "satelitul și modelul la EUXRoOB01-03 (2024-2026), R² 0,00 față de satelit la EUXRo03 (2013-2023); doar pentru "
        "comparație",
    "buoy salinity shows fouling-like drops to 13-15 PSU lasting weeks to months (R2 0.00-0.17 against the model); not "
    "used, the model is the salinity source":
        "salinitatea de la geamandură are scăderi tipice colmatării, până la 13-15 PSU, care durează săptămâni sau luni "
        "(R² 0,00-0,17 față de model); nefolosită, sursa pentru salinitate este modelul",
    # PLATFORMS notes
    "new coastal buoy: O2 units unclear, O2 saturation and salinity implausible (under QC)":
        "geamandură costieră nouă: unitățile pentru O2 sunt neclare, saturația O2 și salinitatea sunt neplauzibile "
        "(în verificare QC)",
    "new coastal buoy: O2 saturation ~3.6 %, salinity ~7.5 (sensor fault, under QC)":
        "geamandură costieră nouă: saturația O2 ~3,6 %, salinitatea ~7,5 (defect de senzor, în verificare QC)",
    "new coastal buoy, not quality-controlled": "geamandură costieră nouă, fără control al calității",
    "NIMH shore station: ~3.5 C colder than open water; air and harbour context only":
        "stație de țărm ANM: cu ~3,5 °C mai rece decât apa din larg; doar context pentru aer și port",
    # PLATFORMS kinds
    "offshore buoy": "geamandură din larg", "offshore buoy (2013-2023)": "geamandură din larg (2013-2023)",
    "shore station": "stație de țărm",
    # SOURCES labels
    "Satellite SST L4 (CMEMS REP + NRT, NRT offset removed)":
        "SST din satelit L4 (CMEMS REP + NRT, decalajul NRT eliminat)",
    "Copernicus Black Sea physics model, top level": "Modelul fizic Copernicus pentru Marea Neagră, nivelul de suprafață",
    "Copernicus Black Sea physics model, bottom level": "Modelul fizic Copernicus pentru Marea Neagră, nivelul de la fund",
    "Copernicus Black Sea physics model, mixed-layer depth":
        "Modelul fizic Copernicus pentru Marea Neagră, adâncimea stratului de amestec",
    "Nearest offshore buoy": "Cea mai apropiată geamandură din larg",
    "NIMH shore station 15480 (Constanta)": "Stația de țărm ANM 15480 (Constanța)",
    "Nearest coastal buoy EUXRoCB0x": "Cea mai apropiată geamandură costieră EUXRoCB0x",
    "Satellite chl-a L4 gap-free 1 km (CMEMS multi-year + NRT)":
        "Clorofilă-a din satelit L4 fără goluri, 1 km (CMEMS multianual + NRT)",
    "Copernicus Black Sea BGC model, surface chl":
        "Modelul biogeochimic Copernicus pentru Marea Neagră (BGC), clorofilă la suprafață",
    "Nearest offshore buoy (fluorescence)": "Cea mai apropiată geamandură din larg (fluorescență)",
    "Satellite Kd490 (CMEMS ocean colour, multi-year + NRT)": "Kd490 din satelit (culoarea oceanului CMEMS, multianual + NRT)",
    "Copernicus Black Sea BGC model, surface O2":
        "Modelul biogeochimic Copernicus pentru Marea Neagră (BGC), O2 la suprafață",
    "Nearest offshore buoy (OSAT)": "Cea mai apropiată geamandură din larg (OSAT)",
    "Model O2 / O2 solubility (Garcia & Gordon 1992) at model T, S":
        "O2 din model / solubilitatea O2 (Garcia & Gordon 1992) la T și S din model",
    "Copernicus Black Sea BGC model, bottom O2": "Modelul biogeochimic Copernicus pentru Marea Neagră (BGC), O2 la fund",
    "Copernicus Black Sea BGC model, surface pH": "Modelul biogeochimic Copernicus pentru Marea Neagră (BGC), pH la suprafață",
    "EMODnet Chemistry bottle samples 0-5 m within 30 km": "Probe de apă EMODnet Chemistry, 0-5 m, pe o rază de 30 km",
    "Copernicus BGC model nitrate (NOT usable as absolute values)":
        "Nitrați din modelul Copernicus BGC (NU se folosesc ca valori absolute)",
    "Copernicus BGC model phosphate (NOT usable as absolute values)":
        "Fosfați din modelul Copernicus BGC (NU se folosesc ca valori absolute)",
    "Copernicus Black Sea wave model, daily max Hs": "Modelul de valuri Copernicus pentru Marea Neagră, Hs maxim zilnic",
    "Open-Meteo marine (MFWAM/ECMWF-WAM), daily max Hs": "Open-Meteo marine (MFWAM/ECMWF-WAM), Hs maxim zilnic",
    "ERA5 via Open-Meteo (forecast after today)": "ERA5 prin Open-Meteo (prognoză după ziua de azi)",
    "Danube discharge at the delta apex, GloFAS v4 (Open-Meteo Flood API)":
        "Debitul Dunării la vârful deltei, GloFAS v4 (Open-Meteo Flood API)",
    # notes in attrs
    "saturation = O2 / O2sat(T, S), Garcia & Gordon (1992); checked against buoy OSAT, r 0.98":
        "saturație = O2 / O2sat(T, S), Garcia & Gordon (1992); verificată cu OSAT de la geamandură, r 0,98",
    "no bottom sensor exists; forecast and reanalysis systems differ by about 2 mg/L":
        "nu există niciun senzor la fund; sistemele de prognoză și de reanaliză diferă cu aproximativ 2 mg/L",
    "model sampled at the buoy position": "modelul este eșantionat în poziția geamandurii",
    "fewer than 3 common days": "mai puțin de 3 zile comune",
    "mean = geometric mean; std = standard deviation of log10(chl)":
        "media = medie geometrică; std = abaterea standard a log10(chl)",
    "mean = geometric mean; std = standard deviation of log10(Kd490)":
        "media = medie geometrică; std = abaterea standard a log10(Kd490)",
    "moving 6-year windows; time = window centre": "ferestre mobile de 6 ani; timp = centrul ferestrei",
    "std is in log10 units when log10_stats=True; mean is then the geometric mean":
        "std este în unități log10 când log10_stats=True; media este atunci media geometrică",
    "GloFAS v4 via Open-Meteo Flood API, Danube at Ceatal Izmail":
        "GloFAS v4 prin Open-Meteo Flood API, Dunărea la Ceatal Izmail",
    "Open-Meteo marine, hourly Hs": "Open-Meteo marine, Hs orar",
    "GeoEcoMar ERDDAP (live, salinity from conductivity)": "GeoEcoMar ERDDAP (în timp real, salinitate din conductivitate)",
    "Copernicus In Situ TAC": "Copernicus In Situ TAC",
    # emodnet_insitu notes
    "no data in requested window": "nicio dată în intervalul cerut",
    "chl is in-situ fluorescence (FLU2), not HPLC/extracted chlorophyll":
        "chl este fluorescență in situ (FLU2), nu clorofilă HPLC/extrasă",
    # in-situ trust notes of the viewer register (map tooltips, Methods platform table)
    "Coastal buoy, new (Sep 2026): under QC. O2 units unclear, salinity 7.5.":
        "Geamandură costieră nouă (sep. 2026): în verificare QC. Unitățile pentru O2 sunt neclare, salinitatea 7,5.",
    "Coastal buoy, new (Sep 2026): under QC. O2 units unclear, O2 saturation 3.6 %.":
        "Geamandură costieră nouă (sep. 2026): în verificare QC. Unitățile pentru O2 sunt neclare, saturația O2 3,6 %.",
    "Coastal buoy, new (Sep 2026): under QC.": "Geamandură costieră nouă (sep. 2026): în verificare QC.",
    "Coastal buoy wave sensor, new (Sep 2026): under QC.":
        "Senzor de valuri pe o geamandură costieră nouă (sep. 2026): în verificare QC.",
    "Shore station (Constanța): about 3.5 °C colder than open water. Air and harbour context only.":
        "Stație de țărm (Constanța): cu aproximativ 3,5 °C mai rece decât apa din larg. Doar context pentru aer și port.",
    "Shore station (Sulina): air and harbour context only.": "Stație de țărm (Sulina): doar context pentru aer și port.",
    "Shore station (Mangalia): air and harbour context only.":
        "Stație de țărm (Mangalia): doar context pentru aer și port.",
    "Shore station (Gura Portiței): air and harbour context only.":
        "Stație de țărm (Gura Portiței): doar context pentru aer și port.",
    "Offshore buoy, checked against the formula for O2 saturation (r 0.98).":
        "Geamandură din larg, verificată cu formula saturației O2 (r 0,98).",
    "Not yet assessed by the team.": "Încă neevaluată de echipă.",
    # EMODnet platform types and names
    "Mooring": "Ancorare", "Tide Gauge": "Maregraf", "Gliders": "Glidere", "Drifting Buoys": "Geamanduri derivante",
    "Thermistor Chain Data": "Lanț de termistori", "Drifting Buoy": "Geamandură derivantă",
})
T("NRT values lowered by {x:n} °C (NRT minus REP offset over their overlap)",
  "valorile NRT coborâte cu {x} °C (decalajul NRT minus REP pe perioada comună)")
T("NRT chl unavailable: {e:k}", "chl NRT indisponibilă: {e}")
T("NRT Kd490 unavailable: {e:k}", "Kd490 NRT indisponibil: {e}")
T("last bottle sample with {c:t} near this point: {d:d}", "ultima probă de apă cu {c} lângă acest punct: {d}")
T("last bottle sample with {c:t} near this point: None", "ultima probă de apă cu {c} lângă acest punct: niciuna")
T("fell back after: {e:k}", "s-a folosit sursa următoare după: {e}")
T("buoy EUXRo{p:k} is {d:n} km from the point", "geamandura EUXRo{p} este la {d} km de punct")
T("observation trust is {t:t} for {v:t} (VARIABLE_TRUST): read the statistics as a sensor check",
  "încrederea în observație este „{t}” pentru {v} (VARIABLE_TRUST): citește statisticile ca o verificare a senzorului")
for _p in ("EUXRoOB01", "EUXRoOB02", "EUXRoOB03", "EUXRo02", "EUXRo03"):
    E("buoy " + _p, "geamandura " + _p)
for _p in ("EUXRoCB01", "EUXRoCB02", "EUXRoCB03"):
    E("coastal buoy " + _p, "geamandura costieră " + _p)
T("EUXRo{p:k} (GeoEcoMar ERDDAP (live, salinity from conductivity))",
  "EUXRo{p} (GeoEcoMar ERDDAP (în timp real, salinitate din conductivitate))")
T("{p:k} (Copernicus In Situ TAC)", "{p} (Copernicus In Situ TAC)")
T("{c:k}: median {x:n} << 100 so treated as mg/L despite units '{u:k}'",
  "{c}: mediana {x} << 100, deci tratată ca mg/L în ciuda unităților „{u}”")

# =================================================================================================== pressure zones
_ee({
    # activity values
    "anchorage": "ancoraj", "port_area": "zonă portuară", "offshore_platform": "platformă offshore",
    "pipeline_cable": "conductă / cablu submarin", "aquaculture_lease": "concesiune de acvacultură",
    "fishing_ground": "zonă de pescuit", "landing_point": "punct de debarcare", "shipping_lane": "culoar de navigație",
    "beach_nourishment": "înnisipare artificială a plajei", "coastal_protection": "protecție costieră",
    "dredging_activity": "dragare", "shipyard": "șantier naval", "bathing_water": "apă de îmbăiere", "beach": "plajă",
    "marina": "port de agrement", "aquaculture_planned": "acvacultură planificată",
    "offshore_wind_planned": "parc eolian offshore planificat", "fishing_restriction": "restricție de pescuit",
    "no_fishing_area": "zonă cu pescuit interzis", "pound_net_zone": "zonă de taliene",
    # buffer basis, season
    "rule": "regulă", "law": "lege", "literature": "literatură",
    "all": "tot anul", "summer": "vara", "winter": "iarna",
    # buffer_label()
    "AIS density cells, no buffer": "celule de densitate AIS, fără zonă tampon",
    "AIS fishing density cells, no buffer": "celule de densitate AIS a pescuitului, fără zonă tampon",
    "AIS dredging density cells, no buffer": "celule de densitate AIS a dragărilor, fără zonă tampon",
    "mapped footprint, no buffer": "amprenta cartografiată, fără zonă tampon",
    "buffer not set": "zonă tampon nestabilită",
    # sector_zones basis_ref
    "anchor and chain swing radius: chain about 5-7 x water depth (20-30 m) plus ship length":
        "raza de rotire a ancorei și a lanțului: lanțul are de aproximativ 5-7 ori adâncimea apei (20-30 m), plus "
        "lungimea navei",
    "1 km around basins and terminals: berths, entrance channel, propeller wash and maintenance dredging (harbour "
    "turbidity and sediment-contamination near field)":
        "1 km în jurul bazinelor și terminalelor: dane, canalul de acces, curentul elicelor și dragajele de întreținere "
        "(turbiditate portuară și contaminarea sedimentelor în imediata apropiere)",
    "Law 17/1990 art. 16(2): safety zones 'up to 500 m from each point of their outer limits' around installations in "
    "the Romanian EEZ; UNCLOS art. 60(5)":
        "Legea 17/1990, art. 16(2): zone de siguranță „de până la 500 m de la fiecare punct al limitelor lor "
        "exterioare” în jurul instalațiilor din ZEE a României; UNCLOS art. 60(5)",
    "Law 17/1990 (republished MO 252/2014) art. 12(2): safety and protection zones 'up to 1,000 m on either side' of "
    "the axis of cables and pipelines laid in the sea":
        "Legea 17/1990 (republicată, MO 252/2014), art. 12(2): zone de siguranță și protecție „de până la 1.000 m de o "
        "parte și de alta” a axei cablurilor și conductelor pozate în mare",
    "benthic effects of shellfish longlines and fish cages are mostly within 50-100 m of the farm edge (Wilding and "
    "Nickell 2013, PLoS ONE 8:e68313; Kalantzi and Karakassis 2006, Mar Pollut Bull 52:484)":
        "efectele bentice ale long-line-urilor pentru moluște și ale cuștilor pentru pești apar mai ales în primii "
        "50-100 m de la marginea fermei (Wilding și Nickell 2013, PLoS ONE 8:e68313; Kalantzi și Karakassis 2006, "
        "Mar Pollut Bull 52:484)",
    "the AIS cells themselves (top decile of EMSA fishing-vessel density)":
        "chiar celulele AIS (decila superioară a densității navelor de pescuit, EMSA)",
    "1 km around the landing point: boats launching and landing, nets set nearby":
        "1 km în jurul punctului de debarcare: lansarea și acostarea bărcilor, plase întinse în apropiere",
    "the AIS cells themselves (top decile of EMSA vessel density, ~1.2 km cells)":
        "chiar celulele AIS (decila superioară a densității navelor, EMSA, celule de ~1,2 km)",
    "300 m seaward of the nourished beach: placement, burial and plume":
        "300 m spre larg de plaja înnisipată: depunerea nisipului, acoperirea fundului și pana de sedimente",
    "200 m: structure footprint plus scour and accretion cell next to it":
        "200 m: amprenta construcției plus celula de eroziune și acumulare de lângă ea",
    "the AIS cells themselves (top 5% of EMSA dredging / underwater-ops density)":
        "chiar celulele AIS (primele 5% după densitatea dragărilor / operațiunilor subacvatice, EMSA)",
    "500 m: dry-dock discharge, blasting grit and antifouling residues near the yard":
        "500 m: evacuări din docul uscat, abraziv de sablare și reziduuri de vopsea antivegetativă lângă șantier",
    "OMT 1079/2014 Annex 2: nautical recreation zones 'may not extend more than 300 m from the shore'; user rule: "
    "300 m seaward from the beach line; applied to 500 m of coastline at each EEA bathing-water site":
        "OMT 1079/2014, anexa 2: zonele de agrement nautic „nu se pot extinde la mai mult de 300 m de țărm”; regula "
        "utilizatorului: 300 m spre larg de linia plajei; aplicată pe 500 m de țărm la fiecare sit EEA de apă de "
        "îmbăiere",
    "OMT 1079/2014 Annex 2: nautical recreation zones 'may not extend more than 300 m from the shore'; user rule: "
    "300 m seaward from the beach line":
        "OMT 1079/2014, anexa 2: zonele de agrement nautic „nu se pot extinde la mai mult de 300 m de țărm”; regula "
        "utilizatorului: 300 m spre larg de linia plajei",
    "300 m, same as the nautical recreation zone: leisure craft leaving the marina":
        "300 m, ca zona de agrement nautic: ambarcațiunile de agrement care ies din port",
    # sector_sites.json "why" parts
    "port area": "zonă portuară", "bathing water": "apă de îmbăiere", "landing point": "punct de debarcare",
    "offshore platform": "platformă offshore", "aquaculture lease": "concesiune de acvacultură",
    # feature names that are English descriptions
    "2 Mai - Vama Veche marine reserve, zone B (no fishing all year)":
        "Rezervația marină 2 Mai - Vama Veche, zona B (pescuit interzis tot anul)",
    "Ana platform (Midia Gas Development)": "Platforma Ana (Midia Gas Development)",
    "Central Platform Complex PFCP + PFS-1 + PFS-2 (manned)":
        "Complexul central de platforme PFCP + PFS-1 + PFS-2 (cu personal)",
    "Central Platform Complex PFCP + PFS-1 + PFS-2 (m": "Complexul central de platforme PFCP + PFS-1 + PFS-2",
    "Constanta roadstead anchorage (zones 1-3)": "Ancorajul din rada Constanța (zonele 1-3)",
    "Corbu (beach)": "Corbu (plajă)",
    "Delta marine zone Zatonul Mare - Periteasca: gillnets banned 9 Apr - 30 Nov (shore to 20 m isobath)":
        "Zona marină a Deltei Zatonul Mare - Periteasca: setcile interzise între 9 apr. și 30 nov. (de la țărm până la "
        "izobata de 20 m)",
    "Dredging and underwater operations (AIS)": "Dragare și operațiuni subacvatice (AIS)",
    "Dry dock no. 1": "Docul uscat nr. 1", "Dry dock no. 2": "Docul uscat nr. 2",
    "Floating Dock no. 1": "Docul plutitor nr. 1", "Floating Dock no. 2": "Docul plutitor nr. 2",
    "Edighiol (Sinoe outlet)": "Edighiol (gura Sinoe)",
    "Fishing grounds (AIS fishing-vessel density)": "Zone de pescuit (densitatea navelor de pescuit din AIS)",
    "KAFOS submarine cable (landing Mangalia)": "Cablul submarin KAFOS (ajunge la țărm la Mangalia)",
    "Mamaia Sat (canal dyke)": "Mamaia Sat (digul canalului)",
    "Midia (Navodari south dyke: Dig Teu, Bujor)": "Midia (digul de sud Năvodari: Dig Teu, Bujor)",
    "Midia anchorage": "Ancoraj Midia",
    "Neptun Alpha production platform (Neptun Deep)": "Platforma de producție Neptun Alpha (Neptun Deep)",
    "Neptun Deep 30-inch gas pipeline and fibre cable, Tuzla landfall to Neptun Alpha":
        "Conducta de gaze de 30 de țoli și cablul de fibră optică Neptun Deep, de la Tuzla (punctul de ajungere la "
        "țărm) până la Neptun Alpha",
    "Pelican South drill centre PSDC1 (Neptun Deep)": "Centrul de foraj Pelican Sud PSDC1 (Neptun Deep)",
    "Potential pound-net (taliene) zone, 5-13 m depth": "Zonă potențială de taliene, 5-13 m adâncime",
    "Quay C": "Cheiul C",
    "Sahalin - Sfantu Gheorghe: all marine fishing banned all year (40-50 m isobaths)":
        "Sahalin - Sfântu Gheorghe: orice pescuit marin interzis tot anul (izobatele de 40-50 m)",
    "Shipping lanes and anchorage traffic (AIS, all ships except dredgers)":
        "Culoare de navigație și trafic de ancoraj (AIS, toate navele, fără drăgi)",
    "breakwater": "dig de protecție", "harbour basin": "bazin portuar",
    # feature sources
    "ACROPO (Romanian offshore oil and gas authority) annual report to the EU, installation list 2020":
        "ACROPO (autoritatea română pentru operațiunile petroliere offshore), raportul anual către UE, lista "
        "instalațiilor 2020",
    "ANAR / ABA Dobrogea-Litoral marine aquaculture perimeters (plan de situatie), awarded 2024 (20-year lease); award "
    "notices rowater.ro 2024/10 and 2024/12":
        "ANAR / ABA Dobrogea-Litoral, perimetre marine de acvacultură (plan de situație), atribuite în 2024 "
        "(concesiune pe 20 de ani); anunțuri de atribuire rowater.ro 2024/10 și 2024/12",
    "ANAR / ABA Dobrogea-Litoral marine perimeters, 2024 tender, not awarded":
        "ANAR / ABA Dobrogea-Litoral, perimetre marine, licitația din 2024, neatribuite",
    "ANAR mollusc tender November 2025 (Stereo 70 converted; no award found)":
        "ANAR, licitația pentru moluște din noiembrie 2025 (coordonate convertite din Stereo 70; nicio atribuire "
        "găsită)",
    "APM Constanta environmental permit Neptun Deep (see Neptun Alpha)":
        "APM Constanța, autorizația de mediu Neptun Deep (vezi Neptun Alpha)",
    "EMODnet Human Activities, EMSA AIS vessel density emodnet__vesseldensity_01avg, mean 2023+2024, top decile of "
    "cells with traffic (>= 0.088 h/km2/month) (CC BY 4.0 (EMODnet data policy))":
        "EMODnet Human Activities, densitatea navelor EMSA AIS emodnet__vesseldensity_01avg, media 2023+2024, decila "
        "superioară a celulelor cu trafic (>= 0,088 h/km2/lună) (CC BY 4.0 (politica de date EMODnet))",
    "EMODnet Human Activities, EMSA AIS vessel density emodnet__vesseldensity_03avg, mean 2023+2024, top 5% of cells "
    "with traffic (>= 0.0883 h/km2/month) (CC BY 4.0 (EMODnet data policy))":
        "EMODnet Human Activities, densitatea navelor EMSA AIS emodnet__vesseldensity_03avg, media 2023+2024, primele "
        "5% dintre celulele cu trafic (>= 0,0883 h/km2/lună) (CC BY 4.0 (politica de date EMODnet))",
    "EMODnet Human Activities, EMSA AIS vessel density emodnet__vesseldensity_allavg, mean 2023+2024, top decile of "
    "cells with traffic (>= 3.02 h/km2/month) (CC BY 4.0 (EMODnet data policy))":
        "EMODnet Human Activities, densitatea navelor EMSA AIS emodnet__vesseldensity_allavg, media 2023+2024, decila "
        "superioară a celulelor cu trafic (>= 3,02 h/km2/lună) (CC BY 4.0 (politica de date EMODnet))",
    "EMODnet Human Activities: EMSA AIS vessel density (cargo vesseldensity_09avg + tanker _10avg) and route density "
    "(cargo routedensity_01avg + tanker _04avg), mean 2023+2024 (CC BY 4.0 (EMODnet data policy))":
        "EMODnet Human Activities: densitatea navelor EMSA AIS (cargouri vesseldensity_09avg + tancuri _10avg) și "
        "densitatea rutelor (cargouri routedensity_01avg + tancuri _04avg), media 2023+2024 (CC BY 4.0 (politica de "
        "date EMODnet))",
    "Ministry of Environment, list of offshore wind perimeters that may be concessioned (Law 121/2024), annex 2, July "
    "2026":
        "Ministerul Mediului, lista perimetrelor eoliene offshore care pot fi concesionate (Legea 121/2024), anexa 2, "
        "iulie 2026",
    "Ordin MADR/MMAP 23/297/2025 art. 4 lit. r": "Ordinul MADR/MMAP 23/297/2025, art. 4 lit. r",
    "Ordin MADR/MMAP 23/297/2025 art. 4 lit. s": "Ordinul MADR/MMAP 23/297/2025, art. 4 lit. s",
    "TeleGeography Submarine Cable Map (CC BY-NC-SA): schematic route, city-level landing point":
        "TeleGeography Submarine Cable Map (CC BY-NC-SA): traseu schematic, punct de ajungere la țărm la nivel de oraș",
    "Totoiu et al. 2016, Turk J Fish Aquat Sci 16:371 (21 pound nets in 2014 on the 5-13 m isobaths); Ordin 388/2016 "
    "(submersible pound nets at 3-14 m); EMODnet Bathymetry DTM":
        "Totoiu et al. 2016, Turk J Fish Aquat Sci 16:371 (21 de taliene în 2014, pe izobatele de 5-13 m); Ordinul "
        "388/2016 (taliene submersibile la 3-14 m); EMODnet Bathymetry DTM",
})
T("{d:i} m (rule)", "{d} m (regulă)")
T("{d:i} m (law)", "{d} m (lege)")
T("{d:i} m (literature)", "{d} m (literatură)")
# sector_sites.json "why"
T("{a:t} ({c:t}), 1 sectors overlap", "{a} (încredere: {c}), un singur sector")
T("{a:t} ({c:t}), {n:i} sectors overlap", "{a} (încredere: {c}), {n} sectoare se suprapun")
for _c in ("official", "mapped", "assumed"):
    T("{a:t} (" + _c + ")", "{a} (încredere: {c})".replace("{c}", {"official": "oficial", "mapped": "cartografiat",
                                                                 "assumed": "presupus"}[_c]))
# feature names (templates)
T("Aquaculture perimeter {p:k} (offered, not awarded)", "Perimetru de acvacultură {p} (oferit, neatribuit)")
T("Aquaculture perimeter {p:k} ({c:k}", "Perimetru de acvacultură {p} ({c}")
T("Beach nourishment lot {p:k}", "Lot de înnisipare a plajei {p}")
T("Offshore wind perimeter {z:k} (phase {n:i}) (planned)", "Perimetru eolian offshore {z} (faza {n}) (planificat)")
T("{p:s} (EMODnet port location)", "{p} (localizarea portului în EMODnet)")
T("{p:s} anchorage, {d:i} km {c:k} (AIS-derived)", "Ancoraj {p}, {d} km {c} (derivat din AIS)")
T("{p:s} waiting area, {d:i} km {c:k} (AIS-derived)", "Zonă de așteptare {p}, {d} km {c} (derivată din AIS)")
# feature sources (templates)
T("OpenStreetMap {k:k} (ODbL)", "OpenStreetMap {k} (ODbL)")
T("EEA bathing water {i:k} via EMODnet Human Activities bathingwaters, {y:i}, class 1 - Excellent",
  "Apă de îmbăiere EEA {i} prin EMODnet Human Activities (bathingwaters), {y}, clasa 1 - Excelentă")
T("EEA bathing water {i:k} via EMODnet Human Activities bathingwaters, {y:i}, class 2 - Good",
  "Apă de îmbăiere EEA {i} prin EMODnet Human Activities (bathingwaters), {y}, clasa 2 - Bună")
T("EEA bathing water {i:k} via EMODnet Human Activities bathingwaters, {y:i}, class 3 - Sufficient",
  "Apă de îmbăiere EEA {i} prin EMODnet Human Activities (bathingwaters), {y}, clasa 3 - Suficientă")
T("EEA bathing water {i:k} via EMODnet Human Activities bathingwaters, {y:i}, class 4 - Poor",
  "Apă de îmbăiere EEA {i} prin EMODnet Human Activities (bathingwaters), {y}, clasa 4 - Slabă")
T("EMODnet Human Activities portlocations {c:k} (CC BY 4.0 (EMODnet data policy))",
  "EMODnet Human Activities portlocations {c} (CC BY 4.0 (politica de date EMODnet))")
T("APM Constanta environmental permit Neptun Deep, authorised EN translation, {u:k}",
  "APM Constanța, autorizația de mediu Neptun Deep, traducere autorizată în engleză, {u}")
T("JICA port study citing the Constantza Port Handbook, {u:k}",
  "Studiu portuar JICA care citează Constantza Port Handbook, {u}")
T("Ordin MADR 5/15.01.2026 annex 3 (landing points and first-sale centres, MO 32/16.01.2026), {u:k}",
  "Ordinul MADR 5/15.01.2026, anexa 3 (puncte de debarcare și centre de primă vânzare, MO 32/16.01.2026), {u}")
T("Ordin MADR/MMAP 10/235/2023 art. 3, {u:k}", "Ordinul MADR/MMAP 10/235/2023, art. 3, {u}")
T("Romanian Waters 'Reduction of coastal erosion' Phase I (2013-2015) and Phase II lots, {u:k}",
  "Apele Române, proiectul „Reducerea eroziunii costiere”, loturile din Faza I (2013-2015) și Faza a II-a, {u}")
T("https://{u:k}", "https://{u}")

# proper names of features and sector sites: kept as they are
_keep([
    "2 Mai", "23 August", "Agigea (cherhana)", "Bazinul Mare", "Bazinul de Nord", "Bazinul de Sud",
    "Cap Aurora I Hotel Opal", "Cap Aurora Iii Restaurant Pescaresc", "Cap Aurura Ii Hotel Onix", "Cap Midia",
    "Cochilia", "Constanta", "Constanta I Delfinariu", "Constanta Ii Modern", "Cordon Eforie N Eforie S I Azur",
    "Cordon Eforie N Eforie S Ii Tabara Luminita", "Cordon Venus Saturn I Bufet Adriana", "Cordon Venus Saturn Ii Actetis",
    "Costinesti I Pescarie", "Costinesti Ii Forum", "Crush Beach", "Damen Shipyards Mangalia", "Dana Pasageri",
    "Dana Tehnică", "Delfin Navodari I Tabara Delfin", "Dig protectie", "Digul Capul Turcului (ESN2)",
    "Digul Cravata Roșie (ECN1)", "Digul Luminița (ECN2)", "Digul Movilă (ESN3)", "Digul Pescărie (ESN1)",
    "Digul Van Oord (ESN 4)", "Digul Vraja Mării (ECN3)", "Digul de Larg", 'Doc uscat "Sorena"', "Doi Mai",
    "Eforie Nord (Belona)", "Eforie Nord I Debarcader", "Eforie Nord Ii Belona", "Eforie Sud (dig nou)",
    "Eforie Sud I Splendid Beach", "Eforie Sud Ii Cazino", "GSP Logistics", "Gsp Shipyard Agigea",
    "Habibi Beach Mamaia", "Jupiter 1 Braseria Delfinul", "Jupiter 2 Complex Cometa", "Jupiter 3 Hotel Capitol",
    "Jupiter 4 Hotel California", "La Nudiști", "LifeHarbour", "Mamaia (bd. Mamaia 306/312D)",
    "Mamaia Viii Aurora", "Mangalia", "Mangalia (pescarie, pod mobil)", "Marina Eforie", "Midia",
    "Neptun I Terasa Briza", "Neptun Ii Neptun", "Olimp", "Olimp I Pescarie", "Olimp Ii Zona 1 Piscina Oltenia",
    "Olimp Ii Zona 2 Zona Protocol", "PFSS-8", "PFSS-U / Pescarus", "PGSU-3", "PGSU-4", "PGSU-6", "PGSU-7",
    "Periboina / Gura Portitei", "Pescărie", "Plaja 2 Mai", "Plaja 23 August", "Plaja Agigea Nord", "Plaja Agigea Sud",
    "Plaja Capul Midia", "Plaja Chituc", "Plaja Corbu", "Plaja Corsa", "Plaja Costinești", "Plaja Cupidon",
    "Plaja Delta", "Plaja Diana", "Plaja Edighiol", "Plaja Eforie", "Plaja Eforie Sud", "Plaja Eminescu",
    "Plaja Farul Genovez", "Plaja Golful Pescarilor", "Plaja Gura Buhazului", "Plaja Júpiter",
    "Plaja Mamaia I Zona 1 Tabara Turist", "Plaja Mamaia I Zona 2 Enigma", "Plaja Mamaia Ii Estival",
    "Plaja Mamaia Iii Vega", "Plaja Mamaia Iv Rex", "Plaja Mamaia V Castel", "Plaja Mamaia Vi Cazino",
    "Plaja Mamaia Vii Perla", "Plaja Mangalia", "Plaja Midia", "Plaja Modern", "Plaja Navodari Ii Hanul Piratilor",
    "Plaja Navodari Iii Zona I Camping Marina Surf", "Plaja Navodari Iii Zona Ii Perla Majestic",
    "Plaja Navodari Iv Zona 1 Popas Iii Mamaia", "Plaja Navodari Iv Zona 2 Camping Pescaresc", "Plaja Pricop",
    "Plaja Saturn", "Plaja Saturn - Venus", "Plaja Sfântu Gheorghe", "Plaja Sulina", "Plaja Tataia",
    "Plaja Trei Papuci", "Plaja Tuzla", "Plaja Vadu", "Plaja de Nudiști",
    "Plaja de Nudiști Golful Francez", "Plaja de Nudiști Neptun Mandala", "Plajă Nudiști",
    "Ponton RoRO", "Port turistic Mangalia", "Portul Constanța", "Portul Constanța Sud - Agigea", "Portul Midia",
    "Portul Turistic Tomis", "Sat De Vacanta Gura Portitei", "Saturn I Adras", "Saturn Ii Plaja Diana",
    "Sfantu Gheorghe", "Sulina", "Tuzla", "Vadu (cherhana)", "Vama Veche", "Vama Veche (Usa din Vama)",
    "Venus I Zona 1 Restaurant Calipso", "Venus I Zona 2 Hotel Afrodita", "Venus Ii Hotel Silvia",
    "Venus Perla Venusului", "White Beach", "Zona A (Project Cargo)", "Zoom Beach", "doc SORENA",
    "Șantierul Naval Constanța",
])
E("La Nudişti", "La Nudiști")
E("Plaja de Nudişti La Hamace", "Plaja de Nudiști La Hamace")
E("Plaja de Nudiști Costinești (neoficial, traditional)", "Plaja de Nudiști Costinești (neoficial, tradițional)")
# top_overlap_areas.csv: area names and "near" distances
for _p in ("2 Mai", "Agigea", "Cap Aurora", "Constanța", "Costinești", "Eforie Nord", "Eforie Sud", "Gura Portiței",
           "Jupiter", "Mamaia", "Mamaia-Sat", "Mangalia", "Neptun", "Năvodari", "Olimp", "Saturn", "Sfântu Gheorghe",
           "Sulina", "Venus"):
    E(f"{_p} coast", f"Coasta {_p}")
    E(f"{_p} offshore", f"Larg {_p}")
    T(_p + " ({d:n} km)", _p + " ({d} km)")

# =================================================================================================== SHORTLIST.md (Methods page)
_ee({
    # section 2 headers
    "ID": "ID", "Indicator": "Indicator", "Formula (short)": "Formulă (pe scurt)", "Data key(s)": "Chei de date",
    "Reference / threshold": "Referință / prag", "Evidence": "Dovezi", "Confidence": "Încredere",
    # evidence codes and confidence cells
    "Mod": "Mod", "S + reanalysis": "S + reanaliză", "Mod + M": "Mod + M", "Mod (no bottom sensor)":
        "Mod (fără senzor la fund)", "M + Mod": "M + Mod", "S + Mod + climatology": "S + Mod + climatologie",
    "M (to 2020 at best)": "M (cel mult până în 2020)", "M (lab)": "M (laborator)", "S + M historical": "S + M istoric",
    "S + Mod": "S + Mod", "Mod proxy": "Mod (indicator indirect)", "M (occurrences)": "M (apariții)",
    "evidence map": "hartă de dovezi",
    "medium-low": "medie spre scăzută", "high offshore": "ridicată în larg", "low-medium": "scăzută spre medie",
    "medium, historical only": "medie, doar istoric", "medium, historical": "medie, istoric",
    "high, annual": "ridicată, anual", "high offshore, medium at the coast": "ridicată în larg, medie la coastă",
    "good for presence only": "bună doar pentru prezență",
    # section 2 rows
    "SST anomaly, heatwave, cold spell": "Anomalie SST, val de căldură marin, val de frig",
    "anomaly = SST − DOY climatology mean; z = anomaly / std; heatwave = above p90 for ≥ 5 days (Hobday)":
        "anomalie = SST − media climatologică pe ziua anului (DOY); z = anomalie / std; val de căldură = peste p90 "
        "timp de ≥ 5 zile (Hobday)",
    "DOY climatology 1991–2020 (OURS, standard WMO period)":
        "climatologie pe ziua anului 1991–2020 (OURS, perioada standard OMM)",
    "Upwelling flag (Jun–Sep)": "Semnal de upwelling (iun.–sep.)",
    "coastal SST − SST 47 km offshore ≤ −2 °C and a wind-based upwelling index > 0 over 3 days":
        "SST la coastă − SST la 47 km în larg ≤ −2 °C și un indice de upwelling bazat pe vânt > 0 timp de 3 zile",
    "sst_l4_*, open_data.marine_weather wind": "sst_l4_*, open_data.marine_weather vânt",
    "summer 1991–2020 distribution (OURS)": "distribuția de vară 1991–2020 (OURS)",
    "Danube influence": "Influența Dunării",
    "discharge ratio vs 1997–2025 DOY mean; surface-salinity anomaly":
        "raportul debitului față de media pe ziua anului 1997–2025; anomalia salinității la suprafață",
    "Stratification strength": "Intensitatea stratificării",
    "Δσ surface − bottom (from T, S); MLD": "Δσ suprafață − fund (din T, S); MLD",
    "reanalysis 1993–2022 (OURS)": "reanaliză 1993–2022 (OURS)",
    "Transparency, light at seabed": "Transparență, lumină la fundul mării",
    "Secchi ≈ k / Kd490 (k calibrated); light at bottom = exp(−Kd490 × depth)":
        "Secchi ≈ k / Kd490 (k calibrat); lumina la fund = exp(−Kd490 × adâncime)",
    "Romanian Secchi GES values (OFFICIAL-RO) + DOY band (OURS)":
        "valorile Secchi de stare ecologică bună ale României (OFFICIAL-RO) + bandă pe ziua anului (OURS)",
    "Bottom-temperature anomaly": "Anomalia temperaturii la fund",
    "as P1, bias-corrected model": "ca P1, model cu bias corectat",
    "Storm / resuspension, surge": "Furtună / resuspensie, supraînălțare",
    "Hs above p95; sea-level surge": "Hs peste p95; supraînălțarea nivelului mării",
    "wav, open_data.marine_weather, tide gauge IOC-csta2, phy_ssh":
        "wav, open_data.marine_weather, maregraful IOC-csta2, phy_ssh",
    "Hs 2021–2026 percentiles (OURS)": "percentile Hs 2021–2026 (OURS)",
    "1997–2025 (OURS)": "1997–2025 (OURS)",
    "Bottom-oxygen class": "Clasa oxigenului la fund",
    "daily class A ≥ 5, B 4–5, C 2–4, D < 2 mg/L; season test May–Sep P10 ≥ 5 mg/L and ≥ 60 % saturation":
        "clasă zilnică A ≥ 5, B 4–5, C 2–4, D < 2 mg/L; test sezonier mai–sep. P10 ≥ 5 mg/L și saturație ≥ 60 %",
    "bgc_o2 (o2_bottom), rea_bgc_o2, bottles 1963–2021": "bgc_o2 (o2_bottom), rea_bgc_o2, probe de apă 1963–2021",
    "D5C5 (OFFICIAL-RO); hypoxia < 2 mg/L": "D5C5 (OFFICIAL-RO); hipoxie < 2 mg/L",
    "Surface O₂ saturation": "Saturația O₂ la suprafață",
    "%sat = O₂ / O₂sat(T, S) (Garcia & Gordon 1992); flags > 120 % bloom, < 80 % respiration or upwelling":
        "%sat = O₂ / O₂sat(T, S) (Garcia & Gordon 1992); semnale > 120 % înflorire algală, < 80 % respirație sau "
        "upwelling",
    "buoys EUXRoOB01–03 (OSAT), bgc_o2 + phy_temp + phy_sal":
        "geamandurile EUXRoOB01–03 (OSAT), bgc_o2 + phy_temp + phy_sal",
    "flags (OURS)": "semnale (OURS)",
    "Eutrophication index": "Indice de eutrofizare",
    "ratio observed / target per criterion, one-out-all-out across nutrients, chl, O₂":
        "raport observat / țintă pe fiecare criteriu, regula „unul afară, toate afară” pentru nutrienți, chl, O₂",
    "RO marine thresholds (OFFICIAL-RO)": "pragurile marine ale României (OFFICIAL-RO)",
    "Nutrient status": "Starea nutrienților",
    "value / official threshold, and value / seasonal climatology":
        "valoare / prag oficial și valoare / climatologie sezonieră",
    "DIN 10.5, PO₄ 0.23 µM marine P75 (OFFICIAL-RO)": "DIN 10,5, PO₄ 0,23 µM, P75 ape marine (OFFICIAL-RO)",
    "as C4": "ca C4",
    "Redfield (literature)": "Redfield (literatură)",
    "Bathing-water class": "Clasa apei de îmbăiere",
    "share Excellent / Good / Sufficient / Poor per year": "ponderea claselor Excelentă / Bună / Suficientă / Slabă pe an",
    "emodnet_layers.bathing_water_history() (49 sites, 2007–2024)":
        "emodnet_layers.bathing_water_history() (49 de situri, 2007–2024)",
    "EU Bathing Water Directive (OFFICIAL-EU)": "Directiva UE privind apele de îmbăiere (OFFICIAL-EU)",
    "pH watch": "Urmărirea pH-ului",
    "pH − DOY climatology; trend": "pH − climatologia pe ziua anului; tendință",
    "Chl anomaly + D5C2": "Anomalia chl + D5C2",
    "log10(chl) − DOY climatology; official D5C2 seasonal test":
        "log10(chl) − climatologia pe ziua anului; testul sezonier oficial D5C2",
    "sat_chl_l4_nrt + sat_chl_l4_my (cross-check open_data.chl_occi_8day)":
        "sat_chl_l4_nrt + sat_chl_l4_my (verificare încrucișată cu open_data.chl_occi_8day)",
    "1998–2020 (OURS) + D5C2 (OFFICIAL-RO)": "1998–2020 (OURS) + D5C2 (OFFICIAL-RO)",
    "Bloom days": "Zile cu înflorire algală",
    "days with chl above the bloom threshold per season; trend since 1998":
        "zile cu chl peste pragul de înflorire algală, pe sezon; tendință din 1998",
    "Community structure": "Structura comunității",
    "micro-size share (satellite); diatoms vs dinoflagellates (NIMRD counts, to 2015)":
        "ponderea fracției micro (satelit); diatomee vs dinoflagelate (numărători INCDM, până în 2015)",
    "Primary production anomaly": "Anomalia producției primare",
    "satellite PP vs model NPP": "PP din satelit vs NPP din model",
    "Mussel-bed hypoxia exposure": "Expunerea bancurilor de midii la hipoxie",
    "days with bottom O₂ < 2 and < 3 mg/L at *Mytilus* bed depths":
        "zile cu O₂ la fund < 2 și < 3 mg/L la adâncimile bancurilor de *Mytilus*",
    "C1 classes; 3 mg/L from literature, not official": "clasele C1; 3 mg/L din literatură, neoficial",
    "Invasive and gelatinous species": "Specii invazive și gelatinoase",
    "presence, last record, records since 2015 (shown as presence over sampling effort, never as a trend)":
        "prezență, ultima înregistrare, înregistrări din 2015 (afișate ca prezență raportată la efortul de eșantionare, "
        "niciodată ca tendință)",
    "Evidence coverage": "Acoperirea cu dovezi",
    "records per grid cell, strandings, ROV habitat labels":
        "înregistrări pe celulă de grilă, eșuări, etichete de habitat din ROV",
    # data keys kept as they are
    "sst_l4_rep + sst_l4_nrt": "sst_l4_rep + sst_l4_nrt",
    "open_data.danube_discharge, phy_sal, rea_phy_sal": "open_data.danube_discharge, phy_sal, rea_phy_sal",
    "phy_temp, phy_sal, phy_mld, rea_*": "phy_temp, phy_sal, phy_mld, rea_*",
    "sat_kd490_my, sat_kd490_nrt, emodnet_layers.depth_at": "sat_kd490_my, sat_kd490_nrt, emodnet_layers.depth_at",
    "phy_temp bottomT, rea_phy_temp": "phy_temp bottomT, rea_phy_temp",
    "sat_chl_l4_my, bgc_o2, DIVAnd DIN / PO₄": "sat_chl_l4_my, bgc_o2, DIVAnd DIN / PO₄",
    "emodnet_insitu.fetch_chemistry_samples, chemistry_climatology_at":
        "emodnet_insitu.fetch_chemistry_samples, chemistry_climatology_at",
    "DIN / PO₄ vs 16; Si / DIN vs 1": "DIN / PO₄ vs 16; Si / DIN vs 1",
    "N:P, Si:N": "N:P, Si:N",
    "bgc_car, rea_bgc_car": "bgc_car, rea_bgc_car",
    "sat_chl_l4_my": "sat_chl_l4_my",
    "sat_pft_l3_my, OBIS": "sat_pft_l3_my, OBIS",
    "sat_pp_my, bgc_* npp": "sat_pp_my, bgc_* npp",
    "rea_bgc_o2 / bgc_o2, OBIS *Mytilus*, depth_at": "rea_bgc_o2 / bgc_o2, OBIS *Mytilus*, depth_at",
    "OBIS API": "OBIS API",
    "emodnet_layers.biology_records_grid, OBIS, vision.py": "emodnet_layers.biology_records_grid, OBIS, vision.py",
    # section 4 (data quality register)
    "Source": "Sursă", "Status": "Stare", "Use": "Utilizare",
    "Offshore buoys EUXRoOB01–03, EUXRo02/03": "Geamandurile din larg EUXRoOB01–03, EUXRo02/03",
    "good for T and O₂; formula matches buoy O₂ saturation (r 0.98)":
        "bune pentru T și O₂; formula reproduce saturația O₂ măsurată de geamandură (r 0,98)",
    "measured reference for O₂ and T (chl and S: see the two rows below)":
        "referință măsurată pentru O₂ și T (pentru chl și S: vezi cele două rânduri de mai jos)",
    "Buoy chlorophyll (fluorescence) at EUXRoOB01–03, EUXRo03":
        "Clorofila de la geamandurile EUXRoOB01–03, EUXRo03 (fluorescență)",
    "indicative: OB01-03 (2024-2026) read 2-3x satellite and model (median ratio satellite / buoy 0.36-0.51, R² "
    "0.15-0.23 vs satellite); EUXRo03 (2013-2023) R² 0.00 vs satellite. Likely factory calibration, daytime quenching, "
    "biofouling":
        "orientativă: OB01-03 (2024-2026) indică de 2-3 ori mai mult decât satelitul și modelul (raport median satelit / "
        "geamandură 0,36-0,51, R² 0,15-0,23 față de satelit); EUXRo03 (2013-2023) R² 0,00 față de satelit. Cauze "
        "probabile: calibrarea din fabrică, stingerea fluorescenței în timpul zilei, murdărirea biologică (biofouling)",
    "comparison only, never thresholds or trends; datahub \"auto\" uses satellite, then model":
        "doar pentru comparație, niciodată pentru praguri sau tendințe; în datahub, „auto” folosește satelitul, apoi "
        "modelul",
    "Buoy salinity at EUXRoOB01–03": "Salinitatea de la geamandurile EUXRoOB01–03",
    "not trusted: fouling-like drops to 13-15 PSU for weeks to months (e.g. OB02 Oct 2025-Mar 2026), R² 0.00-0.17 vs "
    "model, RMSE 1.1-3.5 PSU":
        "nesigură: scăderi tipice colmatării, până la 13-15 PSU, timp de săptămâni sau luni (de ex. OB02 oct. 2025-mar. "
        "2026), R² 0,00-0,17 față de model, RMSE 1,1-3,5 PSU",
    "show greyed out; datahub \"auto\" uses the model (about 1 PSU vs coastal bottles)":
        "afișată în gri; în datahub, „auto” folosește modelul (aproximativ 1 PSU față de probele de apă de la coastă)",
    "Buoy salinity at EUXRo03 (2013-2023)": "Salinitatea de la geamandura EUXRo03 (2013-2023)",
    "kept as before (good): no step-like drops reported, model 0.43 PSU above the buoy, RMSE 0.98 PSU (but R² 0.05), "
    "within the model's own 1 PSU coastal error":
        "păstrată ca înainte (bună): nu sunt raportate scăderi în trepte, modelul este cu 0,43 PSU peste geamandură, "
        "RMSE 0,98 PSU (dar R² 0,05), în limita erorii de 1 PSU a modelului la coastă",
    "usable as a measured check; the record ends in 2023, so recent dates fall back to the model":
        "utilizabilă ca verificare măsurată; seria se încheie în 2023, deci pentru datele recente se folosește modelul",
    "Coastal buoys EUXRoCB01/02 (new, Sep 2026+)": "Geamandurile costiere EUXRoCB01/02 (noi, din sep. 2026)",
    "not trusted: O₂ units unclear, O₂ saturation 3.6 %, salinity 7.5":
        "nesigure: unitățile pentru O₂ sunt neclare, saturația O₂ 3,6 %, salinitatea 7,5",
    "show greyed out, \"under QC\"": "afișate în gri, „în verificare QC”",
    "Station 15480 (Constanța)": "Stația 15480 (Constanța)",
    "shore station: 3.5 °C colder than open water": "stație de țărm: cu 3,5 °C mai rece decât apa din larg",
    "air and harbour context only, not sea temperature":
        "doar context pentru aer și port, nu temperatura mării",
    "Copernicus physics (T, S)": "Fizica Copernicus (T, S)",
    "good: reanalysis vs NIMRD casts, surface T r 0.99, bias +0.19 °C":
        "bună: reanaliza vs profilele INCDM, T la suprafață r 0,99, bias +0,19 °C",
    "maps, stratification, model vs obs": "hărți, stratificare, model vs observații",
    "Copernicus BGC surface O₂": "Copernicus BGC, O₂ la suprafață",
    "usable: forecast vs buoy r 0.93": "utilizabil: prognoza vs geamandura r 0,93",
    "maps, C2": "hărți, C2",
    "Copernicus BGC bottom O₂": "Copernicus BGC, O₂ la fund",
    "indicative: model systems disagree by ~2 mg/L": "orientativ: sistemele de modelare diferă cu ~2 mg/L",
    "C1/B5 with low confidence": "C1/B5 cu încredere scăzută",
    "Copernicus BGC nitrate, phosphate": "Copernicus BGC, nitrați și fosfați",
    "not usable as absolute values": "nu se folosesc ca valori absolute",
    "not shown; use observations and climatology": "nu sunt afișați; se folosesc observațiile și climatologia",
    "Satellite SST, chl": "SST și chl din satelit",
    "good; NRT vs REP SST offset +0.53 °C": "bune; decalajul SST NRT vs REP +0,53 °C",
    "P1, B1, B2": "P1, B1, B2",
    "Bathing-water history (emodnet_layers.bathing_water_history)":
        "Istoricul apelor de îmbăiere (emodnet_layers.bathing_water_history)",
    "fixed and verified: 2022 45/4, 2023 34/15, 2024 41/8 Excellent/Good, matching the EEA factsheet; seasons before "
    "2015 use an older scheme":
        "corectat și verificat: 2022 45/4, 2023 34/15, 2024 41/8 Excelentă/Bună, conform fișei EEA; sezoanele dinainte "
        "de 2015 folosesc o schemă mai veche",
    "C6 per year from 2015; earlier years marked \"not comparable\"":
        "C6 pe an din 2015; anii anteriori sunt marcați „necomparabil”",
    # section 5 (investigate)
    "Trigger": "Declanșator", "Recommended action": "Acțiune recomandată", "Who acts": "Cine acționează",
    "C1 class D or B5 flag at a mussel bed": "C1 clasa D sau semnal B5 la un banc de midii",
    "ROV or drop-camera transect plus grab sample within 2 weeks":
        "Transect cu ROV sau cu cameră coborâtă de pe navă, plus o probă cu graifărul, în maximum 2 săptămâni",
    "B1/B2 high in Jun–Sep": "B1/B2 ridicate în iun.–sep.",
    "Water samples for harmful species; shellfish toxin test for farms":
        "Probe de apă pentru specii dăunătoare; test de toxine în moluște pentru ferme",
    "NIMRD, sanitary authority, farms": "INCDM, autoritatea sanitară, fermele",
    "B6 new non-indigenous species near a port": "B6: specie neindigenă nouă lângă un port",
    "Plankton tow, ballast-water check": "Pescuit de plancton cu fileul, verificarea apelor de balast",
    "port authority": "autoritatea portuară",
    "Any flag inside a Natura 2000 marine site": "Orice semnal într-un sit marin Natura 2000",
    "Check seagrass and brown and red algae condition":
        "Verificarea stării iarbei de mare și a algelor brune și roșii",
    "ANANP (protected areas agency), NIMRD": "ANANP (agenția pentru arii protejate), INCDM",
    "Persistent anomaly in a hotspot (rule 8)": "Anomalie persistentă într-un punct fierbinte (regula 8)",
    "Targeted sampling campaign at that hotspot": "Campanie de prelevare țintită în acel punct fierbinte",
    "environment agency": "agenția pentru protecția mediului",
    "C6 bathing water Sufficient or Poor": "C6: apă de îmbăiere Suficientă sau Slabă",
    "Check nearby wastewater outfalls": "Verificarea gurilor de evacuare a apelor uzate din apropiere",
    "municipality, water operator": "primăria, operatorul de apă",
    # section 3 (rule chain): whole paragraphs and the numbered items without their "N. "
    "Apply in order; the first match labels the event. \"Pressure\" is used only when no natural driver explains it.":
        "Se aplică în ordine; prima regulă care se potrivește dă eticheta evenimentului. „Presiune” se folosește doar "
        "atunci când niciun factor natural nu explică evenimentul.",
    "**Is it a model-only anomaly for a variable the model gets wrong?** (bottom O₂: forecast − reanalysis −2 mg/L; "
    "nitrate and phosphate unusable) → **model artefact** until an observation confirms it.":
        "**Este o anomalie doar în model, pentru o variabilă pe care modelul o redă greșit?** (O₂ la fund: prognoză − "
        "reanaliză −2 mg/L; nitrații și fosfații nu pot fi folosiți) → **artefact de model** până când o observație o "
        "confirmă.",
    "**Upwelling** (P2) in Jun–Sep → cold SST, low surface O₂ saturation, low pH, high nutrients = **natural**.":
        "**Upwelling** (P2) în iun.–sep. → SST rece, saturație scăzută a O₂ la suprafață, pH scăzut, nutrienți mulți = "
        "**natural**.",
    "**Cold saline intrusion** (bottom T drop > 1.5 °C in 7 days, or bottom S > 18.5) with low bottom O₂ = "
    "**natural**.":
        "**Intruziune de apă rece și sărată** (scădere a T la fund > 1,5 °C în 7 zile sau S la fund > 18,5) cu O₂ scăzut "
        "la fund = **natural**.",
    "**Danube plume or flood** (P3 discharge ratio > 1.2 over 30 days, salinity < 14) → low salinity, high nutrients, "
    "low clarity, bloom = **natural**, or **mixed** when the spring discharge is above p75 (river load is partly a "
    "human pressure).":
        "**Pana Dunării sau viitură** (P3: raportul debitului > 1,2 timp de 30 de zile, salinitate < 14) → salinitate "
        "scăzută, nutrienți mulți, transparență scăzută, înflorire algală = **natural** sau **mixt** când debitul de "
        "primăvară depășește p75 (încărcătura adusă de fluviu este parțial o presiune umană).",
    "**Storm** (P7 in the previous 3 days) → low clarity, high SPM = **natural**.":
        "**Furtună** (P7 în ultimele 3 zile) → transparență scăzută, SPM ridicat = **natural**.",
    "**Bloom decay under stratification** (P4 stratified May–Oct, chl peak or O₂ saturation > 120 % 1–4 weeks "
    "earlier) followed by low bottom O₂ = **pressure-related (eutrophication)**.":
        "**Descompunerea unei înfloriri algale în condiții de stratificare** (P4 stratificat mai–oct., vârf de chl sau "
        "saturație O₂ > 120 % cu 1–4 săptămâni înainte) urmată de O₂ scăzut la fund = **legat de presiune "
        "(eutrofizare)**.",
    "**High NH₄, NO₂ or PO₄ at normal salinity near an outfall in summer** = **pressure (wastewater)**.":
        "**NH₄, NO₂ sau PO₄ ridicate la salinitate normală, lângă o gură de evacuare, vara** = **presiune (ape "
        "uzate)**.",
    "**Anomaly lasting 5+ days with no driver, inside a sector pressure zone or hotspot** = **possible pressure "
    "signal → investigate** (see section 5).":
        "**Anomalie care durează 5+ zile fără un factor natural, într-o zonă de presiune a unui sector sau într-un punct "
        "fierbinte** = **posibil semnal de presiune → de investigat** (vezi secțiunea 5).",
    "Live example: every bottom O₂ < 4 mg/L episode in the forecast since Dec 2024 is in the cold season, with bottom "
    "salinity 19.1–19.9. Rule 3 labels them all natural.":
        "Exemplu real: toate episoadele cu O₂ la fund < 4 mg/L din prognoză, din dec. 2024 încoace, sunt în sezonul "
        "rece, cu salinitatea la fund 19,1–19,9. Regula 3 le etichetează pe toate ca naturale.",
    # section 4 closing paragraph (lines joined with spaces, as md() does)
    "**Two-level quality rule.** Level 1 (sensor trust, in `marinekit.datahub`): a whole platform carries a trust in "
    "`PLATFORMS`, and a single platform-variable pair can be overridden in `VARIABLE_TRUST` (trust, reason). "
    "`get_series(..., source=\"auto\")` never picks a pair whose trust is indicative, untrusted or "
    "not_usable_absolute; an explicit `source=\"buoy\"` and `compare_sources` still return it, with `attrs[\"trust\"]` "
    "set to the flag and the reason in `attrs[\"notes\"]`, so the viewer can grey it out. `obs_vs_model` adds "
    "`obs_trust`. Level 2 (value screening, e.g. a fouling screen on salinity) is not implemented yet; a flag is "
    "lifted only after a calibration against bottle samples. Evidence: `docs/indicators/validation/interpretation.md` "
    "and `metrics.csv`.":
        "**Regula de calitate pe două niveluri.** Nivelul 1 (încrederea în senzor, în `marinekit.datahub`): o platformă "
        "întreagă are un nivel de încredere în `PLATFORMS`, iar o singură pereche platformă-variabilă poate fi "
        "suprascrisă în `VARIABLE_TRUST` (încredere, motiv). `get_series(..., source=\"auto\")` nu alege niciodată o "
        "pereche a cărei încredere este indicative, untrusted sau not_usable_absolute; un `source=\"buoy\"` explicit și "
        "`compare_sources` o returnează totuși, cu `attrs[\"trust\"]` setat la acest marcaj și motivul în "
        "`attrs[\"notes\"]`, ca aplicația să o poată afișa în gri. `obs_vs_model` adaugă `obs_trust`. Nivelul 2 "
        "(verificarea valorilor, de ex. un filtru de colmatare pentru salinitate) nu este încă implementat; un marcaj "
        "se ridică doar după o calibrare cu probe de apă. Dovezi: `docs/indicators/validation/interpretation.md` și "
        "`metrics.csv`.",
    "Two-level quality rule.": "Regula de calitate pe două niveluri.",
})

# =================================================================================================== generic (keep last)
T("{a:n} to {b:n} °C", "{a} – {b} °C")
T("{a:n} to {b:n} PSU", "{a} – {b} PSU")
T("{a:n} to {b:n} mg/L", "{a} – {b} mg/L")
T("{a:n} to {b:n} log10 mg/m³", "{a} – {b} log10 mg/m³")
T("{a:n} to {b:n} z (unitless)", "{a} – {b} z (fără unitate)")
T("{a:n} to {b:n}", "{a} – {b}")
T("{a:n} °C", "{a} °C")
T("{a:n} PSU", "{a} PSU")
T("{a:n} mg/L", "{a} mg/L")
T("{a:n} log10 mg/m³", "{a} log10 mg/m³")
T("{a:n} log10(mg/m³)", "{a} log10(mg/m³)")
T("{a:n} z (unitless)", "{a} z (fără unitate)")
T("{d:i} {m:m}", "{d} {m}")                      # phase dates such as "10 Aug"
T("{a:t}, {b:t}", "{a}, {b}")                    # comma lists: sectors, variables, stations, sensors
