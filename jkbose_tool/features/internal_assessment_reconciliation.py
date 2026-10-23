"""Readable reconciliation references; original journals remain authoritative."""
import json
import re
from pathlib import Path
from .internal_assessment_history import public_root, storage_root, manifest_paths


def resolve_manifest(selected, root):
    storage=storage_root(root).resolve()
    path=Path(selected).resolve(strict=True)
    if path.parent == public_root(root)/'Reconciliation':
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema')!='jkbose-reconciliation-reference-v1':
            raise ValueError('Select a reconciliation reference or the original run manifest.')
        relative=Path(data['manifest'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Reconciliation reference must stay inside the history folder.')
        path=(public_root(root)/relative).resolve(strict=True)
    if path.name!='manifest.json' or path.parent.parent!=storage or not re.fullmatch(r'[0-9a-f]{24}',path.parent.name):
        raise ValueError('Choose a subject run manifest, not a class-run report. Open the Reconciliation folder for readable names.')
    return path


def build_reconciliation_references(root):
    from .internal_assessment import Audit
    public=public_root(root)
    folder=public/'Reconciliation';folder.mkdir(exist_ok=True)
    if folder.resolve().parent!=public.resolve() or folder.is_symlink():
        raise ValueError('Reconciliation folder must be inside the private history folder.')
    results=[]
    for manifest in manifest_paths(root):
        # Validate the intact source manifest and hash chain before advertising a run.
        audit,plan=Audit.existing(manifest.parent)
        pending=audit.unresolved()
        if not pending:
            for previous in folder.glob('* - Needs review - '+manifest.parent.name[:8]+'.json'):
                data=json.loads(previous.read_text(encoding='utf-8'))
                if data.get('schema')=='jkbose-reconciliation-reference-v1' and data.get('manifest')==str(manifest.relative_to(public)):
                    completed=folder/'Completed';completed.mkdir(exist_ok=True)
                    destination=completed/previous.name.replace('Needs review','Reviewed')
                    if not destination.exists():previous.rename(destination)
            continue
        label=f'Class {plan.student_class} - {plan.subject} - {plan.session} - Needs review - {manifest.parent.name[:8]}'
        label=re.sub(r'[<>:"/\\|?*]','_',label)
        destination=folder/(label+'.json')
        data={'schema':'jkbose-reconciliation-reference-v1','class':plan.student_class,'subject':plan.subject,
              'session':plan.session,'unresolved_batches':len(pending),
              'manifest':str(manifest.relative_to(public)),
              'instructions':'Select this file in Reconcile an uncertain batch. Verify the entire batch on JKBOSE before recording a finding. This reference is not proof of a save.'}
        destination.write_text(json.dumps(data,indent=2),encoding='utf-8')
        results.append(destination)
    return folder,results
