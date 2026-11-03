import unittest
import numpy as np
from prism_v2.retarget.geometry import from_saliency
from prism_v2.retarget.boxes import DetectorTransform, inverse_boxes
from prism_v2.codec.sei import GeometrySignal


class BoxTests(unittest.TestCase):
    def test_inverse_after_detector_letterbox_and_visible_offset(self):
        g=from_saliency([[0,1,0],[1,0,1]],33,20,17,10).quantize()
        signal=GeometrySignal(g,33,20,32,16,visible_x=3,visible_y=2)
        original=np.array([[0,0,33,20],[2,3,19,15]],float)
        mapped=original.copy()
        mapped[:,[0,2]]=g.x.forward(mapped[:,[0,2]])+3
        mapped[:,[1,3]]=g.y.forward(mapped[:,[1,3]])+2
        mapped[:,[0,2]]=mapped[:,[0,2]]*1.5+7
        mapped[:,[1,3]]=mapped[:,[1,3]]*2+9
        np.testing.assert_allclose(inverse_boxes(mapped,signal,DetectorTransform(1.5,2,7,9)),original)

    def test_crop_retains_original_coordinates(self):
        g=from_saliency(None,32,16,16,8).quantize()
        signal=GeometrySignal(g,100,80,16,16,crop_x=20,crop_y=30,kind='crop')
        np.testing.assert_array_equal(inverse_boxes([[0,0,16,8]],signal),[[20,30,52,46]])

    def test_padding_clipped_and_input_unmodified(self):
        g=from_saliency(None,16,16,8,8).quantize()
        signal=GeometrySignal(g,16,16,16,16)
        boxes=np.array([[9,9,15,15]],float);copy=boxes.copy()
        np.testing.assert_array_equal(inverse_boxes(boxes,signal),[[16,16,16,16]])
        np.testing.assert_array_equal(boxes,copy)
        self.assertEqual(inverse_boxes(np.empty((0,4)),signal).shape,(0,4))

    def test_crop_letterbox_clipping_and_degenerate_boxes(self):
        g=from_saliency(None,31,19,13,7).quantize()
        signal=GeometrySignal(g,101,83,32,16,5,3,23,29,'crop')
        # Full visible region, clipped region, boxes wholly outside opposite
        # corners, and zero-width/height predictions at an interior point.
        local=np.array([[0,0,13,7],[-10,-5,20,10],[-5,-5,-1,-1],
                        [14,8,20,10],[4,2,4,5],[4,2,8,2]],float)
        detector=DetectorTransform(1.5,2.5,7,11)
        observed=(local+np.array([5,3,5,3]))*np.array([1.5,2.5,1.5,2.5])+np.array([7,11,7,11])
        expected=np.clip(local,[0,0,0,0],[13,7,13,7])*np.array([31/13,19/7,31/13,19/7])+np.array([23,29,23,29])
        np.testing.assert_allclose(inverse_boxes(observed,signal,detector),expected,atol=4e-5)
        for invalid in ([[2,0,1,3]],[[0,2,1,1]],[[0,0,float('nan'),1]]):
            with self.assertRaises(ValueError):
                inverse_boxes(invalid,signal)
