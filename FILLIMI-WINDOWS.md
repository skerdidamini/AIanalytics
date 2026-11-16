# Provoje dashboard-in në Windows 10/11

Nuk të duhet server me pagesë apo domain për këtë provë. PC-ja jote do të shërbejë dashboard-in vetëm për shfletuesin në atë PC. Mund ta kalojmë online më vonë, me objektiv buxheti rreth 10 €/muaj.

## 1. Instalo Python

Instalo Python 3.12, 64-bit, nga [python.org](https://www.python.org/downloads/windows/). Gjatë instalimit aktivizo **Add python.exe to PATH**. Nëse e ke tashmë Python 3.10 ose më të ri, mund ta përdorësh atë.

## 2. Shkarko dhe nxirr projektin

[Shkarko ZIP-in e përditësuar](https://github.com/skerdidamini/AIanalytics/archive/refs/heads/project/edge-poc-and-website.zip).

Kliko me të djathtën mbi ZIP → **Extract All / Nxirr të gjitha**. Hyr te dosja e nxjerrë që përmban `NIS-DEMO-WINDOWS.cmd`. Mos e nis nga brenda ZIP-it.

## 3. Nis demonstrimin

Hap me dy klikime **NIS-DEMO-WINDOWS.cmd**.

- Herën e parë krijon mjedisin Python dhe instalon varësitë; duhet internet për instalimin.
- Të pyet për emrin/ID e biznesit (mund të shtypësh Enter për `demo-business`), emailin dhe fjalëkalimin.
- Zgjidh fjalëkalim me të paktën 12 karaktere. Kur e shkruan, nuk duken shkronja apo yje; kjo është normale. Shkruaje përsëri për konfirmim.
- Emaili përdoret si emër hyrjeje; nuk dërgohet email verifikimi. Nuk ka llogari apo fjalëkalim të gatshëm.
- Hap automatikisht shfletuesin. Nëse nuk hapet, shkruaj `http://127.0.0.1:8080` në shfletuesin e të njëjtit PC.
- Hyr me emailin/fjalëkalimin që sapo zgjodhe.

Dashboard-i ka shënimin **MODALITET DEMO** dhe të dhëna të simuluara për ditët e fundit. Nuk janë rezultate nga kamera dhe nuk dërgohen në ndonjë server publik. Mund të provosh datat, filtrat, grafikun, përmbledhjet dhe CSV-në. Për bar/restorant ka edhe shembuj `Zone1`, `Zone2` dhe `Takeaway`, tabelë qëndrimi të vëzhguar dhe CSV zonash. Kartat e pritjes së kamarierit/porosisë, qëndrimit të grupit dhe përdorimit të tavolinës shënohen ende të pamatura; këto funksione edge nuk janë ndërtuar.

## 4. Mbaje terminalin hapur

Dritarja e terminalit është serveri. Nëse e mbyll, paneli ndalon së punuari. Mbyllja vetëm e tab-it të shfletuesit nuk ndalon serverin.

Për ta ndalur, shtyp **Ctrl+C** në terminal; nëse Windows pyet nëse duhet mbyllur batch job, konfirmo. Për ta hapur sërish, përdor të njëjtin `.cmd`; llogaria dhe të dhënat ruhen.

Nëse porta 8080 përdoret nga një program tjetër, hape terminalin në dosjen e projektit dhe përdor:

```bat
py -3 start-local.py --demo --port 8081
```

Hap pastaj portën që shfaq terminali. PC-ja duhet të jetë ndezur gjatë përdorimit; kjo provë nuk hap akses nga telefoni ose nga interneti.

## 5. Mënyra reale lokale, për më vonë

**NIS-REAL-WINDOWS.cmd** nis të njëjtin dashboard me databazë tjetër, fillimisht bosh. Do të kërkojë llogari të veçantë herën e parë. Nuk vendos shënim demo dhe nuk gjeneron evente.

Databazat janë:

- `cloud/runtime/demo.sqlite3` — vetëm provat sintetike.
- `cloud/runtime/local.sqlite3` — të dhënat reale lokale.

Mos kopjo eventet demo në databazën reale. Ruaj dosjen `cloud/runtime` kur përditëson kodin. Fshirja e saj humbet llogaritë dhe historikun lokal. Mos e ngarko në GitHub dhe mos dërgo fjalëkalime në chat.

Lidhja e edge me databazën reale kërkon konfigurim të kredencialeve dhe endpoint HTTPS. Ky instalim lokal përdor HTTP vetëm në loopback për provën e dashboard-it; nuk çaktivizon kërkesën HTTPS të sync-ut edge. Kamera reale dhe detektori do të testohen kur të kemi videon/pajisjen gati.

## Nëse nuk niset

Mos e mbyll dritaren me gabimin. Dërgo një screenshot të mesazhit duke fshehur çdo të dhënë private, që ta diagnostikojmë. Nëse Windows nuk njeh `py`/`python`, kontrollo instalimin e Python dhe opsionin PATH.

Logjika e nisjes Python, llogaritë, demonstrimi dhe izolimi i databazave janë testuar në ambientin Linux të zhvillimit. Wrapper-at `.cmd` janë përgatitur për Windows, por ekzekutimi real në Windows ende duhet konfirmuar në PC-në tënde.

## Hap panelin e instalimit të kamerës

Për kalibrim përdor **NIS-KALIBRIMIN-WINDOWS.cmd**, jo launcher-in e dashboard-it. Ky panel hap foto ose video të shkurtër, vizaton vijën/zonat, merr mostra manuale uniforme dhe shkarkon JSON-in për kamerën. Vetëm Python duhet instaluar; nuk instalohen varësi për këtë panel statik. Mostrat nuk aktivizojnë ende njohje automatike të stafit. Rrjedha e plotë është te `edge/calibration/README.md`. Mbyll terminalin kur mbaron; nëse porta është zënë, përdor `py -3 start-calibration.py --port 8767`.
