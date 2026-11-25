"""Viewer text in English and Romanian, in one place.

    from viewer.i18n import t, data, dt
    t("Water quality")                      -> "Calitatea apei" in RO, the key itself in EN
    t("{n} of 5 sectors", n=3)              -> keys are the English text; placeholders filled with str.format
    data(card["title"])                     -> text produced by marinekit (English): exact lookup, then the small
                                               pattern rules in DATA_PATTERNS; anything else stays in English
    dt(ts, "%d %b")                         -> dates with Romanian month names in RO

The language is st.session_state["lang"] ("en" default; ?lang=ro in the URL opens in Romanian). EN needs no
dictionary: the English key is the text. RO uses comma-below diacritics (ș ț), never the cedilla forms.
"""

from __future__ import annotations

import re

LANGS = {"en": "EN", "ro": "RO"}
_OVERRIDE: list = []  # set_lang_override("ro") for scripts and tests outside a Streamlit run


def set_lang_override(code: str | None):
    _OVERRIDE[:] = [code] if code in LANGS else []


def lang() -> str:
    if _OVERRIDE:
        return _OVERRIDE[0]
    try:
        import streamlit as st
        if not st.runtime.exists():
            return "en"
        v = st.session_state.get("lang", "en")
    except Exception:
        v = "en"
    return v if v in LANGS else "en"


def init_lang():
    """English by default; ?lang=ro in the URL starts in Romanian."""
    import streamlit as st
    ss = st.session_state
    if "lang" not in ss:
        q = st.query_params.get("lang")
        ss.lang = q if q in LANGS else "en"


def toggle_lang():
    import streamlit as st
    ss = st.session_state
    ss.lang = "ro" if lang() == "en" else "en"
    try:
        st.query_params["lang"] = ss.lang
    except Exception:
        pass
    ss.map_nonce = ss.get("map_nonce", 0) + 1  # rebuild the maps with the new legend and tooltips


def t(_key: str, /, **kw) -> str:
    out = RO.get(_key, _key) if lang() == "ro" else _key
    if kw:
        try:
            return out.format(**kw)
        except (KeyError, IndexError, ValueError):
            return _key.format(**kw)
    return out


MONTHS = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august", "septembrie",
          "octombrie", "noiembrie", "decembrie"]
MONTHS_SHORT = ["ian.", "feb.", "mar.", "apr.", "mai", "iun.", "iul.", "aug.", "sept.", "oct.", "nov.", "dec."]


def dt(ts, fmt: str) -> str:
    """strftime with Romanian month names in RO (%b and %B)."""
    import pandas as pd
    ts = pd.Timestamp(ts)
    if lang() == "ro":
        fmt = fmt.replace("%B", MONTHS[ts.month - 1]).replace("%b", MONTHS_SHORT[ts.month - 1])
    return ts.strftime(fmt)


def num(s: str) -> str:
    """Decimal comma for a formatted number in RO ('13.4' -> '13,4'); thousands commas become dots."""
    if lang() != "ro" or not isinstance(s, str):
        return s
    return re.sub(r"(?<=\d)[.,](?=\d)", lambda m: "," if m.group(0) == "." else ".", s)


_COMPASS = {"W": "V"}


def compass(s: str) -> str:
    """N, NNW, SW ... -> Romanian (west is V)."""
    if lang() != "ro" or not isinstance(s, str):
        return s
    return "".join(_COMPASS.get(ch, ch) for ch in s) if re.fullmatch(r"[NSEW]{1,3}", s) else s


# ------------------------------------------------------------------------------------------ data-side text
def data(s):
    """Translate a string produced by marinekit (card titles, short labels, stable sentence templates).
    Unknown text is returned unchanged (English) rather than guessed."""
    if lang() != "ro" or not isinstance(s, str) or not s:
        return s
    if s in DATA_RO:
        return DATA_RO[s]
    for pat, rep in DATA_PATTERNS:
        m = pat.fullmatch(s)
        if m:
            return rep(m) if callable(rep) else m.expand(rep)
    from viewer import i18n_data
    i18n_data.load()
    return i18n_data.tr(s)


def data_md(s):
    """Markdown produced by marinekit (Methods texts), paragraph by paragraph."""
    if lang() != "ro" or not isinstance(s, str) or not s:
        return s
    from viewer import i18n_data
    i18n_data.load()
    return i18n_data.md(s)


DATA_RO: dict[str, str] = {}
DATA_PATTERNS: list = []

# ------------------------------------------------------------------------------------------ Romanian
RO: dict[str, str] = {}
RO.update({
    # status and origin
    "Normal": "Normal", "Watch": "Atenție", "Alert": "Alertă", "No data": "Fără date",
    "normal": "normal", "watch": "atenție", "alert": "alertă", "no data": "fără date",
    "measured": "măsurat", "satellite": "satelit", "model": "model", "model (reanalysis)": "model (reanaliză)",
    "derived": "derivat", "reference": "referință", "unknown": "necunoscut",
    # sectors
    "Ports and logistics": "Porturi și logistică", "Shipyards and marine engineering": "Șantiere navale și inginerie marină",
    "Coastal and marine tourism": "Turism costier și marin", "Fishing": "Pescuit", "Aquaculture": "Acvacultură",
    "Ports": "Porturi", "Shipyards": "Șantiere", "Tourism": "Turism",
    # profiles
    "General public": "Public larg", "Student": "Student", "Sector stakeholder": "Actor din sector",
    "Researcher": "Cercetător", "Visitor": "Vizitator",
    "Public": "Public", "Sector": "Sector", "Research": "Cercetare",
    "Plain language, the main layers only.": "Limbaj simplu, doar straturile principale.",
    "Short explanations of what each measurement means.": "Explicații scurte despre ce înseamnă fiecare măsurătoare.",
    "Starts on your sector's zones and the risks there.": "Pornește de la zonele sectorului tău și riscurile de acolo.",
    "Dataset IDs, QC flags and uncertainty numbers shown.": "Se afișează ID-urile seturilor de date, indicatorii QC și incertitudinile.",
    "Physical (temperature, salinity, waves, currents)": "Fizic (temperatură, salinitate, valuri, curenți)",
    "Chemical (oxygen, nutrients, pH)": "Chimic (oxigen, nutrienți, pH)",
    "Biological (chlorophyll, blooms, species)": "Biologic (clorofilă, înfloriri algale, specii)",
    "physical": "fizic", "chemical": "chimic", "biological": "biologic",
    "See conditions now": "Vezi condițiile de acum", "See long-term change": "Vezi schimbările pe termen lung",
    "Compare data sources": "Compară sursele de date", "Check risks in my area": "Verifică riscurile din zona mea",
    # seasons
    "summer": "vară", "winter": "iarnă", "Summer": "Vară", "Winter": "Iarnă", "auto": "automat",
    # pages and rail
    "Overview": "Prezentare", "Water": "Apă", "Seabed": "Fund marin", "Pressures": "Presiuni", "Methods": "Metode",
    "Water quality": "Calitatea apei", "Coast and seabed": "Coastă și fund marin", "Data and methods": "Date și metode",
    "Light": "Deschis", "Dark": "Închis",
    # variables and layers
    "Sea surface temperature": "Temperatura la suprafața mării", "Sea temperature anomaly": "Anomalia temperaturii mării",
    "Chlorophyll-a (algae)": "Clorofilă-a (alge)", "Water clarity (Kd490)": "Transparența apei (Kd490)",
    "Model water temperature (surface)": "Temperatura apei din model (suprafață)",
    "Model oxygen (surface)": "Oxigen dizolvat din model (suprafață)",
    "Model oxygen near the seabed": "Oxigen dizolvat din model, lângă fundul mării",
    "Temperature": "Temperatură", "Salinity": "Salinitate", "Oxygen, seabed": "Oxigen, la fund",
    "Chlorophyll-a": "Clorofilă-a", "Water clarity": "Transparența apei", "Nutrients": "Nutrienți",
    "Acidity (pH)": "Aciditate (pH)", "Waves": "Valuri", "Currents": "Curenți", "Wind": "Vânt", "Depth": "Adâncime",
    "Natura 2000 protected sites": "Situri protejate Natura 2000", "Natura 2000 site": "Sit Natura 2000",
    "Bathing water": "Apă de îmbăiere",
})
RO.update({
    # shell: rail, switches, place picker, profile menu, selection header, edges
    "Switch to the light theme": "Comută pe tema luminoasă", "Switch to the dark theme": "Comută pe tema întunecată",
    "Station: {name}": "Stație: {name}", " (under QC)": " (în verificare QC)", " (shore station)": " (stație de țărm)",
    "Buoy: {name}": "Geamandură: {name}", "Buoy {name}": "Geamandura {name}",
    "Buoy: {name} (offshore, data to {when})": "Geamandură: {name} (larg, date până în {when})",
    "Zone: {name}": "Zonă: {name}", "{name} zones": "Zone {name}", "Overlap area: {name}": "Zonă de suprapunere: {name}",
    "Place": "Loc", "Search a beach, port, station or zone": "Caută o plajă, un port, o stație sau o zonă",
    "Search another place": "Caută alt loc",
    "Season for pressure zones": "Sezonul pentru zonele de presiune", "From date ({season})": "După dată ({season})",
    "Summer = bathing season, 1 June to 15 September: tourism zones are on.":
        "Vara = sezonul de îmbăiere, 1 iunie - 15 septembrie: zonele de turism sunt incluse.",
    "Edges": "Margini", "Soft": "Difuze", "Sharp": "Precise", "Soft edges": "Margini difuze", "Sharp edges": "Margini precise",
    "Soft: zone limits fade out, because they are approximate. Sharp: the 500 m grid cells and the zone outlines. "
    "Both show the same count of overlapping sectors.":
        "Difuze: limitele zonelor se estompează, pentru că sunt aproximative. Precise: celulele grilei de 500 m și "
        "contururile zonelor. Ambele arată același număr de sectoare suprapuse.",
    "Viewing as: {who}": "Vizualizare ca: {who}", "Who are you?": "Cine ești?", "Focus": "Domeniu",
    "What do you want to do?": "Ce vrei să faci?", "Apply": "Aplică",
    "Start the questionnaire again": "Reia chestionarul",
    "{n} of 5 sectors": "{n} din 5 sectoare", "outside the sector zones": "în afara zonelor sectoarelor",
    "Sectors here: {names}": "Sectoare aici: {names}", "Inside Natura 2000: {names}": "În Natura 2000: {names}",
    "ports": "porturi", "shipyards": "șantiere navale", "tourism": "turism", "fishing": "pescuit",
    "aquaculture": "acvacultură",
    # viewer-made place names (real names such as Constanța or Mangalia stay as they are)
    "Constanța offshore": "Larg Constanța", "Port of Constanța approaches": "Accesul în Portul Constanța",
    "Constanța - Agigea shipyards": "Șantierele Constanța - Agigea", "Mamaia beach waters": "Apele plajei Mamaia",
    "Shelf fishing grounds": "Zone de pescuit pe platou", "Mangalia / 2 Mai": "Mangalia / 2 Mai",
    "Clicked point": "Punct ales pe hartă",
})

# card titles, evidence and confidence words from marinekit.indicators (English on the data side)
DATA_RO.update({
    "Water temperature": "Temperatura apei", "Oxygen": "Oxigen", "Eutrophication and blooms": "Eutrofizare și înfloriri algale",
    "Water clarity": "Transparența apei", "Nutrients (historical)": "Nutrienți (istoric)", "Bathing water": "Apă de îmbăiere",
    "Biodiversity evidence": "Dovezi de biodiversitate", "Drivers (natural variability)": "Factori naturali (variabilitate)",
    "Acidification (watch only)": "Acidifiere (doar urmărire)",
    "measured": "măsurat", "satellite": "satelit", "model": "model", "reanalysis": "reanaliză", "derived": "derivat",
    "high": "ridicată", "medium": "medie", "low": "scăzută",
    "official": "oficial", "mapped": "cartografiat", "assumed": "presupus",
    "Still being computed for this place.": "Încă se calculează pentru acest loc.",
    "Data for this place is still downloading; open this again in a minute.":
        "Datele pentru acest loc încă se descarcă; revino peste un minut.",
    "No anomaly, so no cause to assign.": "Nicio anomalie, deci nicio cauză de atribuit.",
    "The sea has less microscopic algae than usual for this week.":
        "Marea are mai puține alge microscopice decât de obicei în această săptămână.",
    "The sea has more microscopic algae than usual for this week.":
        "Marea are mai multe alge microscopice decât de obicei în această săptămână.",
    "Sea water acidity is normal. This is a model estimate only.":
        "Aciditatea apei de mare este normală. Este doar o estimare din model.",
    "Oxygen near the seabed is low; sensitive animals may be stressed. This comes from a computer model, not a measurement.":
        "Oxigenul de lângă fundul mării este scăzut; animalele sensibile pot fi afectate. Valoarea vine dintr-un model, "
        "nu dintr-o măsurătoare.",
    "Nutrients are fertiliser for algae. These numbers are from past ship samples, and they were within the official limit.":
        "Nutrienții sunt îngrășământ pentru alge. Valorile provin din probe vechi prelevate de nave și erau sub limita oficială.",
    "Introduced species such as the rapa whelk or the comb jelly have been seen here.":
        "Aici au fost observate specii introduse, precum melcul rapana sau ctenoforul (meduza pieptene).",
    "Drivers explain natural variability. They are shown beside every card and never count as damage.":
        "Factorii naturali explică variabilitatea naturală. Apar lângă fiecare card și nu sunt socotiți niciodată daune.",
})
_WARM = {"warmer": "mai caldă", "colder": "mai rece"}
_IN = {"within": "în intervalul normal", "outside": "în afara intervalului normal"}
_CLEAR = {"clearer": "mai limpede", "murkier": "mai tulbure"}
_CLASS = {"Excellent": "Excelent", "Good": "Bun", "Sufficient": "Suficient", "Poor": "Slab"}
_LESSMORE = {"less": "un debit mai mic", "more": "un debit mai mare"}
DATA_PATTERNS.extend([
    (re.compile(r"The sea here is ([\d.]+) °C, ([\d.]+) °C (warmer|colder) than usual for this time of year\. "
                r"That is (within|outside) the normal range\."),
     lambda m: f"Marea are aici {num(m[1])} °C, cu {num(m[2])} °C {_WARM[m[3]]} decât de obicei în această perioadă "
               f"a anului. Valoarea este {_IN[m[4]]}."),
    (re.compile(r"You could see about ([\d.]+) m down here, (clearer|murkier) than usual\."),
     lambda m: f"Aici se vede până la aproximativ {num(m[1])} m adâncime, apa fiind {_CLEAR[m[2]]} decât de obicei."),
    (re.compile(r"The nearest official beach, (.+), was rated (Excellent|Good|Sufficient|Poor) for swimming in (\d{4})\."),
     lambda m: f"Cea mai apropiată plajă oficială, {m[1]}, a primit calificativul {_CLASS[m[2]]} pentru îmbăiere "
               f"în {m[3]}."),
    (re.compile(r"The Danube is carrying (less|more) water than usual \((\d+)% of normal\), so the sea here is "
                r"(saltier and clearer|fresher and murkier) than usual\."),
     lambda m: f"Dunărea are {_LESSMORE[m[1]]} decât de obicei ({m[2]}% din normal), așa că marea este aici "
               f"{'mai sărată și mai limpede' if m[3].startswith('saltier') else 'mai dulce și mai tulbure'} "
               "decât de obicei."),
])

# Overview, layer menu, questionnaire
RO.update({
    "Gridded layer": "Strat în grilă",
    "No gridded layer": "Fără strat în grilă",
    "Use Copernicus map tiles (faster, online only)": "Folosește dalele de hartă Copernicus (mai rapid, doar online)",
    "Measurements": "Măsurători",
    "Context": "Context",
    "Waves, currents and wind": "Valuri, curenți și vânt",
    "In-situ buoys and stations": "Geamanduri și stații in situ",
    "Pressure overlap (number of sectors, 1-5)": "Suprapunerea presiunilor (număr de sectoare, 1-5)",
    "Sector zones (buffers)": "Zonele sectoarelor (zone tampon)",
    "Sector activities (ports, beaches, farms...)": "Activitățile sectoarelor (porturi, plaje, ferme...)",
    "Bathymetry (EMODnet depth)": "Batimetrie (adâncime EMODnet)",
    "Waves (height, direction, period)": "Valuri (înălțime, direcție, perioadă)",
    "Currents (speed and direction)": "Curenți (viteză și direcție)",
    "Wind (speed and direction)": "Vânt (viteză și direcție)",
    "Zones and activities: only {sector}": "Zone și activități: doar {sector}",
    "Map layers and season": "Straturi și sezon",
    "Computing the health signs for this place.": "Se calculează semnele de sănătate pentru acest loc.",
    "The first time takes up to a minute; after that it is cached. The rows appear by themselves.": "Prima dată durează până la un minut; apoi rezultatul este păstrat. Rândurile apar singure.",
    "Water quality analysis": "Analiza calității apei",
    "vs. usual for {day}, cards from the {src}": "față de valorile obișnuite pentru {day}, fișe din {src}",
    "indicators module": "modulul de indicatori",
    "viewer placeholder": "date provizorii ale aplicației",
    "Viewing as": "Vizualizare ca",
    "early {month}": "începutul lui {month}",
    "mid {month}": "mijlocul lui {month}",
    "late {month}": "sfârșitul lui {month}",
    "{n} of {m} health signs are normal for {when}.": "{n} din {m} semne de sănătate sunt normale pentru {when}.",
    "Amber means outside the usual seasonal range or close to a limit; red means clearly unusual. Each row says how the value is measured.": "Galben înseamnă în afara intervalului obișnuit pentru sezon sau aproape de o limită; roșu înseamnă clar neobișnuit. Fiecare rând arată cum este măsurată valoarea.",
    "your sector": "sectorul tău",
    "{n} of 5 sectors share this water: {secs}.": "{n} din 5 sectoare folosesc această apă: {secs}.",
    "This point is outside the five sectors' pressure zones.": "Acest punct este în afara zonelor de presiune ale celor cinci sectoare.",
    "{k} sign to check before planning {sector} work: {flagged}.": "{k} semn de verificat înainte de a planifica activități de {sector}: {flagged}.",
    "{k} signs to check before planning {sector} work: {flagged}.": "{k} semne de verificat înainte de a planifica activități de {sector}: {flagged}.",
    "Nothing flagged for {sector} work here today.": "Nimic semnalat azi aici pentru activități de {sector}.",
    "{c} cards: {a} normal, {b} watch, {d} alert": "{c} fișe: {a} normal, {b} atenție, {d} alertă",
    ", {e} no data.": ", {e} fără date.",
    "Natural-vs-pressure rule chain applied. Coastal buoys EUXRoCB0x and station 15480 excluded (no QC). Model nitrate and phosphate not used.": "Lanțul de reguli natural sau presiune aplicat. Geamandurile costiere EUXRoCB0x și stația 15480 excluse (fără QC). Nitrații și fosfații din model nu sunt folosiți.",
    "Something is unusual here today: {what}.": "Ceva este neobișnuit aici azi: {what}.",
    "Mostly normal today. One thing to keep an eye on.": "În mare, normal azi. Un singur lucru de urmărit.",
    "Mostly normal today. {k} things to keep an eye on.": "În mare, normal azi. {k} lucruri de urmărit.",
    "Everything we track looks normal for the season.": "Tot ce urmărim pare normal pentru sezon.",
    "To watch: {flagged}. Not an alarm.": "De urmărit: {flagged}. Nu este o alarmă.",
    "Scientists would check these first.": "Specialiștii ar verifica acestea mai întâi.",
    "Compared with the usual values for {when}.": "Comparat cu valorile obișnuite pentru {when}.",
    "Threshold: {x}": "Prag: {x}",
    "{d} km away": "la {d} km",
    "confidence {c}": "încredere {c}",
    "high": "ridicată",
    "medium": "medie",
    "low": "scăzută",
    "Close details: {x}": "Închide detaliile: {x}",
    "Open details: {x}": "Deschide detaliile: {x}",
    "Means": "Înseamnă",
    "Source": "Sursă",
    "not given": "nespecificat",
    "Open the chart in Water quality": "Deschide graficul în Calitatea apei",
    "{d} today": "{d} azi",
    "Today": "Azi",
    "{d} forecast": "{d} prognoză",
    "Date": "Data",
    " (today)": " (azi)",
    " (forecast)": " (prognoză)",
    "Which sector do you work in?": "În ce sector lucrezi?",
    "What is your main focus?": "Care este domeniul tău principal?",
    "Black Sea Health Viewer": "Starea de sănătate a Mării Negre",
    "Romanian coast: sea conditions, long-term change, and the pressures from five blue-economy sectors. Three quick questions set up the view for you.": "Litoralul românesc: condițiile mării, schimbările pe termen lung și presiunile din cinci sectoare ale economiei albastre. Trei întrebări rapide pregătesc afișarea pentru tine.",
    "Step {step} of 3": "Pasul {step} din 3",
    "Back": "Înapoi",
    "Skip, use the general view": "Sari peste, folosește vederea generală",
    "You can change this at any time with the profile control at the top of the page.": "Poți schimba oricând asta din controlul de profil din partea de sus a paginii.",
})

# Pressures, map legends and tooltips, Methods
RO.update({
    "Full-screen map": "Hartă pe tot ecranul",
    "Exit full screen": "Ieșire din ecran complet",
    "Basemap (matches the theme)": "Hartă de bază (după temă)",
    "Ocean basemap (bathymetry)": "Hartă de bază oceanică (batimetrie)",
    "Satellite image": "Imagine satelitară",
    "{origin}, Copernicus map tiles": "{origin}, plăci de hartă Copernicus",
    "{title}: {a} not published yet, showing {g}, the latest day.": "{title}: {a} nu este încă publicat, se afișează {g}, ultima zi disponibilă.",
    "{title}: no data for {a}, showing the nearest day, {g}.": "{title}: fără date pentru {a}, se afișează cea mai apropiată zi, {g}.",
    "Depth (EMODnet DTM)": "Adâncime (EMODnet DTM)",
    "Depth, m": "Adâncime, m",
    "Scale stretched for the shelf (0-200 m). Lines: depth contours. Needs the internet (EMODnet map service).": "Scară întinsă pentru platforma continentală (0-200 m). Linii: izobate. Necesită internet (serviciul de hărți EMODnet).",
    "Depth contours (EMODnet)": "Izobate (EMODnet)",
    "{n} of 5 sectors overlap ({season})": "{n} din 5 sectoare se suprapun ({season})",
    "Pressure overlap ({season})": "Suprapunerea presiunilor ({season})",
    "Pressure overlap, soft edges ({season})": "Suprapunerea presiunilor, margini estompate ({season})",
    "Overlap lines (1, 2, 3 sectors)": "Linii de suprapunere (1, 2, 3 sectoare)",
    "Edge of 1+ sector overlapping": "Limita zonei cu cel puțin 1 sector",
    "Edge of 2+ sectors overlapping": "Limita zonei cu cel puțin 2 sectoare suprapuse",
    "Edge of 3+ sectors overlapping": "Limita zonei cu cel puțin 3 sectoare suprapuse",
    "{n} of 5 sectors overlap here ({season}, 500 m grid)": "{n} din 5 sectoare se suprapun aici ({season}, grilă de 500 m)",
    "Exact count on hover": "Numărul exact la trecerea cursorului",
    "{sector} zones, soft": "Zonele {sector}, estompate",
    "Sector zones (outlines of assumed ones)": "Zonele sectoarelor (contur pentru cele presupuse)",
    "Sector zones": "Zonele sectoarelor",
    "Sector activities": "Activitățile sectoarelor",
    "buffer": "zonă tampon",
    "confidence": "încredere",
    "official": "oficial",
    "mapped": "cartografiat",
    "assumed": "presupus",
    "open source": "deschide sursa",
    "Code": "Cod",
    "In-situ platforms": "Platforme in situ",
    "under QC (not trusted yet)": "în control de calitate (încă nesigur)",
    "context only": "doar pentru context",
    "trusted": "de încredere",
    "not assessed": "neevaluat",
    "last data": "ultimele date",
    "status": "stare",
    "Selected: {name}": "Selectat: {name}",
    "{n} note": "{n} notă",
    "{n} notes": "{n} note",
    "Hide legend": "Ascunde legenda",
    "Legend": "Legendă",
    "Copernicus map tiles in the service's own colours and range (the grid is not in the cache, so the viewer cannot set them).": "Plăci de hartă Copernicus în culorile și intervalul serviciului (grila nu este în cache, deci aplicația nu le poate seta).",
    "log scale": "scară logaritmică",
    "Sectors overlapping, of 5 ({season})": "Sectoare suprapuse, din 5 ({season})",
    "where 1, 2, 3 sectors begin": "unde încep 1, 2, 3 sectoare",
    "Hover for the exact count (500 m grid).": "Treceți cursorul pentru numărul exact (grilă de 500 m).",
    "Sectors": "Sectoare",
    "dashed = location assumed": "linie întreruptă = locație presupusă",
    "In-situ": "In situ",
    "trusted or not assessed": "de încredere sau neevaluat",
    "under QC, context only, or old": "în control de calitate, doar context sau vechi",
    "Copernicus map tiles could not be reached; showing the local layer instead.": "Plăcile de hartă Copernicus nu sunt accesibile; se afișează stratul local.",
    "Gaps are clouds: this satellite layer is not gap-filled.": "Golurile sunt nori: acest strat satelitar nu are golurile completate.",
    "Below about 150 m the Black Sea has no oxygen at all (natural, permanent). Red offshore is that deep water, not pollution. Model bottom oxygen near the coast is indicative only.": "Sub aproximativ 150 m, Marea Neagră nu are deloc oxigen (natural, permanent). Roșul din larg este această apă adâncă, nu poluare. Oxigenul de la fund din model, lângă coastă, este doar orientativ.",
    "{title}: still downloading for {day}; it will appear on the next refresh.": "{title}: încă se descarcă pentru {day}; va apărea la următoarea reîmprospătare.",
    "{title}: the grid could not be downloaded, showing Copernicus map tiles instead (online only).": "{title}: grila nu a putut fi descărcată, se afișează plăcile de hartă Copernicus (doar online).",
    "Soft edges show that zone limits are approximate; the colour is still the number of overlapping sectors.": "Marginile estompate arată că limitele zonelor sunt aproximative; culoarea este tot numărul de sectoare suprapuse.",
    "Waves, currents and wind: the vector module is not ready yet.": "Valuri, curenți și vânt: modulul vectorial nu este încă gata.",
    "{kind} layer failed: {err}": "Stratul {kind} a eșuat: {err}",
    "Conditions (gridded, with date)": "Condiții (grilă, cu dată)",
    "Surface currents": "Curenți de suprafață",
    "Wind at 10 m": "Vânt la 10 m",
    "Significant wave height": "Înălțimea semnificativă a valurilor",
    "Current speed": "Viteza curentului",
    "Wind speed": "Viteza vântului",
    "Peak period": "Perioada de vârf",
    "Arrow length = peak period": "Lungimea săgeții = perioada de vârf",
    "short = wind sea, long = swell": "scurtă = valuri de vânt, lungă = hulă",
    "Dot = slower than 0.02 m/s (no clear direction)": "Punct = sub 0,02 m/s (fără direcție clară)",
    "Disc colour = wind speed at reference points (no gridded wind source)": "Culoarea discului = viteza vântului în punctele de referință (nu există o grilă de vânt)",
    "Arrows point where the waves travel to.": "Săgețile arată încotro se deplasează valurile.",
    "Arrows point where the water flows to.": "Săgețile arată încotro curge apa.",
    "Arrows point where the wind blows to.": "Săgețile arată încotro bate vântul.",
    "Click the sea for values.": "Faceți clic pe mare pentru valori.",
    " daily mean": " medie zilnică",
    "No health signs computed here.": "Nu s-au calculat semne de sănătate aici.",
    "Nothing to check yet.": "Nimic de verificat încă.",
    "All {n} signs with data are normal.": "Toate cele {n} semne cu date sunt normale.",
    "All {n} signs normal.": "Toate cele {n} semne sunt normale.",
    "No data for {names}.": "Fără date pentru: {names}.",
    "Nothing flagged.": "Nimic semnalat.",
    "{names} on alert": "{names} în alertă",
    "{names} on watch": "{names} în atenție",
    "Check the card on the Overview page.": "Verificați fișa în pagina Prezentare.",
    "Rule chain:": "Lanțul de reguli:",
    "Tourism zones are switched off outside the bathing season (1 June - 15 September).": "Zonele de turism sunt dezactivate în afara sezonului estival (1 iunie - 15 septembrie).",
    "Site {i}: {name}": "Situl {i}: {name}",
    "summer, tourism on (1 Jun - 15 Sep)": "vară, turism activ (1 iun. - 15 sept.)",
    "winter, tourism off": "iarnă, turism inactiv",
    "Cells (500 m)": "Celule (500 m)",
    "3+ overlap": "Suprapunere 3+",
    "Highest": "Maxim",
    "of 5": "din 5",
    "No zones of this sector in this season.": "Acest sector nu are zone în acest sezon.",
    "Pressures this sector causes": "Presiunile cauzate de acest sector",
    "Show the pressures this sector causes": "Arată presiunile cauzate de acest sector",
    "soft edges: zone limits fade out over 1-3 km because they are approximate; inside the zones the colour is the exact count": "margini estompate: limitele zonelor se estompează pe 1-3 km pentru că sunt aproximative; în interiorul zonelor culoarea este numărul exact",
    "counted in each 500 m cell": "numărat în fiecare celulă de 500 m",
    "Map: number of the 5 sectors whose zones overlap (no weights), {how}. Dashed outlines are assumed locations, to confirm with NIMRD.": "Harta: numărul celor 5 sectoare ale căror zone se suprapun (fără ponderi), {how}. Contururile întrerupte sunt locații presupuse, de confirmat cu INCDM.",
    "Main sites": "Situri principale",
    "No sites found for this sector.": "Nu s-au găsit situri pentru acest sector.",
    "computing": "se calculează",
    "near {place}": "lângă {place}",
    "{n} sectors overlap": "{n} sectoare se suprapun",
    "Open site {name}": "Deschide situl {name}",
    "Close site {name}": "Închide situl {name}",
    "Still computing the health signs for this site.": "Semnele de sănătate pentru acest sit încă se calculează.",
    "Check": "De verificat",
    "Full report for this site": "Raport complet pentru acest sit",
    "Temp.": "Temp.",
    "Oxygen": "Oxigen",
    "Blooms": "Alge",
    "Clarity": "Transp.",
    "Nutr.": "Nutr.",
    "Bathing": "Îmbăiere",
    "Life": "Viață",
    "Drivers": "Factori",
    "pH": "pH",
    "Ship traffic and underwater noise": "Trafic naval și zgomot subacvatic",
    "Oil and fuel spills, ballast water (new non-native species)": "Scurgeri de petrol și combustibil, apă de balast (noi specii alohtone)",
    "Dredging of channels: sediment plumes, murkier water": "Dragarea canalelor: pene de sediment, apă mai tulbure",
    "Contaminants: antifouling paint, metals, hydrocarbons": "Contaminanți: vopsea antivegetativă, metale, hidrocarburi",
    "Hull cleaning and antifouling paints (copper, legacy TBT)": "Curățarea carenelor și vopsele antivegetative (cupru, TBT istoric)",
    "Metals and hydrocarbons in sediments": "Metale și hidrocarburi în sedimente",
    "Coastal works, sea walls and beach nourishment change seabed habitats": "Lucrările costiere, digurile și înnisipările plajelor schimbă habitatele de pe fundul mării",
    "Dredging and offshore construction": "Dragare și construcții în larg",
    "Wastewater load peaks in summer (bathing-water quality)": "Încărcarea cu ape uzate atinge vârful vara (calitatea apei de îmbăiere)",
    "Litter on beaches and at sea": "Deșeuri pe plaje și în mare",
    "Beach nourishment and coastal protection works": "Înnisiparea plajelor și lucrări de protecție costieră",
    "Boat traffic and anchoring near the shore": "Trafic de ambarcațiuni și ancorare lângă țărm",
    "Removal of target species (sprat, turbot, rapa whelk)": "Extragerea speciilor țintă (șprot, calcan, rapană)",
    "Bottom dredging for rapa whelk disturbs the seabed": "Dragarea de fund pentru rapană deranjează fundul mării",
    "Bycatch of dolphins and harbour porpoise in turbot gillnets": "Capturi accidentale de delfini și marsuini în plasele pentru calcan",
    "Lost nets (ghost fishing)": "Plase pierdute (pescuit fantomă)",
    "Organic matter under mussel longlines raises local oxygen demand": "Materia organică de sub liniile de midii crește consumul local de oxigen",
    "Farms are also receptors: blooms, toxins and low oxygen hit them first": "Fermele sunt și receptori: înfloririle algale, toxinele și oxigenul scăzut le afectează primele",
    "Spread of non-native species with seed stock": "Răspândirea speciilor alohtone odată cu materialul de populare",
    "Every value in this viewer shows where it comes from: **measured** (buoys, samples), **satellite** (a measured proxy for the surface), or **model** (computed, fills gaps, gives forecasts).": "Fiecare valoare din aplicație arată de unde provine: **măsurat** (geamanduri, probe), **satelit** (un indicator măsurat pentru suprafață) sau **model** (calculat, completează golurile, oferă prognoze).",
    "Connected modules": "Module conectate",
    "connected": "conectat",
    "not yet (placeholder in use)": "încă nu (se folosește o variantă provizorie)",
    "Pressure zones files": "Fișierele zonelor de presiune",
    "The tables below come from the project documentation and are in English.": "Tabelele de mai jos provin din documentația proiectului și sunt în engleză.",
    "Sources": "Surse",
    "Reference periods and thresholds": "Perioade de referință și praguri",
    "Quality control": "Controlul calității",
    "Natural or pressure?": "Natural sau presiune?",
    "What to investigate": "Ce trebuie investigat",
    "Limitations": "Limitări",
    "**Copernicus Marine Service** (model, reanalysis, satellite, in-situ; free account)": "**Copernicus Marine Service** (model, reanaliză, satelit, in situ; cont gratuit)",
    "Other sources": "Alte surse",
    "EMODnet Physics: buoys, coastal stations, tide gauges near Romania (ERDDAP, no login); QC flags 1 and 2 kept.": "EMODnet Physics: geamanduri, stații costiere, maregrafe lângă România (ERDDAP, fără cont); se păstrează indicatorii QC 1 și 2.",
    "EMODnet Chemistry: 14,746 water samples 1963-2021 and DIVAnd seasonal climatologies (oxygen, nutrients).": "EMODnet Chemistry: 14.746 probe de apă 1963-2021 și climatologii sezoniere DIVAnd (oxigen, nutrienți).",
    "EMODnet Human Activities, Bathymetry, Seabed Habitats; Natura 2000 (EEA); OpenStreetMap for ports, beaches, shipyards.": "EMODnet Human Activities, Bathymetry, Seabed Habitats; Natura 2000 (AEM); OpenStreetMap pentru porturi, plaje, șantiere navale.",
    "NOAA, ESA Ocean Colour CCI, Open-Meteo (waves, wind), GloFAS Danube discharge: no-login backups and drivers.": "NOAA, ESA Ocean Colour CCI, Open-Meteo (valuri, vânt), debitul Dunării GloFAS: surse de rezervă fără cont și factori naturali.",
    "Dataset IDs come from marinekit.sources.copernicus.CATALOG. Details: docs/data_sources/*.md.": "ID-urile seturilor de date provin din marinekit.sources.copernicus.CATALOG. Detalii: docs/data_sources/*.md.",
    "Anomalies are always measured against the **same day of the year** (not the yearly mean). OFFICIAL = Romanian MSFD 2024 (NIMRD) or an EU directive; OURS = a climatology band or a value we propose. Draft thresholds are to be confirmed with NIMRD.": "Anomaliile se calculează mereu față de **aceeași zi a anului** (nu față de media anuală). OFICIAL = evaluarea DCSMM 2024 a României (INCDM) sau o directivă UE; AL NOSTRU = o bandă climatologică sau o valoare propusă de noi. Pragurile provizorii trebuie confirmate cu INCDM.",
    "**Reference periods**: satellite SST 1991-2020 (WMO standard); satellite chlorophyll and Kd490 1998-2022; model reanalysis 1993-2022; Danube discharge 1997-2025.": "**Perioade de referință**: temperatura de suprafață din satelit 1991-2020 (standard OMM); clorofilă-a și Kd490 din satelit 1998-2022; reanaliza modelului 1993-2022; debitul Dunării 1997-2025.",
    "In-situ QC rules": "Reguli QC pentru datele in situ",
    "Only OceanSITES QC flags 1 (good) and 2 (probably good) are kept.": "Se păstrează doar indicatorii QC OceanSITES 1 (bun) și 2 (probabil bun).",
    "Physical bounds per variable (e.g. temperature -2 to 35 °C, salinity 0 to 40) remove sensor spikes.": "Limitele fizice pe variabilă (de ex. temperatura între -2 și 35 °C, salinitatea între 0 și 40) elimină vârfurile de senzor.",
    "New coastal buoys are shown greyed out ('under QC') until their units are confirmed.": "Geamandurile costiere noi apar cu gri („în control de calitate”) până la confirmarea unităților.",
    "Shore stations are not used as sea temperature.": "Stațiile de pe țărm nu sunt folosite ca temperatură a mării.",
    "Data quality register": "Registrul calității datelor",
    "In-situ platforms and their status": "Platformele in situ și starea lor",
    "One rule chain for all cards, applied in order. 'Pressure' is used only when no natural driver explains the event.": "Un singur lanț de reguli pentru toate fișele, aplicat în ordine. „Presiune” se folosește doar când niciun factor natural nu explică evenimentul.",
    "The model's chlorophyll, bottom oxygen and nutrients disagree with its own reanalysis: we use satellite and in-situ data for those, and keep the model for temperature, salinity and currents.": "Clorofila, oxigenul de la fund și nutrienții din model nu concordă cu propria reanaliză: pentru acestea folosim date satelitare și in situ, iar modelul îl păstrăm pentru temperatură, salinitate și curenți.",
    "No bottom-oxygen sensor exists near the coast: the oxygen card has low confidence.": "Nu există niciun senzor de oxigen la fund lângă coastă: fișa de oxigen are încredere scăzută.",
    "Nutrient observations end around 2020-2021: that card is historical only.": "Observațiile de nutrienți se opresc în jurul anilor 2020-2021: fișa este doar istorică.",
    "Satellite chlorophyll near the coast is affected by river sediment (medium confidence within about 20 km of shore).": "Clorofila din satelit lângă coastă este afectată de sedimentele aduse de râuri (încredere medie în primii aproximativ 20 km de la țărm).",
    "Aquaculture sites, fishing landing points and some coastal works are located from place names: marked 'assumed'.": "Fermele de acvacultură, punctele de debarcare a peștelui și unele lucrări costiere sunt localizate după toponime: marcate „presupus”.",
    "Basemap tiles and Copernicus map tiles need the internet; data layers and charts work offline from the cache.": "Hărțile de bază și plăcile de hartă Copernicus necesită internet; straturile de date și graficele funcționează offline din cache.",
    "Trends use annual means without correcting for autocorrelation, so the uncertainty is a lower bound.": "Tendințele folosesc medii anuale fără corecție pentru autocorelație, deci incertitudinea este o limită inferioară.",
})

# tile errors (maps.add_tiles)
RO.update({
    "Some Copernicus map tiles did not load. Turn the map tiles off in Map layers to use the local layer.":
        "Unele dale de hartă Copernicus nu s-au încărcat. Dezactivează dalele din Straturi și sezon pentru a folosi "
        "stratul local.",
})

# Water quality, charts, coast and seabed
RO.update({
    " (the uncertainty is larger than the change)": " (incertitudinea este mai mare decât schimbarea)",
    " At {d} m this is the outer shelf, less affected by the coast.": " La {d} m suntem pe platforma exterioară, mai puțin influențată de coastă.",
    " At {d} m, storms can mix the water down to the seabed.": " La {d} m, furtunile pot amesteca apa până la fund.",
    " At {d} m, the bottom water can stay cut off from the surface in summer, when oxygen can drop.": " La {d} m, apa de la fund poate rămâne izolată de suprafață vara, când oxigenul poate scădea.",
    " Period {a} to {b}, sampled at {la} N {lo} E.": " Perioada {a} - {b}, eșantionat la {la} N {lo} E.",
    " Today the model shows {v} m/s towards {d}": " Astăzi modelul arată {v} m/s spre {d}",
    " Today: {h} m ({w}), {p} s, {k}.": " Astăzi: {h} m ({w}), {p} s, {k}.",
    " Today: {v} m/s from {d}, ": " Astăzi: {v} m/s dinspre {d}, ",
    ", against the usual flow. The model does not say why; short reversals near the coast happen.": ", invers față de curgerea obișnuită. Modelul nu arată de ce; inversări scurte lângă coastă se întâmplă.",
    ", against the usual flow. The wind is also blowing towards {d} today, which can push the surface water that way.": ", invers față de curgerea obișnuită. Vântul bate astăzi tot spre {d}, ceea ce poate împinge apa de suprafață în acea direcție.",
    ", as usual for the season": ", ca de obicei în acest sezon",
    ", in line with the usual flow.": ", în sensul curgerii obișnuite.",
    ", {n} excluded": ", {n} excluse",
    "Analysis": "Analiză",
    "Arrows point where the water or air is going (up = north). For waves, a longer arrow means a longer wave period (swell). The dashed line marks today; later values are forecast.": "Săgețile arată încotro se deplasează apa sau aerul (sus = nord). La valuri, o săgeată mai lungă înseamnă o perioadă mai lungă (hulă). Linia punctată marchează ziua de azi; valorile de după sunt prognoză.",
    "Bias (model - obs)": "Abatere (model - obs.)",
    "Change per decade": "Schimbare pe deceniu",
    "Clear long-term change": "Schimbare clară pe termen lung",
    "Close: why {x} matters": "Închide: de ce contează {x}",
    "Confidence": "Încredere",
    "Correlation r": "Corelație r",
    "Could not draw the chart: {e}": "Graficul nu a putut fi desenat: {e}",
    "Data  ·  CSV download": "Date  ·  descărcare CSV",
    "Dataset IDs and licences are on the Methods page.": "ID-urile seturilor de date și licențele sunt pe pagina Metode.",
    "Days compared": "Zile comparate",
    "Days paired": "Zile împerecheate",
    "Depth profile along the line": "Profilul adâncimii de-a lungul liniei",
    "Depth profile not available (EMODnet Bathymetry needs the internet the first time).": "Profilul adâncimii nu este disponibil (EMODnet Bathymetry are nevoie de internet prima dată).",
    "Difference": "Diferență",
    "Distance": "Distanță",
    "Download the {a}-{b} annual means (CSV)": "Descarcă mediile anuale {a}-{b} (CSV)",
    "Download the {n}-day series (CSV)": "Descarcă seria de {n} zile (CSV)",
    "Excluded: coastal buoys EUXRoCB0x and shore station 15480 are not quality-checked yet.": "Excluse: geamandurile costiere EUXRoCB0x și stația de țărm 15480 nu au încă control de calitate.",
    "Field": "Câmp",
    "Here: {v} m/s from {d}": "Aici: {v} m/s dinspre {d}",
    "Hide": "Ascunde",
    "Last {n} days": "Ultimele {n} zile",
    "Latest": "Cea mai recentă",
    "Left after natural causes: no anomaly to explain, so nothing is attributed to a pressure.": "Rămas după cauzele naturale: nicio anomalie de explicat, deci nimic nu este atribuit unei presiuni.",
    "Left after natural causes: {x}": "Rămas după cauzele naturale: {x}",
    "Loading the multi-year series (first time can take 10-20 s)...": "Se încarcă seria multianuală (prima dată poate dura 10-20 s)...",
    "Loading the series and the usual range...": "Se încarcă seria și intervalul obișnuit...",
    "Loading waves, currents and wind...": "Se încarcă valurile, curenții și vântul...",
    "Long-term trend": "Tendință pe termen lung",
    "Model": "Model",
    "Model ({u})": "Model ({u})",
    "Natural or pressure?  ·  rule chain": "Natural sau presiune?  ·  lanțul de reguli",
    "Natural or pressure?  ·  rule chain, 4 steps": "Natural sau presiune?  ·  lanțul de reguli, 4 pași",
    "Needs both an observation (buoy or satellite) and a model series at this point. Try sea temperature or salinity near a buoy, or pick a buoy from the list.": "Este nevoie atât de o observație (geamandură sau satelit), cât și de o serie de model în acest punct. Încearcă temperatura mării sau salinitatea lângă o geamandură, sau alege o geamandură din listă.",
    "No clear long-term change": "Nicio schimbare clară pe termen lung",
    "No multi-year series for this variable at this point.": "Nu există o serie multianuală pentru această variabilă în acest punct.",
    "No recent series or no usual range for this variable at this point.": "Nu există o serie recentă sau un interval obișnuit pentru această variabilă în acest punct.",
    "Not enough complete years for a trend.": "Prea puțini ani compleți pentru o tendință.",
    "Observation": "Observație",
    "Observed ({u})": "Observat ({u})",
    "Open: why {x} matters": "Deschide: de ce contează {x}",
    "Origin": "Origine",
    "Pairing measurements and model...": "Se împerechează măsurătorile cu modelul...",
    "Period": "Perioadă",
    "Reference": "Referință",
    "River and upwelling drivers: not computed for this place yet.": "Factori fluviali și de upwelling: încă necalculați pentru acest loc.",
    "River and upwelling drivers: {x}": "Factori fluviali și de upwelling: {x}",
    "Sea state": "Starea mării",
    "Seabed depth here": "Adâncimea aici",
    "Season: no recent series here; see the card value and its reference period.": "Sezon: nu există o serie recentă aici; vezi valoarea cardului și perioada sa de referință.",
    "Season: the value is inside the usual range for this date, so the season explains it.": "Sezon: valoarea este în intervalul obișnuit pentru această dată, deci sezonul o explică.",
    "Season: the value is outside the usual range for this date; the season alone does not explain it.": "Sezon: valoarea este în afara intervalului obișnuit pentru această dată; sezonul singur nu o explică.",
    "Shallow water warms and loses oxygen faster than deep water; the shelf here deepens slowly.": "Apa puțin adâncă se încălzește și pierde oxigen mai repede decât apa adâncă; aici platforma coboară lent.",
    "Show": "Arată",
    "Show {name}": "Arată {name}",
    "Slope of the straight line through the annual means, times ten years.": "Panta dreptei prin mediile anuale, înmulțită cu zece ani.",
    "Sources  ·  {n} compared": "Surse  ·  {n} comparate",
    "Status": "Stare",
    "Surface current": "Curent de suprafață",
    "The combined waves / currents / wind chart comes from the vector visualisation module, which is not ready yet.": "Graficul combinat valuri / curenți / vânt vine din modulul de vizualizare vectorială, care nu este încă gata.",
    "The health card for this place is still being computed; it appears here by itself.": "Cardul de sănătate pentru acest loc încă se calculează; apare aici de la sine.",
    "The main coastal current usually runs south along this coast, carrying Danube water, nutrients and mud.": "Curentul costier principal curge de obicei spre sud de-a lungul acestei coaste și duce apă din Dunăre, nutrienți și mâl.",
    "The observation and the model do not overlap in time at this point.": "Observația și modelul nu se suprapun în timp în acest punct.",
    "The observation and the model do not overlap in time here.": "Observația și modelul nu se suprapun în timp aici.",
    "Threshold": "Prag",
    "Trend since {y}": "Tendință din {y}",
    "Trust": "Încredere",
    "Uncertainty (95 %)": "Incertitudine (95 %)",
    "Usual": "Obișnuit",
    "Usual range: ": "Interval obișnuit: ",
    "Waves stir up the seabed in shallow water and make it murky. Long-period swell reaches deeper than short wind waves.": "În apă puțin adâncă, valurile ridică sedimentele de pe fund și tulbură apa. Hula cu perioadă lungă ajunge mai adânc decât valurile scurte de vânt.",
    "Waves, currents and depth": "Valuri, curenți și adâncime",
    "Waves, currents and wind  ·  10 days and forecast": "Valuri, curenți și vânt  ·  10 zile și prognoză",
    "Weather: storms and wind mixing in the last days are checked by the waves and wind data (Seabed page).": "Vreme: furtunile și amestecul prin vânt din ultimele zile sunt verificate cu datele de valuri și vânt (pagina Fund marin).",
    "Why": "De ce",
    "Wind from the south or south-west along this coast can push surface water offshore and pull cold deep water up (upwelling), mostly in summer; the sea temperature then drops fast.": "Vântul din sud sau sud-vest de-a lungul acestei coaste poate împinge apa de suprafață spre larg și poate ridica apă rece de la adâncime (upwelling), mai ales vara; temperatura mării scade atunci repede.",
    "Wind not available here: Open-Meteo returned no values (offline and not in the cache?).": "Vântul nu este disponibil aici: Open-Meteo nu a returnat valori (fără internet și nu e în cache?).",
    "Wind not available: vectorviz.load_field('wind') failed ({e}).": "Vântul nu este disponibil: vectorviz.load_field('wind') a eșuat ({e}).",
    "Wind: Open-Meteo model values at {n} reference points and at the selected place, {t} UTC. There is no gridded wind field, so the map shows points.": "Vânt: valori din modelul Open-Meteo în {n} puncte de referință și în locul selectat, {t} UTC. Nu există un câmp de vânt pe grilă, așa că harta arată puncte.",
    "Years used": "Ani folosiți",
    "a direction and strength that can cause upwelling.": "o direcție și o intensitate care pot produce upwelling.",
    "about {x} times {ref}": "de aproximativ {x} ori {ref}",
    "annual mean": "medie anuală",
    "depth {d}": "adâncime {d}",
    "falling by {x} {u} per decade": "scade cu {x} {u} pe deceniu",
    "flowing towards {d} · daily mean": "curge spre {d} · medie zilnică",
    "from {d}": "dinspre {d}",
    "grid cell {la} N {lo} E": "celula de grilă {la} N {lo} E",
    "height · period · from {d}": "înălțime · perioadă · dinspre {d}",
    "no data here (or still downloading)": "fără date aici (sau încă se descarcă)",
    "no driver active": "niciun factor activ",
    "no source at this point": "nicio sursă în acest punct",
    "not an upwelling wind.": "nu este un vânt de upwelling.",
    "not quality-checked": "fără control de calitate",
    "not used": "nefolosit",
    "observed": "observat",
    "on land": "pe uscat",
    "one day": "o zi",
    "perfect agreement": "acord perfect",
    "platform {p}": "platforma {p}",
    "rising by {x} {u} per decade": "crește cu {x} {u} pe deceniu",
    "still downloading": "încă se descarcă",
    "the usual value": "valoarea obișnuită",
    "the {yrs} average": "media {yrs}",
    "this year": "anul acesta",
    "trend": "tendință",
    "under QC": "în control de calitate",
    "usual": "obișnuit",
    "usual range": "interval obișnuit",
    "usual range (p10-p90)": "interval obișnuit (p10-p90)",
    "x usual": "x obișnuit",
    "{d} km from the point": "{d} km de punct",
    "{p} to open sea": "{p} spre larg",
    "{t} UTC, currents as daily mean": "{t} UTC, curenți ca medie zilnică",
    "{u} / decade": "{u} / deceniu",
    "{v} m/s from {d}": "{v} m/s dinspre {d}",
    "Rising over the last month": "În creștere în ultima lună",
    "Falling over the last month": "În scădere în ultima lună",
    "Steady over the last month": "Stabil în ultima lună",
    "about {x} {unit} warmer than {ref}": "cu aproximativ {x} {unit} mai cald decât {ref}",
    "about {x} {unit} colder than {ref}": "cu aproximativ {x} {unit} mai rece decât {ref}",
    "about {x} {unit} higher than {ref}": "cu aproximativ {x} {unit} peste {ref}",
    "about {x} {unit} lower than {ref}": "cu aproximativ {x} {unit} sub {ref}",
    "Still within the usual range.": "Încă în intervalul obișnuit.",
    "Above the usual range.": "Peste intervalul obișnuit.",
    "Below the usual range.": "Sub intervalul obișnuit.",
    "Now vs usual": "Acum față de obișnuit",
    "Measured vs model": "Măsurat față de model",
    "All three": "Toate trei",
    "Past ship samples (EMODnet Chemistry). No live nutrient data after about 2020.": "Probe vechi prelevate de pe nave (EMODnet Chemistry). Nu există date curente despre nutrienți după aproximativ 2020.",
    "Model estimate (Copernicus BGC). No pH sensor on this coast.": "Estimare din model (Copernicus BGC). Nu există senzor de pH pe această coastă.",
    "calm sea": "mare calmă",
    "smooth sea": "mare liniștită",
    "slight sea": "mare ușor agitată",
    "moderate sea": "mare moderat agitată",
    "rough sea": "mare agitată",
    "very rough sea": "mare foarte agitată",
    "high sea": "mare foarte puternic agitată",
    "mostly wind waves": "mai ales valuri de vânt",
    "swell from farther away": "hulă venită de departe",
    "a mix of wind waves and swell": "un amestec de valuri de vânt și hulă",
    "How the water moves and how deep it is. Values come from the Copernicus wave and current models, Open-Meteo wind and EMODnet Bathymetry.": "Cum se mișcă apa și cât de adâncă este. Valorile vin din modelele Copernicus de valuri și curenți, vântul Open-Meteo și EMODnet Bathymetry.",
    "Bias above zero means the model is too high. RMSE is the typical size of the error. r close to 1 means the model follows the ups and downs.": "O abatere peste zero înseamnă că modelul este prea mare. RMSE este mărimea obișnuită a erorii. Un r apropiat de 1 înseamnă că modelul urmează creșterile și scăderile.",
    "Each dot is the average of one year. The line shows the long-term direction.": "Fiecare punct este media unui an. Linia arată direcția pe termen lung.",
    "Annual means with a least-squares trend. 'Change per decade' is the slope times ten years.": "Medii anuale cu o tendință prin metoda celor mai mici pătrate. „Schimbare pe deceniu” este panta înmulțită cu zece ani.",
    "A rising or falling line means conditions in your area are shifting over decades.": "O linie care urcă sau coboară înseamnă că condițiile din zona ta se schimbă de-a lungul deceniilor.",
    "OLS on annual means (years with at least 300 daily values); 95 % CI from the t distribution, no autocorrelation correction.": "OLS pe medii anuale (ani cu cel puțin 300 de valori zilnice); IÎ 95 % din distribuția t, fără corecție pentru autocorelație.",
    "Sea temperature": "Temperatura mării",
    "Algae in the water (chlorophyll)": "Alge în apă (clorofilă)",
    "Chlorophyll-a (algae indicator)": "Clorofilă-a (indicator de alge)",
    "Chlorophyll-a (algae, blooms)": "Clorofilă-a (alge, înfloriri)",
    "Oxygen in the water": "Oxigen în apă",
    "Dissolved oxygen": "Oxigen dizolvat",
    "Dissolved O2": "O2 dizolvat",
    "Oxygen near the seabed": "Oxigen lângă fundul mării",
    "Bottom oxygen": "Oxigen la fund",
    "Bottom O2 (model)": "O2 la fund (model)",
    "Saltiness of the water": "Cât de sărată este apa",
    "Water clarity (murkiness)": "Transparența apei (turbiditate)",
    "Light attenuation (Kd490)": "Atenuarea luminii (Kd490)",
    "SST (L4, satellite)": "SST (L4, satelit)",
    "Kd490": "Kd490",
    " Source: {src}": " Sursă: {src}",
})
