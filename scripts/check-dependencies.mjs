import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export function pythonPins(text) {
  const pins = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const match = /^([a-z0-9_.-]+)(?:\[[a-z0-9_,.-]+\])?==([a-z0-9_.+!-]+)(?:\s*;.+)?$/i.exec(line);
    if (!match) throw new Error('Unsupported/unpinned Python requirement');
    pins.push({ name: match[1], version: match[2] });
  }
  if (!pins.length) throw new Error('Empty Python lock');
  return pins;
}

export function npmPins(lock) {
  if (lock.lockfileVersion !== 3 || !lock.packages) throw new Error('Expected npm lock v3');
  const pins = [];
  for (const [location, pkg] of Object.entries(lock.packages)) {
    if (!location) continue;
    const name = pkg.name ?? location.split('node_modules/').at(-1);
    if (!name || !pkg.version || !pkg.integrity || !pkg.resolved ||
        !pkg.resolved.startsWith('https://registry.npmjs.org/')) {
      throw new Error('Non-registry, unpinned or unverifiable npm package');
    }
    pins.push({ name, version: pkg.version, integrity: pkg.integrity, resolved: pkg.resolved });
  }
  if (!pins.length) throw new Error('Empty npm lock');
  return pins;
}

export async function verifyPackage(registry, pin, fetcher = fetch) {
  const name = encodeURIComponent(pin.name);
  const version = encodeURIComponent(pin.version);
  const url = registry === 'pypi' ? 'https://pypi.org/pypi/' + name + '/' + version + '/json'
    : 'https://registry.npmjs.org/' + name + '/' + version;
  const response = await fetcher(url, { signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw new Error(registry + ': ' + pin.name + '@' + pin.version + ' HTTP ' + response.status);
  const body = await response.json();
  const normalized = value => value.toLowerCase().replace(/[-_.]+/g, '-');
  if (registry === 'pypi') {
    if (normalized(body.info?.name ?? '') !== normalized(pin.name) ||
        body.info?.version !== pin.version || !body.urls?.length ||
        body.urls.every(file => file.yanked)) throw new Error('Missing/mismatched/yanked PyPI release: ' + pin.name);
  } else if (body.name !== pin.name || body.version !== pin.version ||
      body.dist?.integrity !== pin.integrity || body.dist?.tarball !== pin.resolved) {
    throw new Error('Registry name/version/integrity/tarball mismatch: ' + pin.name);
  }
}

async function main() {
  const unique = pins => [...new Map(pins.map(pin => [JSON.stringify(pin), pin])).values()];
  const python = unique(['requirements.lock', 'requirements-dev.lock'].flatMap(file =>
    pythonPins(fs.readFileSync(path.join(root, 'backend', file), 'utf8'))));
  const npm = unique(npmPins(JSON.parse(fs.readFileSync(path.join(root, 'frontend/package-lock.json'), 'utf8'))));
  for (const file of ['requirements.in', 'requirements-dev.in']) {
    for (const line of fs.readFileSync(path.join(root, 'backend', file), 'utf8').split(/\r?\n/)) {
      if (!line.trim() || line.trim().startsWith('#') || line.trim() === '-r requirements.in') continue;
      const name = /^([a-z0-9_.-]+)(?:\[.*?\])?(?:[<>=!~].*)?$/i.exec(line)?.[1];
      if (!name || !python.some(pin => pin.name === name)) throw new Error('Python input missing from lock');
    }
  }
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'frontend/package.json'), 'utf8'));
  for (const name of Object.keys({ ...manifest.dependencies, ...manifest.devDependencies })) {
    if (!npm.some(pin => pin.name === name)) throw new Error('npm manifest dependency missing from lock: ' + name);
  }
  const queue = [...python.map(pin => ['pypi', pin]), ...npm.map(pin => ['npm', pin])];
  const errors = [];
  await Promise.all(Array.from({ length: 6 }, async () => {
    while (queue.length) {
      const [registry, pin] = queue.shift();
      try { await verifyPackage(registry, pin); } catch (error) { errors.push(error.message); }
    }
  }));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('PyPI: ' + python.length + ' exact releases verified');
  console.log('npm: ' + npm.length + ' exact releases, tarballs and integrity verified');
  console.log('Dependency registry check: PASS (existence is not a malware/security guarantee)');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
