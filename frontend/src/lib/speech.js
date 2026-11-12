// Browser speech adapters. Thin wrappers around Web Speech API, MediaRecorder and
// speechSynthesis; the decisions (texts, chunks, engine choice) live in voice.js.
// Privacy: audio only lives in memory until it is transcribed, then it is dropped.

import { MAX_RECORDING_S, SILENCE_STOP_S, speechChunks, rateValue } from './voice.js';

const w = typeof window !== 'undefined' ? window : {};

export function speechSupport() {
  const SR = w.SpeechRecognition || w.webkitSpeechRecognition;
  return {
    hasSpeechRecognition: Boolean(SR),
    hasMediaRecorder: Boolean(w.MediaRecorder && w.navigator?.mediaDevices?.getUserMedia),
    hasSynthesis: Boolean(w.speechSynthesis && w.SpeechSynthesisUtterance),
    secure: w.isSecureContext !== false,
  };
}

/**
 * Option B: the browser's recognizer, with live text ("Lo que voy entendiendo").
 * Stops by itself after 3 s of silence once something was heard, or after 60 s.
 */
export function startBrowserRecognition({ lang = 'es-ES', onInterim, onEnd }) {
  const SR = w.SpeechRecognition || w.webkitSpeechRecognition;
  const rec = new SR();
  rec.lang = lang;
  rec.continuous = true;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  let finalText = '';
  let interim = '';
  let error = null;
  let cancelled = false;
  let silenceTimer = null;
  const maxTimer = setTimeout(() => rec.stop(), MAX_RECORDING_S * 1000);

  const armSilence = () => {
    clearTimeout(silenceTimer);
    silenceTimer = setTimeout(() => rec.stop(), SILENCE_STOP_S * 1000);
  };

  rec.onresult = (e) => {
    interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText = `${finalText} ${r[0].transcript}`.trim();
      else interim += r[0].transcript;
    }
    onInterim?.(`${finalText} ${interim}`.trim());
    armSilence();
  };
  rec.onerror = (e) => { if (e.error !== 'aborted') error = e.error; };
  rec.onend = () => {
    clearTimeout(silenceTimer);
    clearTimeout(maxTimer);
    if (cancelled) return;
    const text = `${finalText} ${interim}`.trim();
    onEnd?.(text ? { text } : { error: error ?? 'no-speech' });
  };

  try {
    rec.start();
  } catch {
    setTimeout(() => onEnd?.({ error: 'failed' }), 0);
  }

  return {
    stop: () => rec.stop(),
    cancel: () => { cancelled = true; rec.abort(); },
  };
}

function pickMime() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
  return types.find((t) => w.MediaRecorder?.isTypeSupported?.(t)) ?? '';
}

/**
 * Option A: record and send to POST /api/transcribe (Groq Whisper).
 * `transcribe(blob)` is injected so mock mode can fake it.
 */
export function startServerRecording({ transcribe, onState, onEnd }) {
  let cancelled = false;
  let stream = null;
  let recorder = null;
  let audioCtx = null;
  let silenceTimer = null;
  let maxTimer = null;
  let levelTimer = null;
  let heard = false;
  const chunks = [];

  const cleanup = () => {
    clearTimeout(silenceTimer);
    clearTimeout(maxTimer);
    clearInterval(levelTimer);
    stream?.getTracks().forEach((t) => t.stop());
    audioCtx?.close?.().catch(() => {});
  };

  const stop = () => { if (recorder?.state === 'recording') recorder.stop(); };

  w.navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    .then((s) => {
      if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; }
      stream = s;
      const mimeType = pickMime();
      recorder = new w.MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorder.ondataavailable = (e) => { if (e.data?.size) chunks.push(e.data); };
      recorder.onstop = async () => {
        cleanup();
        if (cancelled) return;
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        chunks.length = 0;
        if (blob.size < 1200) { onEnd?.({ error: 'no-speech' }); return; }
        onState?.('transcribing');
        try {
          const text = await transcribe(blob);
          onEnd?.({ text });
        } catch (err) {
          onEnd?.({ error: err?.kind === 'empty' ? 'no-speech' : 'failed', detail: err });
        }
      };
      recorder.start(250);
      onState?.('listening');
      maxTimer = setTimeout(stop, MAX_RECORDING_S * 1000);

      // Silence detection: stop 3 s after the last sound, once the person has spoken.
      try {
        const Ctx = w.AudioContext || w.webkitAudioContext;
        audioCtx = new Ctx();
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        audioCtx.createMediaStreamSource(stream).connect(analyser);
        const data = new Uint8Array(analyser.fftSize);
        levelTimer = setInterval(() => {
          analyser.getByteTimeDomainData(data);
          let sum = 0;
          for (const v of data) sum += ((v - 128) / 128) ** 2;
          const rms = Math.sqrt(sum / data.length);
          if (rms > 0.03) {
            heard = true;
            clearTimeout(silenceTimer);
            silenceTimer = null;
          } else if (heard && !silenceTimer) {
            silenceTimer = setTimeout(stop, SILENCE_STOP_S * 1000);
          }
        }, 120);
      } catch { /* silence detection is optional */ }
    })
    .catch((err) => { cleanup(); if (!cancelled) onEnd?.({ error: err?.name || 'failed' }); });

  return {
    stop,
    cancel: () => { cancelled = true; stop(); cleanup(); },
  };
}

/** Reads text aloud with a Spanish system voice. Returns a handle to stop it. */
export function speak(text, { rate = 'normal', lang = 'es-ES', onEnd } = {}) {
  const synth = w.speechSynthesis;
  if (!synth || !w.SpeechSynthesisUtterance) { onEnd?.(); return { stop() {} }; }
  synth.cancel();
  const voices = synth.getVoices();
  const voice = voices.find((v) => v.lang === lang) ?? voices.find((v) => v.lang?.startsWith('es'));
  const parts = speechChunks(text);
  let stopped = false;
  let i = 0;
  // Chrome stops long speech after ~15 s unless it is nudged; resume() keeps it going.
  const keepAlive = setInterval(() => { if (synth.speaking && !synth.paused) synth.resume(); }, 10_000);

  const finish = () => { clearInterval(keepAlive); onEnd?.(); };
  const next = () => {
    if (stopped) return;
    if (i >= parts.length) { finish(); return; }
    const u = new w.SpeechSynthesisUtterance(parts[i++]);
    u.lang = lang;
    if (voice) u.voice = voice;
    u.rate = rateValue(rate);
    u.onend = next;
    u.onerror = (e) => { if (e.error === 'interrupted' || e.error === 'canceled') return; next(); };
    synth.speak(u);
  };
  next();
  return {
    stop: () => { stopped = true; clearInterval(keepAlive); synth.cancel(); onEnd?.(); },
  };
}
