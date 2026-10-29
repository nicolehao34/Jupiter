import { useEffect, useRef, useState } from "react";

export interface RobotFrame {
  i: number;
  t: number;
  phase: string;
  gripper: string;
  ee: { x: number; y: number };
  base: { x: number; y: number };
  joints: number[];
}

export interface RobotMotionPlan {
  simulation_only: boolean;
  planner: string;
  algorithm_note?: string;
  duration_s?: number;
  frame_count?: number;
  frames: RobotFrame[];
  stations?: Record<string, { x: number; y: number }>;
  obstacle?: { x0: number; y0: number; x1: number; y1: number };
}

const LINKS = [0.22, 0.18, 0.14];

function toCanvas(x: number, y: number, w: number, h: number, pad: number) {
  return { cx: pad + x * (w - 2 * pad), cy: h - pad - y * (h - 2 * pad) };
}

function forwardKinematics(base: { x: number; y: number }, joints: number[]) {
  let x = base.x;
  let y = base.y;
  let angle = 0;
  const points = [{ x, y }];
  for (let i = 0; i < joints.length; i++) {
    angle += joints[i];
    const len = LINKS[i] ?? 0.1;
    x += len * Math.cos(angle);
    y += len * Math.sin(angle);
    points.push({ x, y });
  }
  return points;
}

export function RobotMotionSim({ plan, autoPlay = true }: { plan: RobotMotionPlan; autoPlay?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);

  useEffect(() => {
    setFrameIndex(0);
    setPlaying(autoPlay);
  }, [plan, autoPlay]);

  useEffect(() => {
    if (!playing || !plan.frames.length) return;
    const id = window.setInterval(() => {
      setFrameIndex((i) => (i + 1 >= plan.frames.length ? 0 : i + 1));
    }, 1000 / 30);
    return () => window.clearInterval(id);
  }, [playing, plan.frames.length]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    const pad = 28;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0f1419";
    ctx.fillRect(0, 0, w, h);

    const obs = plan.obstacle;
    if (obs) {
      const o0 = toCanvas(obs.x0, obs.y0, w, h, pad);
      const o1 = toCanvas(obs.x1, obs.y1, w, h, pad);
      ctx.fillStyle = "rgba(255, 120, 80, 0.25)";
      ctx.strokeStyle = "rgba(255, 120, 80, 0.6)";
      ctx.fillRect(o0.cx, o1.cy, o1.cx - o0.cx, o0.cy - o1.cy);
      ctx.strokeRect(o0.cx, o1.cy, o1.cx - o0.cx, o0.cy - o1.cy);
      ctx.fillStyle = "#ffb080";
      ctx.font = "11px system-ui";
      ctx.fillText("Furnace hood (keep-out)", o0.cx + 4, o1.cy - 6);
    }

    if (plan.stations) {
      ctx.font = "10px system-ui";
      for (const [name, pt] of Object.entries(plan.stations)) {
        const { cx, cy } = toCanvas(pt.x, pt.y, w, h, pad);
        ctx.fillStyle = "#6b8cae";
        ctx.beginPath();
        ctx.arc(cx, cy, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#a8c4e0";
        ctx.fillText(name.replace(/_/g, " "), cx + 8, cy + 4);
      }
    }

    const frame = plan.frames[frameIndex] ?? plan.frames[0];
    if (!frame) return;

    const trail = plan.frames.slice(0, frameIndex + 1);
    ctx.strokeStyle = "rgba(120, 200, 255, 0.35)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    trail.forEach((f, idx) => {
      const { cx, cy } = toCanvas(f.ee.x, f.ee.y, w, h, pad);
      if (idx === 0) ctx.moveTo(cx, cy);
      else ctx.lineTo(cx, cy);
    });
    ctx.stroke();

    const chain = forwardKinematics(frame.base, frame.joints);
    ctx.lineWidth = 5;
    ctx.lineCap = "round";
    for (let i = 0; i < chain.length - 1; i++) {
      const a = toCanvas(chain[i].x, chain[i].y, w, h, pad);
      const b = toCanvas(chain[i + 1].x, chain[i + 1].y, w, h, pad);
      ctx.strokeStyle = i === chain.length - 2 ? "#7ee787" : "#58a6ff";
      ctx.beginPath();
      ctx.moveTo(a.cx, a.cy);
      ctx.lineTo(b.cx, b.cy);
      ctx.stroke();
    }

    const base = toCanvas(frame.base.x, frame.base.y, w, h, pad);
    ctx.fillStyle = "#e6edf3";
    ctx.beginPath();
    ctx.arc(base.cx, base.cy, 7, 0, Math.PI * 2);
    ctx.fill();

    const ee = toCanvas(frame.ee.x, frame.ee.y, w, h, pad);
    ctx.fillStyle = frame.gripper === "close" ? "#ffa657" : "#79c0ff";
    ctx.beginPath();
    ctx.arc(ee.cx, ee.cy, 8, 0, Math.PI * 2);
    ctx.fill();
  }, [frameIndex, plan]);

  const frame = plan.frames[frameIndex];

  return (
    <div className="robot-sim">
      <p className="meta">
        <OriginChip /> {plan.planner} · {plan.frame_count ?? plan.frames.length} frames ·{" "}
        {plan.duration_s ?? "—"}s playback
      </p>
      <canvas ref={canvasRef} width={640} height={360} className="robot-canvas" role="img" aria-label="Simulated robotic arm motion on a bench layout" />
      <div className="actions" style={{ marginTop: 8 }}>
        <button type="button" className="secondary" onClick={() => setPlaying((p) => !p)}>
          {playing ? "Pause" : "Play"}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={frameIndex <= 0}
          onClick={() => setFrameIndex((i) => Math.max(0, i - 1))}
        >
          Step back
        </button>
        <button
          type="button"
          className="secondary"
          disabled={frameIndex >= plan.frames.length - 1}
          onClick={() => setFrameIndex((i) => Math.min(plan.frames.length - 1, i + 1))}
        >
          Step forward
        </button>
      </div>
      {frame && (
        <p className="hint">
          Phase: <span className="mono">{frame.phase}</span> · gripper {frame.gripper}
        </p>
      )}
      {plan.algorithm_note && <p className="hint">{plan.algorithm_note}</p>}
    </div>
  );
}

function OriginChip() {
  return <span className="chip simulated">Simulated arm</span>;
}
