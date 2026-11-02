import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'ph_memory.py'
spec = importlib.util.spec_from_file_location('memory', SCRIPT)
mem = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mem)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'Dự án video'
        self.call('init', '--name', 'Video tiếng Việt', '--video')

    def call(self, command, *args, root=None, code=0):
        r = subprocess.run([sys.executable, str(SCRIPT), command, '--root', str(root or self.root), *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, code, r.stderr + r.stdout)
        self.assertNotIn('Traceback', r.stderr)
        return r

    def state(self, root=None):
        return json.loads(((root or self.root) / '.ph-memory/state.json').read_text(encoding='utf-8'))

    def candidate(self):
        s = self.state()
        s['purpose'] = 'Dựng video giới thiệu'
        s['current_task'] = 'Sửa nhạc ở frame 360'
        s['next_actions'] = ['Giảm nhạc ở frame 360–479']
        s['decisions'] = [dict(claim='Giữ take 02', status='user-approved', evidence='User review supplied in this session')]
        s['video'] = {'timeline': {'fps': '30000/1001', 'time_unit': 'frames'}}
        return s

    def checkpoint(self, s=None, revision=0, code=0):
        f = self.base / 'candidate.json'
        f.write_text(json.dumps(s if s is not None else self.candidate(), ensure_ascii=False), encoding='utf-8')
        return self.call('checkpoint', '--file', f, '--expected-revision', revision, code=code)

    def test_unicode_checkpoint_resume(self):
        self.checkpoint()
        self.assertEqual(self.state()['revision'], 1)
        self.assertIn('Giữ take 02', self.call('resume').stdout)
        self.assertEqual(self.state()['video']['timeline']['fps'], '30000/1001')
        self.assertTrue((self.root / '.ph-memory/history/00000000.json').exists())

    def test_stale_revision_does_not_overwrite(self):
        stale = self.candidate()
        self.checkpoint(stale)
        self.checkpoint(stale, code=2)
        self.assertEqual(self.state()['revision'], 1)

    def test_lock_refuses_writer(self):
        lock = self.root / '.ph-memory/.lock'
        lock.touch()
        self.checkpoint(code=2)
        self.assertEqual(self.state()['revision'], 0)

    def test_asset_detects_changes_and_missing(self):
        path = self.root / 'clip.txt'
        path.write_text('original')
        self.call('asset', '--path', 'clip.txt', '--role', 'Source')
        self.call('doctor')
        path.write_text('modified')
        self.assertIn('CHANGED', self.call('doctor', code=1).stdout)
        path.unlink()
        self.assertIn('MISSING', self.call('doctor', code=1).stdout)

    def test_roundtrip_and_no_media_export(self):
        self.checkpoint()
        (self.root / 'private.txt').write_text('not for export')
        archive = self.base / 'handoff.zip'
        self.call('export', '--output', archive)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(set(z.namelist()), {'manifest.json', 'state.json', 'RESUME.md'})
        dest = self.base / 'new'
        self.call('import', '--archive', archive, root=dest)
        self.assertEqual(self.state(), self.state(dest))
        self.assertTrue((dest / 'PROJECT_MEMORY.md').exists())
        self.call('import', '--archive', archive, root=dest, code=2)

    def test_tampered_archive_rejected(self):
        archive = self.base / 'handoff.zip'
        self.call('export', '--output', archive)
        with zipfile.ZipFile(archive) as z:
            contents = {k: z.read(k) for k in z.namelist()}
        contents['state.json'] += b' '
        bad = self.base / 'bad.zip'
        with zipfile.ZipFile(bad, 'w') as z:
            for k, v in contents.items():
                z.writestr(k, v)
        self.call('import', '--archive', bad, root=self.base / 'bad', code=2)
        self.assertFalse((self.base / 'bad/.ph-memory').exists())

    def test_zip_traversal_and_duplicates_rejected(self):
        archive = self.base / 'evil.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('../escape', 'bad')
        self.call('import', '--archive', archive, root=self.base / 'evil', code=2)
        self.assertFalse((self.base / 'escape').exists())

    def test_missing_evidence_rejected(self):
        s = self.candidate()
        s['decisions'][0]['evidence'] = ''
        self.checkpoint(s, code=2)
        self.assertEqual(self.state()['revision'], 0)

    def test_credentials_rejected(self):
        s = self.candidate()
        s['purpose'] = 'api_key=' + 'EXAMPLESECRET123456'
        self.checkpoint(s, code=2)

    def test_invalid_uuid_and_status_rejected(self):
        for field, val in [('project_id', 123), ('schema_version', True)]:
            s = self.candidate()
            s[field] = val
            self.checkpoint(s, code=2)
        s = self.candidate()
        s['decisions'][0]['status'] = []
        self.checkpoint(s, code=2)

    def test_unsafe_asset_paths_rejected(self):
        for path in ('.', '../outside', '/tmp/a', 'C:/outside', '.git/config'):
            self.call('asset', '--path', path, '--role', 'Source', code=2)

    def test_symlink_escape_rejected(self):
        outside = self.base / 'outside.txt'
        outside.write_text('private')
        link = self.root / 'link.txt'
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest('Symlinks unavailable for this account')
        self.call('asset', '--path', 'link.txt', '--role', 'Source', code=2)

    def test_resume_bounded_and_marked(self):
        s = self.candidate()
        s['purpose'] = 'Văn bản dài ' * 1000
        self.checkpoint(s)
        r = self.call('resume', '--max-chars', 512)
        self.assertLessEqual(len(r.stdout), 512)
        self.assertIn('TRUNCATED', r.stdout)

    def test_init_preserves_existing_docs_and_ignore(self):
        root = self.base / 'existing'
        root.mkdir()
        (root / 'PROJECT_MEMORY.md').write_text('Existing decisions')
        (root / 'AGENTS.md').write_text('Existing instructions')
        (root / '.gitignore').write_text('renders/\n')
        self.call('init', '--name', 'Existing', root=root)
        self.assertEqual((root / 'PROJECT_MEMORY.md').read_text(), 'Existing decisions')
        self.assertEqual((root / 'AGENTS.md').read_text(), 'Existing instructions')
        self.assertIn('renders/', (root / '.gitignore').read_text())
        self.call('init', '--name', 'Existing', root=root, code=2)

    def test_history_is_bounded(self):
        for rev in range(12):
            s = self.state()
            s['current_task'] = f'Cut {rev}'
            self.checkpoint(s, revision=rev)
        self.assertEqual(len(list((self.root / '.ph-memory/history').glob('*.json'))), 10)

    def test_export_does_not_overwrite_or_write_inside_project(self):
        self.call('export', '--output', self.root / 'bad.zip', code=2)
        out = self.base / 'existing.zip'
        out.write_bytes(b'existing')
        self.call('export', '--output', out, code=2)
        self.assertEqual(out.read_bytes(), b'existing')

    def test_foreign_project_refused(self):
        s = self.candidate()
        import uuid
        s['project_id'] = str(uuid.uuid4())
        self.checkpoint(s, code=2)

    def test_unknown_schema_refused(self):
        s = self.candidate()
        s['schema_version'] = 2
        self.checkpoint(s, code=2)


if __name__ == '__main__':
    unittest.main()
