import csv,json,subprocess,tempfile
from pathlib import Path
import cv2,numpy as np
root=Path(__file__).resolve().parents[1]
import sys
cli=[sys.executable, '-m', 'edge_analytics.cli']
import unittest

class VideoTests(unittest.TestCase):
 def test_video_pipeline(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)
   config=json.loads((root/'config.example.json').read_text())
   config['database']=str(p/'events.sqlite3')
   (p/'config.json').write_text(json.dumps(config))
   video=cv2.VideoWriter(str(p/'blank.avi'),cv2.VideoWriter_fourcc(*'MJPG'),10,(320,240))
   assert video.isOpened()
   for _ in range(30):video.write(np.zeros((240,320,3),dtype=np.uint8))
   video.release()
   def run(*args):
    result=subprocess.run([*cli,'--config',str(p/'config.json'),*args],capture_output=True,text=True)
    assert result.returncode==0,(result.stdout,result.stderr)
    print(result.stdout.strip())
   run('run','--video',str(p/'blank.avi'))
   records=[{'timestamp':1000+i/5,'points':[[0.5,y]]} for i,y in enumerate([0.35,0.45,0.55,0.65,0.75,0.85,0.95])]
   (p/'points.jsonl').write_text('\n'.join(json.dumps(r) for r in records))
   run('replay',str(p/'points.jsonl'))
   run('report','--output',str(p/'report.csv'))
   with (p/'report.csv').open() as report:
    rows=list(csv.DictReader(report))
   assert sum(int(r['entries']) for r in rows)==1,rows
   assert sum(int(r['exits']) for r in rows)==0,rows
   assert sum(int(r['completed_zone_dwell_sessions']) for r in rows)==1,rows
   run('status')
   print('PASS: local video decode + HOG inference, replay -> SQLite -> hourly CSV; expected 1 entry, 0 exits, 1 completed zone dwell')
