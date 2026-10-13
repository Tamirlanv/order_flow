import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pythonPins, npmPins, verifyPackage } from './check-dependencies.mjs';

test('Python locks include extras/markers and reject unpinned or URL dependencies', () => {
  assert.deepEqual(pythonPins('# comment\ncoverage[toml]==7.0.0 ; sys_platform == "win32"'),
    [{ name: 'coverage', version: '7.0.0' }]);
  for (const text of ['requests', 'requests>=2', '-e ../other', 'git+https://example.com/repo', ''])
    assert.throws(() => pythonPins(text));
});
test('npm covers scoped, nested, optional and aliased packages; rejects external sources', () => {
  const item = { version: '1.0.0', integrity: 'sha512-example', resolved: 'https://registry.npmjs.org/p/-/p.tgz' };
  const pins = npmPins({ lockfileVersion: 3, packages: {
    '': {}, 'node_modules/@scope/p': { ...item, optional: true },
    'node_modules/parent/node_modules/p': item, 'node_modules/alias': { ...item, name: 'real' },
  } });
  assert.deepEqual(pins.map(pin => pin.name), ['@scope/p', 'p', 'real']);
  assert.throws(() => npmPins({ lockfileVersion: 3, packages: {
    'node_modules/p': { ...item, resolved: 'https://attacker.example/p.tgz' },
  } }));
});
test('missing packages, network failures and mismatched registry metadata fail closed', async () => {
  const pin = { name: 'example', version: '1.0.0' };
  await assert.rejects(verifyPackage('pypi', pin, async () => new Response('', { status: 404 })));
  await assert.rejects(verifyPackage('pypi', pin, async () => { throw new Error('offline'); }));
  await assert.rejects(verifyPackage('pypi', pin, async () => Response.json({ info: pin, urls: [] })));
  await verifyPackage('pypi', pin, async () => Response.json({ info: pin, urls: [{ yanked: false }] }));
  await assert.rejects(verifyPackage('npm', { ...pin, integrity: 'sha512-a', resolved: 'https://registry.npmjs.org/a' },
    async () => Response.json({ ...pin, dist: { integrity: 'sha512-b' } })));
});
