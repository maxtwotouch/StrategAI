#!/usr/bin/env node
// Validates the locale resources in `locales/*.json`.
//
// `lib/i18n.ts` makes *missing* keys a compile error, but TypeScript cannot
// reject a key that only exists in the translated file, nor catch placeholder
// drift (`{turn}` vs `{turns}`), empty values, or a duplicate key silently
// overwriting an earlier one. This script covers those, and needs nothing
// beyond Node itself — no test framework, no dependencies.
//
// Usage: npm run check:i18n

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const LOCALES_DIR = join(ROOT, "locales");
const REFERENCE = "en";

/** Locales we ship, in the same order as LOCALES in lib/i18n.ts. */
const LOCALES = [REFERENCE, "zh-CN"];

const PLACEHOLDER = /\{(\w+)\}/g;

const problems = [];

function fail(message) {
  problems.push(message);
}

function readLocale(locale) {
  const path = join(LOCALES_DIR, `${locale}.json`);
  const raw = readFileSync(path, "utf8");

  let data;
  try {
    data = JSON.parse(raw);
  } catch (error) {
    fail(`locales/${locale}.json is not valid JSON: ${error.message}`);
    return null;
  }

  // JSON.parse keeps the last duplicate silently; check the raw text instead.
  const seen = new Set();
  for (const match of raw.matchAll(/^\s*"([^"]+)"\s*:/gm)) {
    const key = match[1];
    if (seen.has(key)) fail(`locales/${locale}.json has a duplicate key "${key}"`);
    seen.add(key);
  }

  return data;
}

function placeholders(value) {
  return new Set([...value.matchAll(PLACEHOLDER)].map((match) => match[1]));
}

const dictionaries = new Map();
for (const locale of LOCALES) {
  const data = readLocale(locale);
  if (data) dictionaries.set(locale, data);
}

const source = dictionaries.get(REFERENCE);
if (!source) {
  console.error(`Missing reference locale locales/${REFERENCE}.json`);
  process.exit(1);
}

if (Object.keys(source).length === 0) fail(`locales/${REFERENCE}.json is empty`);

for (const [locale, data] of dictionaries) {
  if (locale === REFERENCE) continue;

  const sourceKeys = Object.keys(source);
  const targetKeys = Object.keys(data);

  for (const key of sourceKeys) {
    if (!(key in data)) fail(`locales/${locale}.json is missing "${key}"`);
  }
  for (const key of targetKeys) {
    if (!(key in source)) fail(`locales/${locale}.json has an unknown key "${key}"`);
  }

  for (const key of sourceKeys) {
    if (!(key in data)) continue;
    const expected = placeholders(source[key]);
    const actual = placeholders(data[key]);
    for (const name of expected) {
      if (!actual.has(name)) {
        fail(`locales/${locale}.json "${key}" is missing placeholder {${name}}`);
      }
    }
    for (const name of actual) {
      if (!expected.has(name)) {
        fail(`locales/${locale}.json "${key}" has an unexpected placeholder {${name}}`);
      }
    }
  }
}

// Placeholder and content checks that apply to every locale, including English.
for (const [locale, data] of dictionaries) {
  for (const [key, value] of Object.entries(data)) {
    if (typeof value !== "string") {
      fail(`locales/${locale}.json "${key}" must be a string`);
      continue;
    }
    if (value.trim() === "") {
      fail(`locales/${locale}.json "${key}" is empty`);
    }
    // `interpolate()` only matches \w+, so anything else would be shipped as
    // literal text by accident.
    for (const match of value.matchAll(/\{([^}]*)\}/g)) {
      if (!/^\w+$/.test(match[1])) {
        fail(`locales/${locale}.json "${key}" has an unsupported placeholder "${match[0]}"`);
      }
    }
  }
}

if (problems.length > 0) {
  console.error(`i18n check failed (${problems.length} problem${problems.length === 1 ? "" : "s"}):`);
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}

const keyCount = Object.keys(source).length;
console.log(`i18n check passed: ${LOCALES.length} locales, ${keyCount} keys each.`);
