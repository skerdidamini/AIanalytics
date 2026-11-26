"""Pure installer schema mirror. Contract tests also validate with the actual edge runtime."""
import math

def validate_config(config):
    for key in ('organization_id', 'location_id', 'node_id', 'camera_id', 'database'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'Missing or invalid {key}')
    for key in ('sample_fps', 'max_width', 'track_distance', 'track_timeout',
                'occupancy_interval', 'queue_max_events'):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key} must be positive and finite')
    if not isinstance(config['queue_max_events'], int) or config['max_width'] < 64:
        raise ValueError('queue_max_events must be an integer; max_width must be >= 64')
    line = config['line']
    for point in (line['start'], line['end']):
        if len(point) != 2 or not all(isinstance(v, (float, int)) and math.isfinite(v) and 0 <= v <= 1 for v in point):
            raise ValueError('Line coordinates must be normalized to [0,1]')
    if line['start'] == line['end'] or line['enter_side'] not in (-1, 1) or not 0 < line['margin'] < 1:
        raise ValueError('Invalid line direction or margin')
    zones = config.get('zones', [])
    if len({z['id'] for z in zones}) != len(zones):
        raise ValueError('Zone IDs must be unique')
    for zone in zones:
        x1, y1, x2, y2 = zone['rect']
        if not zone['id'] or not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError('Invalid zone rectangle')
    validate_calibration(config)
    return config

def validate_calibration(config):
    kinds={'table','service','takeaway','entrance','exit','other'}
    roles={'waiter','bartender','customer','unknown'}
    if 'enabled' in config['line'] and type(config['line']['enabled']) is not bool:
        raise ValueError('Line enabled must be boolean')
    zones=config.get('zones',[])
    for zone in zones:
        if 'kind' in zone and zone['kind'] not in kinds:
            raise ValueError('Invalid zone kind')
        if zone.get('kind')=='service' and not any(t.get('kind')=='table' and t['id']==zone.get('table_id') for t in zones):
            raise ValueError('Service zones require an existing table zone')
    value=config.get('calibration')
    if value is None:return
    if not isinstance(value,dict) or type(value.get('schema_version')) is not int or value['schema_version']!=1:
        raise ValueError('Unsupported calibration schema')
    if type(value.get('fixed_view_confirmed')) is not bool:
        raise ValueError('Invalid fixed view confirmation')
    source=value.get('source')
    def finite(v):return type(v) in (int,float) and math.isfinite(v)
    if source is not None:
        if not isinstance(source,dict) or source.get('kind') not in ('image','video'):
            raise ValueError('Invalid calibration source')
        if any(type(source.get(k)) is not int or source[k]<=0 for k in ('width','height')):
            raise ValueError('Invalid source dimensions')
        if source['kind']=='video':
            duration,position=source.get('duration_seconds'),source.get('frame_seconds')
            if not finite(duration) or not finite(position) or not 0<=position<=duration+.1 or duration<=0:
                raise ValueError('Invalid source video time')
    samples=value.get('role_samples')
    if not isinstance(samples,list) or len(samples)>30:raise ValueError('Invalid role samples')
    for sample in samples:
        if not isinstance(sample,dict) or sample.get('role') not in roles:raise ValueError('Invalid sample role')
        rect=sample.get('rect')
        if not isinstance(rect,list) or len(rect)!=4 or not all(finite(v) and 0<=v<=1 for v in rect) or not (rect[0]<rect[2] and rect[1]<rect[3]):
            raise ValueError('Invalid sample rectangle')
        rgb=sample.get('rgb')
        if not isinstance(rgb,list) or len(rgb)!=3 or not all(finite(v) and 0<=v<=255 for v in rgb):raise ValueError('Invalid sample RGB')
        hsv=sample.get('hsv')
        if not isinstance(hsv,dict) or not finite(hsv.get('h')) or not 0<=hsv['h']<360 or not all(finite(hsv.get(k)) and 0<=hsv[k]<=1 for k in ('s','v')):
            raise ValueError('Invalid sample HSV')
        if sample.get('frame_seconds') is not None and (not finite(sample['frame_seconds']) or sample['frame_seconds']<0):raise ValueError('Invalid sample time')
    capabilities=value.get('capabilities',{})
    if not isinstance(capabilities,dict) or capabilities.get('uniform_classifier_active') is not False or capabilities.get('table_service_active') is not False:
        raise ValueError('Automatic role/service inference is not supported by this runtime')
    if not isinstance(value.get('review'),dict) or value['review'].get('status') not in ('draft','manual_review'):
        raise ValueError('Invalid calibration review status')
