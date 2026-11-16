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
