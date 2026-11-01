"""Security regression checks for package inspection; no live downloads or customer data."""
import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('release_checker', Path(__file__).with_name('verify_release.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ArchivePolicyTests(unittest.TestCase):
    def inspect(self, extra):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            for name in checker.REQUIRED:
                archive.writestr(name, b'fixture')
            archive.writestr('LICENSE', 'fixture license')
            for name in extra:
                archive.writestr(name, b'fixture')
        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as archive:
            return checker.inventory(archive)

    def test_ordinary_native_package_structure_is_accepted(self):
        self.assertEqual([], self.inspect(['python312.dll', 'libssl-3.dll']))

    def test_windows_and_posix_traversal_are_rejected(self):
        for name in ['../escape.exe', '..\\escape.exe', '/absolute.exe', 'C:/escape.exe', 'app.exe:stream']:
            with self.subTest(name=name):
                self.assertTrue(any('Unsafe archive path' in f for f in self.inspect([name])))

    def test_customer_data_and_signing_keys_cannot_ship(self):
        for name in ['data/books.sqlite3', 'data/books.sqlite3-wal', 'books.json', '.env', '.env.production', 'publisher.pfx', 'publisher.key', '.git/config', 'profile/Local State']:
            with self.subTest(name=name):
                self.assertTrue(any('package' in f for f in self.inspect([name])))

    def test_legacy_launch_scripts_are_detected(self):
        for name in ['Launch.vbs', 'tools/Run.PS1', 'Launch.bat', 'payload.hta']:
            with self.subTest(name=name):
                self.assertTrue(any('script entry' in f for f in self.inspect([name])))

    def test_unsupported_bundled_runtimes_are_reported(self):
        findings = self.inspect(['python39.dll', 'libssl-1_1.dll'])
        self.assertTrue(any('End-of-life runtime' in f for f in findings))

    def test_case_insensitive_duplicate_paths_are_rejected(self):
        self.assertTrue(any('Duplicate archive path' in f for f in self.inspect(['WORKFLOWS.JS'])))


if __name__ == '__main__':
    unittest.main()
