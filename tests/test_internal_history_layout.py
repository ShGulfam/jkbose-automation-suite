"""Migration and presentation must preserve receipts, locks and manual-only holds."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_internal_batch as fixtures
from jkbose_tool.features import internal_assessment as model
from jkbose_tool.features import internal_assessment_batch as batch
from jkbose_tool.features import internal_assessment_browser as browser
from jkbose_tool.features.internal_assessment_history import (
    prepare_layout, publish_history, resolve_reference, manifest_paths, storage_root,
)
from jkbose_tool.features.internal_assessment_policy import CohortAbsencePolicy


class HistoryLayoutTests(unittest.TestCase):
    setUp = fixtures.ClassRunTests.setUp
    write_book = fixtures.ClassRunTests.write_book
    plan = fixtures.ClassRunTests.plan

    def test_moves_intact_and_saved_receipts_still_skip(self):
        plan = self.plan()
        audit = model.Audit(self.history, plan)
        audit.append('run_started', school_account='school-test', source_preview=plan.rows())
        audit.append('submit_attempt', batch_id='saved', registrations=['REG1'])
        audit.append('verified_saved', batch_id='saved', registrations=['REG1'])
        old = audit.folder
        before = {path.name: path.read_bytes() for path in old.iterdir()}
        storage = model.prepare_history_root(self.history)
        self.assertEqual(storage, self.history / 'References')
        moved = storage / old.name
        self.assertEqual(before, {path.name: path.read_bytes() for path in moved.iterdir()})
        self.assertFalse(old.exists())
        self.assertEqual(resolve_reference(old / 'events.jsonl', storage), moved / 'events.jsonl')
        self.assertEqual(batch.verified_history(self.history, plan, 'school-test')['verified'], {'REG1'})
        self.assertEqual(model.Audit.existing(moved)[0].verified(), {'REG1'})
        self.assertEqual(storage, model.prepare_history_root(storage))

    def test_uncertain_saved_attempt_still_blocks_after_moving(self):
        plan = self.plan()
        audit = model.Audit(self.history, plan)
        audit.append('run_started', school_account='school-test', source_preview=plan.rows())
        audit.append('submit_attempt', batch_id='unknown', registrations=['REG1'])
        model.prepare_history_root(self.history)
        with self.assertRaisesRegex(ValueError, 'uncertain'):
            browser._pending_history(self.history, plan, 'school-test')

    def test_absence_hold_survives_migration(self):
        holds = CohortAbsencePolicy(self.history, 'school-test', '11', '2025-26')
        holds.add([{'registration':'REG1', 'exam_roll':'301000001', 'subject':'Physics'}], origin='test', evidence='synthetic')
        storage = model.prepare_history_root(self.history)
        recovered = CohortAbsencePolicy(storage, 'school-test', '11', '2025-26')
        self.assertEqual(recovered.holds, holds.holds)

    def test_lock_and_collision_prevent_any_moves(self):
        self.history.mkdir()
        first = self.history / 'first'; first.mkdir(); (first / 'journal').write_text('intact')
        lock = self.history / 'internal-assessment.lock'; lock.write_text('active')
        with self.assertRaisesRegex(ValueError, 'locked'):
            prepare_layout(self.history)
        self.assertTrue(first.exists())
        lock.unlink()
        (self.history / 'References' / 'first').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'collision'):
            prepare_layout(self.history)
        self.assertEqual((first / 'journal').read_text(), 'intact')
        self.assertFalse(lock.exists())

    def test_lock_uses_same_path_from_public_and_reference_roots(self):
        storage = model.prepare_history_root(self.history)
        with model.RunLock(self.history):
            with self.assertRaises(ValueError):
                with model.RunLock(storage):
                    self.fail('concurrent run')
            with self.assertRaises(ValueError):
                prepare_layout(self.history)

    def test_partial_migration_cannot_hide_uncertain_legacy_history(self):
        storage = model.prepare_history_root(self.history)
        legacy = self.history / ('f' * 24); legacy.mkdir()
        (legacy / 'manifest.json').write_text('{}')
        self.assertIn(legacy / 'manifest.json', manifest_paths(storage))
        duplicate = storage / legacy.name; duplicate.mkdir()
        (duplicate / 'manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            manifest_paths(self.history)

    def synthetic_report(self, storage, run, *, session='2025-26', failed=False, corrupt=False):
        folder = storage / '_class_runs' / run; folder.mkdir(parents=True)
        original = self.history / '_class_runs' / run
        exports = {}
        for kind, suffix in [('excel','xlsx'),('pdf','pdf')]:
            source = folder / ('matching.' + suffix)
            source.write_bytes((run + kind).encode())
            exports[kind] = str(original / source.name)  # Pre-migration absolute paths.
            exports[kind + '_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        report = {'manifest': {'class':'11', 'session':session, 'school_account':'school-test', 'mode':'read_only'},
                  'status': 'failed' if failed else 'finished_with_manual_review',
                  'matching_exports': {}, 'student_report_matching': {} if failed else
                  {'status':'roster_review_required', 'report_session':'2026-2027', 'exports':exports}}
        (folder / 'report.json').write_text(json.dumps(report))
        if corrupt:
            (folder / 'matching.pdf').write_bytes(b'changed')
        return folder, report

    def test_latest_reports_are_named_verified_copies_and_failed_run_is_visible(self):
        storage = model.prepare_history_root(self.history)
        folder, report = self.synthetic_report(storage, '20260101-old')
        self.synthetic_report(storage, '20260102-failed', failed=True)
        before = (folder / 'report.json').read_bytes()
        index = publish_history(storage)
        content = index.read_text()
        self.assertIn('Earlier enrolment report', content)
        self.assertIn('failed', content)
        for kind, suffix in [('excel','xlsx'),('pdf','pdf')]:
            target = self.history / ('Class 11 - school-test - 2025-26 - Student Matching.' + suffix)
            self.assertEqual(target.read_bytes(), (folder / ('matching.' + suffix)).read_bytes())
        self.assertEqual((folder / 'report.json').read_bytes(), before)
        self.assertEqual(len(list(self.history.iterdir())), 4)

    def test_corrupt_export_is_not_published(self):
        storage = model.prepare_history_root(self.history)
        self.synthetic_report(storage, '20260101-old', corrupt=True)
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            publish_history(storage)
        self.assertFalse(list(self.history.glob('*.xlsx')))

    def test_old_visible_session_copies_are_archived_and_user_files_retained(self):
        storage = model.prepare_history_root(self.history)
        self.synthetic_report(storage, '20260101-old')
        publish_history(storage)
        self.synthetic_report(storage, '20270101-new', session='2026-27')
        publish_history(storage)
        self.assertFalse((self.history / 'Class 11 - school-test - 2025-26 - Student Matching.pdf').exists())
        self.assertEqual(len(list((storage / '_published_previous').iterdir())), 2)
        self.assertTrue((self.history / 'Class 11 - school-test - 2026-27 - Student Matching.pdf').exists())

    def test_changed_saved_award_remains_blocked_after_moving(self):
        plan = self.plan()
        audit = model.Audit(self.history, plan)
        audit.append('run_started', school_account='school-test', source_preview=plan.rows())
        audit.append('submit_attempt', batch_id='saved', registrations=['REG1'])
        audit.append('verified_saved', batch_id='saved', registrations=['REG1'])
        model.prepare_history_root(self.history)
        self.write_book(physics=9)
        with self.assertRaisesRegex(ValueError, 'changed'):
            batch.verified_history(self.history, self.plan(), 'school-test')


if __name__ == '__main__':
    unittest.main()
