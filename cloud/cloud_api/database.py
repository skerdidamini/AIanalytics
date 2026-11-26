import hashlib
import json
from pathlib import Path
import sqlite3
import time


SCHEMA = '''
CREATE TABLE IF NOT EXISTS organizations (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS locations (organization_id TEXT NOT NULL, id TEXT NOT NULL,
 PRIMARY KEY(organization_id,id), FOREIGN KEY(organization_id) REFERENCES organizations(id));
CREATE TABLE IF NOT EXISTS nodes (organization_id TEXT NOT NULL, location_id TEXT NOT NULL, id TEXT NOT NULL,
 PRIMARY KEY(organization_id,location_id,id), FOREIGN KEY(organization_id,location_id) REFERENCES locations(organization_id,id));
CREATE TABLE IF NOT EXISTS cameras (organization_id TEXT NOT NULL,location_id TEXT NOT NULL,node_id TEXT NOT NULL,id TEXT NOT NULL,
 PRIMARY KEY(organization_id,location_id,node_id,id), FOREIGN KEY(organization_id,location_id,node_id) REFERENCES nodes(organization_id,location_id,id));
CREATE TABLE IF NOT EXISTS credentials (token_hash TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
 location_id TEXT, node_id TEXT, role TEXT NOT NULL CHECK(role IN ('ingest','reader')), revoked INTEGER NOT NULL DEFAULT 0,
 FOREIGN KEY(organization_id) REFERENCES organizations(id));
CREATE TABLE IF NOT EXISTS events (organization_id TEXT NOT NULL, event_id TEXT NOT NULL,
 location_id TEXT NOT NULL,node_id TEXT NOT NULL,camera_id TEXT NOT NULL,type TEXT NOT NULL,
 timestamp REAL NOT NULL,received_at REAL NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(organization_id,event_id),
 FOREIGN KEY(organization_id,location_id,node_id,camera_id) REFERENCES cameras(organization_id,location_id,node_id,id));
CREATE INDEX IF NOT EXISTS events_time ON events(organization_id,timestamp);
'''


class Rejected(Exception):
    pass


class Conflict(Exception):
    pass


class Database:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        db = self.connect()
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
        finally:
            db.close()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def provision(self, organization, location, node, cameras, token, role='ingest'):
        db = self.connect()
        try:
            with db:
                db.execute('INSERT OR IGNORE INTO organizations VALUES (?)', (organization,))
                if role == 'ingest':
                    db.execute('INSERT OR IGNORE INTO locations VALUES (?,?)', (organization,location))
                    db.execute('INSERT OR IGNORE INTO nodes VALUES (?,?,?)', (organization,location,node))
                    db.executemany('INSERT OR IGNORE INTO cameras VALUES (?,?,?,?)', [(organization,location,node,c) for c in cameras])
                db.execute('INSERT INTO credentials VALUES (?,?,?,?,?,0)', (hashlib.sha256(token.encode()).hexdigest(),organization,location,node,role))
        finally:
            db.close()

    def authenticate(self, token):
        db = self.connect()
        try:
            row=db.execute('SELECT * FROM credentials WHERE token_hash=? AND revoked=0', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def ingest(self, principal, events):
        db=self.connect()
        accepted=[]
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                for event in events:
                    if (event['organization_id'],event['location_id'],event['node_id']) != (principal['organization_id'],principal['location_id'],principal['node_id']):
                        raise Rejected()
                    scope=(event['organization_id'],event['location_id'],event['node_id'],event['camera_id'])
                    if not db.execute('SELECT 1 FROM cameras WHERE organization_id=? AND location_id=? AND node_id=? AND id=?',scope).fetchone():
                        raise Rejected()
                    payload=json.dumps(event,sort_keys=True,separators=(',',':'),allow_nan=False)
                    digest=hashlib.sha256(payload.encode()).hexdigest()
                    old=db.execute('SELECT digest FROM events WHERE organization_id=? AND event_id=?',(event['organization_id'],event['event_id'])).fetchone()
                    if old:
                        if old['digest'] != digest: raise Conflict()
                    else:
                        db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)',(*scope[:1],event['event_id'],*scope[1:],event['type'],event['timestamp'],time.time(),payload,digest))
                    if event['event_id'] not in accepted: accepted.append(event['event_id'])
            return accepted
        finally:
            db.close()

    def hourly(self, organization, start, end, location=None, camera=None, node=None):
        conditions=['organization_id=?','timestamp>=?','timestamp<?']
        args=[organization,start,end]
        if location is not None: conditions.append('location_id=?');args.append(location)
        if camera is not None: conditions.append('camera_id=?');args.append(camera)
        if node is not None: conditions.append('node_id=?');args.append(node)
        query='''SELECT location_id,node_id,camera_id,strftime('%Y-%m-%dT%H:00:00Z',timestamp,'unixepoch') AS hour_utc,
        sum(type='person_entered') AS entries,sum(type='person_exited') AS exits,
        sum(CASE WHEN type='dwell_time_completed' AND json_extract(payload,'$.details.censored')=0 THEN 1 ELSE 0 END) AS completed_zone_dwell_sessions,
        sum(CASE WHEN type='dwell_time_completed' AND json_extract(payload,'$.details.censored')=0 THEN json_extract(payload,'$.details.duration_seconds') ELSE 0 END) AS completed_zone_dwell_seconds,
        max(CASE WHEN type='occupancy_snapshot' THEN json_extract(payload,'$.details.visible_persons') ELSE NULL END) AS peak_visible_persons
        FROM events WHERE '''+' AND '.join(conditions)+''' GROUP BY location_id,node_id,camera_id,hour_utc ORDER BY hour_utc,location_id,node_id,camera_id'''
        db=self.connect()
        try: return [dict(row) for row in db.execute(query,args)]
        finally: db.close()

    def inventory(self, organization):
        db=self.connect()
        try:
            locations=[row['id'] for row in db.execute('SELECT id FROM locations WHERE organization_id=? ORDER BY id',(organization,))]
            cameras=[dict(row) for row in db.execute('SELECT location_id,node_id,id FROM cameras WHERE organization_id=? ORDER BY location_id,node_id,id',(organization,))]
            return {'locations':locations,'cameras':cameras}
        finally:db.close()

    def zones(self, organization, start, end, location=None, camera=None, node=None):
        conditions=['organization_id=?','timestamp>=?','timestamp<?']
        args=[organization,start,end]
        for field,value in [('location_id',location),('camera_id',camera),('node_id',node)]:
            if value is not None:conditions.append(field+'=?');args.append(value)
        query='''WITH scoped AS (SELECT * FROM events WHERE '''+' AND '.join(conditions)+'''), observations AS (
          SELECT location_id,node_id,camera_id,json_extract(payload,'$.details.zone_id') AS zone_id,
          type,json_extract(payload,'$.details.censored') AS censored,
          json_extract(payload,'$.details.duration_seconds') AS duration,NULL AS visible
          FROM scoped WHERE type IN ('dwell_time_completed','zone_crossed')
          UNION ALL
          SELECT s.location_id,s.node_id,s.camera_id,z.key,NULL,NULL,NULL,z.value
          FROM scoped s,json_each(s.payload,'$.details.zones') z WHERE s.type='occupancy_snapshot'
        ) SELECT location_id,node_id,camera_id,zone_id,
          sum(CASE WHEN type='dwell_time_completed' AND censored=0 THEN 1 ELSE 0 END) AS completed_sessions,
          sum(CASE WHEN type='dwell_time_completed' AND censored=1 THEN 1 ELSE 0 END) AS interrupted_sessions,
          sum(CASE WHEN type='dwell_time_completed' AND censored=0 THEN duration ELSE 0 END) AS observed_dwell_seconds,
          max(visible) AS peak_visible_persons
          FROM observations GROUP BY location_id,node_id,camera_id,zone_id ORDER BY location_id,node_id,camera_id,zone_id'''
        db=self.connect()
        try:return [dict(row) for row in db.execute(query,args)]
        finally:db.close()
