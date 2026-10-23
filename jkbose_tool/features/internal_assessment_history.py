"""Simple human-facing history; original audit evidence remains byte-for-byte intact."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import html
import json
import os
import re
import shutil
from urllib.parse import quote

MARKER = '.internal-assessment-references'
INDEX = 'OPEN HISTORY.html'


def storage_root(root):
    path = Path(root).resolve()
    if (path / MARKER).is_file():
        return path
    if (path / 'References' / MARKER).is_file():
        return path / 'References'
    return path


def public_root(root):
    path = storage_root(root)
    return path.parent if (path / MARKER).is_file() else path


def manifest_paths(root):
    """Also notice unfinished migrations; never hide a legacy uncertain receipt."""
    storage = storage_root(root)
    paths = list(storage.glob('*/manifest.json'))
    public = public_root(root)
    if public != storage:
        paths += list(public.glob('*/manifest.json'))
    seen = set()
    for path in paths:
        if path.parent.name in seen:
            raise ValueError('Duplicate legacy/reference history. Reconcile before resuming.')
        seen.add(path.parent.name)
    return sorted(paths)


def resolve_reference(path, root):
    """Locate moved evidence without altering paths inside signed journals/reports."""
    original = Path(path)
    if original.exists():
        return original
    storage, public = storage_root(root), public_root(root)
    try:
        relative = original.resolve().relative_to(public)
    except ValueError:
        return original
    moved = storage / relative
    return moved if moved.exists() else original


def _reparse(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def prepare_layout(root):
    """Move old technical entries under References, refusing locks or collisions."""
    public = public_root(root)
    public.mkdir(parents=True, exist_ok=True)
    storage = public / 'References'
    if _reparse(public) or _reparse(storage):
        raise ValueError('History/reference folders must not be links or junctions.')
    # Only generated report copies and the landing page belong at the top level.
    visible = re.compile(r'^Class (10|11|12) - [A-Za-z0-9_-]+ - [0-9]{4}-[0-9]{2} - Student Matching\.(xlsx|pdf)$')
    moves = [path for path in public.iterdir() if path.name not in {'References', 'Reconciliation', INDEX, 'internal-assessment.lock'}
             and not visible.fullmatch(path.name)]
    if (public / 'internal-assessment.lock').exists() or (storage / 'internal-assessment.lock').exists():
        raise ValueError('History is locked. Finish or reconcile the active run before reorganizing it.')
    if not moves and (storage / MARKER).is_file():
        return storage
    # A migration uses the legacy root lock, then rechecks the new run lock.
    descriptor = os.open(public / 'internal-assessment.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        if (storage / 'internal-assessment.lock').exists():
            raise ValueError('Reference history is locked; no evidence was moved.')
        for path in moves:
            destination = storage / path.name
            if path.resolve().parent != public or destination.resolve().parent != storage.resolve():
                raise ValueError('History migration target escapes the configured folder.')
            if _reparse(path) or (path.is_dir() and any(_reparse(child) for child in path.rglob('*'))):
                raise ValueError('Linked history evidence cannot be moved automatically.')
            if destination.exists():
                raise ValueError('Legacy/reference history collision; no evidence was overwritten.')
        storage.mkdir(exist_ok=True)
        (storage / MARKER).touch(exist_ok=True)
        for path in moves:
            path.rename(storage / path.name)
        return storage
    finally:
        (public / 'internal-assessment.lock').unlink()


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _atomic_text(path, content):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def publish_history(root):
    """Publish only verified exports; this view never grants permission to submit."""
    storage, public = storage_root(root), public_root(root)
    if storage == public:
        raise ValueError('Initialize the References layout before publishing history.')
    runs = []
    for report_path in sorted((storage / '_class_runs').glob('*/report.json'), reverse=True):
        report = json.loads(report_path.read_text(encoding='utf-8'))
        manifest = report['manifest']
        runs.append((report_path, report, manifest))
    latest = {}
    for path, report, manifest in runs:
        if manifest.get('mode') == 'offline_preview':
            continue
        key = (str(manifest['class']), str(manifest['school_account']).lower())
        latest.setdefault(key, []).append((path, report, manifest))
    catalog_path = storage / 'published-reports.json'
    old_catalog = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else []
    catalog, cards = [], []
    def escape(value):
        return html.escape(str(value))
    def readable_status(value):
        labels = {'finished_with_manual_review':'Needs manual review', 'finished':'Completed',
                  'roster_review_required':'Review flagged differences', 'roster_matched':'Enrolment matched'}
        return escape(labels.get(value, str(value).replace('_', ' ').capitalize()))
    def run_time(path):
        try:
            stamp = datetime.strptime(path.parent.name.split('-')[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            return stamp.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime('%d %b %Y, %I:%M %p IST')
        except ValueError:
            return path.parent.name
    def link(path, label):
        path = Path(path).resolve()
        relative = path.relative_to(public).as_posix()
        return '<a href="' + quote(relative, safe='/') + '">' + escape(label) + '</a>'
    for (cls, account), group in sorted(latest.items()):
        newest_path, newest_report, newest_manifest = group[0]
        chosen = None
        for path, report, manifest in group:
            exports = report.get('student_report_matching', {}).get('exports', {})
            if all(exports.get(kind) and exports.get(kind + '_sha256') for kind in ('excel', 'pdf')):
                chosen = path, report, manifest, exports
                break
        title = f'Class {cls} · {account}'
        body = f'<p>Last checked: {escape(run_time(newest_path))}<br>Status: <b>{readable_status(newest_report["status"])}</b></p>'
        body += f'<p>New verified saves in this run: {escape(newest_report.get("new_verified_saved_count", 0))}. '
        body += f'Class-wide manual holds: {len(newest_report.get("class_wide_holds", []))}.</p>'
        if chosen:
            path, report, manifest, exports = chosen
            session = str(manifest['session'])
            if not re.fullmatch(r'20\d{2}-\d{2}', session) or not re.fullmatch(r'[a-z0-9_-]+', account) or cls not in {'10', '11', '12'}:
                raise ValueError('Unsafe class/session/account in history report.')
            links = []
            verified_sources = {}
            for kind in ('excel', 'pdf'):
                source = resolve_reference(exports[kind], storage).resolve(strict=True)
                if not source.is_relative_to(storage) or _digest(source) != exports[kind + '_sha256']:
                    raise ValueError('History export fingerprint differs; the latest report was not replaced.')
                verified_sources[kind] = source
            for kind, suffix in [('excel', 'xlsx'), ('pdf', 'pdf')]:
                source = verified_sources[kind]
                destination = public / f'Class {cls} - {account} - {session} - Student Matching.{suffix}'
                temporary = destination.with_name(destination.name + '.tmp')
                shutil.copyfile(source, temporary)
                if _digest(temporary) != exports[kind + '_sha256']:
                    raise ValueError('Readable history copy failed verification.')
                os.replace(temporary, destination)
                catalog.append({'file': destination.name, 'sha256': exports[kind + '_sha256'],
                                'source': str(source), 'run': path.parent.name})
                links.append(link(destination, kind.upper()))
            data = report['student_report_matching']
            label = 'Latest enrolment report' if path == newest_path else 'Earlier enrolment report — latest run has no completed export'
            body += f'<p><b>{label}</b><br>School session: {escape(session)} · Board report session: {escape(data.get("report_session", "See report"))}<br>Report created: {escape(run_time(path))}</p>'
            body += '<p class="buttons">' + ' '.join(links) + '</p>'
            body += f'<p>Enrolment result: {readable_status(data.get("status", "See report"))}. Review the workbook/PDF for name differences and manual exceptions.</p>'
        else:
            body += '<p>No complete Students report export is available for this class.</p>'
        pending = newest_report.get('matching_exports', {})
        pending_links = []
        for kind in ('excel', 'pdf'):
            if pending.get(kind):
                located = resolve_reference(pending[kind], storage)
                if located.is_file() and located.resolve().is_relative_to(storage):
                    pending_links.append(link(located, kind.upper()))
        if pending_links:
            body += '<p>Pending-awards check (coverage may be incomplete): ' + ' · '.join(pending_links) + '</p>'
        body += '<p>' + link(newest_path, 'Latest run details (References)') + '</p>'
        cards.append('<section><h2>' + escape(title) + '</h2>' + body + '</section>')
    # Retire only unchanged copies that this publisher previously created.
    current_names = {item['file'] for item in catalog}
    for item in old_catalog:
        filename = item['file']
        if Path(filename).name != filename:
            raise ValueError('Invalid published-history filename.')
        previous = public / filename
        if filename not in current_names and previous.is_file() and _digest(previous) == item['sha256']:
            archive = storage / '_published_previous'
            archive.mkdir(exist_ok=True)
            destination = archive / (item['sha256'][:12] + '-' + filename)
            if destination.exists():
                if _digest(destination) != item['sha256']:
                    raise ValueError('Archived readable-report collision.')
                # Keep a unique intact file instead of deleting a copy.
                destination = archive / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-' + filename)
            previous.rename(destination)
    _atomic_text(catalog_path, json.dumps(catalog, indent=2))
    history_rows = []
    for path, report, manifest in runs:
        history_rows.append('<li>' + escape(f'Class {manifest["class"]} · {manifest["session"]} · {manifest["mode"]} · {report["status"]} · ')
                            + link(path, path.parent.name) + '</li>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Internal Assessment History</title><style>body{font:16px system-ui,sans-serif;max-width:1060px;margin:32px auto;padding:0 20px;background:#f4f6fa;color:#192c41}h1{font-size:28px}h2{font-size:21px}section{background:white;border:1px solid #d7e0eb;border-radius:12px;padding:18px 24px;margin:18px 0}p{line-height:1.6}a{color:#175eab} .buttons a{display:inline-block;padding:9px 24px;background:#175eab;color:white;border-radius:7px;text-decoration:none;margin-right:8px}li{margin:10px 0}footer{font-size:13px;color:#53647b;margin-top:24px}</style>
<h1>Internal Assessment History</h1><p>Open the latest matching reports below. Earlier runs and technical evidence are kept in <b>References</b>.</p>
<p><b>Enrolment matching does not prove practical attendance or saved marks.</b> Pending-page checks may be partial. Absence, failed/over-maximum awards, identity conflicts and uncertain submissions retain their existing manual-review safeguards.</p>'''
    page += ''.join(cards) or '<section>No class reports yet. Run a read-only check to create matching reports.</section>'
    page += '<details><summary>Earlier runs and reference details</summary><ul>' + ''.join(history_rows) + '</ul></details>'
    page += '<footer>Confidential institutional history. Updated ' + escape(datetime.now().astimezone().isoformat(timespec='seconds')) + '. Original journals and receipts are preserved unchanged.</footer></html>'
    _atomic_text(public / INDEX, page)
    return public / INDEX
