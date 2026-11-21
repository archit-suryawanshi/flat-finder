import { expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { parseArgs, parseFeet, parsePrice, search } from './flatfinder.mjs';

it('reads feet and prices', () => {
  expect(parseFeet("11'3")).toBe(11.25);
  expect(parseFeet('11.25')).toBe(11.25);
  expect(parsePrice('3cr')).toBe(3e7);
  expect(parsePrice('90L')).toBe(9e6);
});

it('searches a city file: 3 BHK in Pune under 2 Cr finds societies', () => {
  const city = JSON.parse(readFileSync(new URL('../web/public/data/pune.json', import.meta.url)));
  const rows = search(city, parseArgs(['--bhk', '3', '--max-price', '2cr']));
  expect(rows.length).toBeGreaterThan(10);
});

it('reads monthly rent', () => {
  expect(parsePrice('80k')).toBe(80000);
  expect(parseArgs(['--max-rent', '80k']).crit).toMatchObject({ mode: 'rent', maxRent: 80000 });
});
