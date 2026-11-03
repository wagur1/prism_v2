import unittest
import numpy as np
from prism_v2.codec.sei import GeometrySignal,nal_unit
from prism_v2.retarget.geometry import from_saliency
from prism_v2.evaluation.coordinates import predictions_to_original


class EvaluationCoordinatesTests(unittest.TestCase):
    def test_evaluator_uses_geometry_only_from_au(self):
        signal=GeometrySignal(from_saliency(None,32,32,16,16).quantize(),32,32,16,16)
        au=b'\x00\x00\x01\x26\x01\x80'
        np.testing.assert_array_equal(predictions_to_original([[0,0,16,16]],nal_unit(signal)+au),[[0,0,32,32]])
        for data in (au,nal_unit(signal)*2+au):
            with self.assertRaises(ValueError):
                predictions_to_original([[0,0,16,16]],data)
