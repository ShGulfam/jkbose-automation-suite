"""Exact administrator-confirmed source warning corrections; never fixes identifiers."""
from pathlib import Path
import json
from .internal_assessment import norm
WARNING='Portal review required: Award registration differs from roster; review identity.'

def apply_identity_confirmations(plan):
    path=Path(plan.source).with_name('JKBOSE_Identity_Confirmations.json')
    if not path.is_file():return
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('schema')!='jkbose-identity-confirmations-v1' or not isinstance(data.get('confirmations'),list):raise ValueError('Invalid identity confirmation file; review before continuing.')
    for a in plan.awards:
        for record in data['confirmations']:
            if (record.get('class')==plan.student_class and record.get('session')==plan.session and record.get('registration')==a.regno
                and record.get('exam_roll')==a.exam_roll and norm(record.get('name'))==norm(a.name)
                and record.get('warning')==WARNING and record.get('confirmed_by')=='user' and len(record.get('evidence',''))>=20):
                a.issues=[issue for issue in a.issues if issue!=WARNING]
                a.identity_confirmation=record['evidence']
