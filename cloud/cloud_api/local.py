"""One-PC development/demo runner. Always bound to loopback; no public deployment."""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
from pathlib import Path
import secrets
import socket
import threading
import time
import urllib.request
import uuid
import webbrowser

from . import accounts
from .app import create_app
from .database import Database


def ensure_owner(database,demo=False,input_fn=input,password_fn=getpass.getpass):
    connection=database.connect()
    try:row=connection.execute('SELECT organization_id FROM owners ORDER BY email LIMIT 1').fetchone()
    finally:connection.close()
    if row:
        print('The account is already configured. Use your existing email and password in the browser.')
        return row['organization_id']
    print('First setup: create your own dashboard account. No default password exists.')
    default='demo-business' if demo else 'local-business'
    while True:
        organization=input_fn(f'Business name / ID [{default}]: ').strip() or default
        email=input_fn('Your email: ').strip()
        password=password_fn('Choose a password (minimum 12 characters; typing is hidden): ')
        confirm=password_fn('Repeat password: ')
        if password!=confirm:
            print('Passwords do not match. Try again.');continue
        try:accounts.create_owner(database,organization,email,password)
        except ValueError:
            print('Use an email address, a business ID up to 128 characters and password of 12–256 characters.');continue
        return organization


def seed_demo(database,organization,now=None):
    now=now or datetime.now(timezone.utc)
    location,node,camera='demo-location','demo-edge','demo-entrance'
    if not any(c['location_id']==location and c['node_id']==node and c['id']==camera for c in database.inventory(organization)['cameras']):
        database.provision(organization,location,node,[camera],secrets.token_urlsafe(32))
    principal={'organization_id':organization,'location_id':location,'node_id':node,'role':'ingest'}
    events=[]
    for back in range(7):
        day=now.date()-timedelta(days=back)
        for hour in range(9,18):
            instant=datetime(day.year,day.month,day.day,hour,tzinfo=timezone.utc)
            if instant>now:continue
            prefix=f'{organization}:{instant.isoformat()}'
            base={'timestamp':instant.timestamp(),'organization_id':organization,'location_id':location,'node_id':node,'camera_id':camera}
            def add(kind,key,details):
                events.append(dict(base,event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'aicamera-demo-v1:'+prefix+':'+key)),type=kind,details=details))
            count=5+(hour*3+day.weekday())%12
            for i in range(count):add('person_entered',f'entry-{i}',{'track_id':f'demo-{hour}-{i}'})
            for i in range(max(0,count-2)):add('person_exited',f'exit-{i}',{'track_id':f'demo-{hour}-{i}'})
            add('occupancy_snapshot','occupancy',{'visible_persons':count//2,'zones':{'demo-zone':count//3},'scope':'camera_visible_only'})
            for i in range(2):add('dwell_time_completed',f'dwell-{i}',{'track_id':f'demo-{hour}-{i}','zone_id':'demo-zone','duration_seconds':float(120+hour*20+i*30),'completion':'zone_exit','censored':False})
    for index in range(0,len(events),100):database.ingest(principal,events[index:index+100])
    return len(events)


def main():
    parser=argparse.ArgumentParser(description='Local owner dashboard')
    parser.add_argument('--root',required=True)
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',args.port))
        except OSError:raise SystemExit('Port is busy. Close the old server or run start-local.py with --port 8081.') from None
    root=Path(args.root).resolve()
    runtime=root/'runtime';runtime.mkdir(parents=True,exist_ok=True)
    path=runtime/('demo.sqlite3' if args.demo else 'local.sqlite3')
    database=Database(path);accounts.initialize(database)
    organization=ensure_owner(database,args.demo)
    if args.demo:
        seed_demo(database,organization)
        print('DEMO MODE: simulated events only. Real data uses a separate database.',flush=True)
    else:print('REAL LOCAL MODE: starts empty until the edge sends events.',flush=True)
    url=f'http://127.0.0.1:{args.port}'
    print(f'Open dashboard on this PC: {url}\nKeep this window open. Ctrl+C stops the server.',flush=True)
    if not args.no_browser:
        def open_when_ready():
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url+'/healthz',timeout=1) as response:
                        if response.status==200:webbrowser.open(url);return
                except OSError:pass
                time.sleep(.2)
        threading.Thread(target=open_when_ready,daemon=True).start()
    import uvicorn
    uvicorn.run(create_app(path,secure_cookies=False,demo=args.demo),host='127.0.0.1',port=args.port,access_log=False,proxy_headers=False)


if __name__=='__main__':main()
