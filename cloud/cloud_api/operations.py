"""Installer registry, immutable calibration versions and device health observations."""
import hashlib
import json
import time
from datetime import datetime, timezone

SYSTEM_ORG='__system_accounts__'
SCHEMA='''
CREATE TABLE IF NOT EXISTS business_names (organization_id TEXT PRIMARY KEY,name TEXT NOT NULL,FOREIGN KEY(organization_id) REFERENCES organizations(id));
CREATE TABLE IF NOT EXISTS location_names (organization_id TEXT NOT NULL,location_id TEXT NOT NULL,name TEXT NOT NULL,PRIMARY KEY(organization_id,location_id),FOREIGN KEY(organization_id,location_id) REFERENCES locations(organization_id,id));
CREATE TABLE IF NOT EXISTS assignments (email TEXT NOT NULL,organization_id TEXT NOT NULL,location_id TEXT NOT NULL,PRIMARY KEY(email,organization_id,location_id),FOREIGN KEY(email) REFERENCES owners(email),FOREIGN KEY(organization_id,location_id) REFERENCES locations(organization_id,id));
CREATE TABLE IF NOT EXISTS calibrations (organization_id TEXT NOT NULL,location_id TEXT NOT NULL,node_id TEXT NOT NULL,camera_id TEXT NOT NULL,version INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('draft','manual_review')),config TEXT NOT NULL,digest TEXT NOT NULL,created_by TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(organization_id,location_id,node_id,camera_id,version),FOREIGN KEY(organization_id,location_id,node_id,camera_id) REFERENCES cameras(organization_id,location_id,node_id,id));
CREATE TABLE IF NOT EXISTS deployments (organization_id TEXT NOT NULL,location_id TEXT NOT NULL,node_id TEXT NOT NULL,camera_id TEXT NOT NULL,version INTEGER NOT NULL,activated_at REAL NOT NULL,PRIMARY KEY(organization_id,location_id,node_id,camera_id),FOREIGN KEY(organization_id,location_id,node_id,camera_id,version) REFERENCES calibrations(organization_id,location_id,node_id,camera_id,version));
CREATE TABLE IF NOT EXISTS node_health (organization_id TEXT NOT NULL,location_id TEXT NOT NULL,node_id TEXT NOT NULL,received_at REAL NOT NULL,PRIMARY KEY(organization_id,location_id,node_id),FOREIGN KEY(organization_id,location_id,node_id) REFERENCES nodes(organization_id,location_id,id));
CREATE TABLE IF NOT EXISTS camera_health (organization_id TEXT NOT NULL,location_id TEXT NOT NULL,node_id TEXT NOT NULL,camera_id TEXT NOT NULL,state TEXT NOT NULL,last_frame_at REAL,received_at REAL NOT NULL,reported_version INTEGER,reported_digest TEXT,PRIMARY KEY(organization_id,location_id,node_id,camera_id),FOREIGN KEY(organization_id,location_id,node_id,camera_id) REFERENCES cameras(organization_id,location_id,node_id,id));
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,action TEXT NOT NULL,details TEXT NOT NULL,created_at REAL NOT NULL);
'''


def initialize(database):
    db=database.connect()
    try:db.executescript(SCHEMA)
    finally:db.close()


def audit(db,actor,action,details):
    db.execute('INSERT INTO audit(actor,action,details,created_at) VALUES (?,?,?,?)',(actor,action,json.dumps(details,allow_nan=False),time.time()))


def scope_allowed(db,identity,scope):
    if identity['role']=='admin':return True
    return identity['role']=='technician' and db.execute('SELECT 1 FROM assignments WHERE email=? AND organization_id=? AND location_id=?',(identity['email'],*scope[:2])).fetchone() is not None


def camera_exists(db,scope):
    return db.execute('SELECT 1 FROM cameras WHERE organization_id=? AND location_id=? AND node_id=? AND id=?',scope).fetchone() is not None


def canonical(config):
    value={k:v for k,v in config.items() if k!='deployment'}
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def digest(config):return hashlib.sha256(canonical(config).encode()).hexdigest()


def overview(database,identity):
    db=database.connect()
    try:
        orgs=[]
        for row in db.execute('SELECT o.id,coalesce(n.name,o.id) AS name FROM organizations o LEFT JOIN business_names n ON n.organization_id=o.id WHERE o.id!=? ORDER BY name',(SYSTEM_ORG,)):
            if identity['role']!='admin' and not db.execute('SELECT 1 FROM assignments WHERE email=? AND organization_id=?',(identity['email'],row['id'])).fetchone():continue
            item=dict(row)
            item['owners']=[r['email'] for r in db.execute("SELECT email FROM owners LEFT JOIN account_roles USING(email) WHERE organization_id=? AND enabled=1 AND coalesce(role,'reader')='reader'",(row['id'],))] if identity['role']=='admin' else []
            orgs.append(item)
        locations=[]
        for row in db.execute('SELECT l.organization_id,l.id,coalesce(n.name,l.id) AS name FROM locations l LEFT JOIN location_names n ON n.organization_id=l.organization_id AND n.location_id=l.id ORDER BY l.organization_id,l.id'):
            if scope_allowed(db,identity,(row['organization_id'],row['id'])):locations.append(dict(row))
        nodes=[]
        for row in db.execute('SELECT n.*,h.received_at AS last_heartbeat_at FROM nodes n LEFT JOIN node_health h ON h.organization_id=n.organization_id AND h.location_id=n.location_id AND h.node_id=n.id'):
            if not scope_allowed(db,identity,(row['organization_id'],row['location_id'])):continue
            item=dict(row);item['online']=None if row['last_heartbeat_at'] is None else time.time()-row['last_heartbeat_at']<90
            item['credential_configured']=bool(db.execute("SELECT 1 FROM credentials WHERE organization_id=? AND location_id=? AND node_id=? AND role='ingest' AND revoked=0",(row['organization_id'],row['location_id'],row['id'])).fetchone())
            nodes.append(item)
        cameras=[]
        for row in db.execute('SELECT * FROM cameras ORDER BY organization_id,location_id,node_id,id'):
            scope=(row['organization_id'],row['location_id'],row['node_id'],row['id'])
            if not scope_allowed(db,identity,scope):continue
            item=dict(row)
            latest=db.execute('SELECT version,status,created_by,created_at FROM calibrations WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=? ORDER BY version DESC LIMIT 1',scope).fetchone()
            active=db.execute('SELECT d.version,c.digest FROM deployments d JOIN calibrations c USING(organization_id,location_id,node_id,camera_id,version) WHERE d.organization_id=? AND d.location_id=? AND d.node_id=? AND d.camera_id=?',scope).fetchone()
            health=db.execute('SELECT * FROM camera_health WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=?',scope).fetchone()
            events=db.execute('SELECT count(*) AS count,max(received_at) AS received,max(timestamp) AS event_time FROM events WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=?',scope).fetchone()
            fresh=health is not None and time.time()-health['received_at']<90
            frame_recent=health is not None and health['last_frame_at'] is not None and 0<=time.time()-health['last_frame_at']<90
            item.update(latest_calibration=dict(latest) if latest else None,active_version=active['version'] if active else None,
                        applied_version=health['reported_version'] if fresh and active and health['reported_version']==active['version'] and health['reported_digest']==active['digest'] else None,
                        camera_status=('processing' if health['state']=='processing' and frame_recent else health['state']) if fresh else ('stale' if health else 'unknown'),
                        last_frame_at=health['last_frame_at'] if health else None,last_camera_report_at=health['received_at'] if health else None,
                        event_count=events['count'],last_event_received_at=events['received'],last_event_at=events['event_time'])
            if fresh and health['state']=='processing' and not frame_recent:item['camera_status']='stale_frames'
            cameras.append(item)
        technicians=[dict(r) for r in db.execute("SELECT email,enabled FROM owners JOIN account_roles USING(email) WHERE role='technician' ORDER BY email")] if identity['role']=='admin' else []
        assignments=[dict(r) for r in db.execute('SELECT * FROM assignments ORDER BY email,organization_id,location_id') if identity['role']=='admin' or r['email']==identity['email']]
        history=[dict(r) for r in db.execute('SELECT actor,action,details,created_at FROM audit ORDER BY id DESC LIMIT 50')] if identity['role']=='admin' else []
        return {'businesses':orgs,'locations':locations,'nodes':nodes,'cameras':cameras,'technicians':technicians,'assignments':assignments,'audit':history,'observed_at':time.time()}
    finally:db.close()
