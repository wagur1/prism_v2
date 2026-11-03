import struct
import unittest
from prism_v2.codec.sei import GeometrySignal, serialize, parse, nal_unit, extract, attach, UUID, HEADER
from prism_v2.retarget.geometry import from_saliency

AU=b'\x00\x00\x00\x01\x40\x01\x80\x00\x00\x01\x26\x01\x80'


class SEITests(unittest.TestCase):
    def signal(self):
        return GeometrySignal(from_saliency([[0,1],[1,0]],20,18,10,9).quantize(),20,18,16,16)

    def test_payload_and_annex_b_equality(self):
        signal=self.signal()
        self.assertEqual(parse(serialize(signal)),signal)
        self.assertEqual(extract(nal_unit(signal)),[signal])
        encoded=attach(AU,signal,arm='QR')
        self.assertEqual(extract(encoded),[signal])
        self.assertEqual(len(encoded),len(AU)+len(nal_unit(signal)))
        self.assertLess(encoded.index(nal_unit(signal)),encoded.index(b'\x26\x01'))

    def test_wire_golden_widths_and_network_byte_order(self):
        g=from_saliency(None,16,16,16,16).quantize()
        signal=GeometrySignal(g,16,16,16,16)
        expected=UUID+bytes.fromhex('01001000')+struct.pack('>12I2H',16,16,16,16,0,0,16,16,0,0,16,16,2,2)+bytes.fromhex('00000000001000000000000000100000')
        self.assertEqual(serialize(signal),expected)
        self.assertEqual(HEADER.size,56)

    def test_crop_resize_serialization(self):
        g=from_saliency(None,32,16,16,8).quantize()
        for signal in (GeometrySignal(g,32,16,16,16,kind='resize'),GeometrySignal(g,64,64,32,16,2,3,10,20,'crop')):
            self.assertEqual(extract(nal_unit(signal)),[signal])

    def test_stock_and_m2_unchanged_and_no_geometry(self):
        for arm in ('M1','M2'):
            self.assertEqual(attach(AU,None,arm=arm),AU)
            self.assertEqual(extract(AU),[])
            with self.assertRaises(ValueError):
                attach(AU,self.signal(),arm=arm)
        with self.assertRaises(ValueError):
            attach(AU,None,arm='R')
        with self.assertRaises(ValueError):
            attach(attach(AU,self.signal(),arm='R'),self.signal(),arm='R')

    def test_reject_truncated_unknown_version_and_non_monotone(self):
        wire=serialize(self.signal())
        for bad in (wire[:-1],wire+b'\0',wire[:16]+b'\x02'+wire[17:]):
            with self.assertRaises(ValueError):
                parse(bad)
        bad=bytearray(wire);bad[16+HEADER.size+4:16+HEADER.size+8]=b'\0'*4
        with self.assertRaises(ValueError):
            parse(bytes(bad))
        with self.assertRaises(ValueError):
            extract(nal_unit(self.signal())[:-1])

    def test_baseline_kinds_reject_nonuniform_knots_in_constructor_and_wire(self):
        g=from_saliency([[0,1]],32,16,16,8).quantize()
        for kind,code in (('resize',1),('crop',2)):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError,'uniform'):
                    GeometrySignal(g,32,16,16,16,kind=kind)
                wire=bytearray(serialize(GeometrySignal(g,32,16,16,16)))
                wire[17]=code
                with self.assertRaisesRegex(ValueError,'uniform'):
                    parse(bytes(wire))

    def test_asymmetric_crop_wire_fields_match_documented_order(self):
        signal=GeometrySignal(from_saliency(None,31,19,13,7).quantize(),101,83,32,16,5,3,23,29,'crop')
        wire=serialize(signal)
        # Independent offsets, distinct dimensions, no serialize/parse symmetry assumption.
        expected=(101,83,32,16,5,3,13,7,23,29,31,19)
        self.assertEqual(wire[16:20],bytes((1,2,16,0)))
        self.assertEqual(tuple(int.from_bytes(wire[i:i+4],'big') for i in range(20,68,4)),expected)
        self.assertEqual(parse(wire),signal)

    def test_missing_emulation_prevention_is_rejected(self):
        wire=nal_unit(self.signal())
        self.assertIn(b'\x00\x00\x03\x00',wire)
        malformed=wire.replace(b'\x00\x00\x03\x00',b'\x00\x00\x00',1)
        with self.assertRaisesRegex(ValueError,'emulation'):
            extract(malformed)

    def test_geometry_requires_declared_prefix_layer_and_temporal_header(self):
        wire=nal_unit(self.signal())
        for header in (b'\x50\x01',b'\x4e\x09',b'\x4e\x02'):
            with self.subTest(header=header),self.assertRaisesRegex(ValueError,'header'):
                extract(wire[:4]+header+wire[6:])

    def test_annex_b_trailing_zeros_are_not_part_of_ebsp(self):
        self.assertEqual(extract(nal_unit(self.signal())+b'\x00'*5),[self.signal()])
