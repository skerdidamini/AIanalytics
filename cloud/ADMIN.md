# Paneli Admin dhe lidhja me teknikun

Ky version bashkon regjistrin e klientëve me kalibrimin dhe raportimet e pajisjeve. Ende është prototip për pilotim, jo shërbim publik i deploy-uar.

## Prova në Windows

1. Mbyll terminalin ku po punon demoja e pronarit. Admin përdor të njëjtin server/port dhe databazë demo.
2. Ruaj dosjen e vjetër dhe sidomos `cloud/runtime`. Nxirr kodin e përditësuar; mos fshi llogaritë/databazat gjatë përditësimit.
3. Hap **NIS-ADMIN-WINDOWS.cmd**. Në nisjen e parë krijo llogarinë Admin me email të ndryshëm nga pronari ekzistues dhe fjalëkalim tëndin, të paktën 12 karaktere. Nuk ka Admin ose fjalëkalim standard.
4. Hyr në formularin që hapet në shfletues me llogarinë Admin. Llogaria e vjetër e pronarit mbetet e veçantë.
5. Krijo një biznes, lokacion, Mini PC dhe kamera. Te llogaritë krijo pronarin ose teknikun. Cakto teknikun te lokacioni.
6. Dil dhe hyr me llogarinë e teknikut. Ai sheh vetëm kamerat e lokacioneve të caktuara; “Kalibro” hap konfigurimin me ID-të e plotësuara nga serveri.
7. Ruaj draft, ngarko pamjen e duhur, kontrollo manualisht kalibrimin dhe ruaj kontrollin manual.
8. Hyr si Admin dhe aktivizo versionin e kontrolluar. Shkarko JSON-in aktiv dhe instaloje në kamerën/pajisjen përkatëse. Shkarkimi dhe aktivizimi nuk konfirmojnë instalimin real.

Demo mbetet te `cloud/runtime/demo.sqlite3`; mënyra reale lokale mbetet te `cloud/runtime/local.sqlite3`. Paneli nuk shënon kamerat si online vetëm sepse demo ka evente. Fjalëkalimet dhe kredencialet nuk dërgohen automatikisht me email. Për handover përdor kanalin tënd të sigurt.

## Administrator në një server real

Nga dosja cloud, pasi të instalohet paketa:

```sh
.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 create-admin --email admin@example.com
.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 serve
```

Komanda kërkon fjalëkalimin fshehtas. Përdor emailin tënd. Nga faqja kryesore hap **Log In**. Të gjitha rolet përdorin të njëjtën hyrje; për të ndërruar llogari, dil nga sesioni aktual. Në prodhim kërkohet HTTPS dhe `--secure-cookies` pas reverse proxy sipas README-së kryesore cloud. Windows përdor `.venv\\Scripts` për komandat ekuivalente.

Administratorë të tjerë krijohen vetëm nga CLI; paneli web krijon vetëm pronarë dhe teknikë, pa mundësi ngritjeje të rolit në Admin. Llogaritë ekzistuese migrohen si pronarë me të drejtat e mëparshme. Teknikët mund të caktohen në disa lokacione/biznese dhe të hiqen nga caktimet; serveri kontrollon caktimin në çdo kërkesë.

## Regjistri dhe kredencialet

- Krijimi i biznesit nuk krijon automatikisht llogari pronari: krijoje te “Llogaritë / teknikët” dhe zgjidh biznesin.
- Krijimi i Mini PC-së dhe kamerës është regjistrim në databazë, jo lidhje fizike me NVR.
- “Kredencial i ri” shkarkon një token të rastësishëm, të lidhur vetëm me atë node. Vlera nuk shfaqet në tabelë, audit ose log-e; ruhet në DB vetëm hash-i. Skedari `device.token` duhet dorëzuar dhe ruajtur në mënyrë të sigurt. Mos e ngarko në Git ose chat.
- Krijimi i një kredenciali të ri nuk revokon të vjetrin, për të shmangur ndërprerjen e pajisjes gjatë rotacionit. Revokimi bëhet me komandën `revoke --token-file` të dokumentuar te README cloud.
- Token-i vendoset në ambientin e Mini PC si `EDGE_CLOUD_TOKEN`; adresa HTTPS `/v1/events` si `EDGE_CLOUD_URL`. Nuk futet në JSON-in e kalibrimit.

## Kalibrimi me versione

Kalibruesi i platformës është te `/installer/`, por hapet nga kamera e caktuar. Pamja/videoja vazhdon të qëndrojë në shfletues. Serveri vendos/kontrollon `organization_id`, `location_id`, `node_id`, `camera_id`; një JSON i klientit tjetër refuzohet.

Çdo ruajtje krijon version të ri, pa ndryshuar versionet e vjetra. `expected_version` shmang mbishkrimin kur dy persona punojnë njëkohësisht. Statuset:

- **Pa filluar**: ende s'ka konfigurim në platformë.
- **Draft**: konfigurim i ruajtur për punë.
- **Kontroll manual**: tekniku ka ruajtur konfigurim të vlefshëm me konfirmim të pamjes fikse. Nuk është certifikim i saktësisë së AI-së.
- **Version aktiv**: Admin e ka zgjedhur për instalim. Nuk do të thotë që pajisja e ka marrë.
- **Version i konfirmuar**: heartbeat i freskët nga pajisja raporton versionin dhe SHA-256 që përputhen me versionin aktiv.

Eksporti aktiv përmban `deployment.calibration_version` dhe `deployment.configuration_sha256`. Hash-i llogaritet mbi JSON-in kanonik pa objektin `deployment`; edge e rillogarit nga skedari real në nisjen e worker-it. Ndryshimi lokal i parametrave pa krijuar version të ri prish përputhjen dhe nuk shfaqet si version i konfirmuar.

Në panelin lokal të Mini PC-së, konfigurimi që ka `deployment` nis nga skedari ekzistues pa autosave të formularit. Ndryshimet për një konfigurim të menaxhuar bëhen në platformë dhe aktivizohen si version i ri. Instalimi në këtë version është manual (kopjim i JSON-it); endpoint-i `/v1/device/config?camera_id=...` ekziston, por nuk ka ende shkarkim/aplikim automatik në background ose rollout të flotës.

## Heartbeat dhe mbërritja e eventeve

Për gjendje të saktë, nise worker-in dhe sync-un me të njëjtin konfigurim e health file, nga dosja edge:

```sh
.venv/bin/ai-camera-edge --config config.local.json run --health-file worker-health.json
.venv/bin/ai-camera-edge --config config.local.json sync --watch --health-file worker-health.json
```

Këto janë dy procese/terminale të ndara. Nëse përdor panelin lokal për nisje/ndalim, nise atë me `ai-camera-panel --config config.local.json --health-file worker-health.json` dhe përdor të njëjtin health file në procesin sync. Kërkohet që burimi RTSP ose `--video` i provës të jetë konfiguruar. Fjalëkalimi RTSP jepet veçmas përmes ambientit. Worker-i shkruan identitetin e kamerës, kohën e përpunimit të frame-it dhe provën e konfigurimit. Sync-u dërgon heartbeat rreth çdo 30 sekonda, edhe pa evente të reja. Një health file i vjetruar ose i një kamere tjetër nuk përdoret si provë përpunimi.

| Matja | Kuptimi |
|---|---|
| Pajisja Online | Heartbeat është pranuar në server brenda 90 sekondave |
| Frame po përpunohen | Raporti i kamerës dhe koha e frame-it janë të freskëta |
| Pa heartbeat / pa të dhëna | Nuk ka provë; nuk supozohet që pajisja është online |
| Raport/frame i vjetruar | Raportimi nuk është më i freskët |
| Evente në DB | Sa evente janë pranuar dhe kur ka ndodhur mbërritja e fundit |
| Koha e eventit | Koha e deklaruar kur ka ndodhur ngjarja; mund të jetë e vjetër kur vjen backlog offline |

`last_frame_at` është koha kur frame-i u përpunua në Mini PC, jo garanci që NVR nuk po jep video të vjetër. Statuset janë raportime nga node i autorizuar, jo verifikim i pavarur i videos nga cloud. Nëse sync nuk merr health file, mund të konfirmojë komunikimin e node-it, por kamera mbetet e panjohur. Dështimi i heartbeat nuk hedh eventet nga radha; sync i eventeve provohet veçmas. Paneli rifreskohet çdo 30 sekonda kur tab-i është aktiv.

## Kontrolli i aksesit dhe verifikimi

Admin sheh regjistrin global. Teknikët shohin vetëm lokacionet e caktuara dhe nuk aktivizojnë versione, nuk krijojnë biznese ose kredenciale. Pronari mbetet te raportet e biznesit të tij. Veprimet administrative kërkojnë sesion të vlefshëm dhe Origin të njëjtë. Kërkesat kufizohen në 1 MiB përpara parsimit të modeleve. Audit mban 50 veprimet e fundit në UI pa fjalëkalime/token-a.

```sh
cloud/.venv/bin/python -m unittest discover -s cloud/tests -v
edge/.venv/bin/python -m unittest discover -s edge/tests -v
python3 cloud/tests/browser_admin.py
```

Testet kontrollojnë role/caktime, regjistrin, sekretet jashtë audit-it, versionet dhe konfliktet, ID-të e kamerës, aktivizimin dhe përputhjen e hash-it, heartbeat të vjetruar dhe origjinë të gabuar të health file. Prova HTTPS përdor funksionet reale edge të sync-ut dhe heartbeat-it. Testi i shfletuesit krijon një instalim, llogari tekniku, kalibron kamerën e caktuar, aktivizon versionin dhe shkarkon JSON-in.

Kopjet e kalibruesit në `cloud_api/installer` kontrollohen ndaj versionit standalone nga testet; kur ndryshon kalibruesi duhet të sinkronizohen skedarët e UI-së dhe validatori i pastër server-side. Nuk instalohet OpenCV në backend vetëm për të validuar konfigurimin.

Mbeten për më vonë: monitorim hardware/disk, autostart i plotë i edge, alerts/email, rollout automatik i konfigurimit, ftesa dhe rikuperim fjalëkalimesh, emra/ndryshime/fshirje të regjistrit dhe testim fizik në NVR/Mini PC. Backup dhe deploy publik mbeten sipas planit të pilotit.

Ngjarjet e simuluara krijohen vetëm te biznesi `demo-business`, pavarësisht rendit të llogarive të pronarëve. Versionet e vjetra mund të kenë krijuar `demo-location` te një biznes tjetër; përditësimi nuk fshin këto të dhëna. Për prova pa to, filtro vendndodhjen/kamerën reale (jo “Të gjitha”).

## Faqja kryesore dhe hyrja e përbashkët

Serveri shërben faqen prezantuese në `/`, hyrjen e përbashkët në `/login`, panelin e pronarit në `/panel`, Adminin në `/admin` dhe teknikun në `/technician`. Të gjitha janë pjesë e së njëjtës platformë dhe përdorin të njëjtin sesion. Roli merret nga serveri, jo nga një zgjedhje në formular. Skedarët `cloud_api/public` paketohen për instalimin; kur ndryshon faqja kryesore, sinkronizo `index.html`, `styles.css`, `scripts.js`, `i18n.js` dhe `demo.js` nga rrënja e projektit.

Faqja kryesore ka zgjedhjen SQ / EN (shqip në vizitën e parë); shfletuesi ruan vetëm preferencën e gjuhës. Hyrja dhe panelet mbeten në shqip. Tekstet e kontaktit ndërrojnë gjuhë pa humbur fushat e plotësuara.

Demonstrimi në krye të faqes është animim SVG lokal, jo analizë video dhe nuk krijon evente në DB. Numëron dy kalime për cikël, ka pauzë/vazhdim dhe nis i ndalur me preferencën për lëvizje të reduktuara.

Tre skena të tjera ilustruese paraqesin grupet në tavolina, pritjen për kamarierin/qëndrimin dhe pritjen në banak. Koha është e përshpejtuar dhe e simuluar; nuk janë matje reale ose funksione aktive të klasifikimit të stafit/seancave në tavolinë. Nuk dërgojnë të dhëna në API.

Të katër simulimet janë bashkuar në krye të faqes me skedat Hyrje / Tavolinat / Shërbimi / Takeaway. Hyrjet shfaqen fillimisht; kalimi bëhet me klikim ose shigjetat e tastierës.
