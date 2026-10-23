import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from openpyxl import load_workbook
from jkbose_tool.features.exam_history import ExamRunHistory

class ExamHistoryTests(unittest.TestCase):
    def test_original_is_backed_up_and_results_are_durable_and_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input.txt'
            source.write_text('9900000000000007\n', encoding='utf-8')
            history = ExamRunHistory('Submit', source, {2: {'RegNo': '9900000000000007', 'Class': '11', 'Session': '2025-26', 'FormNo': '990007'}}, root / 'history')
            driver = Mock(); driver.find_element.return_value.text = 'Hello sch_synthetic'
            history.bind_account(driver)
            history.progress(2, 'Blocked - manual review', '=Not a receipt')
            history.finish('Stopped')
            events = [json.loads(line) for line in (history.reference / 'Events.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(events[-2]['excel_row'], 4)
            self.assertEqual(events[-2]['school_account'], 'sch_synthetic')
            self.assertEqual(source.read_bytes(), (history.reference / 'Original_Input.txt').read_bytes())
            book = load_workbook(root / 'history/Latest_Submit.xlsx')
            self.assertEqual(book.active['M4'].data_type, 's')
            book.close()
            self.assertEqual(sorted(path.name for path in (root / 'history').iterdir()), ['Latest_Submit.xlsx', 'References'])

    def test_account_must_be_visible_before_work(self):
        with tempfile.TemporaryDirectory() as folder:
            history = ExamRunHistory('Inspect', root=folder)
            driver = Mock(); driver.find_element.return_value.text = 'Please log in'
            with self.assertRaisesRegex(ValueError, 'School account'): history.bind_account(driver)
