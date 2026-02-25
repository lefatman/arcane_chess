export function easeOutCubic(t) {
  t = Math.max(0, Math.min(1, t));
  return 1 - Math.pow(1 - t, 3);
}

export function easeInOutQuad(t) {
  t = Math.max(0, Math.min(1, t));
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

export class Tween {
  constructor({ duration = 250, ease = easeOutCubic, onUpdate = () => {}, onDone = () => {} }) {
    this.t = 0;
    this.duration = duration;
    this.ease = ease;
    this.onUpdate = onUpdate;
    this.onDone = onDone;
    this.done = false;
  }

  step(dt) {
    if (this.done) return;
    this.t += dt;
    const u = this.ease(this.t / this.duration);
    this.onUpdate(u);
    if (this.t >= this.duration) {
      this.done = true;
      this.onUpdate(1);
      this.onDone();
    }
  }
}

export class Animator {
  constructor() {
    this.tweens = [];
  }

  add(tween) {
    this.tweens.push(tween);
    return tween;
  }

  step(dt) {
    if (!this.tweens.length) return;
    for (const tw of this.tweens) tw.step(dt);
    this.tweens = this.tweens.filter(t => !t.done);
  }

  clear() {
    this.tweens.length = 0;
  }

  busy() {
    return this.tweens.length > 0;
  }
}
