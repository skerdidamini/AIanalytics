"""Public homepage language, responsive navigation and contact form regression."""
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as temp:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    process=subprocess.Popen([str(ROOT/'cloud/.venv/bin/python'),'-m','cloud_api.cli','--database',str(Path(temp)/'cloud.sqlite3'),'serve','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(base+'/healthz',timeout=1).close();break
            except OSError:time.sleep(.1)
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base)
            expect(page.locator('html')).to_have_attribute('lang','sq')
            expect(page.locator('h1')).to_contain_text('Ktheji kamerat')
            expect(page.locator('meta[name=description]')).to_have_attribute('content','Analizë video me përpunim lokal që i kthen kamerat ekzistuese në informacion të dobishëm për tregtinë dhe hotelerinë.')
            page.locator('[name=name]').fill('Test User')
            page.locator('[data-language=en]').click()
            expect(page.locator('h1')).to_have_text('Turn Existing Cameras Into Business Intelligence')
            expect(page.locator('[name=name]')).to_have_value('Test User')
            page.reload();expect(page.locator('html')).to_have_attribute('lang','en')
            page.locator('[data-language=sq]').click()
            expect(page.locator('#faq-answer-1')).to_be_hidden()
            page.locator('[aria-controls=faq-answer-1]').click()
            expect(page.locator('#faq-answer-1')).to_contain_text('Jo.')
            for width in [320,390,768,1024,1440]:
                page.set_viewport_size({'width':width,'height':900})
                expect(page.locator('.language-switch')).to_be_visible()
                expect(page.locator('.login-link')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth===innerWidth'),width
            page.set_viewport_size({'width':390,'height':900})
            page.locator('.nav-toggle:not(.close)').click()
            expect(page.locator('#mobile-navigation')).to_be_visible()
            page.keyboard.press('Escape')
            expect(page.locator('#mobile-navigation')).to_be_hidden()
            page.locator('[name=name]').fill('Test User')
            page.locator('[name=company]').fill('Test Business')
            page.locator('[name=email]').fill('test@example.com')
            page.locator('[name=industry]').select_option('Retail')
            page.locator('[name=message]').fill('Test request')
            page.route('https://formspree.io/f/*',lambda route:route.fulfill(status=500,body='{}'))
            page.locator('#contact-form button[type=submit]').click()
            expect(page.locator('#form-feedback')).to_contain_text('Nuk u konfirmua')
            expect(page.locator('[name=name]')).to_have_value('Test User')
            page.locator('[data-language=en]').click()
            expect(page.locator('#form-feedback')).to_contain_text('We could not confirm')
            page.route('https://formspree.io/f/*',lambda route:route.fulfill(status=200,body='{}'))
            page.locator('#contact-form button[type=submit]').click()
            expect(page.locator('#form-feedback')).to_contain_text('submitted successfully')
            page.locator('[data-language=sq]').click()
            expect(page.locator('#form-feedback')).to_contain_text('sukses')
            page.locator('[data-language=en]').click()
            page.locator('.login-link').click()
            expect(page.locator('html')).to_have_attribute('lang','sq')
            expect(page.locator('#login-button')).to_have_text('Hyr në panel')
            assert not errors,errors
            browser.close()
        print('PASS: SQ default, EN persistence, forms preserve input, translated feedback, mobile navigation, responsive switch and Albanian login')
    finally:
        process.terminate();process.wait(timeout=10)
