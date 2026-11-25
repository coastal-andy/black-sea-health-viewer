"""Romanian templates for the health cards of marinekit.indicators (titles, texts per level, why, driver_note,
investigate, reference, sources labels, confidence) and indicators.sst_display().

Built from the f-strings in src/marinekit/indicators.py, not only from observed output. Engine and placeholder
kinds: see viewer/i18n_data.py. Order matters: specific templates before general ones.

Counts before a noun use the {n:c} kind, which adds "de" from 20 up ("23 de zile", "7 zile"); a count that can be
1 gets its own singular template registered first.
"""
from itertools import combinations

from viewer.i18n_data import E, T

# ------------------------------------------------------------------------------------------ small words
E("None", "n.d.")
E("nan", "n.d.")
E("n/a", "n.d.")
for _w in ("REP", "NRT", "REP, NRT", "NRT, REP", "REP/NRT"):
    E(_w, _w)
E("multi-year", "multianual")
E("multi-year (incl. interim)", "multianual (incl. interimar)")
E("multi-year, NRT", "multianual, NRT")
E("multi-year (incl. interim), NRT", "multianual (incl. interimar), NRT")
E("reanalysis", "reanaliză")
E("analysis/forecast", "analiză/prognoză")

# card titles
E("Water temperature", "Temperatura apei")
E("Oxygen", "Oxigen")
E("Eutrophication and blooms", "Eutrofizare și înfloriri algale")
E("Water clarity", "Transparența apei")
E("Nutrients (historical)", "Nutrienți (istoric)")
E("Bathing water", "Apă de îmbăiere")
E("Biodiversity evidence", "Dovezi de biodiversitate")
E("Drivers (natural variability)", "Factori naturali (variabilitate)")
E("Acidification (watch only)", "Acidifiere (doar urmărire)")

# confidence, evidence, status, units
E("high", "ridicată")
E("medium", "medie")
E("low", "scăzută")
E("measured", "măsurat")
E("satellite", "satelit")
E("model", "model")
E("derived", "derivat")
E("in-situ", "in situ")
E("normal", "normal")
E("watch", "atenție")
E("alert", "alertă")
E("no_data", "fără date")
E("class", "clasă")
E("species", "specii")
E("x normal", "× normal")

# sectors (single and every sorted combination, as indicators joins them)
_SEC = {"aquaculture": "acvacultură", "fishing": "pescuit", "ports": "porturi", "shipyards": "șantiere navale",
        "tourism": "turism"}
for _n in range(1, 6):
    for _c in combinations(sorted(_SEC), _n):
        E(", ".join(_c), ", ".join(_SEC[x] for x in _c))

# ------------------------------------------------------------------------------------------ threshold table T
E("above the day-of-year 90th percentile for >= 5 days; categories moderate/strong/severe/extreme by multiples of "
  "(p90 - mean)",
  "peste percentila 90 pentru ziua din an timp de >= 5 zile; categoriile moderat/puternic/sever/extrem după "
  "multiplii lui (p90 - medie)")
E("Hobday et al. 2016, 2018", "Hobday et al. 2016, 2018")
E("A >= 5 mg/L (D5C5 level), B 4-5, C 2-4, D < 2 (hypoxia)",
  "A >= 5 mg/L (nivelul D5C5), B 4-5, C 2-4, D < 2 (hipoxie)")
E("A: RO MSFD 2024 D5C5; B, C: ours; D: Diaz & Rosenberg 2008",
  "A: DCSMM RO 2024 D5C5; B, C: propunerea noastră; D: Diaz & Rosenberg 2008")
E("May-Sep P10 of bottom O2 >= 5 mg/L and >= 60 % saturation",
  "P10 mai-sept. al oxigenului de la fund >= 5 mg/L și saturație >= 60 %")
E("RO MSFD 2024 (NIMRD), D5C5", "DCSMM RO 2024 (INCDM), D5C5")
E("surface saturation > 120 % (bloom), < 80 % (respiration or upwelling)",
  "saturație la suprafață > 120 % (înflorire algală), < 80 % (respirație sau upwelling)")
E("chemical.md C2", "chemical.md C2")
E("May-Sep P75 chl, coastal waters (RO MSFD 2024 D5C2)", "P75 clorofilă-a mai-sept., ape costiere (DCSMM RO 2024 D5C2)")
E("May-Sep mean chl, marine waters south (RO MSFD 2024)", "media clorofilei-a mai-sept., ape marine sud (DCSMM RO 2024)")
E("May-Sep P10 Secchi depth, coastal waters (RO MSFD 2024)", "P10 adâncime Secchi mai-sept., ape costiere (DCSMM RO 2024)")
E("DIN P75, marine waters (RO MSFD 2024)", "DIN P75, ape marine (DCSMM RO 2024)")
E("PO4 P75, marine waters (RO MSFD 2024)", "PO4 P75, ape marine (DCSMM RO 2024)")
E("DIN P75, coastal waters RO-CT (RO MSFD 2024)", "DIN P75, ape costiere RO-CT (DCSMM RO 2024)")
E("PO4 P75, coastal waters RO-CT (RO MSFD 2024)", "PO4 P75, ape costiere RO-CT (DCSMM RO 2024)")
E("Excellent / Good / Sufficient / Poor", "Excelentă / Bună / Suficientă / Slabă")
E("Bathing Water Directive 2006/7/EC", "Directiva privind apa de îmbăiere 2006/7/CE")
E("2006/7/EC", "2006/7/CE")

# threshold-type codes stay as they are
for _w in ("OFFICIAL-RO", "OFFICIAL-EU", "OURS", "LIT", "LIT + OURS", "OURS + OFFICIAL-RO",
           "OFFICIAL-RO (5 mg/L) + OURS (B, C) + LIT (2 mg/L)"):
    E(_w, _w)
E("OFFICIAL-RO + OURS (band)", "OFFICIAL-RO + OURS (bandă)")
E("OFFICIAL-RO targets", "ținte OFFICIAL-RO")

# ------------------------------------------------------------------------------------------ reference dicts
E("day-of-year climatology of satellite SST (REP), 11-day window",
  "climatologie pe ziua din an a temperaturii de suprafață din satelit (REP), fereastră de 11 zile")
E("day-of-year geometric mean of satellite chl, +-15 days, log space",
  "media geometrică pe ziua din an a clorofilei-a din satelit, ±15 zile, spațiu logaritmic")
E("Secchi = 1.1 / Kd(PAR), Kd(PAR) from Kd490 (Morel 2007); normal = day-of-year geometric mean of Kd490",
  "Secchi = 1,1 / Kd(PAR), Kd(PAR) din Kd490 (Morel 2007); normal = media geometrică pe ziua din an a Kd490")
E("presence over sampling effort, never a trend (biological.md B6)",
  "prezență raportată la efortul de eșantionare, niciodată o tendință (biological.md B6)")
E("Danube discharge 30-day mean / 1997-2025 day-of-year mean (GloFAS)",
  "debitul Dunării, media pe 30 de zile / media pe ziua din an 1997-2025 (GloFAS)")
E("day-of-year climatology of the BGC reanalysis", "climatologie pe ziua din an a reanalizei BGC")
E("Excellent or Good", "Excelentă sau Bună")
T("above p90 = anomalous high (OURS); D5C2 May-Sep P75 <= {x:n} mg/m³",
  "peste p90 = valoare anormal de mare (OURS); D5C2 P75 mai-sept. <= {x} mg/m³")
T("May-Sep P10 Secchi depth, coastal waters (RO MSFD 2024) >= {x:n} m",
  "P10 adâncime Secchi mai-sept., ape costiere (DCSMM RO 2024) >= {x} m")
E("river influence when > 1.2 or salinity < 14; upwelling when coast - offshore SST <= -2 °C (Jun-Sep); storm when "
  "Hs > p95; stratified when surface - bottom T > 2 °C (May-Oct)",
  "influență fluvială când > 1,2 sau salinitatea < 14; upwelling când SST țărm - larg <= -2 °C (iun.-sept.); "
  "furtună când Hs > p95; stratificare când T suprafață - fund > 2 °C (mai-oct.)")
E("watch below p10; never alert (model only)", "atenție sub p10; niciodată alertă (doar model)")
E("watch when a tracked non-indigenous species has no record on the Romanian coast before 2015, or when "
  "non-indigenous species are present inside a port or shipyard zone (entry points)",
  "atenție când o specie neindigenă urmărită nu are nicio înregistrare pe litoralul românesc înainte de 2015 sau "
  "când specii neindigene sunt prezente într-o zonă portuară ori de șantier naval (puncte de intrare)")
E("seasonal climatology 2000-2022", "climatologie sezonieră 2000-2022")
T("6-year window centred {y:i}", "fereastră de 6 ani centrată pe {y}")

# ------------------------------------------------------------------------------------------ investigate (SHORTLIST 5)
E("Bottom oxygen class D (hypoxia) or mussel-bed hypoxia flag",
  "Oxigen la fund în clasa D (hipoxie) sau semnal de hipoxie la bancurile de midii")
E("ROV or drop-camera transect plus a grab sample within 2 weeks",
  "Transect cu ROV sau cu cameră coborâtă, plus o probă de sediment cu graiferul, în cel mult 2 săptămâni")
E("NIMRD, aquaculture operators", "INCDM, operatorii din acvacultură")
E("Chlorophyll high in June-September", "Clorofilă-a ridicată în iunie-septembrie")
E("Water samples for harmful species; shellfish toxin test for farms",
  "Probe de apă pentru specii dăunătoare; testarea toxinelor din moluște la ferme")
E("NIMRD, sanitary authority, mussel farms", "INCDM, autoritatea sanitară, fermele de midii")
E("New non-indigenous species near a port", "Specie neindigenă nouă lângă un port")
E("Plankton tow, ballast-water check", "Probă de plancton cu fileul, verificarea apelor de balast")
E("port authority", "autoritatea portuară")
E("Persistent anomaly with no natural driver inside a sector pressure zone",
  "Anomalie persistentă, fără factor natural, într-o zonă de presiune a unui sector")
E("Targeted sampling campaign at this location", "Campanie de prelevare țintită în acest loc")
E("environment agency (APM Constanta), NIMRD", "agenția pentru protecția mediului (APM Constanța), INCDM")
E("Bathing water Sufficient or Poor", "Apă de îmbăiere de calitate suficientă sau slabă")
E("Check nearby wastewater outfalls", "Verificarea gurilor de evacuare a apelor uzate din apropiere")
E("municipality, water operator", "primăria, operatorul de apă")

# ------------------------------------------------------------------------------------------ sources labels
E("climatology 1991-2020 (REP)", "climatologie 1991-2020 (REP)")
E("climatology 1998-2020 (log space)", "climatologie 1998-2020 (spațiu logaritmic)")
E("climatology 1998-2022 (log space)", "climatologie 1998-2022 (spațiu logaritmic)")
E("EMODnet Chemistry DIVAnd Black Sea, 6-year windows (from NIMRD and other bottle data)",
  "EMODnet Chemistry DIVAnd Marea Neagră, ferestre de 6 ani (din datele INCDM și alte probe de apă)")
E("EMODnet Chemistry DIVAnd Danube Delta, seasonal climatology 2000-2022 (0.01 deg)",
  "EMODnet Chemistry DIVAnd Delta Dunării, climatologie sezonieră 2000-2022 (0,01 grade)")
T("box +-{a:n} deg lat, +-{b:n} deg lon around the point", "caseta de ±{a}° lat. și ±{b}° long. în jurul punctului")
T("{n:k} (RO{i:i})", "{n} (RO{i})")  # bathing site name (EEA id): names stay as they are
# datahub series labels (sources[].label)
E("Copernicus Black Sea BGC model, bottom O2", "Modelul BGC Copernicus pentru Marea Neagră, oxigen la fund")
E("Copernicus Black Sea BGC model, surface O2", "Modelul BGC Copernicus pentru Marea Neagră, oxigen la suprafață")
E("Copernicus Black Sea BGC model, surface chl", "Modelul BGC Copernicus pentru Marea Neagră, clorofilă-a la suprafață")
E("Copernicus Black Sea BGC model, surface pH", "Modelul BGC Copernicus pentru Marea Neagră, pH la suprafață")
E("Copernicus Black Sea physics model, bottom level", "Modelul fizic Copernicus pentru Marea Neagră, nivelul de la fund")
E("Copernicus Black Sea physics model, top level", "Modelul fizic Copernicus pentru Marea Neagră, nivelul de suprafață")
E("Copernicus Black Sea physics model, mixed-layer depth",
  "Modelul fizic Copernicus pentru Marea Neagră, adâncimea stratului de amestec")
E("Copernicus Black Sea wave model, daily max Hs", "Modelul de valuri Copernicus pentru Marea Neagră, Hs maxim zilnic")
E("Copernicus BGC model nitrate (NOT usable as absolute values)",
  "Nitrați din modelul BGC Copernicus (NU se pot folosi ca valori absolute)")
E("Copernicus BGC model phosphate (NOT usable as absolute values)",
  "Fosfați din modelul BGC Copernicus (NU se pot folosi ca valori absolute)")
E("Danube discharge at the delta apex, GloFAS v4 (Open-Meteo Flood API)",
  "Debitul Dunării la vârful deltei, GloFAS v4 (Open-Meteo Flood API)")
E("EMODnet Chemistry bottle samples 0-5 m within 30 km", "Probe de apă EMODnet Chemistry, 0-5 m, pe o rază de 30 km")
E("ERA5 via Open-Meteo (forecast after today)", "ERA5 prin Open-Meteo (prognoză după ziua de azi)")
E("Model O2 / O2 solubility (Garcia & Gordon 1992) at model T, S",
  "Oxigen din model / solubilitatea oxigenului (Garcia & Gordon 1992) la T și S din model")
E("NIMH shore station 15480 (Constanta)", "Stația de țărm ANM 15480 (Constanța)")
E("Nearest coastal buoy EUXRoCB0x", "Cea mai apropiată geamandură costieră EUXRoCB0x")
E("Nearest offshore buoy", "Cea mai apropiată geamandură din larg")
E("Nearest offshore buoy (OSAT)", "Cea mai apropiată geamandură din larg (OSAT)")
E("Nearest offshore buoy (fluorescence)", "Cea mai apropiată geamandură din larg (fluorescență)")
E("Nearest offshore buoy (measured O2)", "Cea mai apropiată geamandură din larg (oxigen măsurat)")
E("Open-Meteo marine (MFWAM/ECMWF-WAM), daily max Hs", "Open-Meteo marin (MFWAM/ECMWF-WAM), Hs maxim zilnic")
E("Satellite Kd490 (CMEMS ocean colour, multi-year + NRT)",
  "Kd490 din satelit (CMEMS culoarea oceanului, multianual + NRT)")
E("Satellite SST L4 (CMEMS REP + NRT, NRT offset removed)",
  "Temperatura la suprafață din satelit, L4 (CMEMS REP + NRT, fără decalajul NRT)")
E("Satellite chl-a L4 gap-free 1 km (CMEMS multi-year + NRT)",
  "Clorofilă-a din satelit, L4 fără goluri, 1 km (CMEMS multianual + NRT)")
# sources[].dataset strings that are not plain IDs (shown in the detailed view)
E("EMODnet Human Activities, emodnet:bathingwaters (EEA BWD reporting)",
  "EMODnet Human Activities, emodnet:bathingwaters (raportarea DAI către AEM)")
E("OBIS checklist API (api.obis.org)", "API-ul de liste de specii OBIS (api.obis.org)")
E("GloFAS v4 via Open-Meteo Flood API, Danube at Ceatal Izmail",
  "GloFAS v4 prin Open-Meteo Flood API, Dunărea la Ceatal Izmail")
E("EUXRoOB03 (GeoEcoMar ERDDAP (live, salinity from conductivity))",
  "EUXRoOB03 (GeoEcoMar ERDDAP (în timp real, salinitate din conductivitate))")
E("zone sampling", "eșantionarea zonei")
# zone sampling labels (zone_cards)
E("point", "punct")
E("centroid of the zone", "centroidul zonei")
E("interior point of the zone (centroid falls outside)", "punct din interiorul zonei (centroidul cade în afara ei)")
T("random interior sample {n:i}", "eșantion aleator din interior {n}")
T("{h:t} at {a:n} N {b:n} E (card taken from this point: worst status)",
  "{h} la {a} N {b} E (fișa provine din acest punct: starea cea mai gravă)")
T("{h:t} at {a:n} N {b:n} E", "{h} la {a} N {b} E")

# ------------------------------------------------------------------------------------------ card() wrapper
E("No data for this card here and now.", "Nu există date pentru această fișă aici și acum.")
T("No data for this card here and now. Could not compute: {e:k}",
  "Nu există date pentru această fișă aici și acum. Calculul nu a fost posibil (eroare tehnică): {e}")
T("Could not compute: {e:k}", "Calculul nu a fost posibil (eroare tehnică): {e}")
E("No cause assigned (no data).", "Nicio cauză atribuită (lipsă date).")
E("No anomaly, so no cause to assign.", "Nicio anomalie, deci nicio cauză de atribuit.")

# sst_display()
E("Sea surface temperature (satellite L4, as in the temperature card)",
  "Temperatura la suprafața mării (satelit L4, ca în fișa de temperatură)")
T("{r:k}; NRT values lowered by {x:n} °C (NRT minus REP offset)",
  "{r}; valorile NRT coborâte cu {x} °C (decalajul NRT minus REP)")
T("NRT values lowered by {x:n} °C (NRT minus REP offset)",
  "Valorile NRT coborâte cu {x} °C (decalajul NRT minus REP)")
T("No satellite SST: {e:k}", "Nicio temperatură de suprafață din satelit (eroare tehnică): {e}")

# ------------------------------------------------------------------------------------------ rule chain (classify_cause)
E("No anomaly to explain.", "Nicio anomalie de explicat.")
# rule 1
E("This rests on a model value the model is known to get wrong (bottom O2: the forecast system runs about 2 mg/L "
  "below the reanalysis; nitrate and phosphate are unusable as absolute values).",
  "Valoarea se sprijină pe o mărime pe care modelul, se știe, o redă greșit (oxigenul de la fund: sistemul de "
  "prognoză dă cu aproximativ 2 mg/L mai puțin decât reanaliza; nitrații și fosfații nu pot fi folosiți ca valori "
  "absolute).")
E("Treat it as a model artefact until an observation confirms it.",
  "Se tratează ca artefact de model până când o observație o confirmă.")
# rule 2
T("Upwelling: the coast is {a:n} °C colder than the water 47 km offshore.",
  "Upwelling (ridicarea apelor reci de adânc): la țărm apa este cu {a} °C mai rece decât la 47 km în larg.")
E("South-west winds bring cold, nutrient-rich, low-oxygen deep water to the surface.",
  "Vânturile din sud-vest aduc la suprafață apă de adânc rece, bogată în nutrienți și săracă în oxigen.")
E("This is natural.", "Este un fenomen natural.")
# rule 3
T("Cold saline intrusion: bottom salinity {a:n} PSU, bottom temperature change over 7 days {b:n} °C.",
  "Intruziune de apă rece și sărată: salinitatea la fund {a} PSU, variația temperaturii la fund în 7 zile {b} °C.")
T("Cold saline intrusion: bottom salinity {a:t} PSU, bottom temperature change over 7 days {b:t} °C.",
  "Intruziune de apă rece și sărată: salinitatea la fund {a} PSU, variația temperaturii la fund în 7 zile {b} °C.")
E("Shelf-break water naturally low in oxygen has moved onto the shelf.",
  "Apa de la marginea platoului continental, săracă în mod natural în oxigen, a pătruns pe platou.")
# rule 4
T("Danube influence: river flow {a:n} times normal over 30 days, surface salinity {b:n} PSU.",
  "Influența Dunării: debitul fluviului este de {a} ori cel normal în ultimele 30 de zile, salinitatea la suprafață "
  "{b} PSU.")
T("Danube influence: river flow {a:t} times normal over 30 days, surface salinity {b:t} PSU.",
  "Influența Dunării: debitul fluviului este de {a} ori cel normal în ultimele 30 de zile, salinitatea la suprafață "
  "{b} PSU.")
E("The spring discharge was above its 75th percentile, and the river load is partly a human pressure, so this is "
  "mixed.",
  "Debitul de primăvară a depășit percentila 75, iar încărcătura adusă de fluviu este parțial o presiune umană, "
  "deci cauza este mixtă.")
E("This is natural variability.", "Este variabilitate naturală.")
# rule 5
T("Storm: waves reached {a:n} m in the last 3 days (95th percentile {b:n} m).",
  "Furtună: valurile au atins {a} m în ultimele 3 zile (percentila 95: {b} m).")
T("Storm: waves reached {a:t} m in the last 3 days (95th percentile {b:t} m).",
  "Furtună: valurile au atins {a} m în ultimele 3 zile (percentila 95: {b} m).")
E("Waves stir up the seabed; murky water for a few days is natural.",
  "Valurile ridică sedimentele de pe fund; apa tulbure timp de câteva zile este un fenomen natural.")
# rule 6
T("Bloom decay under stratification: the water column is layered (surface {a:t} °C warmer than the bottom) and an "
  "algal bloom 1-4 weeks earlier is sinking and decaying.",
  "Descompunerea unei înfloriri algale în apă stratificată: coloana de apă este stratificată (la suprafață cu {a} °C "
  "mai caldă decât la fund), iar o înflorire algală de acum 1-4 săptămâni se depune și se descompune.")
E("This is the eutrophication pathway.", "Acesta este mecanismul eutrofizării.")
# rule 7
E("High ammonium, nitrite or phosphate at normal salinity near an outfall in summer: wastewater.",
  "Amoniu, nitriți sau fosfați ridicați la salinitate normală, lângă o gură de evacuare, vara: ape uzate.")
# climate (our addition)
E("Regional sea-temperature event driven by the weather and long-term warming.",
  "Eveniment regional de temperatură a mării, produs de vreme și de încălzirea pe termen lung.")
E("Local activities do not cause it, so it is not counted as a local pressure; its effects (heat stress, blooms, "
  "low oxygen) show on the other cards.",
  "Activitățile locale nu îl provoacă, deci nu este socotit o presiune locală; efectele lui (stres termic, "
  "înfloriri algale, oxigen scăzut) apar pe celelalte fișe.")
# rule 8
T("The anomaly has lasted {n:c} days with no natural driver, inside a pressure zone ({s:t}).",
  "Anomalia durează de {n} zile fără niciun factor natural care s-o explice, într-o zonă de presiune ({s}).")
E("Possible pressure signal: investigate.", "Posibil semnal de presiune: merită investigat.")
T("The anomaly has lasted {n:c} days with no natural driver found.",
  "Anomalia durează de {n} zile și nu s-a găsit niciun factor natural care s-o explice.")
E("No sector pressure zone here.", "Aici nu există nicio zonă de presiune a sectoarelor.")
E("Pressure-zone overlap unknown.", "Suprapunerea zonelor de presiune nu este cunoscută.")
E("Keep watching.", "De urmărit în continuare.")
E("Short anomaly with no natural driver found yet; it may pass.",
  "Anomalie de scurtă durată, fără un factor natural identificat deocamdată; poate trece de la sine.")
T("If the value is real: {x:l}", "Dacă valoarea este reală: {x}")
# _driver_note(): "<tag> (rule N): <text>"
_TAGS = [("Possible model artefact", "Posibil artefact de model"), ("Mixed natural and human", "Mixt (natural și uman)"),
         ("Pressure-related", "Legat de presiuni"), ("Possible pressure", "Posibilă presiune"),
         ("Pressure", "Presiune"), ("Unexplained", "Neexplicat"), ("Regional climate", "Climă regională"),
         ("Natural", "Natural")]
for _en, _ro in _TAGS:
    T(_en + " (rule {r:i}): {x:l}", _ro + " (regula {r}): {x}")
    T(_en + ": {x:l}", _ro + ": {x}")

# ------------------------------------------------------------------------------------------ 1 temperature
E("No satellite SST in the 3 days up to this date.",
  "Nicio temperatură de suprafață din satelit în cele 3 zile de până la această dată.")
T("Sea surface {v:n} °C on {d:d}, {a:n} °C from the 1991-2020 normal ({m:n} °C; usual range {lo:n}-{hi:n} °C).",
  "Temperatura la suprafață: {v} °C pe {d}, abatere de {a} °C față de normala 1991-2020 ({m} °C; interval obișnuit "
  "{lo}-{hi} °C).")
_CAT = {"moderate": "moderat", "strong": "puternic", "severe": "sever", "extreme": "extrem"}
for _c, _cr in _CAT.items():
    T(f"A {_c} marine heatwave has been going on for {{n:c}} days (since {{d:d}}).",
      f"Un val de căldură marin {_cr} durează de {{n}} zile (din {{d}}).")
    T(f"A {_c} marine cold spell has been going on for {{n:c}} days (since {{d:d}}).",
      f"Un val de frig marin {_cr} durează de {{n}} zile (din {{d}}).")
T("The sea here is {v:n} °C, {a:n} °C warmer than usual for this time of year.",
  "Apa mării are aici {v} °C, cu {a} °C mai caldă decât de obicei în această perioadă a anului.")
T("The sea here is {v:n} °C, {a:n} °C colder than usual for this time of year.",
  "Apa mării are aici {v} °C, cu {a} °C mai rece decât de obicei în această perioadă a anului.")
E("That counts as a marine heatwave.", "Este un val de căldură marin.")
E("That counts as a marine cold spell.", "Este un val de frig marin.")
E("That is within the normal range.", "Valoarea este în intervalul normal.")
E("That is unusual, but not yet a heatwave or cold spell.",
  "Este neobișnuit, dar nu este încă un val de căldură sau de frig.")
T("Anomaly = today's satellite SST minus the 1991-2020 mean for the same date: {a:n} °C (z = {z:n}). A marine "
  "heatwave is 5 or more days above the warmest 10 % for that date (Hobday et al. 2016).",
  "Anomalia = temperatura de suprafață de azi, din satelit, minus media 1991-2020 pentru aceeași dată: {a} °C "
  "(z = {z}). Un val de căldură marin înseamnă cel puțin 5 zile peste cele mai calde 10 % dintre valorile pentru "
  "acea dată (Hobday et al. 2016).")
E("Mussels are stressed above about 25 °C; long heatwaves in summer raise mortality risk.",
  "Midiile intră în stres peste aproximativ 25 °C; valurile de căldură lungi din timpul verii cresc riscul de "
  "mortalitate.")
E("Warm water favours jellyfish and blooms; sudden cold water in summer usually means upwelling.",
  "Apa caldă favorizează meduzele și înfloririle algale; apa rece apărută brusc vara înseamnă de obicei upwelling.")
E("Sprat and anchovy shift depth and timing with temperature; expect changed catches during long anomalies.",
  "Șprotul și hamsia își schimbă adâncimea și perioada de apariție în funcție de temperatură; în anomaliile lungi "
  "capturile se pot schimba.")
E("No direct effect on operations; warm summers increase fouling on hulls and structures.",
  "Niciun efect direct asupra operațiunilor; verile calde înmulțesc depunerile biologice pe carene și pe structuri.")
E("Warm water speeds hull fouling and the settlement of introduced species.",
  "Apa caldă grăbește depunerile biologice pe carene și fixarea speciilor introduse.")
for _s, _sr in (("normal", "normal"), ("watch", "atenție"), ("alert", "alertă")):
    T(f"Status {_s}: heatwave days this year 0.",
      f"Stare: {_sr}; nicio zi cu val de căldură marin în acest an.")
    T(f"Status {_s}: heatwave days this year 1.",
      f"Stare: {_sr}; o zi cu val de căldură marin în acest an.")
    T(f"Status {_s}: heatwave days this year {{n:c}}.",
      f"Stare: {_sr}; {{n}} zile cu val de căldură marin în acest an.")
E("Use it to plan, not to blame.", "Informația servește la planificare, nu la căutarea vinovaților.")
T("SST {v:n} °C ({r:t}; NRT lowered by {o:n} °C), clim mean {m:n}, sd {sd:n}, p10 {p10:n}, p90 {p90:n} (DOY, "
  "11-d window, 31-d smoothing).",
  "SST {v} °C ({r}; NRT coborât cu {o} °C), media climatologică {m}, sd {sd}, p10 {p10}, p90 {p90} (ziua din an, "
  "fereastră de 11 zile, netezire pe 31 de zile).")
E("Events: Hobday 2016 recipe, fixed 1991-2020 baseline (includes the warming trend).",
  "Evenimente: metoda Hobday 2016, referință fixă 1991-2020 (include tendința de încălzire).")

# ------------------------------------------------------------------------------------------ 2 oxygen
E("No model bottom oxygen for this date.", "Modelul nu are o valoare a oxigenului de la fund pentru această dată.")
E("A (meets the 5 mg/L level)", "A (atinge nivelul de 5 mg/L)")
E("B (4-5 mg/L, below the good-status level)", "B (4-5 mg/L, sub nivelul stării bune)")
E("C (2-4 mg/L, hypoxia risk)", "C (2-4 mg/L, risc de hipoxie)")
E("D (below 2 mg/L, hypoxic)", "D (sub 2 mg/L, hipoxie)")
T("Bottom oxygen {v:n} mg/L on {d:d} (model, deepest level): class {c:t}.",
  "Oxigen dizolvat la fund: {v} mg/L pe {d} (model, cel mai adânc nivel); clasa {c}.")
T("Surface saturation {s:n} %.", "Saturația în oxigen la suprafață: {s} %.")
E("The forecast model runs about 2 mg/L below the reanalysis, so read the class, not small changes.",
  "Modelul de prognoză dă cu aproximativ 2 mg/L mai puțin decât reanaliza, așa că important este clasa, nu "
  "micile variații.")
E("There is enough oxygen near the seabed for fish and mussels.",
  "Lângă fundul mării este destul oxigen pentru pești și midii.")
E("Oxygen near the seabed is a bit lower than it should be.",
  "Oxigenul de lângă fundul mării este puțin mai scăzut decât ar trebui.")
E("Oxygen near the seabed is low; sensitive animals may be stressed.",
  "Oxigenul de lângă fundul mării este scăzut; animalele sensibile pot fi afectate.")
E("The seabed water is almost out of oxygen; animals there can die.",
  "Apa de lângă fundul mării aproape că a rămas fără oxigen; animalele de acolo pot muri.")
E("This comes from a computer model, not a measurement.", "Valoarea vine dintr-un model, nu dintr-o măsurătoare.")
for _c in "ABCD":
    T(f"Bottom O2 {{v:n}} mg/L, class {_c}.", f"O2 la fund {{v}} mg/L, clasa {_c}.")
E("Classes: A >= 5 mg/L (official good-status level), B 4-5, C 2-4, D < 2 (hypoxia).",
  "Clase: A >= 5 mg/L (nivelul oficial al stării bune), B 4-5, C 2-4, D < 2 (hipoxie).")
E("Oxygen drops when the water is layered and dead algae decay at the bottom.",
  "Oxigenul scade când apa este stratificată și algele moarte se descompun pe fund.")
E("Mussel lines near the bottom are exposed first; class C or D means check the stock.",
  "Liniile de midii de lângă fund sunt primele expuse; clasa C sau D înseamnă că stocul trebuie verificat.")
E("Low bottom oxygen drives turbot and other bottom fish away and can kill benthic shellfish.",
  "Oxigenul scăzut de la fund alungă calcanul și alți pești de fund și poate omorî moluștele bentonice.")
E("Low oxygen at the bottom rarely shows at the beach, except in rare summer fish kills.",
  "Oxigenul scăzut de la fund se vede rar la plajă, cu excepția unor rare episoade de mortalitate a peștilor, vara.")
E("Dredging in late summer can release oxygen-consuming mud; avoid it during class C or D.",
  "Dragajele de la sfârșitul verii pot pune în suspensie mâl care consumă oxigen; trebuie evitate cât timp clasa "
  "este C sau D.")
E("No direct effect; discharges of organic waste make low oxygen worse.",
  "Niciun efect direct; deversările de deșeuri organice agravează lipsa de oxigen.")
E("Class A: no action needed.", "Clasa A: nu este nevoie de nicio acțiune.")
E("Class B: watch the next days.", "Clasa B: de urmărit în zilele următoare.")
E("Class C: watch the next days.", "Clasa C: de urmărit în zilele următoare.")
E("Class D: send divers or an ROV within 2 weeks.",
  "Clasa D: este nevoie de scafandri sau de un ROV în cel mult 2 săptămâni.")
T("o2b {v:n} mg/L (BLKSEA analysis/forecast, 0.032 mg/L per mmol/m3).",
  "o2b {v} mg/L (BLKSEA analiză/prognoză, 0,032 mg/L per mmol/m3).")
T("o2b {v:n} mg/L (BLKSEA BGC reanalysis, 0.032 mg/L per mmol/m3).",
  "o2b {v} mg/L (reanaliza BLKSEA BGC, 0,032 mg/L per mmol/m3).")
T("Rule 1 applies to forecast bottom O2 (anfc - rea about {x:n} mg/L in the 2024 overlap); no bottom sensor exists.",
  "Regula 1 se aplică oxigenului de la fund din prognoză (anfc - rea circa {x} mg/L în perioada comună din 2024); "
  "nu există niciun senzor la fund.")
E("Official NIMRD 2018-2023 P10 at 20-50 m: 5.44 mg/L, 54.3 % saturation.",
  "Valoarea oficială INCDM 2018-2023, P10 la 20-50 m: 5,44 mg/L, saturație 54,3 %.")

# ------------------------------------------------------------------------------------------ 3 blooms
E("No satellite chlorophyll in the 3 days up to this date.",
  "Nicio valoare de clorofilă-a din satelit în cele 3 zile de până la această dată.")
T("Chlorophyll {v:n} mg/m³ on {d:d}, {r:n} times the 1998-2020 normal for this date ({m:n}; p90 {p:n}).",
  "Clorofila-a: {v} mg/m³ pe {d}, de {r} ori normala 1998-2020 pentru această dată ({m}; p90 {p}).")
T("Above p90 for 1 days in a row.", "Peste percentila 90 de o zi.")
T("Above p90 for {n:c} days in a row.", "Peste percentila 90 de {n} zile la rând.")
T("Official D5C2 proxy for {y:i}: fail.", "Criteriul oficial D5C2 (aproximare din satelit) pentru {y}: neîndeplinit.")
T("Official D5C2 proxy for {y:i}: pass.", "Criteriul oficial D5C2 (aproximare din satelit) pentru {y}: îndeplinit.")
E("The sea has much more microscopic algae than usual for this week.",
  "Marea are mult mai multe alge microscopice decât de obicei în această săptămână.")
E("The sea has more microscopic algae than usual for this week.",
  "Marea are mai multe alge microscopice decât de obicei în această săptămână.")
E("The sea has about the usual amount of microscopic algae than usual for this week.",
  "Marea are cam aceeași cantitate de alge microscopice ca de obicei în această săptămână.")
E("The sea has less microscopic algae than usual for this week.",
  "Marea are mai puține alge microscopice decât de obicei în această săptămână.")
E("Water may look green or brown.", "Apa poate părea verde sau maronie.")
T("Satellite chlorophyll compared in log space with a 23-year day-of-year climatology: ratio {r:n}, z = {z:n}.",
  "Clorofila-a din satelit, comparată în spațiu logaritmic cu o climatologie pe ziua din an construită pe 23 de "
  "ani: raport {r}, z = {z}.")
E("Values above the 90th percentile count as bloom days.",
  "Valorile peste percentila 90 sunt socotite zile de înflorire algală.")
E("Blooms can carry toxic species; test shellfish before harvest when this is high in summer.",
  "Înfloririle algale pot conține specii toxice; când valoarea este ridicată vara, moluștele trebuie testate "
  "înainte de recoltare.")
E("A high value means check bathing-water quality; discoloured water is the usual complaint.",
  "O valoare ridicată înseamnă că trebuie verificată calitatea apei de îmbăiere; apa decolorată este plângerea "
  "obișnuită.")
E("Dredging plumes can look like blooms on satellite images; check the clarity card too.",
  "Penele de turbiditate de la dragaje pot semăna cu înfloririle algale pe imaginile din satelit; merită verificată "
  "și fișa de transparență.")
E("More algae means more food at first, but decaying blooms lower bottom oxygen later.",
  "Mai multe alge înseamnă la început mai multă hrană, dar înfloririle care se descompun scad mai târziu oxigenul "
  "de la fund.")
E("No direct effect; nutrient-rich discharges feed blooms.",
  "Niciun efect direct; deversările bogate în nutrienți hrănesc înfloririle algale.")
E("Early warning of an algal bloom, not proof of damage.", "Avertizare timpurie de înflorire algală, nu dovadă de daune.")
E("No bloom signal now.", "Niciun semnal de înflorire algală acum.")
T("CMEMS OC L4 gap-free 1 km ({r:t}); clim gmean {m:n}, sd(log10) {s:n}.",
  "CMEMS OC L4 fără goluri, 1 km ({r}); media geometrică climatologică {m}, sd(log10) {s}.")
E("Case-2 coastal water: CDOM and sediment from the Danube can bias satellite chl upwards.",
  "Apă costieră de tip Case-2: CDOM și sedimentele aduse de Dunăre pot face ca clorofila-a din satelit să pară mai "
  "mare decât este.")
E("Today's value is normal, but the season test failed: the summer chlorophyll level is above the official coastal "
  "threshold.",
  "Valoarea de azi este normală, dar testul sezonier a eșuat: nivelul clorofilei-a din vară depășește pragul oficial "
  "pentru apele costiere.")
E("Danube nutrient load and coastal wastewater both feed it; a single date cannot separate them.",
  "Îl alimentează atât nutrienții aduși de Dunăre, cât și apele uzate de pe coastă; o singură dată nu le poate "
  "separa.")

# ------------------------------------------------------------------------------------------ 4 clarity
E("No cloud-free satellite Kd490 in the 16 days up to this date.",
  "Nicio valoare Kd490 din satelit fără nori în cele 16 zile de până la această dată.")
T("Estimated Secchi depth {s:n} m on {d:d} (normal for the date {n:n} m); Kd490 {k:n} 1/m, {r:n} times normal.",
  "Adâncimea Secchi estimată: {s} m pe {d} (normal pentru această dată: {n} m); Kd490 {k} 1/m, de {r} ori valoarea "
  "normală.")
T("You could see about {x:n} m down here, much murkier than usual.",
  "Aici se vede până la aproximativ {x} m adâncime; apa este mult mai tulbure decât de obicei.")
T("You could see about {x:n} m down here, murkier than usual.",
  "Aici se vede până la aproximativ {x} m adâncime; apa este mai tulbure decât de obicei.")
T("You could see about {x:n} m down here, clearer than usual.",
  "Aici se vede până la aproximativ {x} m adâncime; apa este mai limpede decât de obicei.")
T("You could see about {x:n} m down here, about normal for the season.",
  "Aici se vede până la aproximativ {x} m adâncime, cam cât este normal pentru acest sezon.")
E("Kd490 says how fast blue light fades with depth.", "Kd490 arată cât de repede se stinge lumina albastră cu adâncimea.")
E("Secchi depth is estimated as 1.1 / Kd(PAR), tuned to NIMRD Secchi readings on this coast.",
  "Adâncimea Secchi se estimează ca 1,1 / Kd(PAR), calibrată pe măsurătorile Secchi ale INCDM de pe acest litoral.")
E("Dredging and coastal works make plumes; plan them outside storm and bloom periods.",
  "Dragajele și lucrările costiere produc pene de turbiditate; se recomandă planificarea lor în afara perioadelor cu "
  "furtuni și înfloriri algale.")
E("Murky water after storms is natural and clears in a few days.",
  "Apa tulbure după furtuni este un fenomen natural și se limpezește în câteva zile.")
E("Very turbid water clogs filter-feeding mussels; long episodes slow growth.",
  "Apa foarte tulbure înfundă branhiile midiilor, care se hrănesc prin filtrare; episoadele lungi le încetinesc "
  "creșterea.")
E("Turbid water changes where fish feed; it rarely matters for a single day.",
  "Apa tulbure schimbă locurile în care se hrănesc peștii; pentru o singură zi contează rareori.")
E("Hull cleaning and slipway works release fine sediment; contain it.",
  "Curățarea carenelor și lucrările pe cală eliberează sediment fin, care trebuie reținut.")
E("Seagrass and mussel beds need clear water; long murky periods are what matters.",
  "Pajiștile de iarbă de mare și bancurile de midii au nevoie de apă limpede; contează perioadele lungi cu apă "
  "tulbure.")
T("Kd490 {v:n} 1/m (CMEMS OC, L3 1 km or L4 when available; last cloud-free day {d:d}); Kd(PAR) {k:n}; "
  "z(log Kd) {z:n}.",
  "Kd490 {v} 1/m (CMEMS OC, L3 1 km sau L4 când există; ultima zi fără nori: {d}); Kd(PAR) {k}; z(log Kd) {z}.")
E("Secchi factor 1.1 instead of the open-water 1.7 (fit to INCDM 2018-2023 coastal Secchi).",
  "Factor Secchi 1,1 în loc de 1,7 cât se folosește în larg (ajustat pe măsurătorile Secchi costiere INCDM "
  "2018-2023).")

# ------------------------------------------------------------------------------------------ 5 nutrients
E("No trusted DIVAnd nutrient value at this point (6-year windows and 2000-2022 climatology both masked).",
  "Nicio valoare de încredere a nutrienților DIVAnd în acest punct (atât ferestrele de 6 ani, cât și climatologia "
  "2000-2022 sunt mascate).")
T("Summer DIN {a:t} µmol/L and PO4 {b:t} µmol/L in the DIVAnd seasonal climatology 2000-2022 (the 6-year windows "
  "are masked this close to the coast).",
  "DIN de vară {a} µmol/L și PO4 {b} µmol/L în climatologia sezonieră DIVAnd 2000-2022 (ferestrele de 6 ani sunt "
  "mascate atât de aproape de țărm).")
T("Summer DIN {a:t} µmol/L and PO4 {b:t} µmol/L in the 6-year window centred {y:i} (0 years before this date).",
  "DIN de vară {a} µmol/L și PO4 {b} µmol/L în fereastra de 6 ani centrată pe {y} (chiar anul acestei date).")
T("Summer DIN {a:t} µmol/L and PO4 {b:t} µmol/L in the 6-year window centred {y:i} (1 years before this date).",
  "DIN de vară {a} µmol/L și PO4 {b} µmol/L în fereastra de 6 ani centrată pe {y} (cu un an înainte de această "
  "dată).")
T("Summer DIN {a:t} µmol/L and PO4 {b:t} µmol/L in the 6-year window centred {y:i} ({o:c} years before this date).",
  "DIN de vară {a} µmol/L și PO4 {b} µmol/L în fereastra de 6 ani centrată pe {y} (cu {o} ani înainte de această "
  "dată).")
T("Worst ratio to the official marine threshold: {w:k} {r:n}.",
  "Cel mai mare raport față de pragul oficial pentru apele marine: {w} {r}.")
E("Nutrients are fertiliser for algae.", "Nutrienții sunt îngrășământ pentru alge.")
E("These numbers are from past ship samples, and they were above the official limit.",
  "Valorile provin din probe mai vechi, prelevate de pe nave, și erau peste limita oficială.")
E("These numbers are from past ship samples, and they were within the official limit.",
  "Valorile provin din probe mai vechi, prelevate de pe nave, și erau sub limita oficială.")
E("DIN = nitrate + nitrite + ammonium.", "DIN = nitrați + nitriți + amoniu.")
E("The ratio to the official threshold above 1 means too many nutrients.",
  "Un raport față de pragul oficial mai mare de 1 înseamnă prea mulți nutrienți.")
E("N:P above 16 means phosphorus limits algal growth.",
  "Un raport N:P peste 16 înseamnă că fosforul limitează creșterea algelor.")
E("No live nutrient data exist for this coast after about 2020.",
  "Pentru acest litoral nu există date curente de nutrienți de după aproximativ 2020.")
E("Wastewater operators and farms upstream are the levers.",
  "Pârghiile de acțiune sunt operatorii de ape uzate și fermele din amonte.")
E("Ask NIMRD for recent monitoring results.", "Rezultatele recente ale monitorizării pot fi cerute de la INCDM.")
E("EMODnet Chemistry DIVAnd Black Sea moving 6-year windows, surface, _L1 (relerr < 0.3) values; official statistic "
  "is the P75 of samples, not a gridded mean.",
  "EMODnet Chemistry DIVAnd Marea Neagră, ferestre mobile de 6 ani, suprafață, valori _L1 (relerr < 0,3); statistica "
  "oficială este P75 al probelor, nu o medie pe grilă.")
E("Model nitrate is about 2x the observed shelf median, so it is not shown.",
  "Nitrații din model sunt de circa 2 ori mediana observată pe platou, deci nu sunt afișați.")
E("Historical value, so the live rule chain does not apply.",
  "Valoare istorică, deci lanțul de reguli pentru date curente nu se aplică.")
E("Nutrients on this coast come mostly from the Danube (river load, partly human) and from wastewater outfalls; this "
  "value cannot separate them.",
  "Nutrienții de pe acest litoral vin mai ales din Dunăre (încărcătura fluvială, parțial de origine umană) și din "
  "gurile de evacuare a apelor uzate; această valoare nu le poate separa.")
E("The model nitrate and phosphate are not used (rule 1).", "Nitrații și fosfații din model nu sunt folosiți (regula 1).")

# ------------------------------------------------------------------------------------------ 6 bathing
T("No designated bathing water within 10 km (nearest: {n:k}, {k:n} km).",
  "Nicio zonă oficială de îmbăiere pe o rază de 10 km (cea mai apropiată: {n}, la {k} km).")
E("No official bathing site near this point.", "Nicio zonă oficială de îmbăiere în apropierea acestui punct.")
E("No classified season up to this date for the nearby sites.",
  "Zonele de îmbăiere din apropiere nu au niciun sezon clasificat până la această dată.")
_BW = {"Excellent": "excelentă", "Good": "bună", "Sufficient": "suficientă", "Poor": "slabă"}
for _c, _cr in _BW.items():
    T(f"Nearest official bathing site {{n:k}} ({{k:n}} km): {_c} in {{y:i}}.",
      f"Cea mai apropiată zonă oficială de îmbăiere: {{n}} ({{k}} km), apă de calitate {_cr} în {{y}}.")
    T(f"The nearest official beach, {{n:k}}, was rated {_c} for swimming in {{y:i}}.",
      f"Cea mai apropiată plajă oficială, {{n}}, a avut în {{y}} apă de îmbăiere de calitate {_cr}.")
E("Seasons before 2015 used an older scheme and are not comparable.",
  "Sezoanele dinainte de 2015 foloseau o schemă mai veche și nu sunt comparabile.")
T("Latest classified season is {y:i}.", "Ultimul sezon clasificat este {y}.")
E("The bathing season runs 1 June to 15 September.", "Sezonul de îmbăiere ține de la 1 iunie la 15 septembrie.")
E("The EU class uses four years of E. coli and intestinal enterococci tests. Excellent means very low faecal bacteria.",
  "Clasa UE se bazează pe patru ani de analize pentru E. coli și enterococi intestinali. Excelentă înseamnă foarte "
  "puține bacterii fecale.")
E("The EU class uses four years of E. coli and intestinal enterococci tests.",
  "Clasa UE se bazează pe patru ani de analize pentru E. coli și enterococi intestinali.")
E("Excellent means very low faecal bacteria.", "Excelentă înseamnă foarte puține bacterii fecale.")
T("Tourism: {x:l}", "Turism: {x}")
E("Sufficient or Poor means check nearby wastewater outfalls before the next season.",
  "Clasa Suficientă sau Slabă înseamnă că gurile de evacuare a apelor uzate din apropiere trebuie verificate înainte "
  "de sezonul următor.")
E("The class supports bathing; keep sewage overflows under control in storms.",
  "Clasa permite îmbăierea; deversările de canalizare trebuie ținute sub control în timpul furtunilor.")
E("EMODnet HA bathing waters layer, per-season 'status' field (matches the EEA 2025 factsheet: 2022 45/4, "
  "2023 34/15, 2024 41/8 Excellent/Good).",
  "Stratul EMODnet HA al apelor de îmbăiere, câmpul 'status' pe sezon (concordă cu fișa informativă AEM 2025: "
  "2022 45/4, 2023 34/15, 2024 41/8 Excelentă/Bună).")
E("Bathing class comes from lab tests for faecal bacteria over four seasons; it reflects sewage and runoff "
  "(pressure), not natural variability.",
  "Clasa apei de îmbăiere provine din analize de laborator pentru bacterii fecale pe patru sezoane; reflectă apele "
  "uzate și scurgerile de pe uscat (presiune), nu variabilitatea naturală.")

# ------------------------------------------------------------------------------------------ 7 biodiversity
T("Only 0 biological records since 2015 in this box: too little sampling to say anything.",
  "Nicio înregistrare biologică din 2015 în această casetă: prea puține probe pentru a trage vreo concluzie.")
T("Only 1 biological records since 2015 in this box: too little sampling to say anything.",
  "O singură înregistrare biologică din 2015 în această casetă: prea puține probe pentru a trage vreo concluzie.")
T("Only {n:c} biological records since 2015 in this box: too little sampling to say anything.",
  "Doar {n} înregistrări biologice din 2015 în această casetă: prea puține probe pentru a trage vreo concluzie.")
E("Almost nobody has sampled sea life here since 2015.",
  "Din 2015 aproape nimeni nu a mai prelevat probe de viețuitoare marine aici.")
T("0 of the {t:i} tracked non-indigenous species have OBIS records since 2015 near this point ({r:c} records in all).",
  "Niciuna dintre cele {t} specii neindigene urmărite nu are înregistrări OBIS din 2015 încoace în apropierea acestui "
  "punct ({r} înregistrări în total).")
T("1 of the {t:i} tracked non-indigenous species have OBIS records since 2015 near this point ({r:c} records in all).",
  "Una dintre cele {t} specii neindigene urmărite are înregistrări OBIS din 2015 încoace în apropierea acestui punct "
  "({r} înregistrări în total).")
T("{k:i} of the {t:i} tracked non-indigenous species have OBIS records since 2015 near this point ({r:c} records in "
  "all).",
  "{k} din cele {t} specii neindigene urmărite au înregistrări OBIS din 2015 încoace în apropierea acestui punct "
  "({r} înregistrări în total).")
T("New on the Romanian coast since 2015: {x:k}.", "Specii noi pe litoralul românesc din 2015: {x}.")
E("All are long-established invaders.", "Toate sunt specii invazive stabilite de mult timp.")
T("The point is inside a ports and shipyards zone, an entry route.",
  "Punctul se află într-o zonă portuară și de șantiere navale, o cale de intrare.")
T("The point is inside a ports zone, an entry route.", "Punctul se află într-o zonă portuară, o cale de intrare.")
T("The point is inside a shipyards zone, an entry route.",
  "Punctul se află într-o zonă de șantiere navale, o cale de intrare.")
E("Introduced species such as the rapa whelk or the comb jelly have been seen here.",
  "Aici au fost observate specii introduse, precum melcul rapana sau ctenoforul (meduza pieptene).")
E("No introduced species from our list have been reported here since 2015.",
  "Din 2015 nu a fost raportată aici nicio specie introdusă de pe lista noastră.")
E("OBIS occurrence records.", "Înregistrări de prezență din OBIS.")
E("Many records means many observers, not necessarily many animals, so we show presence and sampling effort, never "
  "a trend.",
  "Multe înregistrări înseamnă mulți observatori, nu neapărat multe animale, așa că arătăm prezența și efortul de "
  "eșantionare, niciodată o tendință.")
E("Ports and shipyards are the entry points; new sightings near a terminal mean checking ballast-water and "
  "hull-cleaning practice.",
  "Porturile și șantierele navale sunt punctele de intrare; observațiile noi lângă un terminal înseamnă că trebuie "
  "verificate practicile privind apele de balast și curățarea carenelor.")
E("Jellyfish and comb jellies affect beaches and fishing nets in late summer.",
  "Meduzele și ctenoforele afectează plajele și plasele de pescuit la sfârșitul verii.")
E("A new species has appeared since 2015.", "Din 2015 a apărut o specie nouă.")
T("OBIS /checklist for the box, split at {d:d}; {a:c} taxa since 2015 vs {b:c} before.",
  "OBIS /checklist pentru casetă, cu separare la {d}; {a} taxoni din 2015 față de {b} înainte.")
E("Presence-only, effort-biased.", "Doar date de prezență, influențate de efortul de eșantionare.")
E("Introduced species arrive mainly with ballast water and hull fouling (ports, shipyards).",
  "Speciile introduse sosesc mai ales cu apele de balast și cu organismele fixate pe carene (porturi, șantiere "
  "navale).")
E("Records reflect where people sampled, so absence is weak evidence.",
  "Înregistrările arată unde s-au prelevat probe, deci absența unei specii este o dovadă slabă.")

# ------------------------------------------------------------------------------------------ 8 drivers
_ACT = [("upwelling", "upwelling"), ("storm in the last 3 days", "furtună în ultimele 3 zile"),
        ("stratified water column", "coloană de apă stratificată")]
for _n in range(1, 4):
    for _c in combinations(_ACT, _n):
        E(", ".join(x[0] for x in _c), ", ".join(x[1] for x in _c))
T("Danube flow {r:n} times normal, {x:t}", "debitul Dunării de {r} ori cel normal, {x}")
T("Danube flow {r:n} times normal", "debitul Dunării de {r} ori cel normal")
T("Active now: {x:t}.", "Factori activi acum: {x}.")
E("No strong natural driver is active.", "Niciun factor natural puternic nu este activ acum.")
T("Danube at {r:n} times its normal flow; surface salinity {s:n} PSU.",
  "Debitul Dunării este de {r} ori cel normal; salinitatea la suprafață este {s} PSU.")
T("Danube at {r:n} times its normal flow; surface salinity {s:t} PSU.",
  "Debitul Dunării este de {r} ori cel normal; salinitatea la suprafață este {s} PSU.")
_DQ = {"more": "mai multă", "less": "mai puțină"}
_DE = {"so the sea here is saltier and clearer than usual.":
       "așa că marea este aici mai sărată și mai limpede decât de obicei.",
       "so expect fresher, murkier water.": "așa că apa va fi probabil mai puțin sărată și mai tulbure.",
       "close to normal.": "aproape de normal."}
for _q, _qr in _DQ.items():
    for _e, _er in _DE.items():
        T(f"The Danube is carrying {_q} water than usual ({{p:i}}% of normal), {_e}",
          f"Dunărea aduce {_qr} apă decât de obicei ({{p}}% din normal), {_er}")
E("close to normal.", "Aproape de normal.")
E("so the sea here is saltier and clearer than usual.", "Marea este aici mai sărată și mai limpede decât de obicei.")
E("so expect fresher, murkier water.", "Apa va fi probabil mai puțin sărată și mai tulbure.")
E("The Danube supplies most of the river water and nutrients here; its plume reaches Constanța about a month later.",
  "Dunărea aduce aici cea mai mare parte a apei dulci și a nutrienților; pana ei de apă ajunge la Constanța după "
  "aproximativ o lună.")
E("Winds cause upwelling; storms stir the seabed; summer heating layers the water.",
  "Vântul produce upwelling; furtunile răscolesc fundul mării; încălzirea de vară stratifică apa.")
E("Use drivers to anticipate, not to blame: high Danube flow means blooms are likely 2-6 weeks later; south-west "
  "winds in summer mean sudden cold water.",
  "Factorii naturali servesc la anticipare, nu la căutarea vinovaților: un debit mare al Dunării face probabile "
  "înfloririle algale după 2-6 săptămâni; vânturile din sud-vest aduc vara apă rece brusc.")
_DRV_EN = ("GloFAS v4 (Open-Meteo), 30-day mean vs DOY mean 1997-2025; upwelling index after physical.md P2 (88 % of "
           "events follow 3 days of S/SW wind); stratification as Ts - Tb from the physics model; storm p95 from "
           "Open-Meteo hourly Hs 2021-2025.")
_DRV_RO = ("GloFAS v4 (Open-Meteo), media pe 30 de zile față de media pe ziua din an 1997-2025; indicele de upwelling "
           "după physical.md P2 (88 % dintre evenimente urmează după 3 zile de vânt din S/SV); stratificarea ca "
           "Ts - Tb din modelul fizic; p95 pentru furtună din Hs orar Open-Meteo 2021-2025.")
E(_DRV_EN, _DRV_RO)
T(_DRV_EN + " Errors: {e:k}", _DRV_RO + " Erori (tehnice): {e}")
E("Drivers explain natural variability. They are shown beside every card and never count as damage.",
  "Factorii naturali explică variabilitatea naturală. Apar lângă fiecare fișă și nu sunt socotiți niciodată daune.")
E("Drivers explain natural variability.", "Factorii naturali explică variabilitatea naturală.")
E("They are shown beside every card and never count as damage.",
  "Apar lângă fiecare fișă și nu sunt socotiți niciodată daune.")

# ------------------------------------------------------------------------------------------ 9 acidification
E("No model pH for this date.", "Modelul nu are o valoare a pH-ului pentru această dată.")
T("Model surface pH {v:n} on {d:d}, {a:n} from the 1993-2022 normal for the date.",
  "pH-ul la suprafață din model: {v} pe {d}, abatere de {a} față de normala 1993-2022 pentru această dată.")
E("Sea water acidity is a little higher than usual.", "Aciditatea apei de mare este puțin mai mare decât de obicei.")
E("Sea water acidity is normal.", "Aciditatea apei de mare este normală.")
E("This is a model estimate only.", "Este doar o estimare din model.")
E("Lower pH means more acidic water, which makes it harder for mussels to build shells.",
  "Un pH mai mic înseamnă apă mai acidă, în care midiile își construiesc mai greu cochiliile.")
E("No measurements exist here; this is model output.", "Aici nu există măsurători; valoarea provine dintr-un model.")
T("Aquaculture: {x:l}", "Acvacultură: {x}")
E("Watch only.", "Doar de urmărit.")
E("Acidification is a slow, global trend; local dips come with upwelling or decaying blooms.",
  "Acidifierea este o tendință lentă, globală; scăderile locale ale pH-ului apar odată cu upwellingul sau cu "
  "descompunerea înfloririlor algale.")
T("BLKSEA BGC pH (total scale) {v:n}, clim mean {m:n}, sd {s:n}; no in-situ pH after the 1990s near Constanța.",
  "pH BLKSEA BGC (scara totală) {v}, media climatologică {m}, sd {s}; niciun pH măsurat in situ după anii 1990 "
  "lângă Constanța.")

# ------------------------------------------------------------------------------------------ units
for _w in ("mg/L", "mg/m³", "pH", "µmol/L", "PSU", "m³/s", "1/m", "°C", "m", "%"):
    E(_w, _w)
E("days", "zile")
E("records", "înregistrări")
E("sites", "situri")
E("ratio", "raport")
E("% of surface", "% din suprafață")

# ------------------------------------------------------------------------------------------ supporting indicators
# (card["supporting"]: name, value when it is text, note)
# temperature
E("Model surface temperature anomaly", "Anomalia temperaturii la suprafață în model")
E("Copernicus physics model vs its 1993-2022 reanalysis climatology",
  "modelul fizic Copernicus față de climatologia propriei reanalize 1993-2022")
E("Bottom temperature anomaly (P6)", "Anomalia temperaturii la fund (P6)")
T("model bottom level, forecast system corrected by -0.41 °C, vs reanalysis 1993-2022; value {v:t} °C",
  "nivelul de la fund al modelului, sistemul de prognoză corectat cu -0,41 °C, față de reanaliza 1993-2022; "
  "valoare {v} °C")
T("model bottom level, vs reanalysis 1993-2022; value {v:t} °C",
  "nivelul de la fund al modelului, față de reanaliza 1993-2022; valoare {v} °C")
E("Marine heatwave days this year", "Zile cu val de căldură marin în acest an")
T("1 events in {y:i} up to {d:d} (window from {w:d})",
  "un eveniment în {y} până la {d} (fereastră începând cu {w})")
T("{n:c} events in {y:i} up to {d:d} (window from {w:d})",
  "{n} evenimente în {y} până la {d} (fereastră începând cu {w})")
# oxygen
E("Hypoxia days (< 2 mg/L), last 30 days", "Zile cu hipoxie (< 2 mg/L), ultimele 30 de zile")
E("Days below 4 mg/L, last 30 days", "Zile sub 4 mg/L, ultimele 30 de zile")
T("D5C5 season test {y:i}: May-Sep P10 bottom O2", "Testul sezonier D5C5 {y}: P10 mai-sept. al oxigenului la fund")
T("pass on the concentration part (>= 5 mg/L); the 60 % saturation part needs bottom T and S and is not computed here",
  "îndeplinit pentru partea de concentrație (>= 5 mg/L); partea de saturație 60 % necesită T și S la fund și nu "
  "este calculată aici")
T("fail on the concentration part (>= 5 mg/L); the 60 % saturation part needs bottom T and S and is not computed here",
  "neîndeplinit pentru partea de concentrație (>= 5 mg/L); partea de saturație 60 % necesită T și S la fund și nu "
  "este calculată aici")
E("Surface O2 saturation (C2)", "Saturația în oxigen la suprafață (C2)")
T("{l:t}; flags > 120 % bloom, < 80 % respiration or upwelling",
  "{l}; semnale: > 120 % înflorire algală, < 80 % respirație sau upwelling")
# blooms
T("D5C2 proxy {y:i}: May-Sep P75 chl", "Aproximarea D5C2 {y}: P75 clorofilă-a mai-sept.")
T("fail vs {x:n} (coastal); satellite surface proxy of the official in-situ test",
  "neîndeplinit față de {x} (ape costiere); aproximare din satelit, la suprafață, a testului oficial in situ")
T("pass vs {x:n} (coastal); satellite surface proxy of the official in-situ test",
  "îndeplinit față de {x} (ape costiere); aproximare din satelit, la suprafață, a testului oficial in situ")
T("May-Sep mean chl {y:i}", "Media clorofilei-a mai-sept. {y}")
T("vs {x:n} (marine waters south)", "față de {x} (ape marine sud)")
T("Bloom days {y:i} (above p90)", "Zile de înflorire algală {y} (peste p90)")
T("June-September: {n:i}", "iunie-septembrie: {n}")
E("Eutrophication index (C3, simplified BEAST)", "Indicele de eutrofizare (C3, BEAST simplificat)")
_HEAT = {"high": "foarte bună", "good": "bună", "moderate": "moderată", "poor": "slabă", "bad": "proastă"}
_WORST = {"nutrients": "nutrienți", "direct": "efecte directe", "indirect": "efecte indirecte"}
for _h, _hr in _HEAT.items():
    for _w, _wr in _WORST.items():
        T(f"{_h}, driven by {_w}; ratios {{r:k}}. Nutrients from DIVAnd windows, O2 from the model: low-medium "
          "confidence",
          f"stare {_hr}, determinată de {_wr}; rapoarte {{r}}. Nutrienți din ferestrele DIVAnd, O2 din model: "
          "încredere scăzută-medie")
# clarity
T("{r:n} times normal; p90 {p:n}", "de {r} ori valoarea normală; p90 {p}")
E("Light reaching the seabed", "Lumina care ajunge la fundul mării")
T("depth {z:n} m (EMODnet); seagrass needs about 11 %, brown algae 0.5 %",
  "adâncime {z} m (EMODnet); iarba de mare are nevoie de aproximativ 11 %, algele brune de 0,5 %")
T("May-Sep P10 Secchi {y:i}", "P10 Secchi mai-sept. {y}")
T("meets the {x:n} m coastal GES value (satellite estimate)",
  "atinge valoarea GES costieră de {x} m (estimare din satelit)")
T("below the {x:n} m coastal GES value (satellite estimate)",
  "sub valoarea GES costieră de {x} m (estimare din satelit)")
E("Max wave height, last 3 days (P7)", "Înălțimea maximă a valurilor, ultimele 3 zile (P7)")
T("storm threshold p95 {x:t} m", "pragul de furtună p95 {x} m")
# nutrients
E("PO4 summer", "PO4 vara")
E("SI summer", "Si vara")
T("window centred {y:i}", "fereastră centrată pe {y}")
E("N:P (C5)", "N:P (C5)")
E("Redfield 16; above means P-limited", "Redfield 16; peste această valoare, limitare prin fosfor")
E("Si:N (C5)", "Si:N (C5)")
E("about 1 for diatoms; below favours flagellates",
  "aproximativ 1 pentru diatomee; sub această valoare sunt favorizate flagelatele")
E("DIN ratio to official marine threshold", "Raportul DIN față de pragul oficial pentru apele marine")
E("PO4 ratio to official marine threshold", "Raportul PO4 față de pragul oficial pentru apele marine")
E("Last bottle sample with phosphate within 30 km", "Ultima probă de apă cu fosfat pe o rază de 30 km")
E("EMODnet Chemistry; newer NIMRD data are not public", "EMODnet Chemistry; datele INCDM mai noi nu sunt publice")
# bathing
T("Sites within 10 km, season {y:i}", "Zone de îmbăiere pe o rază de 10 km, sezonul {y}")
T("History of {n:k}", "Istoricul zonei {n}")
E("2015 onwards (Directive 2006/7/EC)", "din 2015 încoace (Directiva 2006/7/CE)")
for _c, _cr in (("Excellent", "Excelentă"), ("Good", "Bună"), ("Sufficient", "Suficientă"), ("Poor", "Slabă")):
    E(_c, _cr)
    for _i in range(1, 5):
        T(f"{_i} - {_c}: {{n:i}}", f"{_i} - {_cr}: {{n}}")
    T(f"{{y:i}} {_c}", f"{{y}} {_cr}")
# biodiversity
E("Records since 2015 in the box (sampling effort, B7)", "Înregistrări din 2015 în casetă (efort de eșantionare, B7)")
T("1 taxa", "1 taxon")
T("{n:c} taxa", "{n} taxoni")
E("Non-indigenous species recorded since 2015", "Specii neindigene înregistrate din 2015")
E("established invaders unless listed as new", "specii invazive stabilite, dacă nu sunt marcate ca noi")
E("Gelatinous and bloom species recorded since 2015", "Specii gelatinoase și de înflorire înregistrate din 2015")
E("none", "niciuna")
# drivers
E("Danube discharge today (P3)", "Debitul Dunării azi (P3)")
T("spring {a:t} vs p75 {b:t}", "primăvara {a} față de p75 {b}")
E("Surface salinity", "Salinitatea la suprafață")
T("anomaly {a:t} vs 1993-2022", "anomalie {a} față de 1993-2022")
E("Upwelling (P2)", "Upwelling (P2)")
E("yes", "da")
E("no", "nu")
E("not in season (June-September only)", "în afara sezonului (doar iunie-septembrie)")
T("coast - offshore SST {x:t} °C", "SST țărm - larg {x} °C")
E("Stratification (P4)", "Stratificare (P4)")
E("surface minus bottom temperature, model", "temperatura la suprafață minus temperatura la fund, model")
E("Storm (P7)", "Furtună (P7)")
T("max Hs last 3 days; p95 {x:t} m", "Hs maxim în ultimele 3 zile; p95 {x} m")
E("Bottom salinity", "Salinitatea la fund")
E("above 18.5 means shelf-break water (rule 3)",
  "peste 18,5 înseamnă apă de la marginea platoului continental (regula 3)")
E("Sector pressure zones here", "Zonele de presiune ale sectoarelor aici")
E("unknown", "necunoscut")
E("data/zones/sector_zones.geojson", "data/zones/sector_zones.geojson")
for _c, _cr in (("Excellent", "Excelentă"), ("Good", "Bună"), ("Sufficient", "Suficientă"), ("Poor", "Slabă")):
    T(f"{{y:i}} {_c}, {{rest:t}}", f"{{y}} {_cr}, {{rest}}")
E("Kd490", "Kd490")
# HELCOM HEAT classes as bare notes ("high" is left to the confidence word, see report)
E("good", "bună")
E("moderate", "moderată")
E("poor", "slabă")
E("bad", "proastă")
# species lists (Latin names stay; indicators joins them in NIS order)
_NIS_N = ["Mnemiopsis leidyi", "Beroe ovata", "Rapana venosa", "Mya arenaria", "Anadara kagoshimensis",
          "Rhithropanopeus harrisii", "Acartia tonsa"]
_GEL = ["Aurelia aurita", "Rhizostoma pulmo", "Noctiluca scintillans"]
for _lst in (_NIS_N, _GEL):
    for _n in range(1, len(_lst) + 1):
        for _c in combinations(_lst, _n):
            E(", ".join(_c), ", ".join(_c))
