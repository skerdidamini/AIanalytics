"""Optional local-demo startup check using actual Python runtime, not the Windows cmd wrapper."""
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
PYTHON=ROOT/'cloud/.venv/bin/python'
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);(root/'runtime').mkdir()
    setup='''from cloud_api import accounts
from cloud_api.database import Database
from pathlib import Path
import sys
for name,org in [('demo','demo-business'),('local','real-business')]:
 d=Database(Path(sys.argv[1])/'runtime'/f'{name}.sqlite3');accounts.initialize(d)
 accounts.create_owner(d,org,'owner@example.com','local-test-password-123')
'''
    subprocess.run([str(PYTHON),'-c',setup,str(root)],check=True)
    for demo in [True,False]:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        command=[str(PYTHON),'-m','cloud_api.local','--root',str(root),'--port',str(port),'--no-browser']
        if demo:command.append('--demo')
        process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:urllib.request.urlopen(base+'/healthz',timeout=1).close();break
                except OSError:time.sleep(.1)
            else:raise AssertionError('Local runtime failed to start')
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                page=browser.new_page();page.goto(base)
                page.locator('#email').fill('owner@example.com');page.locator('#password').fill('local-test-password-123');page.locator('#login-button').click()
                expect(page.locator('#dashboard')).to_be_visible()
                if demo:
                    expect(page.locator('#demo-banner')).to_be_visible()
                    expect(page.locator('#entries')).not_to_have_text('—')
                    expect(page.locator('#chart')).to_be_visible()
                    expect(page.locator('#zone-rows')).to_contain_text('Zone1')
                    expect(page.locator('#zone-rows')).to_contain_text('Zone2')
                    expect(page.locator('#zone-rows')).to_contain_text('Takeaway')
                    page.set_viewport_size({'width':1440,'height':1100})
                    page.screenshot(path='/tmp/restaurant-dashboard-demo.png',full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth===innerWidth')
                    page.screenshot(path='/tmp/restaurant-dashboard-mobile.png',full_page=True)
                else:
                    expect(page.locator('#demo-banner')).to_be_hidden()
                    expect(page.locator('#status')).to_contain_text('Nuk ka evente')
                    expect(page.locator('#entries')).to_have_text('—')
                browser.close()
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
print('PASS: actual local Python startup, owner login, populated demo banner/chart and isolated empty real database. Windows cmd wrapper requires confirmation on Windows.')
