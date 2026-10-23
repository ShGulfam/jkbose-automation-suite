import hashlib,json,unittest
import test_internal_batch as fixtures
from jkbose_tool.features.internal_assessment import Audit,prepare_history_root
from jkbose_tool.features.internal_assessment_reconciliation import build_reconciliation_references,resolve_manifest

class ReconciliationReferenceTests(unittest.TestCase):
    setUp=fixtures.ClassRunTests.setUp
    write_book=fixtures.ClassRunTests.write_book
    plan=fixtures.ClassRunTests.plan
    def uncertain(self):
        root=prepare_history_root(self.history);plan=self.plan()
        audit=Audit(root,plan)
        audit.append('run_started',source_preview=plan.rows())
        audit.append('submit_attempt',batch_id='synthetic',registrations=['REG1'])
        return root,audit
    def test_readable_reference_resolves_original_manifest_without_changing_evidence(self):
        root,audit=self.uncertain()
        original=audit.path.read_bytes()
        folder,files=build_reconciliation_references(root)
        self.assertEqual(folder,self.history/'Reconciliation');self.assertEqual(len(files),1)
        self.assertTrue(files[0].name.startswith('Class 11 - Physics - 2025-26 - Needs review'))
        self.assertEqual(resolve_manifest(files[0],root),audit.folder/'manifest.json')
        self.assertEqual(resolve_manifest(audit.folder/'manifest.json',root),audit.folder/'manifest.json')
        self.assertEqual(audit.path.read_bytes(),original)
        self.assertEqual(prepare_history_root(self.history),root)
        self.assertTrue(files[0].exists())
    def test_class_run_and_external_or_traversing_references_rejected(self):
        root,audit=self.uncertain();folder,files=build_reconciliation_references(root)
        for target in ('../outside/manifest.json',str(self.file.resolve()),'References/_class_runs/run/manifest.json'):
            data=json.loads(files[0].read_text());data['manifest']=target;files[0].write_text(json.dumps(data))
            with self.assertRaises((ValueError,FileNotFoundError)):resolve_manifest(files[0],root)
        with self.assertRaises(ValueError):resolve_manifest(self.file,root)
    def test_settled_run_not_listed_and_modified_journal_never_advertised(self):
        root,audit=self.uncertain()
        folder,previous=build_reconciliation_references(root)
        audit.append('verified_saved',batch_id='synthetic',registrations=['REG1'])
        self.assertEqual(build_reconciliation_references(root)[1],[])
        self.assertFalse(previous[0].exists())
        self.assertEqual(len(list((folder/'Completed').glob('*.json'))),1)
        audit.path.write_text(audit.path.read_text().replace('verified_saved','changed_event'))
        with self.assertRaisesRegex(ValueError,'modified'):build_reconciliation_references(root)
