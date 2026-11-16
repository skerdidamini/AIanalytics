# AI Camera Analytica — Cloud API minimale

Kjo pjesë pranon **eventet** nga Mini PC dhe i kthen në të dhëna raportimi. Nuk merr RTSP, video, foto ose identitete njerëzish. Përfshin edhe dashboard-in fillestar të pronarit me hyrje email/fjalëkalim. Raportimi me email mbetet për fazën pasuese.

Rrjedha: **kamera → edge → radhë lokale → HTTPS API → databazë qendrore → metrika/CSV**. Kur interneti bie, edge vazhdon ruajtjen lokale. Kur kthehet, ridërgon eventet; cloud-i deduplifikon UUID-të.

## Çfarë përfshin ky version

- FastAPI + Uvicorn, Python 3.10+.
- SQLite persistente për pilotin me një server. Kjo është zgjedhje MVP për prova, jo instalim PostgreSQL/TimescaleDB.
- Regjistrim organizatash, lokacionesh, node-sh dhe kamerash nga CLI administrative.
- Token i veçantë për node: mund të dërgojë vetëm për kamerat e regjistruara të tij.
- Token leximi i veçantë për organizatë: sheh vetëm raportet e atij biznesi.
- Pranim atomik i 1–100 eventeve në batch, maksimumi 1 MiB për kërkesë. Fusha të panjohura, lloje të tjera eventesh dhe payload-e video/foto refuzohen.
- Konfirmim `accepted_event_ids` pas commit-it. Ridërgimi identik konfirmohet pa shtuar rresht tjetër; e njëjta UUID me përmbajtje tjetër kthen 409.
- Metrika sipas orës UTC dhe CSV: hyrje, dalje, total/sesione qëndrimi të plotë në zona dhe peak i personave të dukshëm për kamerë.

## Instalimi dhe nisja lokale

Nga checkout-i ekzistues (nuk nevojitet worktree i ri):

```sh
cd /workspace/AIanalytics/cloud
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
umask 077
mkdir -p runtime
.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 serve
```

Në kompjuterin tënd përdor rrugën ku e ke shkarkuar projektin, jo domosdoshmërisht `/workspace/AIanalytics`. Serveri lidhet vetëm në loopback në portin 8080. `/healthz` kontrollon databazën; `/docs` përmban dokumentimin bazë të API-së. Schema e batch-it përcaktohet në `cloud_api/models.py` dhe kontrata është e njëjta me edge.

## Regjistrimi i pajisjes dhe autorizimi

Me serverin të ndalur ose në një terminal tjetër, nga dosja cloud:

```sh
.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 provision-node \
  --organization pilot-organization --location pilot-location --node edge-001 \
  --camera entrance-001 --token-file runtime/node.token

.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 provision-reader \
  --organization pilot-organization --token-file runtime/reader.token
```

Identifikuesit duhet të përputhen me JSON-in e edge. Përsërit `--camera` për të regjistruar disa kamera te i njëjti node. Gjenerohen token-a të rastësishëm në skedarë privatë 0600; vlerat nuk printohen. Databaza ruan vetëm hash SHA-256 të token-it. Një skedar ekzistues nuk mbishkruhet. Për rotacion, krijo token të ri në skedar të ri dhe revoko të vjetrin pasi pajisja kalon te i riu:

```sh
.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 revoke --token-file runtime/node.token
```

Mos fut token-at në Git, në URL, në frontend ose në chat. Token-i reader nuk është token node dhe nuk lejohet të dërgojë evente. Për MVP provisioning bëhet nga administratori në server; nuk ekspozohet endpoint publik regjistrimi.

## Lidhja me edge

Pasi API të jetë vendosur pas një adrese reale HTTPS:

1. Transfero në mënyrë të sigurt kredencialin e node-it në Mini PC dhe jepja procesit si `EDGE_CLOUD_TOKEN`.
2. Vendos `EDGE_CLOUD_URL` te adresa e plotë e endpoint-it `/v1/events` të serverit tënd.
3. Nis nga dosja edge:

```sh
.venv/bin/ai-camera-edge --config config.local.json sync --watch
```

Sync është proces i veçantë nga analiza dhe paneli lokal; ky version nuk e nis automatikisht. TLS verification nuk çaktivizohet. Serveri HTTP lokal i zhvillimit shërben për API/teste; edge me qëllim kërkon HTTPS. Pas një refuzimi 401/403/409/422, rregullo kredencialet ose eventin e pavlefshëm; edge ruan radhën dhe nuk i hedh eventet. Një batch i pavlefshëm bllokohet i tëri; karantina e eventeve të këqija mbetet për fazën pasuese.

## Endpoint-et

| Endpoint | Autorizimi | Qëllimi |
|---|---|---|
| `GET /healthz` | Publik | Kontroll bazë i shërbimit/databazës |
| `POST /v1/events` | Token node | Evente metadata; përgjigje `accepted_event_ids` |
| `GET /v1/metrics/hourly?start=...&end=...` | Token reader | Përmbledhje të organizatës së autorizuar |
| `GET /v1/reports/hourly.csv?start=...&end=...` | Token reader | Eksport CSV |

Autorizimi: `Authorization: Bearer <credential>`; mos e vendos në query string. `start` dhe `end` janë Unix timestamps UTC; fundi është ekskluziv, intervali maksimal 31 ditë. Filtra opsionalë: `location_id`, `camera_id`. Parametri `organization_id` nuk përdoret për të zgjedhur biznesin: organizata merret nga kredenciali. Për biznes tjetër duhet token i atij biznesi.

Model i batch-it:

```json
{
  "schema_version": 1,
  "events": [{
    "event_id": "00000000-0000-4000-8000-000000000001",
    "type": "person_entered",
    "timestamp": 1700000000.0,
    "organization_id": "pilot-organization",
    "location_id": "pilot-location",
    "node_id": "edge-001",
    "camera_id": "entrance-001",
    "details": {"track_id": "session-local-id"}
  }]
}
```

Timestamp-et më shumë se 5 minuta në të ardhmen refuzohen. Eventet e vjetra lejohen për offline sync. Raportet grupohen sipas kohës së eventit, jo momentit të mbërritjes. Intervalet pa evente nuk prodhojnë rreshta zero; mungesa e rreshtave nuk vërteton që kamera ishte online me zero vizitorë.

## Kuptimi i metrikave

- Hyrje/dalje janë kalime të vijës së kamerës, jo vizitorë unikë midis kamerave.
- Peak është maksimumi i snapshot-eve të personave të dukshëm **për kamerë**, jo occupancy e garantuar e gjithë biznesit.
- Kohëqëndrimi përfshin vetëm sesionet e zonave të mbyllura normalisht. Sesionet `censored` përjashtohen. Totali bashkon zonat; në zona që mbivendosen mund të ketë kohë të numëruar në disa zona. Nuk është kohë mesatare e gjithë vizitës.
- Agregimet llogariten nga eventet kur bëhet kërkesa; nuk ka ende scheduler ose tabela të materializuara.
- Cilësia e raportit varet nga detektimi/kalibrimi edge. Backend-i nuk korrigjon gabimet e HOG.

## Testimi dhe çfarë është verifikuar

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/pip check
```

21 teste: deduplikim, konfirmim, role, izolim biznesesh/node-sh/kamerash, rollback, kufij batch-i, schema, qëndrim i ndërprerë, persistencë, revokim dhe CSV. Testi integrues përdor evente të gjeneruara nga `edge_analytics.Analytics`, radhën SQLite dhe funksionin real `sync_batch` kundër Uvicorn HTTPS. Simulon commit me konfirmim të humbur, ridërgon dhe verifikon vetëm 1 hyrje në raport. Përdor certifikatë provë të besuar shprehimisht brenda testit; verifikimi TLS dhe hostname mbeten aktivë. Kërkon `openssl` dhe dosjen edge pranë cloud.

## Para përdorimit publik

Ky version është testuar lokalisht dhe **nuk është deploy-uar në një cloud publik**. Ende duhen server/domain, certifikatë reale HTTPS ose reverse proxy, secrets në shërbim, backup/restore, monitorim, rate limiting në hyrje, autostart dhe politikë arkivimi. SQLite është për një instancë pilot me disk persistent lokal; PostgreSQL dhe migrimet duhen para zgjerimit në disa instanca. Mos e vendos databazën në filesystem efemer. Për eksport live/backup përdor SQLite backup API ose snapshot konsistent; mos kopjo vetëm skedarin kryesor ndërsa WAL është aktiv.

Mungojnë ende rikuperimi/ndryshimi i fjalëkalimit nga përdoruesi, verifikimi i emailit, MFA, menaxhimi i përdoruesve nga UI, PDF, dërgimi i raporteve me email, menaxhimi në distancë i pajisjeve dhe monitorimi i shëndetit të tyre. Token-at reader mbeten për akses teknik; pronari përdor llogarinë e vet dhe sesionin e shfletuesit. API nuk aktivizon CORS të hapur dhe nuk kërkon që token-at të futen në faqen publike.

## Dashboard-i i pronarit

Dashboard-i shërbehet te rruga kryesore `/` e backend-it. Nuk është HTML që punon veçmas nga serveri. Për nisjen e parë, krijo llogarinë nga terminali i administratorit:

```sh
.venv/bin/ai-camera-cloud --database runtime/cloud.sqlite3 create-owner \
  --organization pilot-organization --email owner@example.com
```

Komanda kërkon fjalëkalimin në terminal pa e shfaqur (12–256 karaktere) dhe kërkon konfirmim. Ndrysho emailin sipas pronarit real; nuk krijohet llogari demo apo fjalëkalim standard. `organization` duhet të jetë i njëjti identifikues me pajisjet e biznesit. Për instalim automatik mund të përdoret `--password-file` me skedar privat jashtë Git. Mos dërgo fjalëkalime në chat.

Pastaj nis backend-in me komandën `serve` më sipër dhe hap faqen kryesore në shfletues. Në Windows përdor `.venv\Scripts\python.exe` dhe `.venv\Scripts\ai-camera-cloud.exe` për komandat ekuivalente.

Paneli përfshin:

- Hyrje me email/fjalëkalim dhe dalje që revokon sesionin në server.
- Identitetin e biznesit dhe inventarin vetëm të lokacioneve/kamerave të autorizuara.
- Filtra datash (interval deri në 31×24 orë), lokacioni dhe kamere, përfshirë node-in kur ID-të e kamerave përsëriten.
- Hyrje/dalje të regjistruara, mesatare të ponderuar të kohës së sesioneve të plota në zona dhe peak të personave të dukshëm kur zgjidhet një kamerë.
- Grafik të fluksit, tabelë orare dhe shkarkim CSV nga API-ja e autorizuar.
- Gjendje bosh/gabimi pa numra të shpikur. Tabela shfaq deri 200 rreshta; CSV përmban të gjithë intervalin. Grafiku bashkon orë në deri 60 grupe kur ka shumë të dhëna.

Datat e zgjedhura interpretohen si ditë në timezone e shfletuesit, pastaj shndërrohen në UTC për API-në; grafiku/tabela përdorin orë lokale. Agregimet bazë mbeten orare UTC. Sesionet e zonave që kalojnë disa orë atribuohen sipas eventit të përfundimit.

Fjalëkalimet përdorin PBKDF2-HMAC-SHA256 me kripë të rastësishme dhe 600000 iteracione. Cookie është HttpOnly, SameSite=Strict dhe afat 8 orë; databaza ruan vetëm hash-in e token-it të sesionit. Fjalëkalimi/token-i nuk ruhen në localStorage. Login kufizohet pas 5 tentativash për email në 5 minuta dhe 20 për burim; kjo nuk zëvendëson rate limiting në reverse proxy.

Në HTTP lokal/loopback CLI përdor cookie jo-Secure vetëm për zhvillim. Me TLS direkt cookie bëhet Secure. Në prodhim pas reverse proxy HTTPS nise patjetër me **`--secure-cookies`**, ruaj Host-in origjinal dhe mos lejo akses publik direkt te porti HTTP i backend-it. Login/logout kontrollojnë Origin dhe nuk lejojnë kërkesa nga faqe të tjera. API-të ekzistuese vazhdojnë të pranojnë token-at teknikë; sesioni i pronarit ka vetëm rol reader dhe nuk mund të dërgojë evente edge.

Testet e llogarive mbulojnë cookie-t, daljen/revokimin, skadimin, kufizimin e tentativave, Origin dhe izolimin e inventarit. Test opsional i shfletuesit (Playwright/Chromium): `python3 tests/browser_dashboard.py` nga dosja cloud. Ai përdor databazë dhe evente sintetike të përkohshme; nuk fut të dhëna demonstrative në databazën e përdoruesit. Dashboard-i ende nuk është deploy-uar publikisht dhe llogaritë reale duhen krijuar nga administratori.

## Provë në PC Windows pa hosting

Udhëzuesi [FILLIMI-WINDOWS.md](../FILLIMI-WINDOWS.md) dhe skriptet në rrënjën e projektit përgatisin `.venv` dhe nisin serverin në loopback. Demo përdor `runtime/demo.sqlite3`, krijon llogarinë e zgjedhur nga përdoruesi dhe evente sintetike idempotente për ditët e fundit. `/v1/me` shënon modalitetin demo dhe UI shfaq banner të qartë. Mënyra reale përdor `runtime/local.sqlite3` pa seed. Të dyja databazat dhe sesionet qëndrojnë lokale, jashtë Git. Demo nuk lidhet me kamerë dhe nuk krijon pagesa hosting.

Testet shtesë mbulojnë krijimin e llogarisë, seed të përsëritur pa dublikime dhe ndarjen demo/reale. Kontrolli opsional i runtime-it lokal: `python3 tests/browser_local.py`. Nisja Python u provua në Linux; wrapper-i Windows `.cmd` pret verifikim në PC real Windows.
