"""Optional real browser flow for Admin -> assignment -> technician calibration -> activation."""
import json
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
import zlib
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
PYTHON=ROOT/'cloud/.venv/bin/python'

def png():
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',640,360,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([20,40,180])*640)*360))+chunk(b'IEND',b'')

with tempfile.TemporaryDirectory() as temp:
    db=Path(temp)/'cloud.sqlite3'
    seed='''from cloud_api.database import Database
from cloud_api import accounts,operations
import sys
D=Database(sys.argv[1]);accounts.initialize(D);operations.initialize(D)
accounts.create_owner(D,operations.SYSTEM_ORG,'admin@example.com','admin-test-password','admin')
accounts.create_owner(D,'private-business','owner@example.com','owner-test-password')
D.provision('private-business','private-site','private-node',['private-camera'],'private-test-token')
'''
    subprocess.run([str(PYTHON),'-c',seed,str(db)],check=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    process=subprocess.Popen([str(PYTHON),'-m','cloud_api.cli','--database',str(db),'serve','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:urllib.request.urlopen(base+'/healthz',timeout=1).close();break
            except OSError:time.sleep(.1)
        else:raise AssertionError('Server failed to start')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page(accept_downloads=True);errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def login(email,password):
                page.goto(base);page.locator('#email').fill(email);page.locator('#password').fill(password);page.locator('#login-button').click()
            def fill(form,values):
                for name,value in values.items():form.locator(f'[name={name}]').fill(value)
            def choose(select,match):
                option=select.locator('option').filter(has_text=match).last
                expect(option).to_have_count(1);select.select_option(option.get_attribute('value'))
            login('admin@example.com','admin-test-password')
            expect(page).to_have_url(base+'/admin');expect(page.locator('#role-label')).to_have_text('PANELI ADMIN')
            page.get_by_role('button',name='Bizneset',exact=True).click()
            form=page.locator('#business-form');fill(form,{'id':'restaurant-new','name':'Restoranti X'});form.locator('button').click()
            expect(page.locator('#business-rows')).to_contain_text('Restoranti X')
            form=page.locator('#location-form');form.locator('[name=organization_id]').select_option('restaurant-new');fill(form,{'id':'durres','name':'Durrës'});form.locator('button').click()
            expect(form.locator('button')).to_be_enabled()
            page.get_by_role('button',name='Instalimet',exact=True).click()
            form=page.locator('#node-form');choose(form.locator('[name=scope]'),'restaurant-new');fill(form,{'id':'edge-01'});form.locator('button').click()
            expect(page.locator('#node-rows')).to_contain_text('edge-01')
            form=page.locator('#camera-form');choose(form.locator('[name=scope]'),'edge-01');fill(form,{'id':'entrance-01'});form.locator('button').click()
            expect(page.locator('#camera-rows')).to_contain_text('entrance-01')
            expect(page.locator('#camera-rows')).to_contain_text('Pa të dhëna')
            credential_row=page.locator('#node-rows tr').filter(has_text='edge-01')
            with page.expect_download() as download:credential_row.get_by_role('button',name='Kredencial i ri').click()
            credential=Path(temp)/'device.token';download.value.save_as(credential)
            assert len(credential.read_text().strip())>32
            expect(credential_row).to_contain_text('Konfiguruar')
            page.get_by_role('button',name='Llogaritë / teknikët',exact=True).click()
            form=page.locator('#account-form');form.locator('[name=role]').select_option('technician');fill(form,{'email':'tech@example.com','password':'tech-test-password'});form.locator('button').click()
            expect(page.locator('#technician-select option').filter(has_text='tech@example.com')).to_have_count(1)
            form=page.locator('#assignment-form');form.locator('[name=email]').select_option('tech@example.com');choose(form.locator('[name=scope]'),'restaurant-new');form.locator('button').click()
            expect(page.locator('#assignment-rows')).to_contain_text('restaurant-new')
            page.locator('#logout').click();expect(page.locator('#login-form')).to_be_visible()
            login('tech@example.com','tech-test-password');expect(page).to_have_url(base+'/technician')
            expect(page.locator('#camera-rows')).to_contain_text('entrance-01')
            expect(page.locator('#camera-rows')).not_to_contain_text('private-camera')
            expect(page.locator('#business-form')).to_be_hidden()
            page.get_by_role('link',name='Kalibro',exact=True).click()
            expect(page.locator('#assigned-scope')).to_contain_text('restaurant-new')
            assert page.locator('#organization_id').get_attribute('readonly') is not None
            page.locator('#save-draft').click();expect(page.locator('#server-status')).to_contain_text('U ruajt v1')
            page.locator('#image-file').set_input_files({'name':'camera.png','mimeType':'image/png','buffer':png()})
            expect(page.locator('#camera-image')).to_be_visible()
            page.locator('#fixed-view').check();page.locator('#review-config').click()
            expect(page.locator('#review-result')).to_contain_text('Kontroll manual')
            page.locator('#save-review').click();expect(page.locator('#server-status')).to_contain_text('U ruajt v2')
            page.get_by_role('link',name='Kthehu te instalimet').click();page.locator('#logout').click()
            expect(page.locator('#login-form')).to_be_visible();login('admin@example.com','admin-test-password')
            expect(page.locator('#camera-rows')).to_contain_text('v2')
            page.get_by_role('button',name='Aktivizo v2',exact=True).click()
            expect(page.locator('#camera-rows')).to_contain_text('Pa konfirmim nga pajisja')
            with page.expect_download() as download:page.get_by_role('link',name='JSON aktiv',exact=True).click()
            path=Path(temp)/'config.json';download.value.save_as(path);config=json.loads(path.read_text())
            assert config['organization_id']=='restaurant-new' and config['camera_id']=='entrance-01'
            assert config['deployment']['calibration_version']==2
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':1000})
                assert page.evaluate('document.documentElement.scrollWidth===innerWidth'),width
            page.screenshot(path='/tmp/admin-overview.png',full_page=True)
            assert not errors,errors
            browser.close()
        print('PASS: administrator registry/account forms, assignment, scoped technician, locked identities, draft/manual review, activation, JSON export and no fabricated online/installed status')
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
