## Try the owner dashboard on Windows

See [FILLIMI-WINDOWS.md](FILLIMI-WINDOWS.md). Extract the full ZIP and double-click **NIS-DEMO-WINDOWS.cmd**. Requires Python 3.10+ (recommended 3.12) and Internet for first-time dependency installation. Creates your own account and starts an isolated, explicitly marked demo. **NIS-REAL-WINDOWS.cmd** uses a separate empty database. Nothing is deployed publicly by these scripts.

# AI Camera Analytica

Static marketing site built with HTML, CSS and JavaScript. This repository does not contain the video analytics engine or a dashboard.

## Local development

Use the existing checkout; cloud tasks are already isolated. No package installation or build is required.

```sh
cd /workspace/AIanalytics
python3 -m http.server 8000 --bind 127.0.0.1
```

Open the served site in your local development browser. Check JavaScript syntax with `node --check scripts.js`.

## Contact form

The public Formspree endpoint is set in `data-formspree-endpoint` on `#contact-form` in `index.html`. No private API key belongs in browser code. Client validation checks required fields and email format. The form resets only after a successful HTTP response; failures preserve entered details.

Real submission and inbox delivery remain unverified because the cloud network blocked Formspree. Browser checks with mocked success and failure responses passed. Do not interpret those checks as email delivery confirmation.

## Before publishing the website

- Supply the official logo and favicon; text branding is used meanwhile.
- Supply verified business contact details if they should be displayed.
- Add a social sharing image and absolute production URLs after the domain is known. The current social card uses a text summary.
- Confirm Formspree recipient verification and perform one real submission/inbox check.
- Set up HTTPS on the selected static hosting provider.
- Review privacy information for contact submissions and use of external Google Fonts.

## Manual regression checks

Check widths 320, 375, 390, 768, 960, 1024 and 1440px for horizontal overflow. Verify skip link, menu focus, Tab/Shift+Tab wrapping, Escape, navigation link closure and desktop resize. Check all five FAQ items. Check invalid email, submission error preserving data and successful submission resetting data. Use mocked responses for routine checks to avoid sending test email.

## Camera calibration panel

Open [edge/calibration/index.html](edge/calibration/index.html) in a modern browser (or serve the repository locally with Python if local files are blocked). Load a camera still, draw the counting line and rectangular zones, then export `config.local.json` for the edge program. Everything runs locally; this panel does not start analytics or connect to RTSP/cloud. See `edge/README.md` for details.

## Local device control panel (Linux/macOS)

After installing the edge package, run `ai-camera-panel --config config.local.json` on the Mini PC and open the loopback address printed in its terminal on that same device. This mode adds configuration saving, start/stop controls and worker frame status to the calibration UI. Set `EDGE_RTSP_URL` in the process environment first, or pass `--video` for a local file test. The static HTML file alone does not control a device. See `edge/README.md` for setup and limits.

## Minimal cloud backend

The `cloud/` directory contains a FastAPI ingestion service, device-scoped credentials, persistent SQLite storage, deduplication, organization-scoped hourly metrics and CSV reports. See [cloud/README.md](cloud/README.md). Twenty-four backend tests passed, including actual edge-to-API HTTPS sync with duplicate retries. This backend has not been deployed publicly; owner login/dashboard are now included; public deployment and report email remain pending.

## Owner dashboard

The cloud server now serves an Albanian owner dashboard at `/`, with email/password login, organization-scoped filters, hourly traffic chart, zone dwell summary and authorized CSV downloads. Create an owner account using the cloud CLI; see `cloud/README.md`. It requires the running backend, not opening the HTML file directly. It has been tested locally with synthetic data, not deployed publicly.

## Restaurant dashboard

The owner UI now includes table/service sections, per-zone observed dwell and a selectable takeaway area with separate zone CSV export. First waiter approach, order delivery, group table sessions and table utilization remain explicitly unmeasured until the corresponding edge/POS logic exists. Local demo includes `Zone1`, `Zone2` and `Takeaway` synthetic data. See `cloud/README.md` for metric definitions.

## Extended installer calibration

Use **NIS-KALIBRIMIN-WINDOWS.cmd** or `python3 start-calibration.py` to open local image/video calibration without installing the inference stack. Supports typed zones, service-to-table links, manual uniform color samples, geometry-only crossing tests and versioned metadata. Automatic staff classification/service measurement is not active. See [edge/calibration/README.md](edge/calibration/README.md).
