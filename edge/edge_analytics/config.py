import json
import math
from pathlib import Path


def load_config(path):
    config = json.loads(Path(path).read_text())
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
    db = Path(config['database'])
    config['database'] = str((Path(path).resolve().parent / db).resolve())
    return config
