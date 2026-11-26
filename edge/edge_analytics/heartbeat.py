"""Device liveness is distinct from event delivery and camera frame freshness."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from urllib.parse import urljoin, urlsplit


def configuration_proof(path):
    value=json.loads(Path(path).read_text())
    deployment=value.pop('deployment',None)
    digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if isinstance(deployment,dict) and type(deployment.get('calibration_version')) is int and deployment['calibration_version']>0 and deployment.get('configuration_sha256')==digest:
        return deployment['calibration_version'],digest
    return None,None


def send_heartbeat(config,cloud_url,token,health_file=None):
    url=urlsplit(cloud_url)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment or not token:
        raise ValueError('Heartbeat requires an HTTPS API and device credential')
    camera={'camera_id':config['camera_id'],'state':'unknown','last_frame_at':None,'applied_version':None,'configuration_sha256':None}
    if health_file:
        try:
            health=json.loads(Path(health_file).read_text())
            expected={key:config[key] for key in ('organization_id','location_id','node_id','camera_id')}
            if health.get('identity')==expected and 0<=time.time()-health.get('updated_at',0)<90:
                state=health.get('state','unknown')
                camera['state']=state if state in ('starting','processing','reconnecting','stopped','unresponsive') else 'unknown'
                camera['last_frame_at']=health.get('last_frame_at')
                camera['applied_version']=health.get('applied_version')
                camera['configuration_sha256']=health.get('configuration_sha256')
                if camera['state']=='processing' and camera['last_frame_at'] is None:camera['state']='unknown'
        except (OSError,ValueError,TypeError):pass
    request=urllib.request.Request(urljoin(cloud_url,'heartbeat'),data=json.dumps({'schema_version':1,'cameras':[camera]},allow_nan=False).encode(),headers={'Authorization':f'Bearer {token}','Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=15) as response:return json.loads(response.read(65536))
