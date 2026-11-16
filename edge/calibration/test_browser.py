"""Optional UI integration check: python3 edge/calibration/test_browser.py.
Requires Playwright + Chromium, separately from the edge runtime dependencies.
"""
import json
import functools
import http.server
import threading
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

def png(width, height):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress((b'\0' + b'\x20\x40\x60' * width) * height)) + chunk(b'IEND', b'')

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'

with tempfile.TemporaryDirectory() as temp, sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page(accept_downloads=True)
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http:', 'https:')) and not r.url.startswith(base + '/') else None)
    page.goto(base + '/edge/calibration/index.html')
    for width in [320, 390, 768, 1440]:
        page.set_viewport_size({'width':width, 'height':900})
        assert page.evaluate('document.documentElement.scrollWidth === innerWidth'), width
    page.set_viewport_size({'width':1440, 'height':1000})
    page.locator('#image-file').set_input_files({'name':'test-camera.png', 'mimeType':'image/png', 'buffer':png(640,480)})
    page.wait_for_function('!document.querySelector("#camera-image").hidden')
    assert page.locator('#camera-image').evaluate('(e)=>e.naturalWidth') == 640
    stage=page.locator('#drawing')
    def click(x,y):
        stage.scroll_into_view_if_needed()
        box=stage.bounding_box()
        page.mouse.click(box['x']+x*box['width'],box['y']+y*box['height'])
    click(.2,.3);click(.8,.6)
    assert abs(float(page.locator('#start-x').input_value())-.2)<.001
    assert abs(float(page.locator('#end-y').input_value())-.6)<.001
    page.locator('#enter-side').select_option('-1')
    page.locator('#zone-tool').click();click(.1,.1);click(.4,.4)
    assert page.locator('#zone-count').inner_text()=='1'
    with page.expect_download() as download:
        page.locator('#export').click()
    path=Path(temp)/'config.local.json';download.value.save_as(path)
    config=json.loads(path.read_text())
    assert config['line']['enter_side']==-1
    assert all(abs(a-b)<.001 for a,b in zip(config['zones'][0]['rect'],[.1,.1,.4,.4]))
    # Load the generated file through the actual edge validator, not a UI-only assertion.
    result=subprocess.run([str(ROOT/'edge/.venv/bin/python'),'-c','from edge_analytics.config import load_config; import sys; load_config(sys.argv[1])',str(path)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    config['sample_fps']=7;config['custom_setting']={'keep':True}
    page.locator('#config-file').set_input_files({'name':'existing.json','mimeType':'application/json','buffer':json.dumps(config).encode()})
    page.wait_for_function('document.querySelector("#status").textContent.includes("u importua")')
    with page.expect_download() as download:page.locator('#export').click()
    download.value.save_as(path);updated=json.loads(path.read_text())
    assert updated['sample_fps']==7 and updated['custom_setting']=={'keep':True}
    page.locator('#config-file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{"line":null}'})
    page.wait_for_function('document.querySelector("#status").classList.contains("error")')
    assert page.locator('#zone-count').inner_text()=='1'
    page.locator('#add-zone').click()
    zone_inputs=page.locator('#zones .zone input')
    # Duplicate names must prevent export.
    page.locator('#zones .zone').nth(1).locator('input').first.fill('zone-1')
    page.locator('#export').click()
    assert 'emra unikë' in page.locator('#status').inner_text()
    page.locator('#zones .zone').nth(1).locator('button').click()
    assert page.locator('#zone-count').inner_text()=='1'
    # Numerical edit (keyboard path) and rejected degenerate line.
    for field,value in [('start-x','.2'),('start-y','.2'),('end-x','.2'),('end-y','.2')]:page.locator('#'+field).fill(value)
    page.locator('#apply-line').click()
    assert 'dy pika të ndryshme' in page.locator('#status').inner_text()
    page.locator('#end-x').fill('.7');page.locator('#apply-line').click()
    assert not page.locator('#status').get_attribute('class')
    page.locator('#line-tool').click();click(.3,.3);page.locator('#export').click()
    assert 'Përfundo vizatimin' in page.locator('#status').inner_text()
    page.keyboard.press('Escape')
    assert not errors,errors
    assert not requests,requests
    browser.close()
server.shutdown()
print('PASS: local HTTP opening, image load, four screen widths, drawing line/zone, direction, valid Python config export, import preservation, invalid import, duplicate zones, delete, keyboard coordinates and unfinished drawing guard. No external network requests.')
