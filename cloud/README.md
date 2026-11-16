# AI Camera Analytica — Cloud API minimale

Kjo pjesë pranon **eventet** nga Mini PC dhe i kthen në të dhëna raportimi. Nuk merr RTSP, video, foto ose identitete njerëzish. Nuk ka ende dashboard, login përdoruesish ose raportim me email.

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

12 teste: deduplikim, konfirmim, role, izolim biznesesh/node-sh/kamerash, rollback, kufij batch-i, schema, qëndrim i ndërprerë, persistencë, revokim dhe CSV. Testi integrues përdor evente të gjeneruara nga `edge_analytics.Analytics`, radhën SQLite dhe funksionin real `sync_batch` kundër Uvicorn HTTPS. Simulon commit me konfirmim të humbur, ridërgon dhe verifikon vetëm 1 hyrje në raport. Përdor certifikatë provë të besuar shprehimisht brenda testit; verifikimi TLS dhe hostname mbeten aktivë. Kërkon `openssl` dhe dosjen edge pranë cloud.

## Para përdorimit publik

Ky version është testuar lokalisht dhe **nuk është deploy-uar në një cloud publik**. Ende duhen server/domain, certifikatë reale HTTPS ose reverse proxy, secrets në shërbim, backup/restore, monitorim, rate limiting në hyrje, autostart dhe politikë arkivimi. SQLite është për një instancë pilot me disk persistent lokal; PostgreSQL dhe migrimet duhen para zgjerimit në disa instanca. Mos e vendos databazën në filesystem efemer. Për eksport live/backup përdor SQLite backup API ose snapshot konsistent; mos kopjo vetëm skedarin kryesor ndërsa WAL është aktiv.

Mungojnë ende llogaritë e përdoruesve, paneli i biznesit, PDF, dërgimi i raporteve me email, menaxhimi në distancë i pajisjeve dhe monitorimi i shëndetit të tyre. Token-at reader janë akses teknik provizor, jo sistem login për klientë finalë. API nuk aktivizon CORS të hapur dhe nuk kërkon që token-at të futen në faqen publike.
