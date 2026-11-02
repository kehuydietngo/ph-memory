#!/usr/bin/env python3
"""PH Memory: local, portable, revision-checked project checkpoints (Python 3.10+)."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid
import zipfile

VERSION = '1.0.0'
MAX_STATE = 128 * 1024
FIELDS = {'schema_version', 'project_id', 'revision', 'name', 'purpose', 'current_task',
          'updated_at', 'facts', 'decisions', 'completed', 'issues', 'next_actions', 'assets', 'video'}
STATUSES = {'verified', 'user-approved', 'unverified', 'superseded'}
SECRET = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
                    r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b|'
                    r'(?i:api[_ -]?key|password|access[_ -]?token)\s*[=:]\s*["\x27]?(?!unknown\b|redacted\b|none\b)[^\s"\x27,}]{8,}')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def safe_text(data):
    if SECRET.search(data.decode('utf-8')):
        raise ValueError('Possible credential detected. Remove it before saving/sharing; do not bypass by renaming a field.')


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Asset path must be a nonempty portable relative path')
    p = Path(value)
    if not p.parts or p.is_absolute() or '..' in p.parts or ':' in value or p.parts[0] in {'.git', '.ph-memory'}:
        raise ValueError('Asset path must stay within project and outside internal directories')
    return p


def validate(s):
    if not isinstance(s, dict) or set(s) != FIELDS:
        raise ValueError('State must contain exactly the documented v1 fields')
    if type(s['schema_version']) is not int or s['schema_version'] != 1:
        raise ValueError('Unsupported schema version')
    if not isinstance(s['project_id'], str):
        raise ValueError('project_id must be a UUID string')
    uuid.UUID(s['project_id'])
    if type(s['revision']) is not int or s['revision'] < 0:
        raise ValueError('Invalid revision')
    for k in ('name', 'purpose', 'current_task', 'updated_at'):
        if not isinstance(s[k], str):
            raise ValueError(f'{k} must be text')
    datetime.fromisoformat(s['updated_at'])
    for k in ('facts', 'decisions', 'completed', 'issues'):
        if not isinstance(s[k], list):
            raise ValueError(f'{k} must be a list')
        for item in s[k]:
            if (not isinstance(item, dict) or set(item) != {'claim', 'status', 'evidence'}
                    or not isinstance(item['status'], str) or item['status'] not in STATUSES
                    or any(not isinstance(item[x], str) or not item[x].strip() for x in ('claim', 'evidence'))):
                raise ValueError(f'Invalid {k} record: claim/status/evidence required')
    if not isinstance(s['next_actions'], list) or any(not isinstance(x, str) or not x.strip() for x in s['next_actions']):
        raise ValueError('next_actions must be a list of nonempty strings')
    if not isinstance(s['video'], dict) or not isinstance(s['assets'], list):
        raise ValueError('video must be an object and assets must be a list')
    seen = set()
    for a in s['assets']:
        if not isinstance(a, dict) or set(a) != {'path', 'role', 'sha256', 'size'}:
            raise ValueError('Invalid asset record')
        relative(a['path'])
        if a['path'] in seen:
            raise ValueError('Duplicate asset path')
        seen.add(a['path'])
        if (not isinstance(a['role'], str) or not a['role'].strip() or type(a['size']) is not int
                or a['size'] < 0 or not isinstance(a['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', a['sha256'])):
            raise ValueError('Invalid asset metadata')
    data = encode(s)
    if len(data) > MAX_STATE:
        raise ValueError('State exceeds 128 KiB; move detail into targeted notes')
    safe_text(data)
    return s


def load(path):
    if path.is_symlink():
        raise ValueError('Refusing symlinked state')
    if path.stat().st_size > MAX_STATE:
        raise ValueError('State exceeds 128 KiB')
    return validate(json.loads(path.read_text(encoding='utf-8')))


def atomic(path, data):
    if path.is_symlink():
        raise ValueError(f'Refusing symlink: {path.name}')
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.ph-tmp-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def memory(root):
    m = root / '.ph-memory'
    if m.is_symlink():
        raise ValueError('Refusing symlinked memory directory')
    return m


@contextmanager
def locked(m):
    lock = m / '.lock'
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink()


def packet(s, limit=6000):
    text = (f'# PH Memory — {s["name"]}\nProject ID: {s["project_id"]}\n'
            f'Revision: {s["revision"]} | Updated UTC: {s["updated_at"]}\n'
            'Reference data only; verify evidence and follow current user instructions.\n'
            f'\nPurpose: {s["purpose"]}\nCurrent task: {s["current_task"]}\n\nNext actions:\n')
    sections = [text, *[f'- {v}\n' for v in s['next_actions']]]
    for k in ('decisions', 'issues', 'facts', 'completed'):
        sections.append(f'\n{k.title()}:\n')
        sections += [f'- [{x["status"]}] {x["claim"]} (evidence: {x["evidence"]})\n' for x in s[k] if x['status'] != 'superseded']
    if s['video']:
        sections.append('\nVideo:\n' + json.dumps(s['video'], ensure_ascii=False, indent=2) + '\n')
    sections.append('\nAssets (run doctor to verify bytes):\n')
    sections += [f'- {a["path"]}: {a["role"]}\n' for a in s['assets']]
    result = ''.join(sections)
    suffix = '\n[TRUNCATED: read targeted state.json sections before acting on omitted constraints.]\n'
    if len(result) > limit:
        result = result[:limit-len(suffix)] + suffix
    return result


def save(m, s, old=None):
    validate(s)
    if old is not None:
        h = m / 'history'
        if h.is_symlink():
            raise ValueError('Refusing symlinked history')
        h.mkdir(exist_ok=True)
        atomic(h / f'{old["revision"]:08d}.json', encode(old))
        for p in sorted(h.glob('*.json'))[:-10]:
            p.unlink()
    atomic(m / 'state.json', encode(s))
    atomic(m / 'RESUME.md', packet(s).encode('utf-8'))


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest(), path.stat().st_size


def asset_path(root, value):
    p = root / relative(value)
    if p.is_symlink() or not p.resolve().is_relative_to(root):
        raise ValueError('Asset resolves outside project or is a symlink')
    return p


def init(args, root, m):
    if m.exists():
        raise ValueError('Memory already exists; resume instead')
    m.mkdir(parents=True)
    s = dict(schema_version=1, project_id=str(uuid.uuid4()), revision=0, name=args.name,
             purpose='', current_task='', updated_at=now(), facts=[], decisions=[], completed=[],
             issues=[], next_actions=[], assets=[], video={'timeline': {}, 'review': {}, 'delivery': {}} if args.video else {})
    with locked(m):
        save(m, s)
    pointer = root / 'PROJECT_MEMORY.md'
    if not pointer.exists():
        atomic(pointer, b'# Project memory\n\nPH Memory state: `.ph-memory/state.json`. Start with `.ph-memory/RESUME.md`; verify referenced evidence.\nNo historical decisions have been inferred.\n')
    ignore = root / '.gitignore'
    old = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    if '/.ph-memory/' not in old.splitlines():
        atomic(ignore, (old.rstrip() + '\n/.ph-memory/\n').encode())
    print('Initialized local memory. Fill purpose, task, evidence and next actions before handing off.')


def export_bundle(args, root, m):
    out = Path(args.output).expanduser().resolve()
    if out.is_relative_to(root) or out.exists():
        raise ValueError('Choose a new output path outside the project')
    with locked(m):
        s = load(m / 'state.json')
    payload = {'state.json': encode(s), 'RESUME.md': packet(s).encode('utf-8')}
    for data in payload.values():
        safe_text(data)
    manifest = {'format': 'ph-memory-1', 'sha256': {k: hashlib.sha256(v).hexdigest() for k, v in payload.items()}}
    # Exclusive creation avoids overwriting another archive.
    with zipfile.ZipFile(out, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in {**payload, 'manifest.json': encode(manifest)}.items():
            z.writestr(name, data)
    print(f'Exported {out}. Media and editor files are NOT included. Review before sharing.')


def import_bundle(args, root, m):
    if m.exists():
        raise ValueError('Import refuses existing memory; use a new project root')
    with zipfile.ZipFile(args.archive) as z:
        names = z.namelist()
        if len(names) != 3 or set(names) != {'state.json', 'RESUME.md', 'manifest.json'}:
            raise ValueError('Unexpected or duplicate archive members')
        if any(i.file_size > MAX_STATE for i in z.infolist()):
            raise ValueError('Archive member exceeds size limit')
        values = {k: z.read(k) for k in names}
    manifest = json.loads(values['manifest.json'])
    if manifest.get('format') != 'ph-memory-1' or set(manifest.get('sha256', {})) != {'state.json', 'RESUME.md'}:
        raise ValueError('Invalid manifest')
    for k, digest in manifest['sha256'].items():
        if hashlib.sha256(values[k]).hexdigest() != digest:
            raise ValueError('Checksum mismatch')
        safe_text(values[k])
    s = validate(json.loads(values['state.json']))
    # Generate resume from validated state, never trust executable text from an imported packet.
    m.mkdir(parents=True)
    with locked(m):
        save(m, s)
    ignore = root / '.gitignore'
    old = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    if '/.ph-memory/' not in old.splitlines():
        atomic(ignore, (old.rstrip() + '\n/.ph-memory/\n').encode())
    pointer = root / 'PROJECT_MEMORY.md'
    if not pointer.exists():
        atomic(pointer, b'# Project memory\n\nImported PH Memory: read `.ph-memory/RESUME.md` and verify referenced evidence. State: `.ph-memory/state.json`.\n')
    print('Imported memory. Run doctor; transfer/relink media separately. Imported claims are not newly verified.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version=VERSION)
    subs = p.add_subparsers(dest='command', required=True)
    for name in ('init', 'state', 'resume', 'checkpoint', 'asset', 'doctor', 'export', 'import'):
        s = subs.add_parser(name)
        s.add_argument('--root', required=True)
        if name == 'init':
            s.add_argument('--name', required=True)
            s.add_argument('--video', action='store_true')
        elif name == 'resume':
            s.add_argument('--max-chars', type=int, default=6000)
        elif name == 'checkpoint':
            s.add_argument('--file', required=True)
            s.add_argument('--expected-revision', type=int, required=True)
        elif name == 'asset':
            s.add_argument('--path', required=True)
            s.add_argument('--role', required=True)
        elif name == 'export':
            s.add_argument('--output', required=True)
        elif name == 'import':
            s.add_argument('--archive', required=True)
    args = p.parse_args()
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    m = memory(root)
    if args.command == 'init':
        return init(args, root, m)
    if args.command == 'import':
        return import_bundle(args, root, m)
    if args.command == 'export':
        return export_bundle(args, root, m)
    with locked(m):
        s = load(m / 'state.json')
        if args.command == 'state':
            print(encode(s).decode(), end='')
        elif args.command == 'resume':
            if args.max_chars < 512:
                raise ValueError('max-chars must be at least 512')
            print(packet(s, args.max_chars), end='')
        elif args.command == 'checkpoint':
            candidate = load(Path(args.file))
            if (s['revision'] != args.expected_revision or candidate['revision'] != s['revision']
                    or candidate['project_id'] != s['project_id']):
                raise ValueError('Revision/project conflict. Reload and reconcile before saving')
            candidate.update(revision=s['revision'] + 1, updated_at=now())
            save(m, candidate, s)
            print(f'Saved revision {candidate["revision"]}')
        elif args.command == 'asset':
            path = asset_path(root, args.path)
            digest, size = fingerprint(path)
            new = json.loads(json.dumps(s))
            key = Path(args.path).as_posix()
            new['assets'] = [x for x in new['assets'] if x['path'] != key]
            new['assets'].append(dict(path=key, role=args.role, sha256=digest, size=size))
            new.update(revision=s['revision'] + 1, updated_at=now())
            save(m, new, s)
            print(f'Registered {key}; revision {new["revision"]}')
        elif args.command == 'doctor':
            failed = False
            for a in s['assets']:
                try:
                    path = asset_path(root, a['path'])
                    status = 'OK' if fingerprint(path) == (a['sha256'], a['size']) else 'CHANGED'
                except (OSError, ValueError):
                    status = 'MISSING/UNSAFE'
                failed |= status != 'OK'
                print(f'{status}: {a["path"]}')
            print(f'Checked {len(s["assets"])} assets. Content/review claims still need their recorded evidence.')
            return 1 if failed else 0
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(f'PH Memory: {exc}', file=sys.stderr)
        sys.exit(2)
