import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prism_v2.codec.gate0 import encode_condition


class RunnerTests(unittest.TestCase):
    def test_worker_has_source_import_path_and_isolated_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix=Path(tmp)/'plus'
            build={'shim':'shim','library':'library','pin':{}}
            with patch('prism_v2.codec.gate0.subprocess.run') as run:
                encode_condition(prefix,'plus6',build,20,128,80)
            environment=run.call_args.kwargs['env']
            self.assertTrue((Path(environment['PYTHONPATH'].split(os.pathsep)[0])/'prism_v2').is_dir())
            self.assertEqual(environment['PRISM_X265_RC_TELEMETRY'],str(prefix.with_suffix('.telemetry.csv').resolve()))
            self.assertEqual(json.loads(prefix.with_suffix('.job.json').read_text())['crf'],20)
            with self.assertRaisesRegex(ValueError,'fresh'):
                encode_condition(prefix,'plus6',build,20,128,80)
