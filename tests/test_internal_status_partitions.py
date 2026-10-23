import copy,hashlib,json,unittest
from unittest.mock import Mock,patch
from jkbose_tool.features import internal_assessment_saved_report as saved
class StatusPartitions(unittest.TestCase):
 def part(self,status,index):
  rows=[] if index==2 else [dict(regno='REG'+str(index),exam_roll='30100000'+str(index),name='Synthetic',subject='Mathematics',marks='12',maximum='20',attendance='P',status=status,rejection_reason='')]
  r=dict(account='school-test',student_class='11',workbook_session='2025-26',report_session='2026-2027',url=saved.URL,coverage_complete=True,total=len(rows),pages=1,records=rows);return self.sign(r)
 def sign(self,r):
  r.pop('sha256',None);r['sha256']=hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest();return r
 def test_all_three_statuses_are_required_and_all_filter_never_used(self):
  statuses=['Requested','Approved','Rejected'];parts=[self.part(x,i)for i,x in enumerate(statuses)]
  with patch.object(saved,'_read_saved_report_status',side_effect=parts)as read:r=saved.read_saved_report(Mock(),'11','school-test','2025-26')
  self.assertEqual([c.kwargs['status']for c in read.call_args_list],statuses);self.assertEqual(r['total'],2);self.assertEqual(r['pages'],3);self.assertTrue(r['coverage_complete']);self.assertEqual(r['status_filters'],statuses);saved._report_index(r,'school-test')
 def test_failed_partition_never_yields_partial_official_receipt(self):
  with patch.object(saved,'_read_saved_report_status',side_effect=[self.part('Requested',0),ValueError('server error')]):
   with self.assertRaisesRegex(ValueError,'server error'):saved.read_saved_report(Mock(),'11','school-test','2025-26')
 def test_wrong_filter_or_cohort_blocks_union(self):
  for kind in ['status','student_class','coverage_complete']:
   parts=[self.part(x,i)for i,x in enumerate(['Requested','Approved','Rejected'])]
   if kind=='status':parts[1]['records'][0]['status']='Requested'
   elif kind=='student_class':parts[1]['student_class']='12'
   else:parts[1]['coverage_complete']=False
   self.sign(parts[1])
   with self.subTest(kind=kind),patch.object(saved,'_read_saved_report_status',side_effect=parts),self.assertRaises(ValueError):saved.read_saved_report(Mock(),'11','school-test','2025-26')
 def test_duplicate_award_across_statuses_blocks_union(self):
  parts=[self.part(x,i)for i,x in enumerate(['Requested','Approved','Rejected'])];parts[1]['records'][0].update(regno='REG0',exam_roll='301000000');self.sign(parts[1])
  with patch.object(saved,'_read_saved_report_status',side_effect=parts),self.assertRaisesRegex(ValueError,'Duplicate'):saved.read_saved_report(Mock(),'11','school-test','2025-26')
if __name__=='__main__':unittest.main()
