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
