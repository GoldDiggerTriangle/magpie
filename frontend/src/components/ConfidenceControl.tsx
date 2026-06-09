interface ConfidenceControlProps {
  score: number | null;
  reason: string;
  onChange: (next: { score: number | null; reason: string }) => void;
}

export function ConfidenceControl({ score, reason, onChange }: ConfidenceControlProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)]">
      <label className="label">
        <span>Confidence</span>
        <input
          className="field"
          max={1}
          min={0}
          step={0.05}
          type="number"
          value={score ?? ""}
          onChange={(event) => onChange({ score: event.target.value === "" ? null : Number(event.target.value), reason })}
        />
      </label>
      <label className="label">
        <span>Confidence reason</span>
        <input className="field" value={reason} onChange={(event) => onChange({ score, reason: event.target.value })} />
      </label>
    </div>
  );
}
