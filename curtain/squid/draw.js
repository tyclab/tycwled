const W = 68, H = 42, TAU = Math.PI * 2;
const B = [90, 162, 255], V = [139, 108, 240], R = [255, 74, 61], E = [180, 140, 245];
const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mix = (a, b, u) => [0, 1, 2].map(i => a[i] + (b[i] - a[i]) * u);
const grad = u => { u = Math.min(1, Math.max(0, u)); return u < .48 ? mix(B, V, u / .48) : mix(V, R, (u - .48) / .52); };
const hash = (a, b) => { const x = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return x - Math.floor(x); };
const ease = u => u * u * (3 - 2 * u);
const frac = x => x - Math.floor(x);
const clamp01 = x => Math.min(1, Math.max(0, x));
const blinkAt = (t, period) => { const b = frac(t / period) * period; return b < .2 ? Math.sin(b / .2 * Math.PI) : 0; };
// One bump from 0 to 1 and back, `len` seconds long, starting at `at`.
const pulse = (t, at, len) => { const u = (t - at) / len; return u > 0 && u < 1 ? Math.sin(u * Math.PI) : 0; };
// Keyframes [[time, value], ...], eased between; a value is a number or a list of numbers.
function kf(t, keys) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    if (t > keys[i][0]) continue;
    const [t0, a] = keys[i - 1], [t1, b] = keys[i], u = ease((t - t0) / (t1 - t0));
    return typeof a === 'number' ? a + (b - a) * u : a.map((v, k) => v + (b[k] - v) * u);
  }
  return keys[keys.length - 1][1];
}

function dot(g, x, y, r, c, a) {
  const q = g.createRadialGradient(x, y, 0, x, y, r);
  q.addColorStop(0, css(c, a)); q.addColorStop(1, css(c, 0));
  g.fillStyle = q; g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill();
}

// The mark's own geometry (the TycStation favicon paths), left-side arms; the right side mirrors them.
const ARMS = [
  [[-40, 22], [-70, 24], [-97, 40], [-105, 64], [-111, 83], [-97, 95], [-85, 87], [-76, 81], [-79, 69], [-88, 69]],
  [[-28, 31], [-50, 45], [-69, 64], [-71, 88], [-72, 105], [-59, 114], [-49, 106], [-41, 99], [-45, 88], [-54, 89]],
  [[-15, 36], [-26, 60], [-34, 82], [-30, 103], [-27, 118], [-14, 123], [-8, 113]],
  [[-5, 37], [-7, 60], [-10, 79], [-6, 95]],
];
// pa, pb: the two sway angles, so a loop can close them on whole turns. spread and stretch scale the arms
// sideways and lengthways from their roots; lift turns the outer arm [left, right] upward, in radians.
function squid(g, o) {
  const { x, y, s, pa = 0, pb = 0, sway = 5, blink = 0, look = [0, 0], alpha = 1, squash = 1, rot = 0,
    arms = true, head = true, eyes = true, eyeK = 1, stroke = null, lw = 1, spread = 1, stretch = 1,
    lift = [0, 0], armAlpha = null, headAlpha = 1, mouth = 'smile' } = o;
  if (alpha <= 0) return;
  g.save(); g.translate(x, y); g.rotate(rot); g.scale(s, s * squash);
  const gr = g.createLinearGradient(-112, 0, 112, 0);
  gr.addColorStop(0, css(B)); gr.addColorStop(.48, css(V)); gr.addColorStop(1, css(R));
  g.strokeStyle = stroke || gr; g.lineWidth = 13 * lw; g.lineCap = 'round'; g.lineJoin = 'round';
  if (arms) for (const side of [1, -1]) ARMS.forEach((a, ai) => {
    const aa = armAlpha ? armAlpha(ai, side) : 1;
    if (aa <= 0) return;
    const n = a.length - 1, [rx, ry] = a[0], th = ai === 0 ? lift[side > 0 ? 0 : 1] : 0, c = Math.cos(th), sn = Math.sin(th);
    const p = a.map(([px, py], k) => {
      const w = Math.pow(k / n, 1.4), off = ai * 1.1 + (side < 0 ? 2 : 0) + k * .45;
      const dx = (px - rx) * spread + Math.sin(pa + off) * sway * w, dy = (py - ry) * stretch + Math.cos(pb + off * .8) * sway * .6 * w;
      return [side * (rx + dx * c - dy * sn), ry + dx * sn + dy * c];
    });
    g.globalAlpha = alpha * aa;
    g.beginPath(); g.moveTo(p[0][0], p[0][1]);
    for (let k = 1; k < p.length; k += 3) g.bezierCurveTo(p[k][0], p[k][1], p[k + 1][0], p[k + 1][1], p[k + 2][0], p[k + 2][1]);
    g.stroke();
  });
  if (head && headAlpha > 0) {
    g.globalAlpha = alpha * headAlpha;
    g.beginPath(); g.moveTo(-53, -2);
    g.bezierCurveTo(-53, -42, -30, -66, 0, -66); g.bezierCurveTo(30, -66, 53, -42, 53, -2);
    g.bezierCurveTo(53, 20, 30, 35, 0, 35); g.bezierCurveTo(-30, 35, -53, 20, -53, -2); g.closePath();
    g.fillStyle = '#000'; g.fill(); g.stroke();
    g.lineWidth = 9 * lw; g.beginPath();
    if (mouth === 'o') g.ellipse(0, 15, 5, 6, 0, 0, TAU);
    else { g.moveTo(-9, 12); g.bezierCurveTo(-4, 17, 4, 17, 9, 12); }
    g.stroke();
  }
  if (eyes) {
    const bl = Array.isArray(blink) ? blink : [blink, blink];
    g.globalAlpha = alpha; g.fillStyle = css(E);
    [-19, 19].forEach((sx, k) => {
      g.beginPath(); g.ellipse(sx + look[0], -10 + look[1], 8 * eyeK, Math.max(.8, 9.5 * eyeK * (1 - bl[k])), 0, 0, TAU); g.fill();
    });
  }
  g.restore();
}

// The five curtain loops, each a sequence of stages. Frame 0 follows the last frame: every keyframe track ends
// where it starts and every cyclic motion runs a whole number of turns in L seconds.
const LOOPS = {
  // hover, gather, jet up, glide down, wave hello, hover
  a: { L: 16, delay: .08, stages: ['hover', 'gather', 'jet up', 'glide down', 'wave hello'], draw(g, t) {
    const w = k => TAU * k * t / 16;
    const bob = kf(t, [[0, 1], [4, 1], [4.6, 0], [8.5, 0], [9.2, 1], [16, 1]]);
    const y = kf(t, [[0, 19], [4, 19], [5.2, 21], [5.9, 12.5], [6.4, 12], [9, 19], [16, 19]]) + Math.sin(w(4)) * .9 * bob;
    const lift = kf(t, [[0, 0], [9, 0], [10, 1.25], [12.2, 1.25], [13, 0], [16, 0]]);
    const hello = Math.sin(TAU * (t - 10) * 1.5) * .3 * clamp01((lift - .2) * 2);
    const both = Math.max(pulse(t, 2, .25), pulse(t, 14.6, .25));
    squid(g, { x: 34, y, s: .155, pa: w(6), pb: w(5),
      sway: kf(t, [[0, 20], [4, 20], [5.2, 6], [6.4, 4], [7.2, 14], [9, 12], [13, 12], [14, 20], [16, 20]]),
      spread: kf(t, [[0, 1], [4, 1], [5.2, .75], [5.7, .45], [6.4, .5], [7.2, 1.25], [9, 1], [16, 1]]),
      stretch: kf(t, [[0, 1], [4, 1], [5.2, .55], [5.7, 1.3], [6.4, 1.25], [7.2, .8], [9, 1], [16, 1]]),
      squash: kf(t, [[0, 1], [4, 1], [5.2, .86], [5.7, 1.1], [6.6, 1], [16, 1]]),
      look: kf(t, [[0, [0, 0]], [4.6, [0, 0]], [5.4, [0, -5]], [6.4, [0, -5]], [7.4, [0, 4]], [9, [0, 0]], [9.8, [-6, -2]], [12.2, [-6, -2]], [13, [0, 0]], [16, [0, 0]]]),
      lift: [lift + hello, 0], blink: [both, Math.max(both, pulse(t, 11, .5))], alpha: .8 + .2 * Math.sin(w(2)) });
  } },

  // swim in, startle, ink burst, dart right, peek, dash left, second burst, shoot out of the top
  b: { L: 9.6, delay: .08, stages: ['swim in', 'startle', 'ink burst', 'dart away', 'peek', 'dash back', 'second burst', 'shoot off'], draw(g, t) {
    const w = k => TAU * k * t / 9.6;
    g.globalCompositeOperation = 'lighter';
    for (const b of [{ at: 2.4, x: 34, y: 15, id: 0, ring: false }, { at: 5.6, x: 17, y: 20, id: 1, ring: true }]) {
      const age = t - b.at;
      if (age < 0 || age > 3.4) continue;
      for (let i = 0; i < 80; i++) {
        const life = 1.8 + hash(i + 7, b.id) * 1.6, f = 1 - age / life;
        if (f <= 0) continue;
        const a = b.ring ? hash(i, b.id) * TAU : (hash(i, b.id) - .5) * 2.6 + Math.PI / 2;
        const sp = b.ring ? 12 + hash(i + 99, b.id) * 12 : 10 + hash(i + 99, b.id) * 26, d = sp * (1 - Math.exp(-1.6 * age)) / 1.6;
        const px = b.x + Math.cos(a) * d * 1.25, py = b.y + Math.sin(a) * d * .9 + age * 1.5;
        dot(g, px, py, 1.2 + age * 2.2 * (.5 + hash(i + 3, b.id)), grad(.5 + (px - b.x) / 40 + (hash(i + 5, b.id) - .5) * .2), f * .75);
      }
    }
    g.globalCompositeOperation = 'source-over';
    if (t > 6.9) return;
    const swim = kf(t, [[0, 1], [1.5, 1], [1.9, 0], [2.4, 0], [2.5, 1], [3.1, 1], [3.4, 0], [4.5, 0], [4.7, 1], [5.4, 1], [5.6, 0], [5.7, 1], [9.6, 1]]);
    const jet = Math.cos(TAU * frac(t / .8));
    const fright = kf(t, [[0, 0], [1.7, 0], [2.3, 1], [2.6, 0], [5.4, 0], [5.6, 1], [5.9, 0], [9.6, 0]]);
    squid(g, { s: .105 * (1 + .12 * fright), pa: w(4), pb: w(3),
      x: kf(t, [[0, -14], [.8, 8], [1.6, 34], [2.4, 34], [3.2, 54], [4.6, 54], [5.5, 17], [9.6, 17]]) + Math.sin(t * 44) * .7 * pulse(t, 1.9, .5),
      y: kf(t, [[0, 17], [1.6, 12], [2.4, 12], [3.2, 9], [4.6, 10], [5.5, 17], [5.7, 17], [6.7, -20], [9.6, -20]]),
      rot: kf(t, [[0, .9], [1.5, .9], [1.9, 0], [2.4, 0], [2.5, .9], [3.1, .9], [3.4, 0], [4.5, 0], [4.7, -.9], [5.4, -.9], [5.6, 0], [9.6, 0]]),
      sway: 14 - 8 * swim, spread: 1 - swim * (.35 - .2 * jet), stretch: 1 + swim * (.1 - .3 * jet), squash: 1 + .15 * fright,
      eyeK: 1.25 + .55 * fright, mouth: fright > .3 ? 'o' : 'smile',
      look: kf(t, [[0, [0, 0]], [3.3, [0, 0]], [3.7, [-8, 3]], [4.4, [-8, 3]], [4.7, [0, 0]], [9.6, [0, 0]]]), blink: pulse(t, 4.05, .25) });
  } },

  // swim in with jet strokes, stop and look around, swim on and out, a school passes
  c: { L: 16, delay: .08, stages: ['swim in', 'stop', 'look around', 'swim on', 'a school passes'], draw(g, t) {
    const L = 16, w = k => TAU * k * t / L;
    const q = g.createLinearGradient(0, 0, 0, H);
    q.addColorStop(0, 'rgba(18,40,100,.85)'); q.addColorStop(1, 'rgba(3,5,16,.4)');
    g.fillStyle = q; g.fillRect(0, 0, W, H);
    g.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 44; i++) {
      const sp = .5 + hash(i, 1) * 1.5, life = L / (1 + (i % 2));
      const tau = frac(t / life + hash(i, 5)) * life, env = Math.min(1, 2.5 * Math.sin(Math.PI * tau / life));
      const x = ((hash(i, 2) * W + Math.sin(w(1) + i) * 1.5 + tau * sp * .3) % W + W) % W;
      const y = hash(i, 3) * (H + 8) - 4 + sp * life / 2 - sp * tau;
      const tw = Math.max(1, Math.round((.5 + hash(i, 4)) * L / Math.PI));
      dot(g, x, y, 1, [B, V, E][i % 3], (.3 + .7 * Math.abs(Math.sin(Math.PI * tw * t / L + i))) * .85 * env);
    }
    if (t > 10.4) for (let k = 0; k < 7; k++) {
      const row = Math.ceil(k / 2), fx = 76 - (t - 10.4) / 5.6 * 104 + row * 3.2, fy = 31 + (k % 2 ? -1 : 1) * row * 1.7 + Math.sin(t * 5 + k) * .5;
      dot(g, fx, fy, 1.5, k % 2 ? B : E, .95); dot(g, fx + 1.3, fy, 1, k % 2 ? B : E, .6);
    }
    g.globalCompositeOperation = 'source-over';
    const swim = kf(t, [[0, 1], [4.6, 1], [5.1, 0], [8.2, 0], [8.6, 1], [16, 1]]), jet = Math.cos(TAU * frac(t / 1.2));
    const both = Math.max(pulse(t, 7.5, .22), pulse(t, 7.85, .22));
    squid(g, { s: .1, pa: w(8), pb: w(6),
      x: kf(t, [[0, -14], [1.2, -2], [2.4, 8], [3.6, 17], [4.8, 26], [8.4, 26], [9.6, 37], [10.8, 50], [12, 64], [13.2, 84], [16, 84]]),
      y: kf(t, [[0, 35], [1.2, 32], [2.4, 29], [3.6, 25.5], [4.8, 22], [8.4, 22], [9.6, 18], [10.8, 14], [12, 9.5], [13.2, 5], [16, 5]]),
      rot: kf(t, [[0, .95], [4.6, .95], [5.2, 0], [8.2, 0], [8.6, .95], [16, .95]]),
      sway: 15 - 9 * swim, spread: 1 - swim * (.3 - .25 * jet), stretch: 1 - swim * .35 * jet, eyeK: 1.4, blink: both,
      look: kf(t, [[0, [0, 0]], [5.3, [0, 0]], [5.8, [-8, 0]], [6.4, [-8, 0]], [6.9, [8, 0]], [7.4, [8, 0]], [7.8, [0, 0]], [16, [0, 0]]]) });
  } },

  // wake, look left and right, squint, startle, follow something, wink, sleep, peek from another corner
  e: { L: 16, delay: .08, stages: ['wake', 'look left and right', 'squint', 'startle', 'follow', 'wink', 'sleep', 'peek from a corner'], draw(g, t) {
    const lid = kf(t, [[0, 1], [.4, 1], [1.5, .45], [2, .1], [4.2, .1], [4.6, .55], [5.2, .55], [5.5, 0], [9.6, 0], [10.6, 1], [16, 1]]);
    const both = Math.max(lid, pulse(t, 5.9, .22), pulse(t, 6.25, .22));
    const th = TAU * clamp01((t - 6.6) / 2);
    const look = t > 6.6 && t < 8.6 ? [14 * Math.sin(th), 6 * Math.sin(2 * th)]
      : kf(t, [[0, [0, 2]], [1.5, [0, 2]], [2.2, [-16, 0]], [2.9, [-16, 0]], [3.5, [16, 0]], [4.1, [16, 0]], [4.6, [0, 0]], [16, [0, 0]]]);
    squid(g, { x: 34, y: 25, s: .46, arms: false, head: false, look, blink: [Math.max(both, pulse(t, 8.9, .5)), both],
      eyeK: kf(t, [[0, 1], [5.2, 1], [5.5, 1.25], [6.6, 1.25], [7, 1], [16, 1]]),
      alpha: kf(t, [[0, 0], [.4, 0], [.6, 1], [10.5, 1], [10.7, 0], [16, 0]]) });
    squid(g, { x: 19, y: 14, s: .3, arms: false, head: false,
      look: kf(t, [[0, [8, 4]], [12.6, [8, 4]], [13.4, [15, 7]], [16, [15, 7]]]),
      blink: Math.max(kf(t, [[0, 1], [11.6, 1], [12.4, .5], [13, .5], [13.3, .15], [14.6, .15], [15.4, 1], [16, 1]]), pulse(t, 14, .22)),
      alpha: kf(t, [[0, 0], [11.6, 0], [11.8, 1], [15.3, 1], [15.5, 0], [16, 0]]) });
  } },

  // four skin patterns in turn; the squid shows as a dark shape, lights arm by arm, pulses and dissolves
  f: { L: 12, delay: .1, stages: ['waves', 'rings', 'dark shape', 'arm by arm', 'pulse', 'sweep', 'sparkle', 'dissolve'], draw(g, t) {
    const L = 12, w = k => TAU * k * t / L;
    const win = c => { const d = Math.abs(t - c); return ease(clamp01(2 - Math.min(d, L - d))); };
    const w1 = win(1.5), w2 = win(4.5), w3 = win(7.5), w4 = win(10.5), band = -14 + (t - 5.5) / 4 * (W + 28);
    g.globalCompositeOperation = 'lighter';
    for (let cy = 0; cy < 11; cy++) for (let cx = 0; cx < 17; cx++) {
      const h = hash(cx + 7, cy), x = 2 + cx * 4 + (hash(cx, cy) - .5) * 1.6 + (cy % 2) * 2 - 1, y = 2 + cy * 3.9 + (hash(cy, cx + 40) - .5) * 1.6;
      const v = w1 * Math.sin(x * .2 + y * .12 - w(6) + h * 1.2) + w2 * Math.sin(Math.hypot(x - 34, (y - 21) * 1.3) * .42 - w(9))
        + w3 * (1 - 2 * clamp01(Math.abs(x - band) / 9)) + w4 * Math.sin(w(6 + Math.floor(h * 6)) + hash(cy, cx) * TAU);
      const s = ease(clamp01(v * .6 + .5));
      dot(g, x, y, .9 + 2.4 * s, grad((1 - w3) * (.5 + .5 * Math.sin(x * .06 + y * .05 - w(1))) + w3 * x / W), .25 + .75 * s);
    }
    g.globalCompositeOperation = 'source-over';
    const pose = { x: 34, y: 16.5, s: .175, pa: w(4), pb: w(3), sway: 8 };
    squid(g, { ...pose, stroke: '#000', lw: 1.7, eyeK: 1.3, blink: Math.max(pulse(t, 5.2, .25), pulse(t, 8.6, .25)),
      alpha: kf(t, [[0, 0], [2.6, 0], [4.2, 1], [9.4, 1], [10.6, 0], [12, 0]]) });
    squid(g, { ...pose, eyes: false, armAlpha: (ai, side) => clamp01((t - 4.4 - (side > 0 ? ai : 7 - ai) * .22) / .3),
      headAlpha: clamp01((t - 6.2) / .4),
      alpha: kf(t, [[0, 0], [4.3, 0], [4.4, 1], [9.2, 1], [10.2, 0], [12, 0]]) * (t > 6.8 && t < 8.8 ? .55 + .45 * Math.cos(TAU * (t - 6.8)) : 1) });
  } },
};

// The other lamps (a strip, a small matrix): the mark's gradient along the row, blue end to red end, with arm waves
// running outward from the middle. One wave period per loop; two waves per half, one on rows under 16 wide.
function armWaves(w, h) {
  const k = TAU * (w >= 16 ? 2 : 1) / (w / 2);
  return { w, h, L: 2, delay: .05, draw(g, t) {
    for (let x = 0; x < w; x++) {
      const v = .08 + .92 * Math.pow(.5 + .5 * Math.sin(Math.abs(x - (w - 1) / 2) * k - Math.PI * t), 3);
      g.fillStyle = css(grad(x / (w - 1)), v); g.fillRect(x, 0, 1, h);
    }
  } };
}
const ROWS = { 'squid-arms-300x1': armWaves(300, 1), 'squid-arms-20x6': armWaves(20, 6), 'squid-arms-8x8': armWaves(8, 8) };
