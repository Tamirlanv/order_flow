import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const binary = path.join(root, '.tmp/tools', process.platform === 'win32' ? 'gitleaks.exe' : 'gitleaks');
if (!fs.existsSync(binary)) throw new Error('Run scripts/install-gitleaks.ps1 first');
const git = args => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
if (git(['rev-parse', '--is-shallow-repository']) !== 'false')
  throw new Error('Full history required: fetch-depth: 0 / git fetch --unshallow');
const audit = path.join(root, '.tmp/security');
fs.mkdirSync(audit, { recursive: true });
const snapshot = fs.mkdtempSync(path.join(audit, 'worktree-'));
const scan = (mode, source, report) => {
  const result = spawnSync(binary, [mode, source, '--no-banner', '--redact=100',
    '--report-format=json', '--report-path=' + path.join(audit, report),
    ...(mode === 'git' ? ['--log-opts=--all'] : [])],
  { cwd: root, stdio: 'inherit' });
  if (result.error || result.status !== 0) throw new Error('Gitleaks ' + mode + ' failed; inspect redacted .tmp/security report');
};
try {
  // Index plus new non-ignored sources; local .env, private keys and dependencies stay out.
  const files = execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'],
    { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);
  for (const file of files) {
    const source = path.resolve(root, file);
    const target = path.resolve(snapshot, file);
    if (!source.startsWith(root + path.sep) || !target.startsWith(snapshot + path.sep))
      throw new Error('Unsafe export path');
    if (!fs.existsSync(source)) continue;
    if (!fs.lstatSync(source).isFile()) throw new Error('Review non-regular file before scanning: ' + file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(source, target);
  }
  scan('git', root, 'gitleaks-history.json');
  scan('dir', snapshot, 'gitleaks-worktree.json');
  console.log('Gitleaks PASS: all Git refs/history + ' + files.length + ' current source files; 0 findings');
} finally {
  if (path.dirname(snapshot) !== audit || !path.basename(snapshot).startsWith('worktree-'))
    throw new Error('Unsafe cleanup path');
  fs.rmSync(snapshot, { recursive: true, force: true });
}
