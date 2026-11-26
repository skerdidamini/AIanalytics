"""Optional image/video/role calibration integration check (Playwright + FFmpeg)."""
import functools
import http.server
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import zlib
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
def png():
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',640,360,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([20,40,180])*640)*360))+chunk(b'IEND',b'')
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
with tempfile.TemporaryDirectory() as temp, sync_playwright() as p:
    video=Path(temp)/'uniform.webm'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=640x360:r=10','-t','2','-c:v','libvpx','-y',str(video)],check=True)
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=b.new_page(accept_downloads=True);errors=[];external=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) and not r.url.startswith(base) else None)
    page.goto(base+'/edge/calibration/index.html')
    page.locator('#image-file').set_input_files({'name':'uniform.png','mimeType':'image/png','buffer':png()})
    expect(page.locator('#camera-image')).to_be_visible()
    def click(x,y):
        stage=page.locator('#drawing');stage.scroll_into_view_if_needed();rect=stage.bounding_box()
        page.mouse.click(rect['x']+x*rect['width'],rect['y']+y*rect['height'])
    page.locator('#apply-line').click()
    page.locator('#zone-tool').click();click(.1,.1);click(.4,.4)
    page.locator('#add-zone').click()
    zone=page.locator('#zones .zone').nth(1)
    zone.locator('select').first.select_option('service')
    zone.locator('select').nth(1).select_option('Zone1')
    page.locator('#add-zone').click();page.locator('#zones .zone').nth(2).locator('select').first.select_option('takeaway')
    page.locator('#sample-role').select_option('waiter');page.locator('#role-tool').click();click(.3,.2);click(.5,.5)
    expect(page.locator('#role-samples')).to_contain_text('Kamarier')
    page.locator('#video-file').set_input_files(str(video))
    expect(page.locator('#camera-video')).to_be_visible()
    expect(page.locator('#video-controls')).to_be_visible()
    page.locator('#video-seek').fill('0.8');page.locator('#video-seek').dispatch_event('input')
    page.wait_for_function('() => !document.querySelector("#camera-video").seeking && document.querySelector("#camera-video").readyState>=2')
    page.locator('#sample-role').select_option('bartender');page.locator('#add-sample').click()
    expect(page.locator('#role-samples')).to_contain_text('Banakier')
    page.locator('#compare-samples').click();expect(page.locator('#sample-result')).to_contain_text('ngjyrë e ndryshme')
    page.locator('#trace-tool').click();click(.5,.3);click(.5,.7)
    expect(page.locator('#crossing-result')).to_contain_text('HYRJE')
    click(.5,.7);click(.5,.3);expect(page.locator('#crossing-result')).to_contain_text('DALJE')
    click(.01,.3);click(.01,.7);expect(page.locator('#crossing-result')).to_contain_text('jashtë segmentit')
    page.locator('#fixed-view').check();page.locator('#review-config').click()
    expect(page.locator('#review-result')).to_contain_text('Kontroll manual')
    with page.expect_download() as download:page.locator('#export').click()
    path=Path(temp)/'config.json';download.value.save_as(path);config=json.loads(path.read_text())
    assert config['zones'][0]['kind']=='table' and config['zones'][1]['table_id']=='Zone1' and config['zones'][2]['kind']=='takeaway'
    meta=config['calibration'];assert len(meta['role_samples'])==2
    assert meta['source']['kind']=='video' and abs(meta['source']['frame_seconds']-.8)<.1
    assert meta['review']['status']=='manual_review'
    assert meta['role_samples'][0]['hsv']['h']>200 and meta['role_samples'][1]['rgb'][0]>200
    assert meta['capabilities']['uniform_classifier_active'] is False
    assert 'blob:' not in path.read_text() and 'data:image' not in path.read_text()
    subprocess.run([str(ROOT/'edge/.venv/bin/python'),'-c','from edge_analytics.config import load_config; import sys; load_config(sys.argv[1])',str(path)],check=True)
    page.locator('#config-file').set_input_files(str(path));expect(page.locator('#status')).to_contain_text('u importua')
    expect(page.locator('#role-samples .uniform-sample')).to_have_count(2)
    assert not page.locator('#fixed-view').is_checked()
    page.locator('#role-samples button').last.click();expect(page.locator('#role-samples .uniform-sample')).to_have_count(1)
    assert not errors,errors
    assert not external,external
    page.set_viewport_size({'width':1440,'height':1100});page.screenshot(path='/tmp/calibration-advanced.png',full_page=True)
    b.close()
server.shutdown()
print('PASS: video seek, table/service/takeaway types, linked table, image/video uniform colors, sample removal/import, manual direction tests, reviewed JSON accepted by real Python validator and no external media upload')
