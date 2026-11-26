import json
from pathlib import Path
import sqlite3
import secrets
import hashlib
import time
from typing import Literal

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import accounts, operations
from .installer_validation import validate_config


class Model(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)

    @model_validator(mode='after')
    def identifiers(self):
        for key,value in self.__dict__.items():
            if (key=='id' or key.endswith('_id')) and isinstance(value,str) and (not value.strip() or value!=value.strip()):raise ValueError('Identifiers cannot have leading/trailing whitespace')
        return self


class Business(Model):
    id:str=Field(min_length=1,max_length=128)
    name:str=Field(min_length=1,max_length=128)


class Location(Model):
    organization_id:str=Field(min_length=1,max_length=128)
    id:str=Field(min_length=1,max_length=128)
    name:str=Field(min_length=1,max_length=128)


class Node(Model):
    organization_id:str=Field(min_length=1,max_length=128)
    location_id:str=Field(min_length=1,max_length=128)
    id:str=Field(min_length=1,max_length=128)


class Camera(Node):
    node_id:str=Field(min_length=1,max_length=128)


class NodeCredential(Model):
    organization_id:str=Field(min_length=1,max_length=128)
    location_id:str=Field(min_length=1,max_length=128)
    node_id:str=Field(min_length=1,max_length=128)


class Assignment(Model):
    email:str=Field(min_length=3,max_length=254)
    organization_id:str=Field(min_length=1,max_length=128)
    location_id:str=Field(min_length=1,max_length=128)


class Account(Model):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=12,max_length=256)
    role:Literal['owner','technician']
    organization_id:str|None=None


class Calibration(Model):
    config:dict
    expected_version:int=Field(ge=0)
    status:Literal['draft','manual_review']='draft'


class Activate(Model):
    version:int=Field(ge=1)


class CameraHealth(Model):
    camera_id:str=Field(min_length=1,max_length=128)
    state:Literal['unknown','starting','processing','reconnecting','stopped','unresponsive']
    last_frame_at:float|None=None
    applied_version:int|None=Field(default=None,ge=1)
    configuration_sha256:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def proof_pair(self):
        if (self.applied_version is None)!=(self.configuration_sha256 is None):raise ValueError('Version and digest must be paired')
        if self.last_frame_at is not None and not 0<=self.last_frame_at<=time.time()+30:raise ValueError('Invalid frame time')
        if self.state=='processing' and self.last_frame_at is None:raise ValueError('Processing requires frame evidence')
        return self


class Heartbeat(Model):
    schema_version:Literal[1]
    cameras:list[CameraHealth]=Field(default_factory=list,max_length=100)


def register(app,database,principal,same_origin,demo):
    def operator(identity=Depends(principal)):
        if identity['role'] not in ('admin','technician') or not identity.get('email'):raise HTTPException(403,'Installer account required')
        return identity

    def admin(identity=Depends(operator)):
        if identity['role']!='admin':raise HTTPException(403,'Administrator required')
        return identity

    def write_operator(request:Request,identity=Depends(operator)):
        same_origin(request);return identity

    def write_admin(request:Request,identity=Depends(admin)):
        same_origin(request);return identity

    def scope(organization_id:str=Query(min_length=1,max_length=128),location_id:str=Query(min_length=1,max_length=128),
              node_id:str=Query(min_length=1,max_length=128),camera_id:str=Query(min_length=1,max_length=128)):
        return organization_id,location_id,node_id,camera_id

    def checked_scope(value,identity):
        db=database.connect()
        try:
            if not operations.scope_allowed(db,identity,value):raise HTTPException(403,'Location not assigned to this technician')
            if not operations.camera_exists(db,value):raise HTTPException(404,'Registered camera not found')
        finally:db.close()
        return value

    def change(identity,action,details,callback):
        db=database.connect()
        try:
            with db:
                result=callback(db)
                operations.audit(db,identity['email'],action,details)
            return result or {'ok':True}
        except sqlite3.IntegrityError:raise HTTPException(409,'Duplicate identifier or missing parent record') from None
        finally:db.close()

    @app.get('/v1/operations')
    def overview(identity=Depends(operator)):
        return {**operations.overview(database,identity),'demo':demo,'role':identity['role'],'email':identity['email']}

    @app.post('/v1/admin/businesses')
    def business(value:Business,identity=Depends(write_admin)):
        if value.id==operations.SYSTEM_ORG or not value.id.strip() or not value.name.strip():raise HTTPException(400,'Invalid business identifier')
        def save(db):
            db.execute('INSERT INTO organizations VALUES (?)',(value.id,))
            db.execute('INSERT INTO business_names VALUES (?,?)',(value.id,value.name))
        return change(identity,'business.created',{'organization_id':value.id},save)

    @app.post('/v1/admin/locations')
    def location(value:Location,identity=Depends(write_admin)):
        def save(db):
            db.execute('INSERT INTO locations VALUES (?,?)',(value.organization_id,value.id))
            db.execute('INSERT INTO location_names VALUES (?,?,?)',(value.organization_id,value.id,value.name))
        return change(identity,'location.created',value.model_dump(exclude={'name'}),save)

    @app.post('/v1/admin/nodes')
    def node(value:Node,identity=Depends(write_admin)):
        return change(identity,'node.created',value.model_dump(),lambda db:db.execute('INSERT INTO nodes VALUES (?,?,?)',(value.organization_id,value.location_id,value.id)) and None)

    @app.post('/v1/admin/cameras')
    def camera(value:Camera,identity=Depends(write_admin)):
        return change(identity,'camera.created',value.model_dump(),lambda db:db.execute('INSERT INTO cameras VALUES (?,?,?,?)',(value.organization_id,value.location_id,value.node_id,value.id)) and None)

    @app.post('/v1/admin/node-credential')
    def credential(value:NodeCredential,identity=Depends(write_admin)):
        token=secrets.token_urlsafe(32)
        def save(db):
            if not db.execute('SELECT 1 FROM nodes WHERE organization_id=? AND location_id=? AND id=?',(value.organization_id,value.location_id,value.node_id)).fetchone():raise HTTPException(404,'Node not registered')
            db.execute("INSERT INTO credentials VALUES (?,?,?,?,?,0)",(hashlib.sha256(token.encode()).hexdigest(),value.organization_id,value.location_id,value.node_id,'ingest'))
        change(identity,'device.credential_created',value.model_dump(),save)
        return Response(token+'\n',media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="device.token"'})

    @app.post('/v1/admin/accounts')
    def account(value:Account,identity=Depends(write_admin)):
        organization=operations.SYSTEM_ORG if value.role=='technician' else value.organization_id
        db=database.connect()
        try:
            if value.role=='owner' and (not organization or organization==operations.SYSTEM_ORG or not db.execute('SELECT 1 FROM organizations WHERE id=?',(organization,)).fetchone()):raise HTTPException(400,'Choose a registered business')
        finally:db.close()
        try:accounts.create_owner(database,organization,value.email,value.password,'technician' if value.role=='technician' else 'reader')
        except (ValueError,sqlite3.IntegrityError):raise HTTPException(409,'Account already exists or fields are invalid') from None
        return change(identity,'account.created',{'email':value.email.casefold(),'role':value.role,'organization_id':organization},lambda _:None)

    @app.post('/v1/admin/assignments')
    def assign(value:Assignment,identity=Depends(write_admin)):
        def save(db):
            if not db.execute("SELECT 1 FROM account_roles JOIN owners USING(email) WHERE email=? AND role='technician' AND enabled=1",(value.email.casefold(),)).fetchone():raise HTTPException(400,'Choose an active technician')
            db.execute('INSERT OR IGNORE INTO assignments VALUES (?,?,?)',(value.email.casefold(),value.organization_id,value.location_id))
        return change(identity,'technician.assigned',value.model_dump(),save)

    @app.post('/v1/admin/unassign')
    def unassign(value:Assignment,identity=Depends(write_admin)):
        return change(identity,'technician.unassigned',value.model_dump(),lambda db:db.execute('DELETE FROM assignments WHERE email=? AND organization_id=? AND location_id=?',(value.email.casefold(),value.organization_id,value.location_id)) and None)

    @app.get('/v1/installations/context')
    def context(value=Depends(scope),identity=Depends(operator)):
        checked_scope(value,identity);db=database.connect()
        try:
            versions=[dict(row) for row in db.execute('SELECT version,status,created_by,created_at,digest FROM calibrations WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=? ORDER BY version DESC',value)]
            latest=db.execute('SELECT config FROM calibrations WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=? ORDER BY version DESC LIMIT 1',value).fetchone()
            config=json.loads(latest['config']) if latest else json.loads((Path(__file__).parent/'installer/default_config.json').read_text(encoding='utf-8'))
            config.update(dict(zip(('organization_id','location_id','node_id','camera_id'),value)))
            return {'config':config,'versions':versions,'latest_version':versions[0]['version'] if versions else 0}
        finally:db.close()

    @app.post('/v1/installations/calibrations')
    def save_calibration(body:Calibration,value=Depends(scope),identity=Depends(write_operator)):
        checked_scope(value,identity)
        try:
            config=json.loads(operations.canonical(body.config))
            if tuple(config.get(k) for k in ('organization_id','location_id','node_id','camera_id'))!=value:raise ValueError('Scope mismatch')
            config['database']='events.sqlite3'
            validate_config(config)
            if body.status=='manual_review':
                calibration=config.get('calibration') or {}
                if not calibration.get('source'):
                    raise HTTPException(422,'Ngarko foton ose videon e kamerës përpara kontrollit manual.')
                if not calibration.get('fixed_view_confirmed'):
                    raise HTTPException(422,'Shëno kutinë: Pamja është fikse, pa zoom ose prerje gjatë analizës.')
                if calibration.get('review',{}).get('status')!='manual_review':
                    raise HTTPException(422,'Shtyp Kontrollo konfigurimin, pastaj Ruaj kontrollin manual. Nëse ndryshon konfigurimin, kontrolloje sërish.')
            if 'calibration' in config:config['calibration']['review']={'status':body.status}
        except (ValueError,KeyError,TypeError):raise HTTPException(422,'Invalid calibration, identity or manual review') from None
        text=operations.canonical(config);digest=operations.digest(config)
        def save(db):
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT coalesce(max(version),0) FROM calibrations WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=?',value).fetchone()[0]
            if previous!=body.expected_version:raise HTTPException(409,'Calibration changed; reload before saving')
            version=previous+1
            db.execute('INSERT INTO calibrations VALUES (?,?,?,?,?,?,?,?,?,?)',(*value,version,body.status,text,digest,identity['email'],time.time()))
            return {'version':version,'status':body.status,'sha256':digest}
        return change(identity,'calibration.saved',dict(zip(('organization_id','location_id','node_id','camera_id'),value))|{'status':body.status},save)

    @app.post('/v1/admin/activate')
    def activate(body:Activate,value=Depends(scope),identity=Depends(write_admin)):
        checked_scope(value,identity)
        def save(db):
            row=db.execute('SELECT status FROM calibrations WHERE organization_id=? AND location_id=? AND node_id=? AND camera_id=? AND version=?',(*value,body.version)).fetchone()
            if not row or row['status']!='manual_review':raise HTTPException(409,'Only manually reviewed calibration can be activated')
            db.execute('INSERT INTO deployments VALUES (?,?,?,?,?,?) ON CONFLICT(organization_id,location_id,node_id,camera_id) DO UPDATE SET version=excluded.version,activated_at=excluded.activated_at',(*value,body.version,time.time()))
        return change(identity,'calibration.activated',dict(zip(('organization_id','location_id','node_id','camera_id'),value))|{'version':body.version},save)

    def active_config(value):
        db=database.connect()
        try:
            row=db.execute('SELECT c.config,c.version,c.digest FROM deployments d JOIN calibrations c USING(organization_id,location_id,node_id,camera_id,version) WHERE d.organization_id=? AND d.location_id=? AND d.node_id=? AND d.camera_id=?',value).fetchone()
            if not row:raise HTTPException(404,'No activated configuration')
            config=json.loads(row['config']);config['deployment']={'calibration_version':row['version'],'configuration_sha256':row['digest']}
            return config
        finally:db.close()

    @app.get('/v1/installations/config')
    def export(value=Depends(scope),identity=Depends(operator)):
        checked_scope(value,identity)
        return Response(json.dumps(active_config(value),indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="config.local.json"'})

    @app.get('/v1/device/config')
    def device_config(camera_id:str=Query(min_length=1,max_length=128),identity=Depends(principal)):
        if identity['role']!='ingest':raise HTTPException(403,'Device credential required')
        value=(identity['organization_id'],identity['location_id'],identity['node_id'],camera_id)
        db=database.connect()
        try:
            if not operations.camera_exists(db,value):raise HTTPException(403,'Camera not registered to this node')
        finally:db.close()
        return active_config(value)

    @app.post('/v1/heartbeat')
    def heartbeat(body:Heartbeat,identity=Depends(principal)):
        if identity['role']!='ingest':raise HTTPException(403,'Device credential required')
        base=(identity['organization_id'],identity['location_id'],identity['node_id']);now=time.time();db=database.connect()
        try:
            with db:
                for camera in body.cameras:
                    if not operations.camera_exists(db,(*base,camera.camera_id)):raise HTTPException(403,'Camera not registered to this node')
                db.execute('INSERT INTO node_health VALUES (?,?,?,?) ON CONFLICT(organization_id,location_id,node_id) DO UPDATE SET received_at=excluded.received_at',(*base,now))
                for camera in body.cameras:
                    db.execute('INSERT INTO camera_health VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(organization_id,location_id,node_id,camera_id) DO UPDATE SET state=excluded.state,last_frame_at=excluded.last_frame_at,received_at=excluded.received_at,reported_version=excluded.reported_version,reported_digest=excluded.reported_digest',(*base,camera.camera_id,camera.state,camera.last_frame_at,now,camera.applied_version,camera.configuration_sha256))
        finally:db.close()
        return {'received_at':now}

    page_headers={'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",'Referrer-Policy':'no-referrer'}

    @app.get('/admin',include_in_schema=False)
    @app.get('/technician',include_in_schema=False)
    def page():
        return Response((Path(__file__).parent/'admin/index.html').read_bytes(),media_type='text/html',headers=page_headers)

    @app.get('/admin-assets/{asset}',include_in_schema=False)
    def asset(asset:str):
        types={'app.js':'text/javascript','installer.js':'text/javascript','styles.css':'text/css'}
        if asset not in types:raise HTTPException(404)
        return Response((Path(__file__).parent/'admin'/asset).read_bytes(),media_type=types[asset])

    @app.get('/installer/',include_in_schema=False)
    def installer(identity=Depends(operator)):
        text=(Path(__file__).parent/'installer/index.html').read_text(encoding='utf-8')
        text=text.replace('</head>','<link rel="stylesheet" href="/admin-assets/styles.css"><script src="/admin-assets/installer.js" defer></script></head>').replace('href="../../index.html"','href="/technician"')
        return Response(text,media_type='text/html',headers=page_headers)

    @app.get('/installer/{asset}',include_in_schema=False)
    def installer_asset(asset:str,identity=Depends(operator)):
        types={'app.js':'text/javascript','calibration.js':'text/javascript','styles.css':'text/css'}
        if asset not in types:raise HTTPException(404)
        return Response((Path(__file__).parent/'installer'/asset).read_bytes(),media_type=types[asset])
