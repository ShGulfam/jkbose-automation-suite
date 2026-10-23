"""Private local exam evidence, with technical files under References."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
from uuid import uuid4
from openpyxl import Workbook

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / 'history' / 'exam_forms'

class ExamRunHistory:
    def __init__(self, mode, source=None, rows=None, root=None):
        self.root = Path(root or DEFAULT_ROOT)
        self.mode = mode
        self.run_id = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S') + '_' + uuid4().hex[:8]
        self.reference = self.root / 'References' / self.run_id
        self.reference.mkdir(parents=True, exist_ok=False)
        self.rows = rows or {}
        self.account = ''
        self.events = []
        self.source_sha = ''
        self.source = str(source or '')
        if source:
            path = Path(source)
            self.source_sha = sha256(path.read_bytes()).hexdigest()
            shutil.copy2(path, self.reference / ('Original_Input' + path.suffix))
        self.record('run_started', source=str(source or ''), source_sha256=self.source_sha)

    def bind_account(self, driver):
        from selenium.webdriver.common.by import By
        match = re.search(r'Hello\s+([a-z0-9_-]+)', driver.find_element(By.TAG_NAME, 'body').text, re.I)
        if not match:
            raise ValueError('School account could not be verified. Stop and sign in again.')
        if self.account and self.account != match.group(1).lower():
            raise ValueError('The signed-in school account changed. Stop and review the run.')
        if self.account:
            return
        self.account = match.group(1).lower()
        self.record('school_verified')

    def record(self, kind, **data):
        event = dict(time=datetime.now(timezone.utc).isoformat(), run=self.run_id,
                     mode=self.mode, school_account=self.account, kind=kind, **data)
        with (self.reference / 'Events.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')
            file.flush()
            os.fsync(file.fileno())
        self.events.append(event)

    def progress(self, index, status, notes=''):
        row = self.rows.get(index, {})
        self.record('student_result', excel_row=int(index) + 2,
                    registration=row.get('RegNo', ''), exam_roll=row.get('ExamRollNo', ''),
                    class_name=row.get('Class', ''), session=row.get('Session', ''),
                    form=row.get('FormNo', ''), status=status, notes=notes)
        self.report()

    def report(self):
        book = Workbook()
        sheet = book.active
        sheet.title = 'Run History'
        columns = ['time', 'run', 'mode', 'school_account', 'kind', 'excel_row', 'class_name', 'session', 'registration', 'exam_roll', 'form', 'status', 'notes', 'file']
        sheet.append(columns)
        for event in self.events:
            sheet.append([str(event.get(key, '')) for key in columns])
        for row in sheet:
            for cell in row:
                cell.data_type = 's'
                cell.number_format = '@'
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        info = book.create_sheet('Run Info')
        for label, value in [('Run', self.run_id), ('School account', self.account), ('Original source', self.source), ('Original SHA256', self.source_sha), ('References', str(self.reference)), ('Submission evidence', 'Only explicit verified responses count as submitted. Stopped/blocked/check events do not prove submission.')]:
            info.append([label, value])
        info.column_dimensions['A'].width = 28
        info.column_dimensions['B'].width = 90
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 25
        for target in [self.reference / 'Run_Report.xlsx', self.root / f'Latest_{self.mode}.xlsx']:
            temporary = target.with_suffix('.tmp.xlsx')
            book.save(temporary)
            os.replace(temporary, target)
        book.close()

    def finish(self, status, notes=''):
        self.record('run_finished', status=status, notes=notes)
        self.report()
        print(f'[HISTORY] {self.root / ("Latest_" + self.mode + ".xlsx")}')
