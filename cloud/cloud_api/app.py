import csv
import io
import time
import json
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .database import Database, Conflict, Rejected
from .models import Batch
from . import accounts, operations
from .limits import RequestSizeLimit

MAX_BODY = 1024 * 1024


def create_app(database_path, secure_cookies=True, demo=False):
    database = Database(database_path)
    accounts.initialize(database)
    operations.initialize(database)
    app = FastAPI(title='AI Camera Analytica — Cloud MVP', version='0.1.0')
    app.add_middleware(RequestSizeLimit,max_bytes=MAX_BODY)
    bearer = HTTPBearer(auto_error=False)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request,exception):
        return JSONResponse(status_code=422,content={'detail':'Invalid request fields'})

    @app.middleware('http')
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            identity=accounts.authenticate(database,request.cookies.get('owner_session'))
            if identity is not None:return identity
        if not credentials or credentials.scheme.lower() != 'bearer' or len(credentials.credentials) > 256:
            raise HTTPException(401, 'Valid bearer credential required', headers={'WWW-Authenticate':'Bearer'})
        identity = database.authenticate(credentials.credentials)
        if identity is None:
            raise HTTPException(401, 'Valid bearer credential required', headers={'WWW-Authenticate':'Bearer'})
        return identity

    def role(required):
        def check(identity=Depends(principal)):
            if identity['role'] != required: raise HTTPException(403, 'Credential role not allowed')
            return identity
        return check

    @app.get('/healthz')
    def health():
        try:
            connection=database.connect()
            try: connection.execute('SELECT 1').fetchone()
            finally: connection.close()
        except Exception:
            raise HTTPException(503, 'Storage unavailable') from None
        return {'status':'ok'}

    @app.post('/v1/events')
    async def ingest(request: Request, identity=Depends(role('ingest'))):
        if request.headers.get('content-type','').split(';')[0].lower() != 'application/json':
            raise HTTPException(415,'application/json required')
        body=bytearray()
        async for chunk in request.stream():
            if len(body)+len(chunk) > MAX_BODY: raise HTTPException(413,'Batch body too large')
            body.extend(chunk)
        try:
            batch=Batch.model_validate_json(bytes(body))
            if type(batch.schema_version) is not int: raise ValueError()
            events=[event.model_dump() for event in batch.events]
            if any(event['timestamp'] > time.time()+300 for event in events): raise ValueError()
        except (ValidationError, ValueError):
            raise HTTPException(422,'Invalid analytics batch; schema version 1 and 1–100 valid metadata events required') from None
        try:
            accepted=await run_in_threadpool(database.ingest,identity,events)
        except Rejected:
            raise HTTPException(403,'Events do not belong to this registered node/camera') from None
        except Conflict:
            raise HTTPException(409,'An event ID was reused with different content; batch not committed') from None
        return {'accepted_event_ids':accepted}

    def report_rows(start, end, location, camera, identity, node=None):
        if not 0 <= start < end or end-start > 31*86400:
            raise HTTPException(422,'Use a positive UTC time range of at most 31 days; end is exclusive')
        return database.hourly(identity['organization_id'],start,end,location,camera,node)

    @app.get('/v1/metrics/hourly')
    def metrics(start: float = Query(ge=0,allow_inf_nan=False), end: float = Query(ge=0,allow_inf_nan=False),
                location_id: str | None = Query(default=None,max_length=128), camera_id: str | None = Query(default=None,max_length=128),
                node_id: str | None = Query(default=None,max_length=128), identity=Depends(role('reader'))):
        return {'timezone':'UTC','start':start,'end':end,'rows':report_rows(start,end,location_id,camera_id,identity,node_id)}

    @app.get('/v1/metrics/zones')
    def zone_metrics(start: float = Query(ge=0,allow_inf_nan=False), end: float = Query(ge=0,allow_inf_nan=False),
                     location_id: str | None = Query(default=None,max_length=128), camera_id: str | None = Query(default=None,max_length=128),
                     node_id: str | None = Query(default=None,max_length=128), identity=Depends(role('reader'))):
        if not 0 <= start < end or end-start > 31*86400:
            raise HTTPException(422,'Use a positive UTC time range of at most 31 days; end is exclusive')
        return {'start':start,'end':end,'rows':database.zones(identity['organization_id'],start,end,location_id,camera_id,node_id),
                'measurement':'observed_person_tracks',
                'capabilities':{'staff_first_approach':False,'order_delivery':False,'table_group_sessions':False,'table_utilization':False}}

    @app.get('/v1/reports/hourly.csv')
    def report(start: float = Query(ge=0,allow_inf_nan=False), end: float = Query(ge=0,allow_inf_nan=False),
               location_id: str | None = Query(default=None,max_length=128), camera_id: str | None = Query(default=None,max_length=128),
               node_id: str | None = Query(default=None,max_length=128), identity=Depends(role('reader'))):
        rows=report_rows(start,end,location_id,camera_id,identity,node_id)
        output=io.StringIO(newline='')
        fields=['hour_utc','location_id','node_id','camera_id','entries','exits','completed_zone_dwell_sessions','completed_zone_dwell_seconds','peak_visible_persons']
        writer=csv.DictWriter(output,fieldnames=fields)
        writer.writeheader()
        for row in rows:
            # Neutralize spreadsheet formulas in externally configured identifiers.
            writer.writerow({key:("'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value) for key,value in row.items()})
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="hourly.csv"'})

    def same_origin(request):
        origin=urlsplit(request.headers.get('origin',''))
        expected_scheme='https' if secure_cookies else request.url.scheme
        if origin.scheme!=expected_scheme or origin.netloc!=request.headers.get('host'):
            raise HTTPException(403,'Same-origin request required')

    @app.post('/auth/login')
    async def owner_login(request: Request):
        same_origin(request)
        if request.headers.get('content-type','').split(';')[0]!='application/json':raise HTTPException(415,'JSON required')
        raw=bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk)>4096:raise HTTPException(413,'Request too large')
            raw.extend(chunk)
        try:
            value=json.loads(raw)
            email,password=value['email'],value['password']
            if not isinstance(email,str) or not isinstance(password,str) or len(email)>254 or not 1<=len(password)<=256:raise ValueError()
        except (ValueError,KeyError,TypeError):raise HTTPException(400,'Invalid login request') from None
        try:token=await run_in_threadpool(accounts.login,database,email,password,request.client.host if request.client else 'unknown')
        except accounts.Throttled:raise HTTPException(429,'Too many attempts; retry in five minutes') from None
        if token is None:raise HTTPException(401,'Email or password incorrect')
        response=Response(status_code=204)
        response.set_cookie('owner_session',token,httponly=True,secure=secure_cookies,samesite='strict',max_age=accounts.SESSION_SECONDS,path='/')
        return response

    @app.post('/auth/logout')
    def owner_logout(request: Request):
        same_origin(request)
        accounts.logout(database,request.cookies.get('owner_session',''))
        response=Response(status_code=204)
        response.delete_cookie('owner_session',path='/',secure=secure_cookies,httponly=True,samesite='strict')
        return response

    @app.get('/v1/me')
    def me(identity=Depends(principal)):
        if identity['role'] not in ('reader','admin','technician'):raise HTTPException(403,'Account required')
        return {'organization_id':identity['organization_id'],'email':identity.get('email'),'demo':demo,'role':identity['role']}

    @app.get('/v1/inventory')
    def inventory(identity=Depends(role('reader'))):
        return database.inventory(identity['organization_id'])

    @app.get('/',include_in_schema=False)
    def home():
        return Response((Path(__file__).parent/'public/index.html').read_bytes(),media_type='text/html',headers={
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://formspree.io; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self' https://formspree.io",
            'Referrer-Policy':'no-referrer'})

    @app.get('/styles.css',include_in_schema=False)
    @app.get('/scripts.js',include_in_schema=False)
    @app.get('/i18n.js',include_in_schema=False)
    @app.get('/demo.js',include_in_schema=False)
    def public_asset(request: Request):
        asset=request.url.path.lstrip('/')
        return Response((Path(__file__).parent/'public'/asset).read_bytes(),media_type='text/css' if asset.endswith('.css') else 'text/javascript')

    @app.get('/login',include_in_schema=False)
    @app.get('/panel',include_in_schema=False)
    def dashboard():
        return Response((Path(__file__).parent/'dashboard/index.html').read_bytes(),media_type='text/html',headers={
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob: data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Referrer-Policy':'no-referrer'})

    @app.get('/dashboard/{asset}',include_in_schema=False)
    def dashboard_asset(asset: str):
        types={'app.js':'text/javascript','styles.css':'text/css'}
        if asset not in types:raise HTTPException(404)
        return Response((Path(__file__).parent/'dashboard'/asset).read_bytes(),media_type=types[asset])

    from .admin_api import register
    register(app,database,principal,same_origin,demo)
    return app
