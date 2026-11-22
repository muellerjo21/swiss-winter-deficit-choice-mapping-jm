# Code-Review (Teil 1: Audit, nur gelesen)

Stand: HEAD `a3733c9`, 20.11.2026. Tests 185/185 grün, `git status` sauber.
Referenz-Snapshot (ausserhalb des Repos): `/private/tmp/claude-501/-Users-josua-Documents-ETH-Semester-Project-swiss-winter-deficit-choice-mapping-jm/1bac7b42-d91c-4a04-9b60-14f5922d822d/scratchpad/review/snapshot_a3733c9`
(sha256 von 420 Dateien in `data/processed`, `build/data`, `build/figures`, `graphics`, `docs/*.csv`, `docs/sensitivities`, `docs/pipeline_map.yaml`, `build/pipeline_map.html`; Kerntabellen mit Rang, P(Rang 1), ΔU, P(A > B) und Tie-Gruppen für CH, DE-CH, FR-CH und 23 Regionen in 2016–2018, 884 Zeilen). Vergleich: `snapshot.py compare` im selben Ordner. Alle Plausibilitäts-Anker erfüllt.

Risiko: **kein** = ändert kein Ergebnis; **möglich** = kann Ergebnisse oder Ausgabedateien ändern (dann nur nach OK und mit gemessener Abweichung). Aufwand: S (< 30 min), M (< 2 h), L (> 2 h).

## A) Hartkodierte Werte

### A1 Parameter und Annahmen, die in die Config gehören

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| A1-01 | src/config.py:105 | Flächendichten (Wind 8 MW/km², PV 80 MW/km²) als Python-Dict, Quelle nur im Kommentar | `land.capacity_density_gw_per_km2` in die Config (mit Einheit und Quelle Tröndle et al.) | kein | S |
| A1-02 | src/config.py:238 | Sprachgewichte DE/FR 61/23 (BFS 2023) im Code; wirken im nationalen Aggregat und bei TI `mixed` | `utility.language_region_weights` in die Config (Quelle, Normierung) | kein | S |
| A1-03 | src/config.py:246 | Kostenänderung aus Mellot Table 3 (12 Werte) im Code | `mellot.cost_change_pct` in die Config (oder eine kleine CSV unter `data/`) | kein | S |
| A1-04 | src/load_data.py:990 | `transmission_change: 0.0` fest im Code (Begründung 13.249 GW nur im Kommentar) | Config-Key `attributes.transmission_change` mit Begründung | kein | S |
| A1-05 | README.md:72, docs (Text) | Tie-Konvention (P(A > B) < 0.95, \|ΔU\| < 1e-5) steht nur in Texten, kein Code wendet sie an | `report.tie_threshold` und `report.tie_utility_tolerance` in die Config; `adjacent_pairs.py` schreibt die Tie-Gruppen mit | kein | S |
| A1-06 | scripts/sensitivity_runs.sh:33-46 | Override-Werte als Literale im Shell-Skript: p_ref ±20 % als 13.552 / 20.328 (folgen nicht, wenn p_ref sich ändert), Margen 0.2 / 0.3, Namen der Zuschläge und Definitionen | Varianten als Liste in die Config (`sensitivity.named_variants`); p_ref ±20 % als Faktor aus `price.energy_reference_ct_per_kwh` berechnen | kein | M |
| A1-07 | scripts/sensitivity_summary.py:31-32 | Wetterjahre 2016/2017/2018 hartkodiert | aus `config.sensitivity.weather_years` und `weather_year` lesen | kein | S |
| A1-08 | src/make_graphics.py:808 | Fussnote von fig11 nennt „2016 (main analysis), 2017 and 2018“ fest | aus `params.weather_years` und `weather_year` bilden | kein (gleicher Text bei gleicher Config) | S |
| A1-09 | docs/pipeline_map.yaml:98 | „(2016, 2017, 2018)“ fest im Text | Platzhalter `{weather_years}` | kein | S |
| A1-10 | tests/test_regional.py:28-29, tests/test_pairwise.py:55-61, tests/test_ticino.py:20 | Regionszahl 23/22 hartkodiert | aus Fixture (Bevölkerungstabelle bzw. ticino/exclude) ableiten | kein | S |
| A1-11 | tests/test_imports.py:76,80 | Szenariozahl 12 hartkodiert | aus `weather_scenarios`/Config ableiten | kein | S |
| A1-12 | config/default.yaml:40-41 | Kommentar nennt HICP-Umrechnung EUR 2020 → 2025 (1.2255), sonst gilt EUR 2015 (Z. 213) | Kommentar an EUR 2015 angleichen (nur Text) | kein | S |

### A2 Daten und Mappings im Code

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| A2-01 | src/config.py:115 | OWNERSHIP_MAPPING (Annahme, nicht empirisch) im Code | in die Config (`attributes.ownership`), zusammen mit A2-02 und A2-03 | kein | M |
| A2-02 | src/config.py:143 | TECH_SOURCE_MAPPING im Code; Lücke (SCGT) blieb unbemerkt | in die Config; Prüfung D-02 | kein | M |
| A2-03 | src/config.py:166 | PV-Techs in 4 Listen doppelt (PV_REFERENCE_TECHS, CAPACITY_DENSITY, OWNERSHIP, cost_groups) | eine Liste in der Config, die anderen davon ableiten | kein | S |
| A2-04 | src/config.py:158 | SECTOR_COUPLING_ELEC_TECHS im Code (Nenner von Import und Strompreis-Varianten) | in die Config neben `price.end_use_techs` | kein | S |
| A2-05 | src/load_data.py:817, 833 | HEAT_DEMAND_TECHS und das Muster `_transport_` definieren die Endenergie im Code | in die Config (`final_energy.heat_techs`, `final_energy.transport_pattern`) | kein | S |
| A2-06 | src/load_data.py:1001 | Szenario-ID für Table 3 aus dem Dateinamen (`scenario_id_from_filename`): EP2050+ 2017/2018 heisst dort „baseline“ und bekommt `mellot_cost_change_pct = NaN` (geprüft in `data/processed/weather/2017|2018`) | Szenario-ID aus der Config (Wildcard/Parameter) übergeben | **möglich** (nur Vergleichsspalten `mellot_cost_change_pct`, `rank_mellot_cost`, `rank_diff_*` in 2017/2018, nicht Rang oder P) | S |
| A2-07 | src/config.py:262 | SCENARIO_DISPLAY_NAMES: „EP2050+ (5 TWh winter cap)“, Bericht verlangt „EP2050+ (5 TWh constraint)“ | Name in die Config; Umbenennung ändert Abbildungen | **möglich** (Abbildungen) | S |
| A2-08 | src/config.py:219 | ATTRIBUTE_UNITS veraltet (Preis „vs. the ElCom reference“, Import „/ electricity demand“); landet in `build/data/beta_real_units.csv` | Text aus der aktiven Config ableiten | **möglich** (Textspalte einer Ausgabe) | S |
| A2-09 | src/make_graphics.py:39 | REFERENCE_SCENARIO = "baseline" als Szenario-ID-Literal | aus Config (Szenario ohne Table-3-Wert) ableiten | kein | S |
| A2-10 | src/make_graphics.py:89-95 | Beschriftungs-Offsets pro Szenario-ID | Layout-Dict in plot_style oder Config; bei neuen IDs Warnung | kein | S |
| A2-11 | src/make_graphics.py:40-41, src/regional.py:25, scripts/weather_year_summary.py:6, src/sensitivity.py:region_tags | Gruppenlisten (national/DE_CH/FR_CH) vierfach definiert | eine Konstante (z. B. `config.GROUPS`) | kein | S |
| A2-12 | src/maps.py:16 vs. src/regional.py:28 | `region_of_canton` doppelt (maps-Umgebung ohne xarray) | in `config.py` (leichtes Modul) verschieben, beide importieren | kein | S |
| A2-13 | src/config.py:31-97 | Kantonslisten (Name→Code, Nummer→Code, Sprache, Merges) im Code | zentral ok; optional als YAML unter `data/` | kein | M |
| A2-14 | scripts/independent_check.py:30, weather_year_check.py:20, strategy_check.py:23 | FOREIGN-Liste dreifach (bewusst unabhängig von der Pipeline) | so lassen, Absicht im Kopfkommentar nennen | kein | S |
| A2-15 | scripts/pipeline_map.py:21 | deutsche Erklärtexte für Land-Definitionen im Code | nach `docs/pipeline_map.yaml` | kein | S |

### A3 Pfade, Dateinamen, Arbeitsverzeichnis

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| A3-01 | src/config.py:12 | `src/config.py` liest `config/default.yaml` direkt: `--config`-Overrides erreichen Modulkonstanten nicht (z. B. `END_USE_TECHS` in load_data.py:889, `CHOICE_MODEL_PATH` als Default in make_graphics.py:176) | fachliche Werte nur über Rule-Params; Modul-Defaults entfernen (Fehler, wenn nicht übergeben) | kein | M |
| A3-02 | src/config.py:24 | `SCENARIO_DIR = data/raw/scenario_data` (alter Ort), nur von totem Code genutzt | entfernen (mit B-01) | kein | S |
| A3-03 | src/config.py:27 | `CANTON_AREA_CSV_PATH` doppelt zu `data.canton_area` (Default von load_canton_area) | Default entfernen, Pfad immer übergeben | kein | S |
| A3-04 | src/make_graphics.py:36-37 | Defaults `data/processed` und `graphics/` (alter Ausgabeort) | Defaults entfernen, Pfade immer übergeben | kein | S |
| A3-05 | src/load_data.py:544, 606, 795 | API-Endpunkte (LINDAS, BFS PxWeb, Frankfurter) im Code | `sources.*` in die Config | kein | S |
| A3-06 | Snakefile:587, 705 | `figure_dir = "build/figures"` und `build/test-report.html` doppelt zu Output/Log (Lint-Hinweis) | aus FIGURE_PATH bzw. `log` ableiten | kein | S |
| A3-07 | .gitignore:33-36, Projektordner | `build` → `build.nosync` (iCloud) maschinenspezifisch, nur in .gitignore erklärt; leerer iCloud-Ordner `build 2` | im README erwähnen; `build 2` löschen (lokal, nicht in git) | kein | S |

### A4 Plot-Konstanten

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| A4-01 | src/maps.py:60, 84 | Farbe `#d9d8d4` zweimal, nicht in plot_style | Konstante in plot_style | kein | S |
| A4-02 | src/make_graphics.py:55, 141 (u. a.), src/maps.py:102 | Schriftgrössen als Literale (z. B. Fussnote 8.5) in zwei Modulen | Konstanten in plot_style | kein | S |
| A4-03 | Snakefile:50, 112, 458, 831 | Formatlisten mehrfach (`["png", "pdf"]`) | zwei benannte Listen | kein | S |

### A5 Legitime Konstanten (bleiben im Code)

Umrechnungen CHF → Rp. (`* 100`, load_data.py:921), GWh → TWh (`/ 1e3`), m² → km² (`/ 1e6`, maps.py:42); numerische Toleranzen der Konsistenzprüfungen (1e-12/1e-15 in pairwise.py, regional_utility.py, Tests); Konvergenz von `fuel_unit_costs` (100 Iterationen, 1e-15, load_data.py:707/731); Rundung der Quantile auf 12 Stellen (intervals.py:26); Prüf-Ziehungen `CHECK_DRAWS` (beta_real_units.py:37); Timeouts der Downloads; Referenzwerte Table 1S in `weather_year_check.py:21` (unabhängige Kontrolle, Quelle im Kopf). Einheitenumrechnungen kommen je nur an einer Stelle der Pipeline vor. Keine Zufallszahlen, daher keine Seeds nötig; Draws (4000), σ-Skalen, Länder und Attribute werden aus der Modelldatei gelesen.

**sensitivity_runs.sh:** Die 44 Läufe (2016: 14, 2017/2018: je 15) sind vollständig Config-Overrides, aber die Override-Werte stehen als Literale im Skript (A1-06). Die Varianten „import: regional balance“, „land: national share“ und die TI-Varianten rechnet `regional_utility.py` intern.

## B) Toter und überflüssiger Code

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| B-01 | src/load_data.py:166, 176, 204, 210, 224, 250, 274, 289, 314, 345, 369, 501, 1006, 1027, 1031, 1048 | 16 Definitionen ohne Aufruf aus Pipeline oder Tests (AST-Erreichbarkeit): load_scenarios, compute_beta_real_units, load_scenario_land, get_ch_foreign_transmission_techs, load_scenario_transmission_capacity, load_scenario_import, get_ch_fuel_import_techs, load_scenario_fuel_import, extract_all_scenarios, save_all_scenarios, compute_relative_land, compute_import_share_extended, compute_all_scenarios, SWISSGRID_LISTING_URL, get_swissgrid_report_url, download_swissgrid_report; nur `legacy/notebooks` nutzt einige | entfernen (bricht legacy-Notebooks, siehe B-06) | kein | S |
| B-02 | src/config.py:173-199 | 9 Konstanten ohne Pipeline-Nutzung (PRICE_MARGIN, PRICE_REFERENCE_YEAR, PRICE_CATEGORY, PRICE_COST_SCALE_FACTOR, PRICE_COST_SCOPE, PRICE_COST_GROUPS, PRICE_POWER_FUEL, LAND_DEFINITION, TRANSMISSION_REFERENCE_YEAR) | entfernen; laden die Config am Pipeline vorbei | kein | S |
| B-03 | src/load_data.py:1059 | `__main__`-Block (Demo-Ausgabe) | entfernen | kein | S |
| B-04 | data/processed/beta_real_units.csv, scenario_capacity/fuel_import/import/land/transmission_capacity.csv | 6 veraltete Tabellen, keine Referenz der Tests (scenario_* aus totem `save_all_scenarios`, Stand mit alten Dateinamen) | löschen (Freigabe nötig) | kein | S |
| B-05 | graphics/ (41 von 45 Dateien) | alte Abbildungen (fig1–fig5, figA1, cost_vs_preference, fig3_captions.md, fig6 regional alt), werden nicht mehr erzeugt; nur `fig6_p_rank1_vs_reference_price_national.{pdf,png,svg}` sind Testreferenz | löschen (Freigabe nötig) | kein | S |
| B-06 | legacy/ (15 Dateien) | „unmaintained first approach“, nutzt totes `compute_all_scenarios` usw. | löschen oder einfrieren (Freigabe nötig) | kein | S |
| B-07 | rules/.gitkeep | leerer Ordner | löschen oder für `rules/common.smk` nutzen (Lint) | kein | S |
| B-08 | scripts/regional_utility.py:105-108 | Variante „import: electricity + fuels + synthetic diesel (year)“ ist seit der Hauptdefinition identisch mit main | Zeile behalten (Teil von sensitivity_regional.csv) oder entfernen | **möglich** (Ausgabetabelle) | S |
| B-09 | src/load_data.py:992-993 | Kommentar „import_share_extended deliberately not included … electricity import only“ widerspricht der Hauptdefinition | Kommentar korrigieren | kein | S |

**Skripte und docs: Wovon hängt der Bericht ab?**

| Datei | Rolle |
|---|---|
| scripts/ (27 Skripte, die das Snakefile aufruft) | Pipeline; Methods/Results beruhen auf ihren Ausgaben |
| scripts/independent_check.py, weather_year_check.py, strategy_check.py | unabhängige Kontrolle (Methods 3.2), behalten |
| scripts/adjacent_pairs.py, sensitivity_runs.sh, sensitivity_summary.py | Belege für Zahlen in Results 4.1, 4.3, 4.4, behalten |
| docs/data_provenance.md | Methods 3.2 (Herkunft, SHA-256), behalten |
| docs/independent_check.csv, weather_year_check.csv, strategy_check.csv | Belege Methods 3.2, behalten |
| docs/adjacent_pairs.csv, sensitivity_summary.csv, sensitivities/ | Belege Results, behalten |
| docs/pipeline_map.yaml, pipeline_map_template.html | Doku (Pipeline-Karte), Bericht hängt nicht davon ab |
| Einmal-Skripte | keine in scripts/; Kandidaten zum Löschen sind nur legacy/, graphics/ alt und data/processed alt (B-04 bis B-06) |

## C) Effizienz (gemessen)

Messung: erzwungener Neulauf aller Rules ohne Netzwerk (`--forcerun`, 1 Kern), Speicher-Sampler alle 0.5 s, Funktionsprofil mit cProfile auf den erhaltenen Wrapper-Skripten. Der Neulauf war bitidentisch zum Snapshot (auch SVG und HTML).

| Lauf | Wanduhr |
|---|---|
| Volle Pipeline (39 Jobs) | 339 s |
| Sensitivitätslauf Marge 20 % (5 Ziele) | 55 s, davon 50 s Lesen der Szenariodateien (scenario_attributes, regional_attributes) |
| Sensitivitätslauf Wetterjahr 2017 | 67 s, davon 61 s Dateilesen |
| Wiederherstellen nach einem Sensitivitätslauf | 305 s (fast alles neu, siehe C-04) |

| Top 5 Zeit | s (Anteil) | Ursache (cProfile) |
|---|---|---|
| weather_year_rankings (3 Jobs) | 140 (42 %) | 204 `open_dataset`-Aufrufe für 12 Dateien (17 pro Szenario) = 77 % der Zeit |
| scenario_attributes (12 Jobs) | 36 (11 %) | 7 Öffnungen pro Datei, `carrier_con` zweimal ganz gelesen |
| cost_groups | 34 (10 %) | import_quantities, final energy, demand, fuel: jede Grösse liest die Datei neu |
| cost_scale_regional | 33 (10 %) | 453 Aufrufe `regional_utilities` (151 Faktoren × 3 Gruppen einzeln) = 76 % |
| import_shares / regional_attributes | je 16 (5 %) | dieselben Größen wie oben, nochmals gelesen |

| Top 5 Speicher (Spitzen-RSS) | MB |
|---|---|
| weather_year_rankings | 926 |
| make_pairwise_plot | 869 |
| cost_groups | 818 |
| regional_attributes | 756 |
| import_shares | 710 |

Das Laden des Choice-Modells (7.8 GB, lazy) kostet nur 0.2 s pro Rule und ist kein Engpass. Kein Speicher über 1 GB.

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| C-01 | src/load_data.py (alle `load_scenario_*`, `import_quantities`, `load_fuel_imports`), src/regional.py:122 | jede Funktion öffnet die .nc neu und liest `carrier_prod`/`carrier_con` erneut (bis 17-mal pro Datei und Rule) | jede Datei einmal pro Prozess öffnen und die nötigen Variablen einmal laden (Cache nach Pfad), Funktionen nehmen das Dataset; Rechnung unverändert | kein (bitidentisch zu prüfen) | M |
| C-02 | src/regional.py:306 | `regional_cost_scale_switches` rechnet `leader_at` pro Gruppe getrennt: 453 statt 151 Auswertungen | Ergebnis pro Faktor für alle Gruppen zwischenspeichern | kein | S |
| C-03 | Snakefile:398 | weather_year_rankings rechnet das Hauptjahr 2016 komplett ein zweites Mal (≈ 47 s) | für `weather_year` die Ausgaben der Hauptkette übernehmen | kein (Test prüft Gleichheit bereits) | M |
| C-04 | Snakefile:250-275 | `regional_attributes` schreibt auch Bevölkerung und regionale Referenzpreise; jeder Preis- oder Jahreslauf erneuert sie (gleicher Inhalt, neue mtime) und löst alle nachgelagerten Rules aus | Bevölkerung/Referenzpreise in eigene Rule ohne Preis- und Szenario-Params | kein | S |
| C-05 | Snakefile (Sensitivitäten) | jeder Sensitivitätslauf liest alle Szenariodateien neu, obwohl sich nur Preis/Marge ändern | Extraktions-Rule pro (Jahr, Szenario) mit allen Mengen (Kosten, Endenergie, Endverbrauch, Importe, Kapazitäten) als verlustfreie Tabelle; Preis-Rules lesen nur diese | kein (bitidentisch zu prüfen) | L |
| C-06 | src/sensitivity.py:77-95 | Kreuzungspunkt-Bisektion rechnet in jedem Schritt komplette Rankings mit 4000 Ziehungen, braucht aber nur den Mittelwert | Punktnutzen ohne Ziehungen | kein | S |
| C-07 | src/utility.py:60-89 | Nutzen pro Zeile mit pandas (126 684 Aufrufe in cost_scale_regional) | vektorisieren nur, wenn die Summenreihenfolge gleich bleibt; Matrixprodukt ändert die Rundung | **möglich** (nur Bericht) | M |
| C-08 | src/pairwise.py:48 | Matrix rechnet A>B und B>A und die Diagonale (2 s) | so lassen (Gewinn klein, 1 − p ist nicht bitidentisch) | – | – |

## D) Robustheit und Reproduzierbarkeit

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| D-01 | Snakefile (alle Rules) | Module in `src/` sind nirgends Input: Code-Änderungen lösen keine Neuberechnung aus (so blieb der SCGT-Fix zunächst unbemerkt) | `src/*.py` (bzw. die importierten Module) als Input der Rules | kein (einmalige Neuberechnung) | S |
| D-02 | src/load_data.py:511, 526 | unbekannte Technologien fallen still aus Ownership- und Source-Anteil (Ursache des SCGT-Fehlers); heute nicht zugeordnet: battery, hydrogen_electricity_storage (Speicher), Wasserkraft bei Source (bewusst) | Prüfung: jede Schweizer Technologie mit Stromerzeugung ist zugeordnet oder steht in einer expliziten Ausnahmeliste der Config, sonst Fehler; Test dazu | kein | S |
| D-03 | src/load_data.py:656, 681, 701 | fehlt die Kostenklasse „monetary“, nimmt der Code still die erste Klasse | Fehler statt Fallback | kein | S |
| D-04 | src/load_data.py:460-471 | fehlende Import-Techs zählen still 0 | so lassen, aber im Ergebnis vermerken (Spalte) oder Warnung | kein | S |
| D-05 | src/load_data.py:795 | `requests.get` ohne Timeout (EUR/CHF) | Timeout wie bei den anderen Downloads | kein | S |
| D-06 | src/load_data.py:20 | setzt beim Import `SSL_CERT_FILE` global (Seiteneffekt) | nur in den Fetch-Funktionen setzen | kein | S |
| D-07 | envs/*.yaml, environment.yaml | Top-Level gepinnt, aber keine Lock-Datei (transitive Pakete wie hdf5/netcdf-c offen); `certifi` ohne Version; `python=3.12` ohne Patch | `conda-lock` oder `conda list --explicit` pro Umgebung ablegen | kein | M |
| D-08 | Snakefile | 32 Rules ohne `log:`; Funktionen im Snakefile; `clean` mit langem `run:` (Lint) | Logs pro Rule, Funktionen nach `rules/common.smk` | kein | M |
| D-09 | tests/test_runner.py | Tests laufen nur über die Rule `test` (Fixtures aus `snakemake`); ohne `build/` und `data/raw/` gibt es keine verständliche Meldung | kurzer Hinweis im README; optional Prüfung der Inputs mit klarer Meldung | kein | S |
| D-10 | Determinismus | erzwungener Neulauf und Wiederherstellen nach Sensitivitätsläufen bitidentisch (420 Dateien) | – | – | – |
| D-11 | `snakemake -n` / `--lint` | `-n`: „Nothing to be done“; `--lint`: nur Stil-Hinweise (D-08, A3-06), keine Fehler | – | – | – |

## E) Konsistenz Code ↔ Doku

| ID | Datei:Zeile | Problem | Vorschlag | Risiko | Aufwand |
|---|---|---|---|---|---|
| E-01 | src/load_data.py:994 | nationales Aggregat (Anhang) nutzt den Stromimport über den Stromverbrauch; die regionale Hauptanalyse Strom + Brennstoffe + Diesel über die Endenergie | klären, ob gewollt (methodische Entscheidung, nicht im Review ändern) | **möglich** | S |
| E-02 | README.md:41 | „byte-identical results (except SVG and HTML)“: gemessen sind auch SVG und HTML identisch | Satz korrigieren | kein | S |
| E-03 | README.md:62 | „--config passes nested numbers as text …“: `numbers_from_text` im Snakefile wandelt sie inzwischen um | Hinweis entfernen | kein | S |
| E-04 | README.md:74 | „reproduces the references frozen on 8 Nov 2026 exactly“: diese Referenzen sind seit dem Neueinfrieren nicht mehr im Repo; nicht prüfbar | Satz entfernen oder auf git-Commit verweisen | kein | S |
| E-05 | README.md:67, docs/pipeline_map.yaml:100 | „Baseline (5 TWh)“ statt „EP2050+ (5 TWh constraint)“ | Begriffe angleichen | kein | S |
| E-06 | config/default.yaml:1-4, 159-165, 189 | Kommentare: src/config.py „für Notebooks“, „coefficients of the region's language region“, „ElCom reference price“ (veraltet für measured und energy) | Kommentare aktualisieren | kein | S |
| E-07 | src/regional.py:1-12, src/utility.py:2, src/pairwise.py:6 | Docstrings veraltet (regionaler ElCom-Preis, Sprachregion-Koeffizienten, „Jan 2026 model“, „equal-tailed interval“ statt Config-Typ) | Docstrings aktualisieren | kein | S |
| E-08 | src/config.py:225-226 | ATTRIBUTE_UNITS beschreiben alte Preis- und Importdefinition (siehe A2-08) | – | möglich | S |
| E-09 | docs/pipeline_map.yaml | Text sonst konsistent (Platzhalter werden aus den Ergebnissen gefüllt, Build bricht bei unbekannten Regeln ab) | – | – | – |

## Priorisierung

**Muss**
- D-01 `src/` als Input der Rules
- D-02 laute Prüfung der Technologie-Mappings mit Test
- A1-01 bis A1-04, A2-01 bis A2-05: fachliche Parameter und Mappings in die Config, Code ohne eigene Defaults
- C-01 jede .nc einmal lesen
- C-02 Memo in cost_scale_regional
- C-04 Bevölkerung/Preise in eigene Rule

**Sollte**
- B-01 bis B-03, B-09 toter Code
- A3-01 bis A3-05 Pfade und Defaults
- A1-05 bis A1-11 (Tie-Schwelle, Shell-Literale, Jahre, Tests)
- C-03 Hauptjahr nicht doppelt
- C-06
- D-03, D-05, D-06
- E-02 bis E-07 Doku

**Optional**
- C-05 Extraktions-Rule (grösster Gewinn, grösster Umbau)
- D-07 Lock-Dateien
- D-08 Logs und Lint
- A2-10 bis A2-15
- A4

**Löschen nur nach Freigabe**
- B-04 data/processed alt (6 Dateien)
- B-05 graphics alt (41 Dateien)
- B-06 legacy/
- B-07 rules/

**Nur Bericht (würde Ausgaben ändern)**
- A2-06 Table-3-ID 2017/18
- A2-07 Anzeigename
- A2-08/E-08 Einheitstexte
- B-08
- C-07
- E-01

## Unsicher

- C-01/C-05: Bitidentität ist zu erwarten (gleiche Daten, gleiche numpy-Reduktionen), aber erst der Snapshot-Vergleich beweist sie; sonst rückgängig.
- E-01: ob das nationale Aggregat bewusst bei der alten Importdefinition bleibt.
- B-05/B-06: ob du `graphics/` (alt) oder `legacy/` noch für Overleaf oder Notizen brauchst.
- A2-06: ob die Spalte „Mellot-Kostenrang“ für 2017/2018 überhaupt sinnvoll ist (Table 3 gilt für 2016).
- Gewinn von C-01: geschätzt 50–70 % der Laufzeit der dateilastigen Rules (aus dem Profil), gemessen erst nach der Umsetzung.

## Umsetzung (Teil 2, 20.11.2026)

| Schritt | Inhalt | Prüfung |
|---|---|---|
| 1 | D-01 `src/`-Module als Inputs (ohne Fetch-Rules); D-02/D-03 `src/checks.py`: Mapping-Lücken, leere Auswahl, fehlende Kostenklasse stoppen; Test `tests/test_checks.py` | identisch, 191 Tests |
| 2 | Parameter, Mappings, Konventionen, Quellen nach `config/default.yaml` (neue Abschnitte `calliope`, `regions`, `attributes`, `mellot_cost_change_pct`, `sources`, `figures.display_names`, `price.elcom_product`); keine fachlichen Defaults im Code; `--config` erreicht `src/config.py` (Nachweis per Override); p_ref ±20 % in `sensitivity_runs.sh` abgeleitet | identisch, 191 Tests |
| 3 | 30 unerreichbare Definitionen und `__main__`-Block aus `src/` entfernt, tote Importe | identisch, 191 Tests |
| 4 | 63 getrackte Dateien (data/processed alt, graphics alt, legacy/, rules/.gitkeep) in den Backup-Ordner `/Users/josua/Documents/ETH/Semester Project/repo_cleanup_backup_2026-11-20`; Lint-Befunde behoben (`rules/common.smk`, Logs, `scripts/clean.py`) | identisch bis auf die verschobenen Dateien; Lint sauber |
| 5 | Doku: README, Config-Kommentare, Docstrings, Kartentexte; Tie-Konvention `report.*`, `docs/tie_groups.csv` | identisch bis auf Kartentext |
| 7 | C-01 jede .nc einmal lesen, C-04 Rule `regional_reference`, C-02 Memo, C-06 Bisektion ohne Ziehungen | identisch; voller Lauf 339 → 149 s |
| 6 | A2-06 Table-3-ID, A2-07 Anzeigename, A2-08 Einheitentexte, E-01 Import des nationalen Aggregats | Diff nur bei diesen Punkten; 18 Regressionstests des nationalen Aggregats warten auf das Neueinfrieren |
