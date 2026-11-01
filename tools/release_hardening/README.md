# IndependentBooks release checks

This directory is additive tooling from Codex. The checkout and separate landing-page directory are shared with Antigravity. Re-read current files and coordinate before rebuilding or deploying. Do not reset the other agent's changes or run concurrent builds against `dist`.

## Current findings

The 31 October 2026 revised Inno installer and portable ZIP scanned without threats in Microsoft Defender. Earlier IndependentBooks downloads have actual Defender detection records, including Wacatac, Qwexlafiba, Suschil and Wacapew names. Those historical detections do not prove the current artifacts are malicious or that they were false positives. Chrome's exact detection cause still needs verification.

The publisher has confirmed there is no code-signing setup. Checked installer, launcher and backend signatures are `NotSigned`. Do not create a self-signed certificate and claim a publicly trusted publisher. A certificate/signing service must verify the legitimate publisher, and signing still does not guarantee Google's verdict.

## Inspect the exact package

Run from the repository with an existing Python interpreter:

```powershell
python .\tools\release_hardening\verify_release.py `
  --installer .\dist\IndependentBooksSetup.exe `
  --portable .\dist\IndependentBooks_Portable.zip `
  --report-dir C:\path\to\a-new-private-report-folder `
  --scan
```

The directory must be new/empty and outside the public website. It contains private inspection copies, JSON results, checksums and the Defender log. Inspection never launches the installer or disables antivirus. Defender's `-DisableRemediation` option disables cleanup actions for that custom scan; protections remain enabled.

The checker rejects archive traversal/duplicate paths, customer databases/key material, legacy scripts in the native customer package, missing notices, unsupported Python/OpenSSL libraries, missing/invalid publisher signatures and timestamps, and an incomplete malware scan. `artifact_gate_passed` is an artifact-policy result, not a complete security assessment or a Google Chrome verdict.

Run policy regression tests:

```powershell
python .\tools\release_hardening\test_verify_release.py
```

## Finish the signing and publishing workflow

1. Provision a legitimate publicly trusted code-signing identity using a CA or supported hosted signing service. Keep its key in protected storage; do not commit/export it or paste credentials into chat.
2. Rebuild the backend from reviewed source with a supported Python/OpenSSL runtime. Do not merely relabel existing Python 3.9 DLLs.
3. Sign and timestamp `app_server.exe` and `IndependentBooks.exe` before packaging. Configure Inno Setup to sign the generated uninstaller. Build with Inno Setup, then verify the final installer's signature/timestamp as well.
4. Run this checker and clean-machine install/upgrade/uninstall tests against the exact final artifacts. Review third-party notices, not only the project's own license.
5. Publish immutable versioned artifacts with checksums calculated after signing. Keep metadata, download links and actual bytes consistent. Do not overwrite the same version repeatedly.
6. Check the site's Google Search Console Security issues report and request review of a remediated, verified artifact if the harmful-download warning persists. Prepare the evidence first. Do not assert that unsigned status or a script extension is automatically the cause.

When replacing a file at a mutable download URL, purge that exact custom-domain URL (including active query variants and the release manifest) from Cloudflare's cache. Verify HTTP status, redirect chain, size and SHA-256 on the public URL afterward. On 31 October a stale cached 302 still pointed the plain portable ZIP URL at an unavailable GitHub release even though the Pages origin and versioned URL served the new file. A targeted cache purge restored direct HTTP 200 delivery. This is separate from Google's dangerous-download classification; do not claim that purging the CDN clears that verdict.

The publisher can configure Windows SDK SignTool or their provider's signing client. No private signing key, certificate or publisher identity is created by this tooling.

## Changes to the existing builder

The builder now also creates `IndependentBooks_Installer.zip` **after** Inno Setup succeeds. This archive contains exactly one file: the complete setup EXE selected with `-OutputExe`. It verifies the inner file's SHA-256 against the built installer and writes `INSTALLER-SHA256SUMS.txt`. Do not zip only `IndependentBooks.exe`: that file is a launcher and needs the backend and its libraries. The installer archive is not a portable application and must not be labelled “extract and run without installation.” A ZIP wrapper does not establish Chrome acceptance.

The application's engine version remains 1.1.0 for packaging revision 2. The website's `download_installer_zip` field explicitly identifies the one-EXE archive; the older `download_zip` field retains its legacy portable-package meaning for compatibility. Immutable release assets use `downloads/releases/1.1.0-r2/`.

The small Codex preflight addition requires native backend output and Inno Setup before `dist` cleanup, preventing use of the legacy self-extracting installer fallback. It restricts cleanup to named `dist` child directories, checks matching backend/manifest versions, stops on native tool failures, includes the project license, and restores the per-user installer privilege setting. It preserves Antigravity's script removal, module trimming and native launcher work.

Use a separate, previously unused output such as `dist-codex-check` while another agent owns `dist`. The native backend must be freshly reviewed/rebuilt before a real release. Packaging alone does not resolve the security/correctness issues in the separate audit.
