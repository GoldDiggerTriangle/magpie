import type { ProductCategory, UUID } from "../types";

interface CategorySelectProps {
  categories: ProductCategory[];
  value: UUID | null;
  onChange: (value: UUID | null) => void;
}

export function CategorySelect({ categories, value, onChange }: CategorySelectProps) {
  return (
    <select
      className="field"
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value || null)}
    >
      <option value="">Uncategorised</option>
      {categories.map((category) => (
        <option key={category.id} value={category.id}>
          {category.name}
        </option>
      ))}
    </select>
  );
}
