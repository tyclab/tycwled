const W = 68, H = 42, TAU = Math.PI * 2;
const B = [90, 162, 255], V = [139, 108, 240], R = [255, 74, 61], E = [180, 140, 245];
const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mix = (a, b, u) => [0, 1, 2].map(i => a[i] + (b[i] - a[i]) * u);
const grad = u => { u = Math.min(1, Math.max(0, u)); return u < .48 ? mix(B, V, u / .48) : mix(V, R, (u - .48) / .52); };
const hash = (a, b) => { const x = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return x - Math.floor(x); };
const ease = u => u * u * (3 - 2 * u);
const frac = x => x - Math.floor(x);
const blinkAt = (t, period) => { const b = frac(t / period) * period; return b < .2 ? Math.sin(b / .2 * Math.PI) : 0; };

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
// pa, pb: the two sway angles, so a loop can close them on whole turns.
function squid(g, o) {
  const { x, y, s, pa = 0, pb = 0, sway = 5, blink: bl = 0, look = [0, 0], alpha = 1, squash = 1, rot = 0,
    arms = true, head = true, eyeK = 1, stroke = null, lw = 1 } = o;
  g.save(); g.translate(x, y); g.rotate(rot); g.scale(s, s * squash); g.globalAlpha = alpha;
  const gr = g.createLinearGradient(-112, 0, 112, 0);
  gr.addColorStop(0, css(B)); gr.addColorStop(.48, css(V)); gr.addColorStop(1, css(R));
  g.strokeStyle = stroke || gr; g.lineWidth = 13 * lw; g.lineCap = 'round'; g.lineJoin = 'round';
  if (arms) for (const side of [1, -1]) ARMS.forEach((a, ai) => {
    const n = a.length - 1;
    const p = a.map(([px, py], k) => {
      const w = Math.pow(k / n, 1.4), off = ai * 1.1 + (side < 0 ? 2 : 0) + k * .45;
      return [side * (px + Math.sin(pa + off) * sway * w), py + Math.cos(pb + off * .8) * sway * .6 * w];
    });
    g.beginPath(); g.moveTo(p[0][0], p[0][1]);
    for (let k = 1; k < p.length; k += 3) g.bezierCurveTo(p[k][0], p[k][1], p[k + 1][0], p[k + 1][1], p[k + 2][0], p[k + 2][1]);
    g.stroke();
  });
  if (head) {
    g.beginPath(); g.moveTo(-53, -2);
    g.bezierCurveTo(-53, -42, -30, -66, 0, -66); g.bezierCurveTo(30, -66, 53, -42, 53, -2);
    g.bezierCurveTo(53, 20, 30, 35, 0, 35); g.bezierCurveTo(-30, 35, -53, 20, -53, -2); g.closePath();
    g.fillStyle = '#000'; g.fill(); g.stroke();
    g.lineWidth = 9 * lw; g.beginPath(); g.moveTo(-9, 12); g.bezierCurveTo(-4, 17, 4, 17, 9, 12); g.stroke();
  }
  g.fillStyle = css(E);
  for (const sx of [-19, 19]) {
    g.beginPath(); g.ellipse(sx + look[0], -10 + look[1], 8 * eyeK, Math.max(.8, 9.5 * eyeK * (1 - bl)), 0, 0, TAU); g.fill();
  }
  g.restore();
}

// The five curtain loops. Every motion runs a whole number of turns in L seconds, so frame 0 follows the last frame.
const LOOPS = {
  a: { L: 14, delay: .08, draw(g, t) {
    const w = k => TAU * k * t / 14;
    squid(g, { x: 34, y: 16.5 + Math.sin(w(2)) * .7, s: .175, pa: w(3), pb: w(2), sway: 7,
      blink: blinkAt(t, 14 / 3), alpha: .74 + .26 * Math.sin(w(2)) });
  } },

  b: { L: 4.8, delay: .06, draw(g, t) {
    const P = 2.4, w = k => TAU * k * t / 4.8, b0 = Math.floor(t / P);
    g.globalCompositeOperation = 'lighter';
    for (let bi = 0; bi < 2; bi++) {
      const b = b0 - bi, age = t - b * P, id = ((b % 2) + 2) % 2;
      if (age > 3.2) continue;
      for (let i = 0; i < 70; i++) {
        const life = 1.6 + hash(i + 7, id) * 1.6, f = 1 - age / life;
        if (f <= 0) continue;
        const a = (hash(i, id) - .5) * 2.6 + Math.PI / 2, sp = 10 + hash(i + 99, id) * 26, d = sp * (1 - Math.exp(-1.6 * age)) / 1.6;
        const px = 34 + Math.cos(a) * d * 1.25, py = 15 + Math.sin(a) * d * .9 + age * 1.5;
        const u = .5 + (px - 34) / 40 + (hash(i + 5, id) - .5) * .2;
        dot(g, px, py, 1.2 + age * 2.2 * (.5 + hash(i + 3, id)), grad(u), f * .75);
      }
    }
    g.globalCompositeOperation = 'source-over';
    const kick = Math.exp(-(t % P) * 5);
    squid(g, { x: 34, y: 11 - kick * 2, s: .105, pa: w(1), pb: w(1), sway: 6 + kick * 10, blink: blinkAt(t, 4.8),
      squash: 1 - kick * .18, eyeK: 1.2 });
  } },

  c: { L: 14, delay: .08, draw(g, t) {
    const L = 14, w = k => TAU * k * t / L;
    const q = g.createLinearGradient(0, 0, 0, H);
    q.addColorStop(0, 'rgba(18,40,100,.85)'); q.addColorStop(1, 'rgba(3,5,16,.4)');
    g.fillStyle = q; g.fillRect(0, 0, W, H);
    g.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 44; i++) {
      const sp = .5 + hash(i, 1) * 1.5, turns = 1 + (i % 2), life = L / turns;
      const tau = frac(t / life + hash(i, 5)) * life, env = Math.min(1, 2.5 * Math.sin(Math.PI * tau / life));
      const x = ((hash(i, 2) * W + Math.sin(w(1) + i) * 1.5 + tau * sp * .3) % W + W) % W;
      const y = hash(i, 3) * (H + 8) - 4 + sp * life / 2 - sp * tau;
      const tw = Math.max(1, Math.round((.5 + hash(i, 4)) * L / Math.PI));
      dot(g, x, y, 1, [B, V, E][i % 3], (.3 + .7 * Math.abs(Math.sin(Math.PI * tw * t / L + i))) * .85 * env);
    }
    g.globalCompositeOperation = 'source-over';
    const u = t / L, jet = Math.pow(1 - frac(11 * u), 3);
    squid(g, { x: -12 + u * (W + 24), y: 36 - u * 28 + Math.sin(u * 18) * 1.2, s: .1, pa: w(6), pb: w(5),
      sway: 5 + jet * 9, rot: .4, squash: 1 + jet * .1, eyeK: 1.4, blink: blinkAt(t, L / 3) });
  } },

  e: { L: 12.8, delay: .08, draw(g, t) {
    const L = 12.8, w = k => TAU * k * t / L;
    const lx = Math.sin(w(1)) * Math.min(1, Math.abs(Math.sin(w(.5))) * 2) * 16, ly = Math.sin(w(1) + 1) * 5;
    const squint = t > 6.2 && t < 7 ? Math.sin((t - 6.2) / .8 * Math.PI) * .85 : 0;
    squid(g, { x: 34, y: 25, s: .46, arms: false, head: false, look: [lx, ly], blink: Math.max(blinkAt(t, L / 3), squint) });
  } },

  f: { L: 9.6, delay: .1, draw(g, t) {
    const L = 9.6, w = k => TAU * k * t / L;
    g.globalCompositeOperation = 'lighter';
    for (let cy = 0; cy < 11; cy++) for (let cx = 0; cx < 17; cx++) {
      const x = 2 + cx * 4 + (hash(cx, cy) - .5) * 1.6 + (cy % 2) * 2 - 1, y = 2 + cy * 3.9 + (hash(cy, cx + 40) - .5) * 1.6;
      const v = Math.sin(x * .2 + y * .12 - w(3) + hash(cx + 7, cy) * 1.2), s = ease(Math.min(1, Math.max(0, v * .6 + .5)));
      dot(g, x, y, .9 + 2.4 * s, grad(.5 + .5 * Math.sin(x * .06 + y * .05 - w(1))), .25 + .75 * s);
    }
    g.globalCompositeOperation = 'source-over';
    const b = t % 2.4, flash = b < .3 ? 1 - b / .3 : 0, bl = blinkAt(t, 4.8);
    squid(g, { x: 34, y: 16.5, s: .175, pa: w(2), pb: w(2), sway: 5, stroke: '#000', lw: 1.7, eyeK: 1.3, blink: bl });
    if (flash > 0) squid(g, { x: 34, y: 16.5, s: .175, pa: w(2), pb: w(2), sway: 5, alpha: flash, blink: bl });
  } },
};
