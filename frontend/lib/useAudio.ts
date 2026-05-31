"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Drop MP3/OGG/WAV files into frontend/public/audio/ and the hook picks them
// up. Missing files are tolerated — audio.play() rejects silently and the game
// continues without sound.
const MUSIC_TRACKS = [
  "/audio/ambient.mp3",
  "/audio/bards-tale.mp3",
  "/audio/medieval-battle.mp3",
];

// Volume targets and crossfade duration. Tweak here.
const INTRO_VOLUME = 0.6;
const AMBIENT_VOLUME = 0.22;
const NARRATION_DUCK_VOLUME = 0.18;
const INTRO_FADE_IN_MS = 1200;
const NARRATION_DUCK_MS = 650;
const CROSSFADE_MS = 2400;

const MUTE_KEY = "inf3600:audioMuted";

type Phase = "silent" | "intro" | "ambient";

export interface UseAudio {
  muted: boolean;
  toggleMute: () => void;
  /** Call from the user gesture that begins the session (Begin Campaign). */
  startIntro: () => void;
  /** Play generated campaign narration over the current intro music. */
  playNarration: (src: string) => void;
  /** Stop any active spoken intro. */
  stopNarration: () => void;
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
  const musicRef = useRef<HTMLAudioElement | null>(null);
  const narrationRef = useRef<HTMLAudioElement | null>(null);
  const phaseRef = useRef<Phase>("silent");
  const trackIndexRef = useRef(0);
  const targetVolumeRef = useRef(INTRO_VOLUME);
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
    if (musicRef.current) musicRef.current.muted = muted;
    if (narrationRef.current) narrationRef.current.muted = muted;
  }, [muted]);

  // Pause everything on unmount so HMR + navigation don't leak playback.
  useEffect(() => {
    return () => {
      narrationRef.current?.pause();
      musicRef.current?.pause();
    };
  }, []);

  const restoreTargetVolume = useCallback(() => {
    const music = musicRef.current;
    if (!music) return;
    rampVolume(music, targetVolumeRef.current, NARRATION_DUCK_MS);
  }, []);

  const stopNarration = useCallback(() => {
    if (typeof window === "undefined") return;
    const narration = narrationRef.current;
    if (narration) {
      narration.pause();
      narration.src = "";
      narrationRef.current = null;
    }
    restoreTargetVolume();
  }, [restoreTargetVolume]);

  const ensureAudio = useCallback(() => {
    if (typeof window === "undefined") return;
    if (musicRef.current) return;
    const music = new Audio(MUSIC_TRACKS[0]);
    music.preload = "auto";
    music.loop = false;
    music.volume = 0;
    music.muted = muted;
    music.addEventListener("ended", () => {
      if (phaseRef.current === "silent") return;
      const nextIndex = (trackIndexRef.current + 1) % MUSIC_TRACKS.length;
      trackIndexRef.current = nextIndex;
      music.src = MUSIC_TRACKS[nextIndex];
      music.currentTime = 0;
      music.volume = targetVolumeRef.current;
      music.play().catch(() => {});
    });
    musicRef.current = music;
  }, [muted]);

  const startIntro = useCallback(() => {
    if (phaseRef.current !== "silent") return;
    phaseRef.current = "intro";
    targetVolumeRef.current = INTRO_VOLUME;
    trackIndexRef.current = 0;
    ensureAudio();
    const music = musicRef.current;
    if (!music) return;
    music.src = MUSIC_TRACKS[0];
    music.currentTime = 0;
    music.volume = 0;
    // Reject is fine — missing file, autoplay denial, etc. Silence preserved.
    music.play().catch(() => {});
    rampVolume(music, INTRO_VOLUME, INTRO_FADE_IN_MS);
  }, [ensureAudio]);

  const playNarration = useCallback(
    (src: string) => {
      if (typeof window === "undefined" || muted || !src) return;
      stopNarration();
      const narration = new Audio(src);
      narration.preload = "auto";
      narration.volume = 1;
      narration.muted = muted;
      narration.addEventListener("play", () => {
        const music = musicRef.current;
        if (music) rampVolume(music, NARRATION_DUCK_VOLUME, NARRATION_DUCK_MS);
      });
      narration.addEventListener("ended", restoreTargetVolume);
      narration.addEventListener("error", restoreTargetVolume);
      narrationRef.current = narration;
      narration.play().catch(() => restoreTargetVolume());
    },
    [muted, restoreTargetVolume, stopNarration],
  );

  const startAmbient = useCallback(() => {
    if (phaseRef.current === "ambient") return;
    stopNarration();
    phaseRef.current = "ambient";
    targetVolumeRef.current = AMBIENT_VOLUME;
    ensureAudio();
    const music = musicRef.current;
    if (!music) return;
    if (music.paused) music.play().catch(() => {});
    rampVolume(music, AMBIENT_VOLUME, CROSSFADE_MS);
  }, [ensureAudio, stopNarration]);

  const toggleMute = useCallback(() => setMuted((m) => !m), []);

  return { muted, toggleMute, startIntro, playNarration, stopNarration, startAmbient };
}
