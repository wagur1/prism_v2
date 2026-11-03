from pathlib import Path
import tempfile
import unittest
from prism_v2.codec.criteria import verify_condition

FIXTURES=Path(__file__).resolve().parents[1]/'fixtures'


class SyntheticNetTests(unittest.TestCase):
    def test_base_drift_is_removed_in_both_directions(self):
        # minus raw final-QP change is +12; true control effect is -6.
        for name,sign in (('plus6',1),('minus6',-1)):
            result=verify_condition(FIXTURES/'synthetic_zero.csv',FIXTURES/f'synthetic_{name}.csv',
                [[sign*6]*2]*2,name=name,width=20,height=20,frames=2)
            self.assertEqual(result[str(sign)],6)
            self.assertEqual(result['per_frame'][f'1:{sign}']['kind'],'I')
            self.assertEqual(result['per_frame'][f'1:{sign}']['frame_class'],'compensated')

    def test_missing_frame_and_non_intra_fail(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            verify_condition(FIXTURES/'synthetic_zero.csv',FIXTURES/'synthetic_plus6.csv',
                [[6]*2]*2,name='plus6',width=20,height=20,frames=10)
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/'inter.csv'
            bad.write_text((FIXTURES/'synthetic_plus6.csv').read_text().replace(',I,',',P,'))
            with self.assertRaisesRegex(ValueError,'intra'):
                verify_condition(FIXTURES/'synthetic_zero.csv',bad,[[6]*2]*2,name='plus6',width=20,height=20,frames=2)
