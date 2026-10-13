import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// User-supplied reference documents intentionally remain untouched and untracked.
const ignored = new Set(['DESIGN.md', 'README_example.md']);
const files = ['README.md', 'AGENTS.md'];
for (const directory of ['docs', 'docs/features']) {
  files.push(...fs.readdirSync(path.join(root, directory))
    .filter(name => name.endsWith('.md') && !ignored.has(name))
    .map(name => `${directory}/${name}`));
}
const errors = [];
for (const file of files) {
  const text = fs.readFileSync(path.join(root, file), 'utf8');
  if (text.includes('\uFFFD')) errors.push(`${file}: invalid UTF-8 replacement character`);
  if ((text.match(/^```/gm) ?? []).length % 2) errors.push(`${file}: unclosed code fence`);
  const links = [...text.matchAll(/\[[^\]]*\]\(([^)]+)\)/g), ...text.matchAll(/(?:src|href)="([^"]+)"/g)];
  for (const [, link] of links) {
    if (/^(?:https?:|#)/.test(link)) continue;
    const target = path.resolve(root, path.dirname(file), link.split('#')[0]);
    if (!fs.existsSync(target)) errors.push(`${file}: missing ${link}`);
  }
}
if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`Documentation links and formatting: ${files.length} files passed`);
