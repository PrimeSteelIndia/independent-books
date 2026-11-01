"""Read-only release inspection. Does not install, publish, or bypass browser warnings.

Example:
  python tools/release_hardening/verify_release.py --installer dist/IndependentBooksSetup.exe \
    --portable dist/IndependentBooks_Portable.zip --report-dir <new-private-report-directory> --scan

Exit 0 means configured artifact checks passed; it is NOT a Chrome verdict or a
complete security assessment. Exit 1 means a release blocker was found.
Unsigned builds may be inspected, but never pass the publisher-signature gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import uuid
import zipfile

REQUIRED = ('IndependentBooks.exe', 'app_server.exe', 'index.html', 'workflows.js', 'version.json')
MAX_ENTRY = 128 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
SCRIPT_EXTENSIONS = {'.vbs', '.vbe', '.ps1', '.psm1', '.bat', '.cmd', '.hta', '.wsf'}


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def inventory(archive):
    """Inspect names and size limits before reading any payload; never extractall."""
    findings = []
    infos = archive.infolist()
    if len(infos) > 5000 or sum(i.file_size for i in infos) > MAX_TOTAL:
        return ['Archive exceeds inspection size/count limits']
    names = set()
    for info in infos:
        name = info.filename.replace('\\', '/')
        parts = PurePosixPath(name).parts
        if name.startswith('/') or ':' in name or '..' in parts:
            findings.append('Unsafe archive path: ' + name)
        folded = name.casefold()
        if folded in names:
            findings.append('Duplicate archive path: ' + name)
        names.add(folded)
        if info.flag_bits & 1:
            findings.append('Encrypted entry cannot be verified: ' + name)
        if info.file_size > MAX_ENTRY:
            findings.append('Entry exceeds inspection size limit: ' + name)
        if info.file_size > 1024 * 1024 and info.file_size > max(info.compress_size, 1) * 1000:
            findings.append('Excessive compression ratio: ' + name)
        if any(p.casefold() in {'.git', '.wrangler', '.venv', 'profile'} for p in parts):
            findings.append('Development/private state in package: ' + name)
        leaf = parts[-1].casefold() if parts else ''
        if '.sqlite' in leaf or leaf in {'books.json', '.env'} or leaf.startswith('.env.') or leaf.endswith(('.pfx', '.p12', '.key')):
            findings.append('Database/secret/key material in package: ' + name)
        if PurePosixPath(name).suffix.casefold() in SCRIPT_EXTENSIONS:
            findings.append('Unexpected script entry in native customer package: ' + name)
    for required in REQUIRED:
        if required.casefold() not in names:
            findings.append('Required root entry missing: ' + required)
    if not any(PurePosixPath(i.filename).name.casefold().startswith(('license', 'copying', 'notice')) for i in infos):
        findings.append('Package does not include license/notice files')
    unsupported = sorted({PurePosixPath(i.filename).name for i in infos
                          if re.fullmatch(r'python(?:3[0-9]|310)\.dll', PurePosixPath(i.filename).name, re.I)
                          or PurePosixPath(i.filename).name.casefold() in {'libssl-1_1.dll', 'libcrypto-1_1.dll'}})
    if unsupported:
        findings.append('End-of-life runtime libraries bundled: ' + ', '.join(unsupported))
    return findings


def powershell_path():
    for name in ('pwsh.exe', 'pwsh', 'powershell.exe'):
        path = shutil.which(name)
        if path:
            return path
    system_root = os.environ.get('SystemRoot', r'C:\Windows')
    candidate = Path(system_root) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    return str(candidate) if candidate.is_file() else None


def inspect_signatures(items, work):
    shell = powershell_path()
    if not shell:
        raise RuntimeError('Windows Authenticode checker unavailable')
    input_path, output_path = work / 'signature-input.json', work / 'signatures.json'
    input_path.write_text(json.dumps(items), encoding='utf-8')
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File',
                             str(Path(__file__).with_name('inspect_signatures.ps1')),
                             '-InputJson', str(input_path), '-OutputJson', str(output_path)],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Authenticode inspection failed: ' + result.stderr[:1000])
    return json.loads(output_path.read_text(encoding='utf-8-sig'))


def defender_path():
    base = Path(os.environ.get('ProgramData', r'C:\ProgramData')) / 'Microsoft/Windows Defender/Platform'
    candidates = sorted((p for p in base.glob('*/MpCmdRun.exe') if p.parent.name[:1].isdigit()),
                        key=lambda p: tuple(int(x) for x in re.findall(r'\d+', p.parent.name)), reverse=True)
    if candidates:
        return candidates[0]
    fallback = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Windows Defender/MpCmdRun.exe'
    return fallback if fallback.is_file() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--portable', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--scan', action='store_true', help='Scan private artifact copies with Defender; remediation disabled')
    args = parser.parse_args()
    report_dir = args.report_dir.resolve()
    # Never overwrite another agent's report or extract into a public artifact directory.
    if report_dir.exists() and any(report_dir.iterdir()):
        raise SystemExit('Report directory must be new or empty')
    report_dir.mkdir(parents=True, exist_ok=True)
    work = report_dir / ('inspection-' + uuid.uuid4().hex)
    work.mkdir()
    artifacts = []
    blockers = []
    payload = work / 'payload'
    payload.mkdir()
    for source in (args.installer.resolve(), args.portable.resolve()):
        if not source.is_file():
            raise SystemExit('Missing artifact: ' + str(source))
        target = work / source.name
        if target.exists():
            raise SystemExit('Artifact filenames must differ')
        shutil.copy2(source, target)
        # Detect a concurrent replacement rather than verifying mixed release bytes.
        original_hash = sha256(source)
        if sha256(target) != original_hash:
            raise SystemExit('Artifact changed while copying; retry after the other build finishes')
        artifacts.append(dict(name=source.name, path=str(source), bytes=target.stat().st_size, sha256=original_hash,
                              copy_path=str(target)))
    installer = Path(artifacts[0]['copy_path'])
    portable = Path(artifacts[1]['copy_path'])
    version = None
    executable_items = [dict(name='installer', path=str(installer))]
    try:
        with zipfile.ZipFile(portable) as archive:
            blockers.extend(inventory(archive))
            # Read only fixed root names and bounded executable sizes. No archive-controlled filesystem paths.
            for name in ('IndependentBooks.exe', 'app_server.exe'):
                if name in archive.namelist() and archive.getinfo(name).file_size <= MAX_ENTRY:
                    destination = payload / name
                    destination.write_bytes(archive.read(name))
                    executable_items.append(dict(name=name, path=str(destination)))
            if 'version.json' in archive.namelist() and archive.getinfo('version.json').file_size < 1024 * 1024:
                version = json.loads(archive.read('version.json').decode('utf-8-sig')).get('version')
    except (ValueError, zipfile.BadZipFile, OSError) as error:
        blockers.append('Archive inspection failed: ' + str(error))
    signatures = []
    try:
        signatures = inspect_signatures(executable_items, work)
        publishers = set()
        for signature in signatures:
            if signature['status'] != 'Valid':
                blockers.append(signature['name'] + ': Authenticode status ' + signature['status'])
            if not signature['timestamped']:
                blockers.append(signature['name'] + ': publisher timestamp missing')
            if signature['thumbprint']:
                publishers.add(signature['thumbprint'])
        if len(publishers) > 1:
            blockers.append('Own executables do not use a consistent publisher certificate; review signer identities')
    except Exception as error:
        blockers.append(str(error))
    scan = dict(requested=args.scan, completed=False)
    if args.scan:
        scanner = defender_path()
        if scanner is None:
            blockers.append('Microsoft Defender command-line scanner unavailable')
        else:
            try:
                result = subprocess.run([str(scanner), '-Scan', '-ScanType', '3', '-File', str(work), '-DisableRemediation'],
                                        capture_output=True, text=True, timeout=600)
                log = (result.stdout or '') + (result.stderr or '')
                (report_dir / 'defender-scan.txt').write_text(log, encoding='utf-8')
                scan.update(completed=True, exit_code=result.returncode, remediation_disabled=True,
                            no_threats_reported=result.returncode == 0 and 'found no threats' in log.casefold())
                if not scan['no_threats_reported']:
                    blockers.append('Defender did not explicitly report a successful no-threats scan; inspect log')
            except Exception as error:
                blockers.append('Defender scan did not complete: ' + str(error))
    else:
        blockers.append('Final artifact malware scan not requested/completed')
    for artifact in artifacts:
        if sha256(Path(artifact['path'])) != artifact['sha256']:
            blockers.append('Original artifact changed during inspection: ' + artifact['name'])
    report = dict(version=version, artifacts=artifacts, signatures=signatures, defender=scan,
                  blockers=blockers, artifact_gate_passed=not blockers,
                  chrome_verdict='NOT_VERIFIED', browser_warning_resolved=False,
                  note='Passing this gate is not a guarantee of Chrome acceptance or full application security.')
    (report_dir / 'release-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (report_dir / 'SHA256SUMS.txt').write_text(''.join(a['sha256']+'  '+a['name']+'\n' for a in artifacts), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if not blockers else 1


if __name__ == '__main__':
    sys.exit(main())
