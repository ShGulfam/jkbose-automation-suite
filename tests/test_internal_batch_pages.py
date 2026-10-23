"""Synthetic Class 12 Mathematics 10+5 submission through the real adapter loop."""
import copy,json,hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from openpyxl import Workbook
from jkbose_tool.features import internal_assessment_batch as batch
from jkbose_tool.features import internal_assessment_browser as browser
from jkbose_tool.features.internal_assessment_policy import CohortAbsencePolicy

class DisplayedBatchTests(unittest.TestCase):
    def run_case(self,late_absence=False,confirm=True,verify_final=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'synthetic.xlsx';history=root/'history'
            book=Workbook();ws=book.active;ws.title='JKBOSE_Internal_Assessment'
            ws.append(['Class','Session','Evaluation Type','Subject Code','Subject Name','Board Reg. No.','Exam Roll No.','Class Roll No.','Student Name','Marks','Max Marks','Attendance','Source Issues','Export Schema','Source Award ID'])
            for i in range(1,16):ws.append(['12th','2025-26','Internal Assessment','MA','Mathematics',f'REG{i}',str(301000000+i),str(i),f'Synthetic {i}',12,20,'Present','','hss-jkbose-ia-v1','synthetic'])
            book.save(source);book.close()
            jobs=batch.load_jobs(source,student_class='12',session='2025-26',subjects=['Mathematics'])
            plan=jobs[0]['plan'];pending=[]
            for i,a in enumerate(plan.awards):pending.append(dict(regno=a.regno,exam_roll=a.exam_roll,name=a.name,subject='Mathematics',attendance='A' if late_absence and i==14 else 'P',max='20',min='0',step='any',value='',input_id=a.regno,disabled=False,readonly=False))
            driver=Mock();saves=[];driver.find_elements.return_value=[]
            driver.switch_to=Mock()
            type(driver.switch_to).alert=property(lambda _:(_ for _ in ()).throw(browser.NoAlertPresentException()))
            def state(*a,**k):return dict(total=len(pending),rows=copy.deepcopy(pending[:10]),maximum='20',hidden_maximum='20')
            def save():saves.append([r['regno'] for r in pending[:10]]);del pending[:10]
            def element(by,key):
                if key=='bodypH_btnSaveMarks':return Mock(click=save)
                row=next(r for r in pending if r['input_id']==key)
                return Mock(get_attribute=lambda attr:row['value'],clear=lambda:row.update(value=''),send_keys=lambda value:row.update(value=value))
            driver.find_element.side_effect=element
            confirmation=Mock(return_value=confirm)
            def official(*args):
                remaining={r['regno'] for r in pending}
                records=[dict(regno=a.regno,exam_roll=a.exam_roll,name=a.name,subject=plan.subject,marks=a.marks,maximum=plan.maximum,attendance='P',status='Requested',rejection_reason='') for a in plan.awards if a.regno not in remaining]
                from jkbose_tool.features.internal_assessment_saved_report import URL
                data=dict(account='school-test',student_class='12',workbook_session='2025-26',report_session='2026-2027',url=URL,coverage_complete=True,total=len(records),pages=max(1,(len(records)+9)//10),records=records)
                data['sha256']=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest();return data
            with patch.object(browser,'open_subject'),patch.object(browser,'snapshot',side_effect=state),patch.object(browser,'_evidence',return_value='synthetic-evidence'),patch.object(browser,'show_students'),patch.object(browser,'_begin_read'),patch.object(browser,'_wait_page'):
                result=batch.run_jobs(jobs,source,history,'school-test',student_class='12',session='2025-26',execute=True,confirm_session=True,confirm_callback=confirmation,driver_factory=Mock(return_value=driver),login_callback=Mock(),verify_saved=verify_final,saved_report_reader=official)
            if not confirm:
                self.assertEqual(saves,[]);self.assertEqual(result['status'],'cancelled');self.assertEqual(confirmation.call_count,1)
            elif late_absence:
                self.assertEqual([len(rows) for rows in saves],[10]);self.assertEqual(result['subjects'][0]['status'],'manual_required')
                policy=CohortAbsencePolicy(history/'References','school-test','12','2025-26')
                self.assertTrue(any(h['registration']=='REG15' for h in policy.holds))
                self.assertEqual(result['new_verified_saved_count'],10)
            else:
                self.assertEqual([len(rows) for rows in saves],[10,5]);self.assertEqual(confirmation.call_count,2)
                self.assertEqual(result['new_verified_saved_count'],15)
                factory=Mock()
                resumed=batch.run_jobs(jobs,source,history,'school-test',student_class='12',session='2025-26',execute=True,confirm_session=True,confirm_callback=Mock(),driver_factory=factory)
                factory.assert_not_called();self.assertEqual(resumed['subjects'][0]['status'],'skipped_verified_history')
            self.assertFalse(result['safety_preflight'][0]['matching_summary']['coverage_complete'])
    def test_class_12_mathematics_saves_exactly_ten_then_five_and_resume_skips(self):self.run_case()
    def test_ten_then_five_uses_exact_official_receipts_on_final_batch(self):self.run_case(verify_final=True)
    def test_late_absence_is_persisted_and_blocks_its_batch_without_second_save(self):self.run_case(late_absence=True)
    def test_declined_first_confirmation_never_fills_or_saves(self):self.run_case(confirm=False)

if __name__=='__main__':unittest.main()

