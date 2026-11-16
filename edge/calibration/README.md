# Paneli i instalimit dhe kalibrimit — versioni i zgjeruar

Paneli përgatit konfigurimin për një kamerë, lokacion dhe klient. Është i veçantë nga dashboard-i i pronarit. Fotoja/videoja hapet në shfletues; nuk dërgohet në cloud dhe nuk përfshihet në JSON.

## Hapja

Në Windows, nga dosja e nxjerrë e projektit, hap `NIS-KALIBRIMIN-WINDOWS.cmd`. Kërkon vetëm Python; nuk instalon OpenCV dhe nuk nis backend-in cloud. Hap shfletuesin në të njëjtin PC dhe mbaje terminalin hapur.

Në Linux/macOS: `python3 start-calibration.py` nga rrënja e projektit. Mund të hapësh edhe `edge/calibration/index.html` direkt, kur politika e shfletuesit e lejon. Paneli i pajisjes `ai-camera-panel` shërben të njëjtin kalibrues dhe shton kontrollet e worker-it.

## Rrjedha e instalimit

1. Plotëso organizatën, lokacionin, node-in dhe kamerën. Importo JSON-in ekzistues nëse po rikalibron, për të ruajtur parametrat e tjerë.
2. Ngarko foto PNG/JPEG/WebP deri në 20 MB ose video MP4/WebM/Ogg deri në 150 MB, jo më shumë se 2 minuta. Rekomandohet MP4 H.264 ose WebM, me gjithë pamjen fikse të kamerës, pa kontrolle të aplikacionit/zoom/prerje. HEVC mund të mos lexohet nga shfletuesi; përdor foto ose konverto klipin në format të mbështetur.
3. Për video, luaj/pauzo dhe zgjidh momentin me slider. Klikimi për vizatim e pauzon videon. Vizatimet mbeten në koordinata relative gjatë luajtjes; kjo supozon që kamera nuk ndryshon kënd/zoom.
4. Aktivizo vijën vetëm për kamera që shohin një kalim hyrjeje/daljeje. Vizato dy pika dhe kontrollo shigjetat: jeshile = hyrje, portokalli = dalje. Në kamerat vetëm për tavolina, çaktivizo numërimin e kalimeve. Kjo çaktivizim mbështetet realisht nga motori edge.
5. Vizato zonat drejtkëndore. Jep ID unike si `Zone1`, `Zone2`, `Takeaway`. Zgjidh funksionin: tavolinë, afrim shërbimi, takeaway, hyrje, dalje ose zonë tjetër. Zona e shërbimit duhet lidhur me një zonë tavoline ekzistuese. Ndryshimi i ID-së së tavolinës kërkon kontrollin e lidhjes; JSON me lidhje të prishur refuzohet.
6. Për mostra uniforme, zgjidh rolin (kamarier, banakier, klient si kundërshembull, i panjohur), pastaj vizato vetëm bluzën. Mund të përdorësh edhe koordinatat numerike. Ruaj disa shembuj në ndriçime të ndryshme, deri në 30 mostra. Ruhen mesatarja e ngjyrës RGB/HSV, drejtkëndëshi dhe momenti i videos, pa fytyrë, foto ose identitet.
7. “Krahaso ngjyrat” krahason ngjyrën e frame-it aktual me mostrat **në të njëjtat koordinata**. Nuk ndjek personin; nëse personi është larguar nga drejtkëndëshi, po matet sfondi. Nuk është provë e klasifikimit të rolit.
8. Me “Provë kalimi”, kliko nisjen dhe fundin e trajektores. Kontrollo hyrjen/daljen, brezin e tolerancës dhe segmentin e kufizuar. Kjo është provë gjeometrike manuale; nuk detekton person dhe nuk krijon evente reale.
9. Konfirmo pamjen fikse dhe shtyp “Kontrollo konfigurimin”. Kontrolli verifikon strukturën dhe lidhjet. Paralajmëron për role me ngjyra të ngjashme. Nuk mat saktësinë e AI-së. Pas ndryshimeve, statusi bëhet draft.
10. Eksporto `config.local.json`, ruaje për klientin/kamerën dhe instaloje në pajisje. Ndryshimet e formularit nuk ruhen automatikisht në disk. Importi i JSON-it rikthen mostrat dhe zonat, por duhet të ngarkosh sërish median dhe të kontrollosh përputhjen.

## Çfarë përdor sot edge

- Vijën, drejtimin, aktivizimin/çaktivizimin, zonat dhe parametrat ekzistues të tracking-ut.
- Metadata e pamjes për kontrollin e raportit gjerësi/lartësi. Diferencë mbi 3% refuzohet. Ky kontroll nuk zbulon zhvendosjen ose zoom-in me të njëjtin raport; këto kërkojnë inspektim/rikalibrim.
- Llojet dhe lidhjet e zonave ruhen për konfigurim, por motori aktual vazhdon të prodhojë evente të përgjithshme zonash; nuk llogarit ende pritjen e kamarierit apo sesionin e grupit.

Mostrat e uniformës **nuk aktivizojnë klasifikim automatik**. JSON përmban `calibration.capabilities.uniform_classifier_active: false` dhe `table_service_active: false`. Runtime-i i refuzon këto flamuj nëse ngrihen në true pa mbështetje reale. Nuk gjenerohen modele të trajnuara ose certifikim saktësie. Modeli modern i detektimit, klasifikimi i stafit mbi persona të ndjekur dhe prova automatike vizuale mbi video mbeten për fazën pasuese me video reale.

## Formati

Fushat ekzistuese mbeten të njëjta; konfigurimet e vjetra vazhdojnë të lexohen. Zonat shtojnë `kind` dhe, kur janë `service`, `table_id`. `line.enabled` është opsionale, default true për konfigurimet e vjetra.

Objekti opsional `calibration` ka `schema_version: 1`, `source`, `fixed_view_confirmed`, `role_samples`, `capabilities`, dhe `review.status` (`draft` ose `manual_review`). Source ruan vetëm llojin, përmasat dhe kohët, jo file path ose përmbajtje video. Asnjë kredencial RTSP/cloud nuk futet këtu; mbetet në konfigurimin e sigurt të pajisjes.

## Verifikimi

`edge/.venv/bin/python -m unittest discover -s edge/tests -v` nga rrënja e projektit. Kontrolli opsional i avancuar: `python3 edge/calibration/test_advanced_browser.py` (Python Playwright, Chromium dhe FFmpeg). Ai përdor foto/video sintetike për mostrat, llojet/lidhjet e zonave, seek, hyrje/dalje manuale dhe JSON të pranuar nga validatori real Python. Kjo nuk zëvendëson matjen e saktësisë me kamerë reale. Wrapper-i Windows kërkon ende konfirmim në PC real Windows.
