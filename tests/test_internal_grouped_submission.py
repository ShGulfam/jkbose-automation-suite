import copy,json,unittest
from unittest.mock import Mock,patch
import test_internal_batch as fixtures
import test_internal_saved_report as oldtests
from jkbose_tool.features import internal_assessment_saved_report as saved
from jkbose_tool.features import internal_assessment_batch as batch
from jkbose_tool.features.internal_assessment import Audit,match_batch
class GroupedSubmissionTests(unittest.TestCase):
 setUp=fixtures.ClassRunTests.setUp
 write_book=fixtures.ClassRunTests.write_book
 plan=fixtures.ClassRunTests.plan
 state=fixtures.ClassRunTests.state
 sign=oldtests.SavedReportTests.sign
 def report(self,status='Requested'):
  p=self.plan('Mathematics');return self.sign(dict(account='school-test',student_class='11',workbook_session='2025-26',report_session='2026-2027',url=saved.URL,coverage_complete=True,total=1,pages=3,receipt_detail='status_only_grouped',status_filters=['Requested','Approved','Rejected'],records=[dict(regno='REG1',exam_roll='301000001',name=p.awards[0].name,subject='Mathematics',marks=None,maximum=None,attendance=None,status=status,rejection_reason='',detail='status_only')]))
 def test_grouped_page_expands_awards_without_inventing_marks(self):
  driver=Mock(current_url=saved.URL);driver.find_element.return_value.get_attribute.return_value='2026-2027'
  page=dict(account='school-test',**{'class':'11'},status='Requested',session='2026-2027',page_label='Page 1 of 1 (1 records)',headers=saved.GROUPED_HEADERS,next_disabled=True,rows=[['1','11','REG1','301000001','Synthetic One','Mathematics: Requested, Physics: Rejected']])
  driver.execute_script.side_effect=lambda script:page if script==saved.SNAPSHOT else 'complete'
  with patch.object(saved,'Select'),patch.object(saved,'begin_read'),patch.object(saved,'wait_read'):r=saved._read_saved_report_status(driver,'11','school-test','2025-26',status='Requested')
  self.assertEqual(r['total'],2);self.assertEqual(r['student_rows'],1);self.assertEqual(r['receipt_detail'],'status_only_grouped');self.assertIsNone(r['records'][0]['marks']);self.assertEqual(r['records'][1]['status'],'Rejected')
 def test_recorded_award_skips_without_claiming_exact_numeric_verification(self):
  p=self.plan('Mathematics');r=self.report();saved.recognise_saved_awards(self.history,[p],'school-test',r,self.root/'official.json');self.assertEqual(batch.verified_history(self.history,p,'school-test')['verified'],{'REG1'});audit=Audit(self.history,p);self.assertFalse(audit.verified());self.assertEqual(audit.events[-1]['kind'],'official_recorded_award');self.assertIn('unverified',audit.events[-1]['verification'])
 def test_status_receipt_confirms_final_batch_but_rejected_cannot(self):
  p=self.plan('Mathematics');self.assertEqual(saved.verify_saved_batch(p,p.awards,'school-test',self.report()),{'REG1':'Requested'})
  with self.assertRaises(ValueError):saved.verify_saved_batch(p,p.awards,'school-test',self.report('Rejected'))
 def test_wrong_name_or_pair_never_skips_or_confirms(self):
  for key,value in [('name','Different Person'),('regno','REG9'),('exam_roll','301000009')]:
   r=self.report();r['records'][0][key]=value;self.sign(r);p=self.plan('Mathematics')
   with self.subTest(key=key),self.assertRaises(ValueError):saved.verify_saved_batch(p,p.awards,'school-test',r)
 def test_exact_rejected_status_allows_current_source_to_replace_pending_old_marks(self):
  p=self.plan('Mathematics');r=self.report('Rejected');saved.recognise_saved_awards(self.history,[p],'school-test',r,self.root/'official.json');d=self.state(p);d['rows'][0]['value']='15';self.assertFalse(match_batch(p,d,allow_absent=True)[1]);p.rejected_receipts={};self.assertTrue(match_batch(p,d,allow_absent=True)[1])
 def test_grouped_subject_syntax_and_filter_membership_are_strict(self):
  driver=Mock(current_url=saved.URL);driver.find_element.return_value.get_attribute.return_value='2026-2027'
  for text in ['Mathematics Requested','Mathematics: Unknown','Mathematics: Requested, Mathematics: Requested','Mathematics: Approved']:
   page=dict(account='school-test',**{'class':'11'},status='Requested',session='2026-2027',page_label='Page 1 of 1 (1 records)',headers=saved.GROUPED_HEADERS,next_disabled=True,rows=[['1','11','REG1','301000001','Synthetic One',text]])
   driver.execute_script.side_effect=lambda script:page if script==saved.SNAPSHOT else 'complete'
   with self.subTest(text=text),patch.object(saved,'Select'),patch.object(saved,'begin_read'),patch.object(saved,'wait_read'),self.assertRaises(ValueError):saved._read_saved_report_status(driver,'11','school-test','2025-26',status='Requested')
 def test_empty_requested_filter_preserves_approved_grouped_receipt_detail(self):
  empty=self.report();empty['records']=[];empty['total']=0;empty['receipt_detail']='detailed';self.sign(empty)
  approved=self.report('Approved')
  with patch.object(saved,'_read_saved_report_status',side_effect=[empty,approved,empty]):r=saved.read_saved_report(Mock(),'11','school-test','2025-26')
  self.assertEqual(r['receipt_detail'],'status_only_grouped');p=self.plan('Mathematics');self.assertEqual(saved.verify_saved_batch(p,p.awards,'school-test',r),{'REG1':'Approved'})
 def test_exact_duplicate_grouped_status_across_filters_is_deduplicated(self):
  a=self.report();b=copy.deepcopy(a);c=self.report();c['records']=[];c['total']=0;self.sign(c)
  with patch.object(saved,'_read_saved_report_status',side_effect=[a,b,c]):r=saved.read_saved_report(Mock(),'11','school-test','2025-26')
  self.assertEqual(r['total'],1)
if __name__=='__main__':unittest.main()
