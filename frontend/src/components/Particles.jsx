import { useEffect, useRef } from "react";

export default function Particles() {
  const ref = useRef(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    let raf;
    const dots = Array.from({ length: 70 }, () => ({
      x: Math.random(), y: Math.random(), r: Math.random() * 1.8 + 0.4,
      v: Math.random() * 0.00025 + 0.00008, hue: Math.random() > 0.5 ? "10,200,185" : "200,170,110",
    }));
    const resize = () => { canvas.width = innerWidth; canvas.height = innerHeight; };
    resize();
    addEventListener("resize", resize);
    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const d of dots) {
        d.y -= d.v;
        if (d.y < -0.02) { d.y = 1.02; d.x = Math.random(); }
        ctx.beginPath();
        ctx.fillStyle = `rgba(${d.hue},${0.25 + d.r / 4})`;
        ctx.arc(d.x * canvas.width, d.y * canvas.height, d.r, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(tick);
    };
    tick();
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", resize); };
  }, []);

  return <canvas ref={ref} aria-hidden className="pointer-events-none fixed inset-0 -z-0" />;
}
