# Instalimi pilot në VPS

Shembulli përdor një VPS Linux me systemd, Python 3.10+, Caddy dhe një disk
persistent. Caddy shërben HTTPS dhe ia kalon kërkesat aplikacionit në
`127.0.0.1:8080`. Lejo trafikun publik në portat 80 dhe 443 dhe mbaj SSH
të aksesueshëm për administrim.

Krijo një përdorues sistemi me emrin `aianalytica` dhe vendos kopjen e projektit
në `/opt/aianalytica`. Kodi dhe mjedisi Python duhet të jenë të lexueshëm për
atë përdorues. Me një llogari administrimi:

```sh
cd /opt/aianalytica
sudo python3 -m venv .venv
sudo .venv/bin/pip install ./cloud
sudo install -m 644 cloud/deploy/aianalytica.service /etc/systemd/system/aianalytica.service
sudo systemctl daemon-reload
sudo systemctl enable --now aianalytica
curl --fail http://127.0.0.1:8080/healthz
```

Krijo llogarinë e parë të Adminit. Komanda kërkon fjalëkalimin në terminal.

```sh
sudo -u aianalytica /opt/aianalytica/.venv/bin/ai-camera-cloud \
  --database /var/lib/aianalytica/cloud.sqlite3 create-admin --email admin@example.com
```

Shto bllokun nga `Caddyfile` te konfigurimi i Caddy dhe zëvendëso
`{$AIANALYTICA_DOMAIN}` me emrin e domain-it. Drejto DNS-in te IP-ja e VPS-së,
valido konfigurimin me `caddy validate --config /etc/caddy/Caddyfile` dhe rifresko
Caddy me `sudo systemctl reload caddy`. Lëri Caddy-t header-in origjinal Host.
Kontrollo `/healthz`, hyrjen, raportet dhe dërgimin e një eventi provë.

Në këtë konfigurim backend-i sheh adresën lokale të Caddy-t si burim të
kërkesave. Kufiri ekzistues prej 20 tentativash hyrjeje në pesë minuta për burim
ndahet nga përdoruesit e pilotit.

## Kopje rezervë

Shembulli krijon një kopje konsistente edhe gjatë punës së aplikacionit. Ruaj
kopje të rregullta në një vend privat jashtë VPS-së.

```sh
sudo install -d -m 700 -o aianalytica /var/backups/aianalytica
sudo -u aianalytica python3 /opt/aianalytica/cloud/deploy/backup.py \
  /var/lib/aianalytica/cloud.sqlite3 \
  "/var/backups/aianalytica/cloud-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
```

Për rikthim, ndal shërbimin dhe zhvendos databazën aktuale së bashku me
skedarët shoqërues `-wal` dhe `-shm` (nëse ekzistojnë) në një dosje private.
Kopjo rezervën në `/var/lib/aianalytica/cloud.sqlite3` me pronar `aianalytica`
dhe leje `0600`. Nise shërbimin dhe kontrollo `/healthz` dhe raportet.
