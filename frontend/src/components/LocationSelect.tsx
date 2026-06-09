import type { StorageLocation, UUID } from "../types";

interface LocationSelectProps {
  locations: StorageLocation[];
  value: UUID | null;
  onChange: (value: UUID | null) => void;
}

export function LocationSelect({ locations, value, onChange }: LocationSelectProps) {
  return (
    <select
      className="field"
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value || null)}
    >
      <option value="">No location</option>
      {locations.map((location) => (
        <option key={location.id} value={location.id}>
          {location.label}
        </option>
      ))}
    </select>
  );
}
