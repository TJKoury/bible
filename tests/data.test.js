import test from 'node:test';
import assert from 'node:assert/strict';
import { parseReference, referenceLabel, inverseMapping, nativeToEnglish } from '../src/lib/data.js';

const books = [{ id: 43, name: 'John' }, { id: 19, name: 'Psalms' }, { id: 62, name: '1 John' }];

test('reference parsing distinguishes numbered books and defaults to verse one', () => {
  assert.deepEqual(parseReference('1 John 3:16', books), { book: 62, chapter: 3, verse: 16 });
  assert.deepEqual(parseReference('Psalm 23', books), { book: 19, chapter: 23, verse: 1 });
  assert.equal(parseReference('in the beginning', books), null);
  assert.equal(referenceLabel('43.1.1', books), 'John 1:1');
});

test('inverse mapping keeps multiple English coordinates and unmapped references', () => {
  const inverse = inverseMapping({ '19.51.0': ['19.51.1', '19.51.2'], '19.51.1': ['19.51.3'], '19.51.2': ['19.51.3'] });
  assert.deepEqual(nativeToEnglish('19.51.3', inverse), ['19.51.1', '19.51.2']);
  assert.deepEqual(nativeToEnglish('1.1.1', inverse), ['1.1.1']);
});
