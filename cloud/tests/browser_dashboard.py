"""Optional: python3 cloud/tests/browser_dashboard.py (Playwright + Chromium)."""
import csv
import io
import json
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
    db=Path(temp)/'cloud.sqlite3'
    seed='''from cloud_api.database import Database
from cloud_api import accounts
import sys,time,uuid
from datetime import datetime
D=Database(sys.argv[1]);accounts.initialize(D)
accounts.create_owner(D,'business-a','owner@example.com','test-owner-password-123')
D.provision('business-a','site-a','node-a',['camera-a'],'test-node-a')
D.provision('business-b','site-b','node-b',['camera-b'],'test-node-b')
p=D.authenticate('test-node-a')
base={'timestamp':time.time()-30,'organization_id':'business-a','location_id':'site-a','node_id':'node-a','camera_id':'camera-a'}
events=[]
for _ in range(3):events.append(dict(base,event_id=str(uuid.uuid4()),type='person_entered',details={'track_id':'x'}))
events.append(dict(base,event_id=str(uuid.uuid4()),type='dwell_time_completed',details={'track_id':'x','zone_id':'zone-a','duration_seconds':120.,'censored':False,'completion':'zone_exit'}))
events.append(dict(base,event_id=str(uuid.uuid4()),type='occupancy_snapshot',details={'visible_persons':4,'zones':{'zone-a':3},'scope':'camera_visible_only'}))
D.ingest(p,events)
'''
    subprocess.run([str(PYTHON),'-c',seed,str(db)],check=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    process=subprocess.Popen([str(PYTHON),'-m','cloud_api.cli','--database',str(db),'serve','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(base+'/healthz',timeout=1).close();break
            except OSError:time.sleep(.1)
        else:raise AssertionError('Dashboard server failed to start')
        with sync_playwright() as p:
            b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=b.new_page(accept_downloads=True);errors=[];external=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) and not r.url.startswith(base) else None)
            page.goto(base)
            expect(page.locator('#login-view')).to_be_visible()
            page.locator('#email').fill('owner@example.com');page.locator('#password').fill('test-owner-password-123');page.locator('#login-button').click()
            expect(page.locator('#dashboard')).to_be_visible()
            expect(page.locator('#entries')).to_have_text('3')
            expect(page.locator('#dwell')).to_contain_text('2')
            expect(page.locator('#peak')).to_have_text('—')
            expect(page.locator('#chart')).to_be_visible()
            assert 'business-b' not in page.locator('#dashboard').inner_text()
            assert 'site-b' not in page.locator('#location').inner_text()
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':1000})
                assert page.evaluate('document.documentElement.scrollWidth===innerWidth'),width
            assert 'owner_session' not in page.evaluate('document.cookie')
            assert page.evaluate('Object.keys(localStorage).length')==0
            camera=page.locator('#camera option').nth(1).get_attribute('value')
            page.locator('#camera').select_option(camera);page.locator('#refresh').click()
            expect(page.locator('#peak')).to_have_text('4')
            page.set_viewport_size({'width':1440,'height':1050})
            page.screenshot(path='/tmp/owner-dashboard.png',full_page=True)
            with page.expect_download() as download:page.locator('#download').click()
            file=Path(temp)/'report.csv';download.value.save_as(file)
            rows=list(csv.DictReader(io.StringIO(file.read_text())))
            assert sum(int(row['entries']) for row in rows)==3
            assert all(row['camera_id']=='camera-a' for row in rows)
            page.locator('#start').fill('2020-01-01');page.locator('#end').fill('2020-01-02');page.locator('#refresh').click()
            expect(page.locator('#status')).to_contain_text('Nuk ka evente')
            expect(page.locator('#entries')).to_have_text('—')
            expect(page.locator('#chart-empty')).to_be_visible()
            page.locator('#start').fill('2020-02-01');page.locator('#end').fill('2020-01-02');page.locator('#refresh').click()
            expect(page.locator('#status')).to_have_class('error')
            page.locator('#logout').click();expect(page.locator('#login-view')).to_be_visible()
            page.reload();expect(page.locator('#login-view')).to_be_visible()
            assert not errors,errors
            assert not external,external
            b.close()
        print('PASS: owner login, scoped KPI data/inventory, graph, camera peak, four screen widths, CSV, empty/error states, private cookie, logout and no external requests')
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
