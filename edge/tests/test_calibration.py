import copy
import json
from pathlib import Path
import tempfile
import unittest
from edge_analytics.config import load_config, validate_calibration, verify_frame_aspect


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((Path(__file__).parents[1]/'config.example.json').read_text())
        self.config['zones']=[{'id':'Zone1','kind':'table','rect':[.1,.1,.4,.4]},
                              {'id':'service-1','kind':'service','table_id':'Zone1','rect':[.1,.4,.4,.6]}]
        self.config['calibration']={'schema_version':1,'source':{'kind':'video','width':640,'height':360,'frame_seconds':.8,'duration_seconds':2.},
          'fixed_view_confirmed':True,'role_samples':[{'role':'waiter','rect':[.1,.1,.3,.3],'rgb':[20,40,180],'hsv':{'h':232.5,'s':.88,'v':.7},'frame_seconds':.8}],
          'capabilities':{'uniform_classifier_active':False,'table_service_active':False},'review':{'status':'manual_review'}}

    def test_new_metadata_loads_with_existing_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config.json';path.write_text(json.dumps(self.config))
            loaded=load_config(path)
            self.assertEqual(loaded['zones'][1]['table_id'],'Zone1')
            self.assertEqual(loaded['calibration']['role_samples'][0]['role'],'waiter')

    def test_orphan_service_link_rejected(self):
        self.config['zones'][1]['table_id']='missing'
        with self.assertRaises(ValueError):validate_calibration(self.config)

    def test_invalid_samples_and_unsupported_activation_rejected(self):
        for field,value in [('role','face-id'),('rect',[.8,.8,.2,.2]),('rgb',[300,0,0]),('hsv',{'h':360,'s':1,'v':1}),('frame_seconds',-1)]:
            config=copy.deepcopy(self.config);config['calibration']['role_samples'][0][field]=value
            with self.assertRaises(ValueError):validate_calibration(config)
        self.config['calibration']['capabilities']['uniform_classifier_active']=True
        with self.assertRaises(ValueError):validate_calibration(self.config)

    def test_aspect_mismatch_rejected_and_matching_scaled_allowed(self):
        verify_frame_aspect(self.config,960,540)
        with self.assertRaises(ValueError):verify_frame_aspect(self.config,640,480)

    def test_disabled_line_does_not_create_crossing_events(self):
        from edge_analytics.analytics import Analytics
        self.config['line']['enabled']=False
        self.config['track_distance']=.5
        engine=Analytics(self.config)
        engine.update([[.5,.4]],0)
        result=engine.update([[.5,.6]],1)
        self.assertFalse(any(e['type'] in ('person_entered','person_exited') for e in result))

    def test_legacy_config_remains_compatible(self):
        self.config.pop('calibration')
        for zone in self.config['zones']:zone.pop('kind',None)
        validate_calibration(self.config)
        verify_frame_aspect(self.config,640,480)


if __name__=='__main__':unittest.main()
