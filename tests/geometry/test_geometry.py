import unittest
import numpy as np
from prism_v2.retarget.geometry import AxisMap, QuantizedMap, from_saliency, axis_from_marginal, boundaries, SCALE
from prism_v2.codec.qg import expand_ctu64, warp_qg


class GeometryTests(unittest.TestCase):
    def test_random_monotonicity_no_holes_and_inverse(self):
        rng=np.random.default_rng(927)
        for _ in range(80):
            w,h=(int(v) for v in rng.integers(1,1000,2))
            ow,oh=max(1,w//2),max(1,h//2)
            saliency=rng.random((len(boundaries(h))-1,len(boundaries(w))-1))
            g=from_saliency(saliency,w,h,ow,oh).quantize()
            for axis,source,visible in ((g.x,w,ow),(g.y,h,oh)):
                points=np.linspace(0,source,301)
                mapped=axis.forward(points)
                self.assertTrue(np.all(np.diff(mapped)>0))
                np.testing.assert_allclose(axis.inverse(mapped),points,atol=1e-10)
                self.assertEqual((mapped[0],mapped[-1]),(0,visible))
                self.assertEqual(sum(np.diff(axis.destination)),visible)
                for a,b in zip(axis.source,axis.destination):
                    self.assertEqual(axis.forward(a),b)
            self.assertEqual(QuantizedMap.parse(g.serialize()),g)

    def test_weight_formula_partial_cells_and_area_marginals(self):
        a=axis_from_marginal(20,30,[0,1])
        self.assertEqual(a.source,(0,16,20))
        np.testing.assert_allclose(a.destination,(0,20,30))
        g=from_saliency([[0,0],[1,1]],20,20,20,20)
        # Last row has four pixels; marginal is one fifth, not one half.
        expected=axis_from_marginal(20,20,[0,1])
        self.assertEqual(g.y,expected)
        np.testing.assert_allclose(g.x.destination,(0,16,20))

    def test_empty_roi_and_full_saliency_are_uniform(self):
        for saliency in (None,np.zeros((2,3)),np.ones((2,3))):
            g=from_saliency(saliency,33,17,66,34).quantize()
            np.testing.assert_array_equal(g.x.destination,np.array(boundaries(33))*2)
            np.testing.assert_array_equal(g.y.destination,np.array(boundaries(17))*2)

    def test_quantization_error_bound(self):
        g=from_saliency([[.13,.77,.98]],33,8,17,4)
        q=g.quantize()
        self.assertLessEqual(max(abs(np.array(g.x.destination)-q.x.destination)),.5/SCALE)

    def test_invalid_maps_fail(self):
        for src,dst in [((0,16,32),(0,2,2)),((0,16,32),(0,2,1)),((0,17,32),(0,1,2)),((0,16),(0,float('nan')))]:
            with self.subTest(src=src,dst=dst),self.assertRaises(ValueError):
                AxisMap(src,dst)

    def test_quantization_collapse_rejected(self):
        from prism_v2.retarget.geometry import Geometry
        with self.assertRaises(ValueError):
            Geometry(AxisMap((0,16,32),(0,.000001,1)),AxisMap((0,16),(0,1))).quantize()
        with self.assertRaises(ValueError):
            QuantizedMap(32,16,1,1,(0,0,SCALE),(0,SCALE))

    def test_invalid_saliency_and_outside_coordinates(self):
        for value in ([[float('nan')]], [[-1]], [[1.1]], [[0,1]]):
            with self.assertRaises(ValueError):
                from_saliency(value,16,16,16,16)
        a=axis_from_marginal(16,16,[0])
        for p in (-1,17,float('inf')):
            with self.assertRaises(ValueError):
                a.forward(p)

    def test_max_dimensions_and_smallest_partial_interval_survive_quantization(self):
        for width,output in ((65521,1),(65535,65535)):
            r=np.ones((1,len(boundaries(width))-1));r[0,-1]=0
            g=from_saliency(r,width,1,output,1).quantize()
            self.assertTrue(all(b>a for a,b in zip(g.x_ticks,g.x_ticks[1:])))
            self.assertEqual(g.x_ticks[-1],output*SCALE)
            if output==1:
                # The one-pixel edge is only just over half a tick before rounding.
                self.assertEqual(g.x_ticks[-1]-g.x_ticks[-2],1)

    def test_asymmetric_partial_area_marginals_follow_a3(self):
        # A single salient corner occupies four by two valid pixels.
        g=from_saliency([[0,0],[0,1]],20,18,20,18)
        self.assertEqual(g.x,axis_from_marginal(20,20,[0,2/18]))
        self.assertEqual(g.y,axis_from_marginal(18,18,[0,4/20]))


class QGTests(unittest.TestCase):
    def test_v1_bilinear_half_pixel_centers(self):
        result=expand_ctu64(np.array([[[[0.,8.]]]],np.float32),128,64)
        np.testing.assert_array_equal(result[0,0,0],[0,0,1,3,5,7,8,8])
        self.assertEqual(result.shape,(1,1,4,8))
        np.testing.assert_array_equal(result[0,0,0],result[0,0,-1])

    def test_partial_ctu_shape_and_bound_preservation(self):
        values=np.random.default_rng(1).uniform(-6,6,(2,1,2,2)).astype(np.float32)
        result=expand_ctu64(values,65,69)
        self.assertEqual(result.shape,(2,1,8,8))
        self.assertLessEqual(abs(result).max(),6)

    def test_warp_identity_partial_area_and_padding(self):
        g=from_saliency(None,18,20,18,20).quantize()
        source=np.array([[-6,6],[3,0]])
        result=warp_qg(source,g,32,32)
        np.testing.assert_array_equal(result[:2,:2],source)
        self.assertEqual(result.shape,(4,4))
        np.testing.assert_array_equal(result[2:],result[[1,1]])

    def test_warp_uses_destination_area(self):
        g=from_saliency([[0,1]],32,16,16,16).quantize()
        result=warp_qg([[-6,6]],g,16,16)
        edge=g.x.destination[1]
        self.assertAlmostEqual(float(result[0,0]),(-6*edge+6*(16-edge))/16,places=6)
        self.assertLessEqual(abs(result).max(),6)

    def test_warp_rejects_float_map_and_out_of_bound_offsets(self):
        g=from_saliency(None,16,16,16,16)
        with self.assertRaises(ValueError):
            warp_qg([[0]],g,16,16)
        with self.assertRaises(ValueError):
            warp_qg([[7]],g.quantize(),16,16)

    def test_warp_coded_dimensions_follow_signal_domain(self):
        g=from_saliency(None,16,16,16,16).quantize()
        for width,height in ((16.0,16),(16,16.0),(65536,16),(16,65536),(0,16)):
            with self.subTest(width=width,height=height),self.assertRaises(ValueError):
                warp_qg([[0]],g,width,height)

    def test_identity_retains_full_v1_buffer_with_partial_ctus(self):
        ctu=np.array([[[[-6.,6.],[2.,-3.]]]],dtype=np.float32)
        source=expand_ctu64(ctu,65,69)[0,0]
        g=from_saliency(None,65,69,65,69).quantize()
        np.testing.assert_array_equal(warp_qg(source,g,80,80),source)
        # The inherited padding contains further bilinear samples, not repeated visible cells.
        self.assertNotEqual(source[0,4],source[0,5])

    def test_padding_extends_boundary_field_before_area_reduction(self):
        g=from_saliency(None,32,32,20,20).quantize()
        source=np.array([[-6.,2.],[4.,6.]])
        # Source boundaries map to 0, 10, 20. The first output cell mixes
        # 10 and 6 pixels; cells beyond it see the terminal source value.
        weights=np.array([[10/16,6/16],[0,1],[0,1],[0,1]])
        expected=weights@source@weights.T
        np.testing.assert_allclose(warp_qg(source,g,32,32),expected,atol=1e-7)

    def test_partial_destination_cell_includes_extended_pixels(self):
        g=from_saliency(None,32,16,10,16).quantize()
        # Five pixels of -6 and eleven pixels of +6 fill the coded QG.
        result=warp_qg([[-6,6]],g,16,16)
        self.assertEqual(float(result[0,0]),2.25)
        np.testing.assert_array_equal(result[:,1:],6)
