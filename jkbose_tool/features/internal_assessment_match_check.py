"""Bound, expiring read-only Match evidence for one-click submission."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from .internal_assessment_history import storage_root

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _scope(plans,account,report_session):
    if not plans:raise ValueError('Choose valid source subjects before matching.')
    return dict(account=account.lower(),report_session=report_session or 'Auto',
                plans=sorted((plan.subject,plan.digest()) for plan in plans))
def _path(root,scope):
    key=hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()[:24]
    return storage_root(root)/'_match_checks'/(key+'.json')

def save_match_check(root,plans,account,report_session,folder,snapshot_path):
    root=storage_root(root).resolve();folder=Path(folder).resolve()
    if folder.parent!=root/'_class_runs':raise ValueError('Match evidence must belong to the configured class-run history.')
    scope=_scope(plans,account,report_session)
    evidence=[Path(snapshot_path).resolve(),folder/'events.jsonl',folder/'report.json',folder/'official_saved_assessment_report.json']
    if any(not p.is_relative_to(folder) or not p.is_file() for p in evidence):raise ValueError('Complete read-only Match evidence is required.')
    data=dict(schema='jkbose-read-only-match-v1',scope=scope,created_at=datetime.now(timezone.utc).isoformat(),
              snapshot=str(evidence[0].relative_to(root)),proofs={str(p.relative_to(root)):_sha(p) for p in evidence})
    path=_path(root,scope);path.parent.mkdir(exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    return path

def load_match_check(root,plans,account,report_session,now=None):
    root=storage_root(root).resolve();scope=_scope(plans,account,report_session);path=_path(root,scope)
    message='Run 2. Match read only again for this exact workbook, subjects, class, session and school account before automatic Submit.'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        # JSON converts scope pairs to arrays; compare their canonical encoding.
        if data.get('schema')!='jkbose-read-only-match-v1' or json.dumps(data['scope'],sort_keys=True)!=json.dumps(scope,sort_keys=True):raise ValueError(message)
        current=now or datetime.now(timezone.utc);created=datetime.fromisoformat(data['created_at'])
        if created>current or current-created>timedelta(hours=24):raise ValueError(message)
        for relative,digest in data['proofs'].items():
            proof=(root/relative).resolve()
            if not proof.is_relative_to(root) or _sha(proof)!=digest:raise ValueError(message)
        snapshot=(root/data['snapshot']).resolve()
        if not snapshot.is_relative_to(root) or data['snapshot'] not in data['proofs']:raise ValueError(message)
        for plan in plans:
            if _sha(plan.source)!=plan.source_sha256:raise ValueError(message)
        return dict(path=str(path),sha256=_sha(path),snapshot=json.loads(snapshot.read_text(encoding='utf-8')))
    except (OSError,KeyError,TypeError,json.JSONDecodeError,ValueError) as exc:
        raise ValueError(message) from exc
