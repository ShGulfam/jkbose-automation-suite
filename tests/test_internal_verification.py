"""Synthetic offline evidence only; never connects to a portal."""
import unittest,tempfile,json,threading
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
from jkbose_tool.features import internal_assessment_verification as v

ROLL='901000001';REG='990000000000001'
def award(code='EN',marks=16,mx=20,attendance='P',roll=ROLL,reg=REG):
    return v.record(roll,reg,'Example Student',code,marks,mx,attendance,'synthetic')
def card(subjects=None):return dict(roll=ROLL,reg=REG,name='Example Student',subjects=subjects or ['EN'])
def source(rows,label='Synthetic'):return dict(label=label,kind='synthetic',rows=rows)

class VerificationTests(unittest.TestCase):
    def test_alphanumeric_registration_is_preserved_in_every_pdf_layout(self):
        for reg in ['N99999999999','N999999999']:
            text=f'ADMIT CARD\n(Class 12th), Annual Regular 2026\nName Example Student Gender Female {ROLL}\nMother Name R.R No. {reg}\nCompulsory 1. General English 2. Physical Education\nAdditional\nVocational Candidate\'s Signature'
            cards=v.read_admits([text],'12','2025-26');self.assertEqual(cards[0]['reg'],reg)
            header='SL. EXAM ROLL REG. NO. STUDENT NAME EN PH CH BI ES PD MA UR ED HT PS EC HASH'
            matrix=v.read_matrix([header+f'\n1 {ROLL} {reg} Example Student 16 x x x x 15 x x x x x x 31'],'12')
            grouped=v.read_grouped([f'1 12 {reg} {ROLL} Example Student     General English: (16/20), Physical Education: (15/15)'],'12')
            flat=v.read_flat_pdf([f'100 12 {ROLL} {reg} Example Student General English P 16 20 01-Jan-26'],'12')
            self.assertEqual(flat[0]['reg'],reg)
            report=v.analyze(cards,[source(matrix,'School'),source(grouped,'Board')],'12','2025-26')
            self.assertEqual(report['error_count'],0);self.assertEqual(report['expected_awards'],2)

    def test_numeric_and_alphanumeric_identifiers_remain_distinct(self):
        cards=[dict(card(),reg='N999999999')]
        report=v.analyze(cards,[source([award(reg='999999999')])],'12','2025-26')
        self.assertTrue(report['error_count']);self.assertEqual(report['sources'][0]['missing'],1)

    def test_admit_identifiers_subjects_and_vocational(self):
        text=f'ADMIT CARD\n(Class 11th), Annual Regular 2026\nName Example Student   Gender Male  {ROLL}\nMother Name R.R No. {REG}\nCompulsory 1. General English 2. Biology\nAdditional 3. Physical Education\nVocational IT And ITES Candidate\'s Signature'
        cards=v.read_admits([text],'11','2025-26')
        self.assertEqual(cards[0]['subjects'],['EN','BI','PD']);self.assertEqual(cards[0]['reg'],REG)
        with self.assertRaises(ValueError):v.read_admits([text],'12','2025-26')
        with self.assertRaises(ValueError):v.read_admits([text],'11','2026-27')

    def test_matrix_touching_serial_roll_and_registration(self):
        header='SL EXAM ROLL REG NO NAME EN PH CH BI ES PD MA UR ED HT PS EC HASH'
        rows=v.read_matrix([header+f'\n1{ROLL}{REG}Example Student 16 x x x x 9 x x x x x x 25'],'11')
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['reg'],REG)
        with self.assertRaises(ValueError):v.read_matrix([header+f'\n2 {ROLL} {REG} Example Student 16 x x x x 9 x x x x x x 25'],'11')
        with self.assertRaises(ValueError):v.read_matrix([header+f'\n1 {ROLL} {REG} Example Student 16 x x x x 9 x x x x x x 26'],'11')

    def test_grouped_wrapping_and_flat_pdf(self):
        grouped=f'1 11 {REG} {ROLL} Example Student     General English: (16/20), Political\nScience: (19/20)'
        rows=v.read_grouped([grouped],'11');self.assertEqual([r['subject']for r in rows],['EN','PS'])
        flat=f'100 11 {ROLL} {REG} Example Student General English P 16 20 01-Jan-26'
        self.assertEqual(v.read_flat_pdf([flat],'11')[0]['marks'],'16')
        with self.assertRaises(ValueError):v.read_grouped([grouped],'12')

    def test_excel_formats_and_html(self):
        flat=[['ID','Class','Roll Number','Registration Number','Name','Subject','Present_Absent','Given_marks','Max. Marks'],[1,'11',ROLL,REG,'Example Student','General English','P',16,20]]
        self.assertEqual(v.read_table(flat,'11','2025-26','test')[0]['marks'],'16')
        grouped=[['Registration No.','Roll No.','Name','Subject-wise Marks / Status'],[REG,ROLL,'Example Student','General English: (16/20)']]
        self.assertEqual(v.read_table(grouped,'11','2025-26','test')[0]['reg'],REG)
        parser=v.HtmlRows();parser.feed('<table><tr><th>Name</th><td>A &amp; B</td></tr></table>');self.assertEqual(parser.rows,[['Name','A & B']])

    def test_biology_combines_once_and_rejects_unsafe_component(self):
        rows=v.combine_components([award('BO',4,5),award('ZO',5,5)])
        self.assertEqual((rows[0]['subject'],rows[0]['marks'],rows[0]['maximum']),('BI','9','10'))
        with self.assertRaises(ValueError):v.combine_components([award('BO',5,5)])
        with self.assertRaises(ValueError):v.combine_components([award('BO',6,5),award('ZO',4,5)])

    def test_exact_pairs_missing_extra_duplicates_names(self):
        wrong=award(reg=REG+'9');duplicate=award();duplicate['name']='Other Name'
        report=v.analyze([card()],[source([wrong,duplicate,duplicate])],'11','2025-26')
        kinds={i['kind']for i in report['issues']}
        self.assertTrue({'Conflicting identifier ownership','Duplicate award','Unexpected student/subject','Name differs (secondary check)'}<=kinds)
        missing=v.analyze([card(['EN','PH'])],[source([award()])],'11','2025-26')
        self.assertEqual(missing['sources'][0]['missing'],1)
        self.assertEqual(missing['expected_subjects']['PH'],1)

    def test_pass_threshold_and_physical_education_per_class(self):
        for cls,mx in [('11',10),('12',15)]:
            good=v.analyze([card(['PD'])],[source([award('PD',mx*.4,mx)])],cls,'2025-26')
            self.assertEqual(good['error_count'],0)
            bad=v.analyze([card(['PD'])],[source([award('PD',mx*.4-.1,mx)])],cls,'2025-26')
            self.assertEqual(bad['error_count'],1)
        self.assertEqual(v.analyze([card()],[source([award(attendance='A')])],'11','2025-26')['error_count'],1)
        self.assertIsNone(v.subject('IT And ITES'));self.assertIsNone(v.subject('Healthcare'))

    def test_optional_combinations_and_independent_source_counts(self):
        for count in [1,2,3]:
            sources=[source([award()],str(i))for i in range(count)]
            full=v.analyze([card()],sources,'11','2025-26');self.assertEqual(full['outcome'],'All supplied evidence matches')
            self.assertEqual(full['expected_awards'],1)
            limited=v.analyze([],sources,'11','2025-26');self.assertFalse(limited['completeness_checked']);self.assertIn('Limited',limited['outcome'])
        different=v.analyze([], [source([award()],'A'),source([award(marks=15)],'B')],'11','2025-26')
        self.assertEqual(different['issues'][0]['kind'],'Award values differ')

    def test_workbook_handoff_matrix_consistency(self):
        with tempfile.TemporaryDirectory()as root:
            path=Path(root)/'synthetic.xlsx';book=Workbook();ws=book.active;ws.title='JKBOSE_Internal_Assessment'
            ws.append(['BoardRegNo','ExamRollNo','StudentName','SubjectCode','Marks','MaxMarks','Attendance','Class','Session'])
            ws.append([REG,ROLL,'Example Student','EN',16,20,'Present','11','2025-26'])
            matrix=book.create_sheet('Awards_Matrix');matrix.append(['BoardRegNo','ExamRollNo','StudentName','English (EN)']);matrix.append([REG,ROLL,'Example Student',15]);book.save(path);book.close()
            ds=v.read_awards(path,'school','11','2025-26');r=v.analyze([card()],[ds],'11','2025-26')
            self.assertEqual(r['issues'][0]['kind'],'Workbook views differ')

    def test_verify_unreadable_and_partial_admit_never_passes(self):
        with tempfile.TemporaryDirectory()as root:
            a=Path(root)/'a.pdf';b=Path(root)/'b.pdf';s=Path(root)/'school.pdf'
            for p in[a,b,s]:p.write_bytes(b'synthetic fixture')
            with patch.object(v,'pdf_pages',return_value=['synthetic']),patch.object(v,'read_admits',side_effect=[[card()],ValueError('Unreadable card')]),patch.object(v,'read_awards',return_value=source([award()])):
                report=v.verify_files([a,b],[s],[],'11','2025-26')
            self.assertFalse(report['completeness_checked']);self.assertEqual(report['outcome'],'Needs review')
            with self.assertRaises(ValueError):v.verify_files([],[],[],'11','2025-26')
            stop=threading.Event();stop.set()
            with self.assertRaises(ValueError):v.verify_files([],[s],[],'11','2025-26',stop)

    def test_history_save_copy_integrity_and_source_protection(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory()as root:
            r=v.analyze([card()],[source([award()])],'11','2025-26');evidence=Path(root)/'source.pdf';evidence.write_bytes(b'original');r['inputs']=[{'path':str(evidence)}]
            folder=v.save_history(r,root);self.assertEqual(len(v.list_history(root)),1)
            self.assertEqual(v.load_history(folder,root)['expected_awards'],1)
            self.assertIn('Verification Report',PdfReader(Path(folder)/'Verification_Report.pdf').pages[0].extract_text())
            dest=Path(root)/'copy.pdf';v.save_report_copy(folder,dest,root);self.assertTrue(dest.exists())
            with self.assertRaises(ValueError):v.save_report_copy(folder,evidence,root)
            self.assertEqual(evidence.read_bytes(),b'original')
            with self.assertRaises(ValueError):v.load_history(Path(root),root)
            (Path(folder)/'analysis.json').write_text('{}')
            with self.assertRaises(ValueError):v.load_history(folder,root)

    def test_invalid_numeric_or_cohort_rejected(self):
        for mark in ['NaN','Infinity','not marks']:
            with self.assertRaises(ValueError):award(marks=mark)
        with self.assertRaises(ValueError):award(roll='1')
        with self.assertRaises(ValueError):v.session_end('2025-27')

    def test_other_classes_custom_subject_maxima_and_context_isolation(self):
        token=v.RULES.set(v.parse_rules('English=20; Science=10; Computing=25'))
        try:
            self.assertEqual(v.subject('Science'),'SC')
            self.assertEqual(v.subject('Computing'),'COMPUTING')
            r=v.analyze([card(['EN','SC','COMPUTING'])],[source([award('EN',8,20),award('SC',4,10),award('COMPUTING',10,25)])],'10','2025-26')
            self.assertEqual(r['error_count'],0);self.assertEqual(r['subject_maxima']['COMPUTING'],'25')
            with tempfile.TemporaryDirectory()as root:v.export_pdf(r,Path(root)/'custom.pdf')
        finally:v.RULES.reset(token)
        self.assertIsNone(v.maximum('EN','10'))
        with self.assertRaises(ValueError):v.subject('Computing')
        self.assertTrue(v.analyze([card()],[source([award()])],'10','2025-26')['error_count'])
        with self.assertRaises(ValueError):v.parse_rules('English=20; EN=30')
        with self.assertRaises(ValueError):v.parse_rules('Science=0')

    def test_verification_window_controls_fit_supported_small_size(self):
        import tkinter as tk
        from tkinter import ttk
        from types import SimpleNamespace
        from jkbose_tool.internal_assessment_verification_gui import AwardVerificationGUI
        try:root=tk.Tk()
        except tk.TclError:self.skipTest('Desktop unavailable')
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory()as history:
                owner=SimpleNamespace(root=root,worker=None,ia={k:tk.StringVar(value=val)for k,val in [('class','10'),('session','2025-26'),('history',history)]})
                AwardVerificationGUI._open_award_verification(owner)
                top=next(c for c in root.winfo_children()if isinstance(c,tk.Toplevel));top.transient('');top.deiconify();top.geometry('800x560');top.update()
                def walk(w):
                    yield w
                    for c in w.winfo_children():yield from walk(c)
                buttons=[w for w in walk(top)if isinstance(w,ttk.Button)and w.winfo_ismapped()]
                self.assertTrue(any(w['text']=='Verify selected files'for w in buttons))
                right=top.winfo_rootx()+top.winfo_width();bottom=top.winfo_rooty()+top.winfo_height()
                for button in buttons:
                    self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),right)
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),bottom)
        finally:root.destroy()

if __name__=='__main__':unittest.main()
