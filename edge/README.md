# AI Camera Analytica — Edge PoC 0.1

Versioni i parë për **një kamerë për proces**, i ndarë nga website-i. Bazuar në dokumentet orientuese të projektit: përpunim lokal, evente anonime dhe ruajtje kur mungon interneti. Ky është proof of concept për zhvillim, jo sistem i validuar për klientë.

## Çfarë punon

- Video lokale ose RTSP nga kamera/NVR; sampling dhe reconnect.
- Detektor personash OpenCV HOG/SVM në CPU, pa shkarkim modeli.
- Tracker bazë me distancë midis pikave të poshtme të detektimeve.
- Vijë e kufizuar hyrje/dalje me brez tolerance kundër dridhjeve.
- Zona drejtkëndore, hyrje/dalje në zona dhe kohë e dukshme e qëndrimit.
- Snapshot i personave të dukshëm për kamerë/zonë.
- SQLite WAL: evente me UUID dhe radhë persistente; ringritja ruan eventet.
- Sync i veçantë HTTPS me konfirmim eksplicit të ID-ve dhe retry/backoff.
- Raport CSV sipas orës UTC dhe kontroll i radhës nga CLI.

Nuk ruan apo dërgon video/foto. Track ID është lokal për sesionin e kamerës; nuk identifikon individë midis kamerave. Eventet përmbajnë organizatë, lokacion, node dhe kamerë.

## Instalimi

Python 3.10+ (u testua me 3.12 në Linux):

```sh
cd /workspace/AIanalytics/edge
python3 -m venv .venv
.venv/bin/pip install -e .
cp config.example.json config.local.json
.venv/bin/python -m unittest discover -s tests -v
```

Përdor checkout-in ekzistues; një task cloud është tashmë i izoluar. Mos krijo worktree nëse nuk kërkohet.

## Provë pa kamerë

```sh
.venv/bin/ai-camera-edge --config config.local.json replay examples/crossing.jsonl
.venv/bin/ai-camera-edge --config config.local.json status
.venv/bin/ai-camera-edge --config config.local.json report --output /tmp/edge-report.csv
```

Me një databazë të re, shembulli prodhon 1 hyrje, 0 dalje dhe 1 sesion zone të përfunduar. Çdo ekzekutim është sesion i ri; përsëritja shton evente të reja. Mos përziej të dhënat demonstrative me të dhënat e pilotit. Raporti përmbledh kohëqëndrimin e zonave bashkë; nuk është mesatare vizitash apo raport sipas zonës. Sesionet e ndërprera nuk përfshihen në totalin e sesioneve të plota.

## Video dhe kamera

```sh
.venv/bin/ai-camera-edge --config config.local.json run --video /path/to/video.mp4
```

Për kamerë/NVR, vendos `EDGE_RTSP_URL` në mjedisin e procesit përmes konfigurimit të sigurt të pajisjes. Mos e shkruaj në Git, chat ose argumente CLI, sepse mund të përmbajë kredenciale. Pastaj:

```sh
.venv/bin/ai-camera-edge --config config.local.json run
```

`Ctrl+C`/SIGTERM ndal procesin. Kur stream ndërpritet, track-et mbyllen si sesione të paplota dhe provohet rilidhja pas 5 sekondash. Video lokale përfundon në EOF; `--max-frames 100` kufizon provën. Native logging i OpenCV/FFmpeg çaktivizohet për të ulur rrezikun e shfaqjes së URL-së së kamerës; kontrollo log-et gjatë instalimit real.

## Kalibrimi

Koordinatat janë relative 0–1: `[x,y]`. Pika e një personi është qendra e poshtme e bounding box. Për vijën nga majtas në djathtas, `enter_side: 1` do të thotë lëvizje drejt pjesës së poshtme të figurës; `-1` e përmbys. Një kalim numërohet vetëm nëse trajektorja pret segmentin e vijës. Kalo vijën me këmbë në të dy drejtimet gjatë kalibrimit dhe krahaso manualisht.

`line.margin` shmang luhatjet pranë vijës. `track_distance` dhe `track_timeout` kontrollojnë lidhjen e detektimeve. `zones` janë drejtkëndësha `[x1,y1,x2,y2]`. Duhet kalibrim për çdo kamerë. Një kalim i humbur ose një ID e ndryshuar mund të ndryshojë numërimin.

## Cloud sync — kontrata, jo backend i ndërtuar

Backend-i minimal cloud tani ndodhet te `../cloud`; është testuar lokalisht me HTTPS, por nuk është ende deploy-uar publikisht. Shih `../cloud/README.md` për regjistrimin e node-it dhe kontratën e API-së. Formspree shërben vetëm website-in dhe **nuk përdoret për eventet e kamerës**. Vendos `EDGE_CLOUD_URL` dhe `EDGE_CLOUD_TOKEN` në ambientin e pajisjes vetëm kur të ekzistojë API-ja përkatëse.

```sh
.venv/bin/ai-camera-edge --config config.local.json sync --watch
```

Ekzekutohet si proces i veçantë, me të njëjtin konfigurim/SQLite si analiza. POST HTTPS me `Authorization: Bearer …`:

```json
{"schema_version":1,"events":[{"event_id":"uuid","type":"person_entered","timestamp":1700000000.0,"organization_id":"pilot-organization","location_id":"pilot-location","node_id":"edge-001","camera_id":"entrance-001","details":{"track_id":"session-local-id"}}]}
```

Përgjigjja duhet të jetë JSON: `{"accepted_event_ids":["uuid"]}`. Vetëm ID-të e pranuara shënohen synced. Backend-i duhet të deduplifikojë `event_id`, të lidhë token-in me node/tenant-in dhe të mos besojë identifikuesit e klientit si autorizim. Pas humbjes së përgjigjes eventi ridërgohet me të njëjtën UUID (at-least-once). TLS verification mbetet aktiv. Nuk ka dërgim automatik nëse sync nuk niset.

## Kufijtë dhe hapi i ardhshëm

- HOG është baseline me dobësi në pamje nga lart, errësirë, mbulim dhe turma. Duhet vlerësuar OpenVINO/model modern pas marrjes së videos dhe hardware-it.
- Tracker-i me distancë mund të ndërrojë ID në turma. Nuk ka re-identifikim ose bashkim të kamerave.
- Occupancy është **numër personash të dukshëm**, jo total i garantuar i njerëzve në biznes.
- Dwell është qëndrim i dukshëm në zonë. Humbja e track-ut shënohet `censored: true`; nuk paraqitet si vizitë e përfunduar. Ndalimi i detyruar mund të humbasë sesionin aktiv, por jo eventet e kryera në SQLite.
- Sampling ul inferencën, por jo domosdoshmërisht koston e dekodimit. Numri i kamerave që përballon pajisja ende nuk është matur.
- Kufiri `queue_max_events` ndalon procesin në vend që të hedhë evente pa njoftim. Eventet synced ruhen; politika e arkivimit/retention dhe monitorimi i hapësirës në disk duhen shtuar për prodhim.
- `status` në CLI kontrollon radhën lokale. Paneli i pajisjes tregon edhe gjendjen e procesit dhe frame-t e përpunuar; nuk është monitorim i plotë i hardware-it/cloud.
- Mungojnë ende deploy si shërbim/systemd ose Docker, health dashboard, menaxhimi i konfigurimit nga cloud dhe backend-i i raporteve.

Testet automatike mbulojnë drejtimin, dridhjet, segmentin e kufizuar, skadimin e track-ut, dwell të plotë/të ndërprerë, persistencën, deduplikimin lokal, kapacitetin, konfirmimet e pjesshme dhe dështimin e rrjetit. Prova e videos sintetike verifikon dekodimin dhe ekzekutimin e HOG, jo saktësinë në njerëz realë. Kamera reale dhe saktësia mbeten të patestuara. Sync me backend-in minimal është testuar përmes HTTPS lokal; deploy publik mbetet i paprovuar.

## Paneli lokal i kalibrimit

Paneli është statik dhe mund të hapet nga `calibration/index.html` në shfletues. Nëse politika e shfletuesit bllokon skedarët lokalë, nga dosja e projektit nis `python3 -m http.server 8000 --bind 127.0.0.1`, pastaj hap shtegun `/edge/calibration/index.html` në serverin lokal. Testet në këtë ambient u kryen përmes HTTP lokal, sepse politika e Chromium bllokon file://. Ngarko një foto PNG/JPEG/WebP të pamjes fikse të kamerës. Zgjidh mjetin e vijës dhe kliko dy pika; shigjeta jeshile tregon drejtimin e hyrjes. Për zonat, kliko dy cepat e kundërt të një drejtkëndëshi. Mund të përdorësh edhe fushat numerike me tastierë.

Shkarko `config.local.json`, vendose në dosjen `edge` dhe rinis procesin me `--config config.local.json`. Paneli shkarkon skedar në kompjuter; nuk e instalon automatikisht në pajisje. Importo konfigurimin ekzistues për të ruajtur parametrat e runtime-it dhe rrugën e databazës. Mos ndrysho kornizimin/aspektin e pamjes midis kalibrimit dhe analizës. Për konfigurimin e disa kamerave ruaj një JSON për secilën, me `camera_id` të ndryshëm.

Pamja qëndron në shfletues dhe nuk përfshihet në JSON. Paneli nuk lexon stream RTSP, nuk kryen detektim dhe nuk lidhet me cloud. Nëse mbyll panelin pa eksportuar, ndryshimet nuk ruhen. Nuk ka ruajtje të fshehtë në localStorage.

Test opsional i panelit me Python Playwright dhe Chromium: `python3 calibration/test_browser.py` nga dosja edge. Testi kontrollon edhe eksportin me validatorin real Python; kërkon instalimin ekzistues në `.venv`. Këto varësi të shfletuesit nuk nevojiten në Mini PC për të ekzekutuar analytics.

## Paneli i pajisjes: ruaj / nis / ndalo

Në Mini PC Linux (ose macOS për zhvillim), instalo/refresko paketën nga dosja `edge`:

```sh
.venv/bin/pip install -e .
.venv/bin/ai-camera-panel --config config.local.json
```

Pastaj hap shfletuesin **në të njëjtën pajisje**, te adresa lokale që shfaq terminali (porti standard 8765). Paneli shërbehet vetëm në 127.0.0.1; nuk hapet nga telefoni përmes IP-së së Mini PC. Windows mund të përdorë kalibruesin statik, por paneli i procesit për momentin kërkon Linux/macOS.

Për lidhje reale, `EDGE_RTSP_URL` duhet të jetë konfiguruar në ambientin e procesit para nisjes së panelit. Adresa nuk kërkohet në faqe dhe nuk shfaqet në përgjigjet API. Për test me video lokale:

```sh
.venv/bin/ai-camera-panel --config config.local.json --video /path/to/video.mp4
```

- **Ruaj në pajisje**: validon JSON-in dhe zëvendëson konfigurimin atomikisht. Databaza fiksohet te `events.sqlite3` në të njëjtën dosje, pavarësisht rrugës në JSON-in e importuar. Eventet ekzistuese nuk fshihen.
- **Ruaj dhe nis analizën**: ruan fushat aktuale dhe nis worker-in Python me konfigurimin e ri. Bllokohet nëse mungon burimi ose ka proces tjetër të nisur nga ky panel.
- **Ndalo analizën**: ndalon vetëm worker-in e nisur nga ky panel. Nëse nuk mbyllet brenda 15 sekondash, ndërpritet me forcë; një sesion aktiv mund të mbetet i paplotë, por eventet e kryera në SQLite mbeten.
- **Statusi**: dallon nisjen, përpunimin e frame-ve, rilidhjen, statusin e vjetruar dhe ndalimin. Proces aktiv nuk do të thotë domosdoshmërisht kamerë online. Shfaq frame-t, orën e fundit të përpunimit dhe eventet lokale në pritje. “Frame i fundit” mat kohën kur u përpunua frame-i, jo freskinë e garantuar të stream-it në NVR.

Ruajtja bllokohet gjatë analizës; ndalo, ndrysho dhe rinis. Për këtë version përdor vetëm një panel dhe një worker për këtë kamerë; mos nis paralelisht një `run` manual. Paneli nuk nis cloud sync dhe nuk përmirëson saktësinë e modelit HOG. Ndërrimi i `camera_id` nuk fshin historikun e kamerës së mëparshme. Mbyllja e panelit në terminal ndalon edhe worker-in; mbyllja e tab-it të shfletuesit e lë analizën në punë. Nuk ka ende autostart pas reboot-it ose ruajtje automatike të fotos.

Serveri përdor kufizim Host/Origin dhe token për veprime, pa CORS të hapur. Nuk është panel publik me login; mos e ekspozo në internet ose me proxy të hapur. Testet përfshijnë ruajtje/ringarkim, konfigurim të pavlefshëm, bllokim kërkesash nga origjina të tjera, nisje reale worker-i mbi video sintetike dhe ndalim me ruajtje eventesh. Kontrolli opsional nga shfletuesi: `python3 calibration/test_panel_browser.py` nga dosja edge.

## Kalibrimi i zgjeruar: foto/video, funksione zonash dhe mostra uniforme

Shih [calibration/README.md](calibration/README.md) për rrjedhën e re. Paneli pranon video lokale me pause/seek, zona tavoline/shërbimi/takeaway, lidhje shërbimi→tavolinë, mostra manuale RGB/HSV sipas rolit, provë gjeometrike hyrje/daljeje dhe kontroll manual të konfigurimit. Numërimi i vijës mund të çaktivizohet për kamerat e tavolinave; edge kontrollon edhe raportin e përmasave të pamjes kundrejt kalibrimit.

Mostrat dhe funksionet e zonave janë metadata për instalimin. Klasifikimi automatik i stafit dhe matjet e shërbimit ende nuk janë aktive; JSON i shënon të dyja false. Dallimi i stafit, tracking-u i përmirësuar dhe preview automatik i detektimeve kërkojnë zhvillimin/vlerësimin e modelit me video reale. Mos e paraqit kontrollin manual si validim të saktësisë së AI-së.

## Version i menaxhuar nga platforma dhe heartbeat

JSON-i aktiv nga Paneli Admin ka metadata `deployment` me version dhe hash. Worker-i e verifikon skedarin real dhe e përfshin provën në health file. Për raportim, nise `run --health-file worker-health.json` dhe veçmas `sync --watch --health-file worker-health.json`, me të njëjtin `--config`. Sync dërgon heartbeat rreth çdo 30 sekonda në endpoint-in fqinj `/v1/heartbeat`; pa health file të freskët të asaj kamere raportohet gjendje e panjohur, jo përpunim videoje. Lidhja mbetet HTTPS dhe token-i i pajisjes mbetet në ambient.

Paneli lokal nuk autosave-on një konfigurim që ka `deployment` kur nis analizën: përdor skedarin aktiv ekzistues, për të mos ndryshuar hash-in pa version të ri në platformë. Për konfigurime lokale të pamenaxhuara ruajtja/nisja mbetet si më parë. Detajet e autorizimit, kalibrimit dhe instalimit manual janë te `../cloud/ADMIN.md`.
