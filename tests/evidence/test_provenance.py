import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class ProvenanceTests(unittest.TestCase):
    def test_ported_file_hashes_and_headers(self):
        manifest=json.loads((ROOT/'evidence/manifests/port_sources.json').read_text())
        self.assertTrue(manifest['v1_commit'].startswith('a34d943'))
        for entry in manifest['entries']:
            raw=(ROOT/entry['destination']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['destination_sha256'],entry['destination'])
            header=raw.decode('utf-8')[:500]
            self.assertIn('C:/Users/Wagur1/prism-vcm/',header)
            self.assertIn('a34d943',header)
            self.assertIn('2026-11-04',header)

    def test_synthetic_fixture_hashes(self):
        manifest=json.loads((ROOT/'evidence/manifests/synthetic_fixtures.json').read_text())
        self.assertEqual(manifest['status'],'SYNTHETIC_ONLY')
        for entry in manifest['artifacts']:
            self.assertEqual(hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest(),entry['sha256'])

    def test_patch_pins_match_the_files(self):
        pin=json.loads((ROOT/'third_party/x265/PINNED_SOURCE.json').read_text())
        self.assertTrue(pin['enable_assembly'])
        for name,expected in pin['patches'].items():
            self.assertEqual(hashlib.sha256((ROOT/'third_party/x265/patches'/name).read_bytes()).hexdigest(),expected)
