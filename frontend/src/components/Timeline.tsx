import type { SimulationResult } from "../lib/types";

interface Props {
  result: SimulationResult | null;
  frameIndex: number;
  playing: boolean;
  onFrame: (i: number) => void;
  onPlaying: (p: boolean) => void;
}

export function Timeline({ result, frameIndex, playing, onFrame, onPlaying }: Props) {
  const n = result?.time.length ?? 0;
  const t = n ? result!.time[Math.min(frameIndex, n - 1)] : 0;
  const tEnd = n ? result!.time[n - 1] : 0;

  return (
    <div className="timeline-bar">
      <button
        type="button"
        className="primary"
        disabled={!result}
        onClick={() => onPlaying(!playing)}
      >
        {playing ? "Pause" : "Play"}
      </button>
      <input
        type="range"
        min={0}
        max={Math.max(0, n - 1)}
        value={n ? Math.min(frameIndex, n - 1) : 0}
        disabled={!result}
        onChange={(e) => {
          onPlaying(false);
          onFrame(Number(e.target.value));
        }}
      />
      <div className="timeline-time">
        t = {t.toFixed(2)} / {tEnd.toFixed(2)}
      </div>
      <button
        type="button"
        disabled={!result}
        onClick={() => {
          onPlaying(false);
          onFrame(0);
        }}
      >
        Reset
      </button>
    </div>
  );
}
