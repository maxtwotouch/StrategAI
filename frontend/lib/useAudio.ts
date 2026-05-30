"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Drop two MP3/OGG/WAV files into frontend/public/audio/ and the hook picks
// them up. Missing files are tolerated — audio.play() rejects silently and
// the game continues without sound.
const INTRO_SRC = "/audio/intro.mp3";
const AMBIENT_SRC = "/audio/ambient.mp3";

// Volume targets and crossfade duration. Tweak here.
const INTRO_VOLUME = 0.6;
const AMBIENT_VOLUME = 0.22;
const INTRO_FADE_IN_MS = 1200;
const CROSSFADE_MS = 2400;

const MUTE_KEY = "inf3600:audioMuted";

type Phase = "silent" | "intro" | "ambient";

export interface UseAudio {
  muted: boolean;
  toggleMute: () => void;
  /** Call from the user gesture that begins the session (Begin Campaign). */
  startIntro: () => void;
  /** Call when the intro is dismissed — crossfades intro → ambient. */
  startAmbient: () => void;
}

function rampVolume(
  audio: HTMLAudioElement,
  to: number,
  ms: number,
  onComplete?: () => void,
): void {
  const from = audio.volume;
  const start = performance.now();
  const step = (now: number) => {
    const t = ms > 0 ? Math.min(1, (now - start) / ms) : 1;
    // Clamp to [0, 1] — overlapping ramps (intro fading out while ambient
    // fades in on the same element after a fast user action) or float drift
    // can otherwise produce a tiny negative that HTMLMediaElement rejects
    // with IndexSizeError.
    const next = from + (to - from) * t;
    audio.volume = next < 0 ? 0 : next > 1 ? 1 : next;
    if (t < 1) {
      requestAnimationFrame(step);
    } else {
      onComplete?.();
    }
  };
  requestAnimationFrame(step);
}

export function useAudio(): UseAudio {
  const introRef = useRef<HTMLAudioElement | null>(null);
  const ambientRef = useRef<HTMLAudioElement | null>(null);
  const phaseRef = useRef<Phase>("silent");
  const [muted, setMuted] = useState(false);

  // Hydrate persisted mute preference once on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      setMuted(window.localStorage.getItem(MUTE_KEY) === "1");
    } catch {
      // localStorage unavailable — keep default (unmuted).
    }
  }, []);

  // Apply mute changes to live audio elements + persist.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    } catch {
      // ignore
    }
    if (introRef.current) introRef.current.muted = muted;
    if (ambientRef.current) ambientRef.current.muted = muted;
  }, [muted]);

  // Pause everything on unmount so HMR + navigation don't leak playback.
  useEffect(() => {
    return () => {
      introRef.current?.pause();
      ambientRef.current?.pause();
    };
  }, []);

  const ensureAudio = useCallback(() => {
    if (typeof window === "undefined") return;
    if (!introRef.current) {
      const intro = new Audio(INTRO_SRC);
      intro.preload = "auto";
      intro.loop = true;
      intro.volume = 0;
      intro.muted = muted;
      introRef.current = intro;
    }
    if (!ambientRef.current) {
      const ambient = new Audio(AMBIENT_SRC);
      ambient.preload = "auto";
      ambient.loop = true;
      ambient.volume = 0;
      ambient.muted = muted;
      ambientRef.current = ambient;
    }
  }, [muted]);

  const startIntro = useCallback(() => {
    if (phaseRef.current !== "silent") return;
    phaseRef.current = "intro";
    ensureAudio();
    const intro = introRef.current;
    if (!intro) return;
    intro.volume = 0;
    // Reject is fine — missing file, autoplay denial, etc. Silence preserved.
    intro.play().catch(() => {});
    rampVolume(intro, INTRO_VOLUME, INTRO_FADE_IN_MS);
  }, [ensureAudio]);

  const startAmbient = useCallback(() => {
    if (phaseRef.current === "ambient") return;
    phaseRef.current = "ambient";
    ensureAudio();
    const intro = introRef.current;
    const ambient = ambientRef.current;
    if (!ambient) return;
    if (intro) {
      rampVolume(intro, 0, CROSSFADE_MS, () => {
        intro.pause();
        intro.currentTime = 0;
      });
    }
    ambient.volume = 0;
    ambient.play().catch(() => {});
    rampVolume(ambient, AMBIENT_VOLUME, CROSSFADE_MS);
  }, [ensureAudio]);

  const toggleMute = useCallback(() => setMuted((m) => !m), []);

  return { muted, toggleMute, startIntro, startAmbient };
}
