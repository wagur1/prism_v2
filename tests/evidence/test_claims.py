import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from prism_v2.evidence.ledger import validate_record,load_ledger
from prism_v2.evidence.claims import check_markdown


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'artifact').write_bytes(b'synthetic evidence, not a scientific result')
        self.artifact={'path':'artifact','sha256':hashlib.sha256((self.root/'artifact').read_bytes()).hexdigest()}
        self.design={'id':'test-design','type':'design-constant','statement':'Synthetic threshold','value':6,'unit':'QP','authority':self.artifact}

    def test_all_typed_records(self):
        records=[self.design,{'id':'lit','type':'literature','statement':'Quote','source':self.artifact,'citation':'Synthetic citation','context':'Test','verification_status':'NEEDS VERIFY'},
            {'id':'old','type':'rejected-historical','statement':'Old claim','source':self.artifact,'reason':'Not supported'},
            {'id':'est','type':'derived-estimate','statement':'Estimate','formula':'a * 2','inputs':{'a':{'value':3,'unit':'h','source':self.artifact}},'assumptions':['Linear'],'verification_status':'NEEDS VERIFY'},
            {'id':'meas','type':'measured','statement':'Synthetic test','metric':'test','value':1.,'unit':'unit','detector':'synthetic','weights':self.artifact,
             'split_manifest':self.artifact,'seeds':[1,2,3],'crfs':[20,24],'checkpoint':self.artifact,'commit':'a'*40,
             'build':self.artifact,'patch':self.artifact,'analysis_configuration':self.artifact,
             'uncertainty':{'method':'synthetic','lower':0,'upper':2,'level':.95},'validity':{'status':'valid','reason':'synthetic'},'result':self.artifact,'harvest':self.artifact}]
        for record in records:
            self.assertEqual(validate_record(record,self.root),record)
        measured=records[-1].copy();measured.pop('harvest')
        with self.assertRaises(ValueError):validate_record(measured,self.root)
        measured=records[-1].copy();measured['commit']='316134d2'
        with self.assertRaises(ValueError):validate_record(measured,self.root)

    def test_artifact_hash_and_ledger_duplicate_rejected(self):
        bad=copy.deepcopy(self.design);bad['authority']['sha256']='0'*64
        with self.assertRaises(ValueError):validate_record(bad,self.root)
        ledger=self.root/'ledger.jsonl';ledger.write_text((json.dumps(self.design)+'\n')*2)
        with self.assertRaises(ValueError):load_ledger(ledger,self.root)

    def test_synthetic_markdown_tripwire_and_citation(self):
        path=self.root/'synthetic.md'
        path.write_text('Saving is 3.5%.\nThreshold is 6 QP. [claim:test-design]\nValue 7 [claim:missing]\n```\nx=20\n```\n')
        problems=check_markdown(path,{'test-design':self.design})
        self.assertEqual(len(problems),2)
        self.assertTrue(any('quantitative prose' in p for p in problems))
        self.assertTrue(any('unknown claim' in p for p in problems))
        self.assertTrue(check_markdown(path,{'test-design':self.design},readme=True))

    def test_cli_exit_code_for_synthetic_md(self):
        ledger=self.root/'ledger.jsonl';ledger.write_text('')
        md=self.root/'tripwire.md';md.write_text('An unsupported gain of 17%.\n')
        script=Path(__file__).resolve().parents[2]/'scripts/check_claims.py'
        run=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--ledger',str(ledger),str(md)],capture_output=True,text=True)
        self.assertEqual(run.returncode,1)
        self.assertIn('quantitative prose',run.stdout)

    def test_compact_quantities_and_numeric_code_spans_are_flagged(self):
        path=self.root/'quantities.md'
        for text in ('Speedup is 3x.','Budget is 60GPU-h.','Rate is 30fps.',
                     'Memory is 12MiB.','Resolution is 256x256.',
                     'Saving is `3.5%`.','Gain is `0.5`.'):
            with self.subTest(text=text):
                path.write_text(text,encoding='utf-8')
                self.assertTrue(any('quantitative prose' in p for p in check_markdown(path,{})))

    def test_citations_in_code_comments_or_link_targets_do_not_support_prose(self):
        path=self.root/'hidden-citation.md'
        for citation in ('`[claim:test-design]`','<!-- [claim:test-design] -->',
                         '[reference](https://example.invalid/[claim:test-design])'):
            with self.subTest(citation=citation):
                path.write_text('Saving is 3%. '+citation,encoding='utf-8')
                self.assertTrue(any('quantitative prose' in p for p in check_markdown(path,{'test-design':self.design})))

    def test_fence_delimiter_length_and_inline_backticks(self):
        path=self.root/'fences.md'
        for text in ('```\ncode\n````\nSaving is 3%.\n',
                     '```literal```\nSaving is 3%.\n'):
            path.write_text(text,encoding='utf-8')
            self.assertTrue(any('quantitative prose' in p for p in check_markdown(path,{})))
        path.write_text('````\n```\nSaving is 3%.\n````\n',encoding='utf-8')
        self.assertEqual(check_markdown(path,{}),[])

    def test_comment_examples_in_code_do_not_hide_following_prose(self):
        path=self.root/'comments.md'
        for text in ('```\n<!--\n```\nSaving is 3%.\n',
                     'The token `<!--` starts a comment.\nSaving is 3%.\n',
                     '<!--\n```\n-->\nSaving is 3%.\n'):
            path.write_text(text,encoding='utf-8')
            self.assertTrue(any('quantitative prose' in p for p in check_markdown(path,{})))

    def test_cli_scans_nested_reports_and_resolves_paths_under_root(self):
        (self.root/'evidence').mkdir();(self.root/'evidence/ledger.jsonl').write_text('')
        (self.root/'README.md').write_text('Scope and status only.\n')
        nested=self.root/'reports/nested';nested.mkdir(parents=True)
        (nested/'result.md').write_text('Unsupported saving is 3%.\n')
        script=Path(__file__).resolve().parents[2]/'scripts/check_claims.py'
        for paths in ([],['reports/nested/result.md']):
            run=subprocess.run([sys.executable,str(script),'--root',str(self.root),*paths],capture_output=True,text=True)
            self.assertEqual(run.returncode,1)
            self.assertIn('quantitative prose',run.stdout)
