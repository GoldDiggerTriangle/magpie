import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";

import { getCategorySchema } from "../api/categories";
import type { FieldSpec, UUID } from "../types";

type Attributes = Record<string, unknown>;

interface SchemaFieldsFormProps {
  categoryId: UUID | null;
  attributes: Attributes;
  onChange: (attributes: Attributes) => void;
  className?: string;
}

export function SchemaFieldsForm({
  categoryId,
  attributes,
  onChange,
  className
}: SchemaFieldsFormProps) {
  const schema = useQuery({
    queryKey: ["category-schema", categoryId],
    queryFn: () => getCategorySchema(categoryId as UUID),
    enabled: Boolean(categoryId)
  });
  const fields = schema.data?.fields ?? [];

  useEffect(() => {
    if (!fields.length) {
      return;
    }
    const next = { ...attributes };
    let changed = false;
    for (const field of fields) {
      if (field.default !== undefined && isBlank(next[field.name])) {
        next[field.name] = field.default;
        changed = true;
      }
    }
    if (changed) {
      onChange(next);
    }
  }, [fields, attributes, onChange]);

  if (!categoryId || (!schema.isLoading && fields.length === 0)) {
    return null;
  }

  if (schema.isLoading) {
    return (
      <div className="rounded border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400">
        Loading category fields
      </div>
    );
  }

  return (
    <div className={className ?? "grid gap-4 rounded border border-slate-800 bg-slate-950/40 p-4 sm:grid-cols-2 lg:grid-cols-3"}>
      {fields.map((field) => (
        <FieldControl
          key={field.name}
          field={field}
          value={attributes[field.name]}
          onChange={(value) => {
            const next = { ...attributes };
            if (isBlank(value) || isEmptyObject(value) || isEmptyList(value)) {
              delete next[field.name];
            } else {
              next[field.name] = value;
            }
            onChange(next);
          }}
        />
      ))}
    </div>
  );
}

function FieldControl({
  field,
  value,
  onChange
}: {
  field: FieldSpec;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (field.type === "choice") {
    return (
      <label className="label">
        <span>{field.label}</span>
        <select className="field" value={stringValue(value)} onChange={(event) => onChange(event.target.value)}>
          <option value="">Unspecified</option>
          {field.choices.map((choice) => (
            <option key={choice} value={choice}>{humanizeChoice(choice)}</option>
          ))}
        </select>
        {field.help_text ? <HelpText text={field.help_text} /> : null}
      </label>
    );
  }

  if (field.type === "int" || field.type === "decimal") {
    return (
      <label className="label">
        <span>{field.label}</span>
        <input
          className="field"
          inputMode={field.type === "decimal" ? "decimal" : "numeric"}
          max={field.max ?? undefined}
          min={field.min ?? undefined}
          step={field.type === "decimal" ? "any" : "1"}
          type="number"
          value={stringValue(value)}
          onChange={(event) => onChange(event.target.value)}
        />
        {field.help_text ? <HelpText text={field.help_text} /> : null}
      </label>
    );
  }

  if (field.type === "object") {
    return (
      <fieldset className="rounded border border-slate-800 bg-slate-900/60 p-3 sm:col-span-2 lg:col-span-3">
        <legend className="px-1 text-sm font-semibold text-slate-200">{field.label}</legend>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          {Object.values(field.item_shape ?? {}).map((nested) => (
            <NestedField
              key={nested.name}
              field={nested}
              value={objectValue(value)[nested.name]}
              onChange={(nestedValue) => {
                const next = { ...objectValue(value) };
                if (isBlank(nestedValue)) {
                  delete next[nested.name];
                } else {
                  next[nested.name] = nestedValue;
                }
                onChange(next);
              }}
            />
          ))}
        </div>
        {field.help_text ? <HelpText text={field.help_text} /> : null}
      </fieldset>
    );
  }

  if (field.type === "list[object]") {
    const rows = Array.isArray(value) ? value.map(objectValue) : [];
    return (
      <fieldset className="rounded border border-slate-800 bg-slate-900/60 p-3 sm:col-span-2 lg:col-span-3">
        <legend className="px-1 text-sm font-semibold text-slate-200">{field.label}</legend>
        <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
          <button
            className="btn-secondary gap-2"
            type="button"
            onClick={() => onChange([...rows, {}])}
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add
          </button>
        </div>
        <div className="mt-3 space-y-3">
          {rows.map((row, index) => (
            <div key={index} className="grid gap-3 rounded border border-slate-800 bg-slate-950/50 p-3 sm:grid-cols-[1fr_1fr_auto]">
              {Object.values(field.item_shape ?? {}).map((nested) => (
                <NestedField
                  key={nested.name}
                  field={nested}
                  value={row[nested.name]}
                  onChange={(nestedValue) => {
                    const nextRows = [...rows];
                    const nextRow = { ...row };
                    if (isBlank(nestedValue)) {
                      delete nextRow[nested.name];
                    } else {
                      nextRow[nested.name] = nestedValue;
                    }
                    nextRows[index] = nextRow;
                    onChange(nextRows);
                  }}
                />
              ))}
              <button
                aria-label={`Remove ${field.label} ${index + 1}`}
                className="icon-button-danger self-end"
                title={`Remove ${field.label}`}
                type="button"
                onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          ))}
          {rows.length === 0 ? <p className="text-sm text-slate-500">No rows added.</p> : null}
        </div>
        {field.help_text ? <HelpText text={field.help_text} /> : null}
      </fieldset>
    );
  }

  const longText = ["notes", "faults", "accessories"].some((part) => field.name.includes(part));
  if (longText) {
    return (
      <label className="label sm:col-span-2 lg:col-span-3">
        <span>{field.label}</span>
        <textarea className="field min-h-20" value={stringValue(value)} onChange={(event) => onChange(event.target.value)} />
        {field.help_text ? <HelpText text={field.help_text} /> : null}
      </label>
    );
  }

  return (
    <label className="label">
      <span>{field.label}</span>
      <input className="field" value={stringValue(value)} onChange={(event) => onChange(event.target.value)} />
      {field.help_text ? <HelpText text={field.help_text} /> : null}
    </label>
  );
}

function NestedField({
  field,
  value,
  onChange
}: {
  field: FieldSpec;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  return (
    <FieldControl
      field={field}
      value={value}
      onChange={onChange}
    />
  );
}

function HelpText({ text }: { text: string }) {
  return <span className="block text-xs font-normal text-slate-500">{text}</span>;
}

function stringValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function objectValue(value: unknown): Attributes {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Attributes
    : {};
}

function isBlank(value: unknown) {
  return value === null || value === undefined || (typeof value === "string" && value.trim() === "");
}

function isEmptyObject(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0;
}

function isEmptyList(value: unknown) {
  return Array.isArray(value) && value.length === 0;
}

export function sanitizeSchemaAttributes(attributes: Attributes) {
  const cleaned: Attributes = {};
  for (const [key, value] of Object.entries(attributes)) {
    if (isBlank(value)) {
      continue;
    }
    if (Array.isArray(value)) {
      const rows = value
        .map((entry) => sanitizeSchemaAttributes(objectValue(entry)))
        .filter((entry) => Object.keys(entry).length > 0);
      if (rows.length) {
        cleaned[key] = rows;
      }
      continue;
    }
    if (value && typeof value === "object") {
      const nested = sanitizeSchemaAttributes(objectValue(value));
      if (Object.keys(nested).length > 0) {
        cleaned[key] = nested;
      }
      continue;
    }
    cleaned[key] = typeof value === "string" ? value.trim() : value;
  }
  return cleaned;
}

function humanizeChoice(value: string) {
  if (value === value.toUpperCase()) {
    return value;
  }
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
