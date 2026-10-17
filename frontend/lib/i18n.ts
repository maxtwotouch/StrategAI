// Lightweight i18n for StrategAI.
//
// Two locale dictionaries live in `locales/*.json` as flat, dotted keys
// (`game.endTurn`-style) so they diff cleanly and stay independent of the
// components that use them. English is the canonical source of truth: its key
// set *is* `TranslationKey`, and `zh-CN` is typed as a complete map over that
// union, so a *missing* translation fails `npm run typecheck` instead of
// silently falling back at runtime. TypeScript cannot reject a key that only
// exists in the translated file, so `scripts/check-i18n.mjs` reports those.
//
// There is no external dependency — the runtime is the handful of pure
// functions below plus the `useI18n` hook. Locale selection is client-side only
// (no URL routing); the choice persists in localStorage so it survives a reload.

import { useCallback, useEffect, useMemo, useState } from "react";

import en from "@/locales/en.json";
import zhCN from "@/locales/zh-CN.json";

/** Locales the UI ships with. The first entry is the default. */
export const LOCALES = ["en", "zh-CN"] as const;
export type Locale = (typeof LOCALES)[number];

/** English stays the default so existing players see no change. */
export const DEFAULT_LOCALE: Locale = "en";

/** Same `inf3600:` prefix the audio and cinematic preferences use. */
export const LOCALE_STORAGE_KEY = "inf3600:locale";

/**
 * Language names are shown in their own language, as is i18n convention, so
 * they are intentionally *not* part of the translation dictionaries.
 */
export const LOCALE_LABELS: Record<Locale, { short: string; name: string }> = {
  en: { short: "EN", name: "English" },
  "zh-CN": { short: "中文", name: "简体中文" },
};

/** Every translatable string, derived from the English dictionary. */
export type TranslationKey = keyof typeof en;

/**
 * A parameter carrying a game enum id (unit type, tech id, …) that is
 * translated at render time, so sentences stay correct after a language switch.
 */
export type EnumParam = { ns: string; value: string };
export type TranslateParams = Record<string, string | number | EnumParam>;

export type TFunction = (key: TranslationKey, params?: TranslateParams) => string;

// A missing key is the compile error above; a *stray* key is structurally
// allowed by TypeScript for an imported JSON module, so `npm run check:i18n`
// is what flags it.
const DICTIONARIES: Record<Locale, Record<TranslationKey, string>> = {
  en,
  "zh-CN": zhCN,
};

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "en" || value === "zh-CN";
}

/** `bronze_working` → `Bronze working`; used when a key has no translation yet. */
export function humanizeEnum(value: string): string {
  if (!value) return "";
  const spaced = value.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** English fallback → raw key, so a typo degrades instead of blanking the UI. */
function templateFor(locale: Locale, key: TranslationKey): string {
  return DICTIONARIES[locale]?.[key] ?? en[key] ?? key;
}

function interpolate(template: string, values?: Record<string, string | number>): string {
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name)
      ? String(values[name])
      : placeholder,
  );
}

/**
 * Translator for a data-driven label such as a unit type or tech id, with a
 * useful fallback for values the dictionaries do not know (e.g. a unit type
 * added on the backend but not yet translated).
 */
export function translateEnum(
  locale: Locale,
  namespace: string,
  value: string | null | undefined,
  suffix?: string,
): string {
  if (!value) return "";
  const key = (suffix ? `${namespace}.${value}.${suffix}` : `${namespace}.${value}`) as TranslationKey;
  const template = DICTIONARIES[locale]?.[key] ?? en[key];
  return template ?? humanizeEnum(value);
}

export function translate(
  locale: Locale,
  key: TranslationKey,
  params?: TranslateParams,
): string {
  const template = templateFor(locale, key);
  if (!params) return template;
  const values: Record<string, string | number> = {};
  for (const [name, value] of Object.entries(params)) {
    values[name] =
      typeof value === "object" && value !== null
        ? translateEnum(locale, value.ns, value.value)
        : value;
  }
  return interpolate(template, values);
}

/**
 * Count-dependent strings use a `<base>.one` / `<base>.other` key pair, which
 * keeps English pluralisation readable without pulling in an ICU formatter.
 * Chinese uses the same text for both forms.
 */
export type PluralBase = "city.count" | "map.unread" | "selection.workOrder";

export function translatePlural(
  locale: Locale,
  base: PluralBase,
  count: number,
  params?: TranslateParams,
): string {
  const form = count === 1 ? "one" : "other";
  return translate(locale, `${base}.${form}` as TranslationKey, {
    ...params,
    count,
  });
}

export function createTranslator(locale: Locale): TFunction {
  return (key, params) => translate(locale, key, params);
}

/** localStorage may be unavailable (private mode, SSR); read defensively. */
export function readStoredLocale(): Locale | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return isLocale(stored) ? stored : null;
  } catch {
    return null;
  }
}

export interface I18n {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  /** Translate a static key; `{param}` placeholders are interpolated. */
  t: TFunction;
  /** Translate a data-driven label, e.g. `tEnum("unit", unit.type)`. */
  tEnum: (namespace: string, value: string | null | undefined, suffix?: string) => string;
  /** Translate a `<base>.one` / `<base>.other` pair by count. */
  tPlural: (base: PluralBase, count: number, params?: TranslateParams) => string;
}

/**
 * Locale state for the game page. The persisted choice is restored in an
 * effect rather than during render so the server-rendered markup and the first
 * client render agree (no hydration mismatch); the swap happens on the next
 * frame.
 */
export function useI18n(): I18n {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = readStoredLocale();
    if (stored) setLocaleState(stored);
  }, []);

  // Keep <html lang> in step for screen readers and CJK font selection.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // Persisting is best-effort; the session still switches.
    }
  }, []);

  const t = useMemo(() => createTranslator(locale), [locale]);

  const tEnum = useCallback(
    (namespace: string, value: string | null | undefined, suffix?: string) =>
      translateEnum(locale, namespace, value, suffix),
    [locale],
  );

  const tPlural = useCallback(
    (base: PluralBase, count: number, params?: TranslateParams) =>
      translatePlural(locale, base, count, params),
    [locale],
  );

  return { locale, setLocale, t, tEnum, tPlural };
}
