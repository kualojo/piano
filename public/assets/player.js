/* Plays the notes read from the sheet and draws them as a piano roll, with letter names.
   Red = right hand, blue = left hand, square = flat, circle = sharp (same as the PDF). */
(() => {
  const root = document.getElementById('player');
  if (!root) return;
  const canvas = root.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  const statusEl = root.querySelector('.status');
  const playBtn = root.querySelector('[data-act=play]');
  const speedEl = root.querySelector('[data-act=speed]');
  const COLORS = { R: '#cc0000', L: '#0033d9' };
  const BLACK = new Set([1, 3, 6, 8, 10]);
  const KEYS_W = 64, PX_PER_BEAT = 70, PLAYHEAD = KEYS_W + 90;
  let data = null, piano = null, part = null, endBeat = 0, lo = 48, hi = 84, H = 320;
  const hands = { R: true, L: true };
  const active = new Map();   // midi -> hand, for lighting keys

  const say = (t) => { statusEl.textContent = t; };

  function makePiano() {
    return new Promise((resolve) => {
      const urls = {};
      ['A0', 'C1', 'D#1', 'F#1', 'A1', 'C2', 'D#2', 'F#2', 'A2', 'C3', 'D#3', 'F#3', 'A3', 'C4', 'D#4', 'F#4', 'A4',
        'C5', 'D#5', 'F#5', 'A5', 'C6', 'D#6', 'F#6', 'A6', 'C7', 'D#7', 'F#7', 'A7', 'C8']
        .forEach((n) => { urls[n] = n.replace('#', 's') + '.mp3'; });
      let done = false;
      const fallback = () => {
        if (done) return; done = true;
        resolve(new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'triangle' },
          envelope: { attack: 0.005, decay: 0.4, sustain: 0.2, release: 0.8 } }).toDestination());
      };
      const s = new Tone.Sampler({ urls, release: 1, baseUrl: 'https://tonejs.github.io/audio/salamander/',
        onload: () => { if (!done) { done = true; resolve(s.toDestination()); } }, onerror: fallback });
      setTimeout(fallback, 6000);
    });
  }

  function resize() {
    const w = root.clientWidth;
    canvas.width = w * devicePixelRatio;
    H = Math.min(Math.max((hi - lo + 1) * 13, 240), 640);
    canvas.height = H * devicePixelRatio;
    canvas.style.width = w + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  }

  const beatNow = () => Tone.Transport.ticks / Tone.Transport.PPQ;

  function rowY(m) { return 6 + (hi - m) * ((H - 12) / (hi - lo + 1)); }
  function rowH() { return (H - 12) / (hi - lo + 1); }

  function label(x, y, n, size, color) {
    const letter = n.name[0], acc = n.name.slice(1);
    ctx.font = `bold ${size}px system-ui, sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    if (acc) {
      ctx.fillStyle = '#fff'; ctx.strokeStyle = color; ctx.lineWidth = 1.5;
      const r = size * 0.62;
      ctx.beginPath();
      if (acc.startsWith('#') || acc === 'x') ctx.arc(x, y, r, 0, 7); else ctx.rect(x - r, y - r, 2 * r, 2 * r);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = color;
    } else {
      ctx.fillStyle = '#fff';
    }
    ctx.fillText(letter, x, y + 0.5);
  }

  function draw() {
    const W = canvas.width / devicePixelRatio, now = beatNow(), h = rowH();
    ctx.fillStyle = '#fbfaf7'; ctx.fillRect(0, 0, W, H);
    for (let m = lo; m <= hi; m++) {           // lanes
      if (BLACK.has(m % 12)) { ctx.fillStyle = '#f0eee8'; ctx.fillRect(KEYS_W, rowY(m), W, h); }
      if (m % 12 === 0) { ctx.fillStyle = '#ddd8cc'; ctx.fillRect(KEYS_W, rowY(m) + h - 1, W, 1); }
    }
    for (const n of data.notes) {              // notes
      const x = PLAYHEAD + (n.t - now) * PX_PER_BEAT;
      const w = Math.max(n.d * PX_PER_BEAT - 2, 6);
      if (x > W || x + w < KEYS_W) continue;
      const y = rowY(n.midi), on = hands[n.hand];
      ctx.globalAlpha = on ? 1 : 0.25;
      ctx.fillStyle = COLORS[n.hand];
      ctx.beginPath(); ctx.roundRect(x, y + 0.5, w, h - 1, 3); ctx.fill();
      if (h >= 9) label(x + Math.min(w / 2, 9), y + h / 2, n, Math.min(h * 0.8, 13), COLORS[n.hand]);
      ctx.globalAlpha = 1;
    }
    ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(PLAYHEAD - 1, 0, 2, H);   // playhead
    for (let m = lo; m <= hi; m++) {           // keyboard
      const y = rowY(m), black = BLACK.has(m % 12), lit = active.get(m);
      ctx.fillStyle = lit ? COLORS[lit] : (black ? '#222' : '#fff');
      ctx.fillRect(0, y, black ? KEYS_W * 0.62 : KEYS_W, h);
      ctx.strokeStyle = '#bbb'; ctx.strokeRect(0, y, KEYS_W, h);
      if (!black && h >= 8) {
        ctx.fillStyle = lit ? '#fff' : '#666';
        ctx.font = `${Math.min(h * 0.75, 11)}px system-ui, sans-serif`; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        ctx.fillText('CDEFGAB'[[0, 2, 4, 5, 7, 9, 11].indexOf(m % 12)] + (m % 12 === 0 ? Math.floor(m / 12) - 1 : ''), KEYS_W - 4, y + h / 2);
      }
    }
    if (!data.paid && now >= endBeat && endBeat > 0) {
      ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.fillRect(KEYS_W, 0, W, H);
      ctx.fillStyle = '#222'; ctx.font = 'bold 18px system-ui, sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('That is the end of the free preview.', (W + KEYS_W) / 2, H / 2 - 12);
      ctx.font = '15px system-ui, sans-serif';
      ctx.fillText('Unlock the whole piece to hear it all.', (W + KEYS_W) / 2, H / 2 + 14);
    }
    requestAnimationFrame(draw);
  }

  function schedule() {
    part = new Tone.Part((time, n) => {
      if (!hands[n.hand]) return;
      const secs = Tone.Ticks(Math.max(n.d, 0.1) * Tone.Transport.PPQ).toSeconds();
      piano.triggerAttackRelease(Tone.Frequency(n.midi, 'midi').toNote(), secs, time, n.hand === 'R' ? 0.75 : 0.55);
      Tone.Draw.schedule(() => { active.set(n.midi, n.hand); }, time);
      Tone.Draw.schedule(() => { active.delete(n.midi); }, time + secs * 0.9);
    }, data.notes.map((n) => [Math.round(n.t * Tone.Transport.PPQ) + 'i', n])).start(0);
    Tone.Transport.scheduleOnce(() => {
      Tone.Draw.schedule(() => { Tone.Transport.pause(); playBtn.textContent = '▶ Play';
        if (!data.paid) say('End of the free preview.'); }, Tone.now());
    }, Math.round(endBeat * Tone.Transport.PPQ) + 'i');
  }

  function setSpeed() {
    Tone.Transport.bpm.value = data.tempo * speedEl.value / 100;
    speedEl.nextElementSibling.textContent = speedEl.value + '%';
  }

  playBtn.addEventListener('click', async () => {
    await Tone.start();
    if (!piano) { say('Loading the piano sound…'); piano = await makePiano(); schedule(); say(''); }
    if (Tone.Transport.state === 'started') { Tone.Transport.pause(); piano.releaseAll?.(); playBtn.textContent = '▶ Play'; return; }
    if (beatNow() >= endBeat) Tone.Transport.ticks = 0;
    Tone.Transport.start(); playBtn.textContent = '❚❚ Pause';
  });
  root.querySelector('[data-act=restart]').addEventListener('click', () => {
    Tone.Transport.ticks = 0; active.clear(); piano?.releaseAll?.();
  });
  speedEl.addEventListener('input', () => data && setSpeed());
  root.querySelectorAll('[data-hand]').forEach((el) => el.addEventListener('change', () => { hands[el.dataset.hand] = el.checked; }));
  window.addEventListener('resize', resize);

  fetch(root.dataset.notes).then((r) => r.json()).then((d) => {
    data = d;
    if (!d.notes.length) { say('We could not read any notes to play.'); return; }
    const ms = d.notes.map((n) => n.midi);
    lo = Math.min(...ms) - 1; hi = Math.max(...ms) + 1;
    endBeat = Math.max(...d.notes.map((n) => n.t + n.d));
    setSpeed(); resize(); draw();
    say(d.paid ? 'Press play. Untick a hand to practise the other one.' :
      `Press play to hear the first ${d.preview_lines} lines. Untick a hand to practise the other one.`);
  });
})();
