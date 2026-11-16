"""Optional full local-panel browser check; requires Playwright and installed edge venv."""
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / 'edge/.venv/bin/python'
with tempfile.TemporaryDirectory() as temp:
    directory=Path(temp)
    video=directory/'test.avi'
    code='''import cv2,numpy as np,sys
w=cv2.VideoWriter(sys.argv[1],cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
assert w.isOpened()
for _ in range(2000):w.write(np.zeros((240,320,3),dtype=np.uint8))
w.release()
'''
    subprocess.run([str(PYTHON),'-c',code,str(video)],check=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    process=subprocess.Popen([str(PYTHON),'-m','edge_analytics.panel','--config',str(directory/'config.local.json'),'--port',str(port),'--video',str(video)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base+'/api/status',timeout=1).close();break
            except OSError:time.sleep(.1)
        else:raise AssertionError('Local panel did not start')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base)
            page.locator('#save-device').wait_for()
            expect(page.locator('#save-device')).to_be_enabled()
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':1000})
                assert page.evaluate('document.documentElement.scrollWidth===innerWidth'),width
            page.locator('#camera_id').fill('browser-camera')
            page.locator('#save-device').click()
            expect(page.locator('#runtime-message')).to_contain_text('u ruajt')
            assert json.loads((directory/'config.local.json').read_text())['camera_id']=='browser-camera'
            page.reload();expect(page.locator('#camera_id')).to_have_value('browser-camera')
            page.locator('#start-worker').click()
            expect(page.locator('#stop-worker')).to_be_enabled()
            expect(page.locator('#runtime-state')).to_contain_text('po përpunohet', timeout=15000)
            assert page.locator('#save-device').is_disabled()
            page.locator('#stop-worker').click()
            expect(page.locator('#runtime-state')).to_contain_text('e ndalur', timeout=25000)
            assert not page.locator('#save-device').is_disabled()
            assert not errors,errors
            browser.close()
        with urllib.request.urlopen(base+'/api/status') as response:
            state=json.load(response)
        assert not state['running'] and state['processed_frames']>0 and state['pending_events']>0,state
        print('PASS: full browser save -> reload -> actual video worker start -> processed frames -> stop -> SQLite events, four viewport widths and no JS errors')
    finally:
        process.terminate()
        try:process.wait(timeout=20)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        process.stderr.close()
