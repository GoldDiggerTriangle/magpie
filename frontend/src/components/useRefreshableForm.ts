import { useEffect, useRef, useState, type SetStateAction } from "react";

function same(a: unknown, b: unknown) { return JSON.stringify(a) === JSON.stringify(b); }
function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// Refresh clean fields only, including individual schema attributes; never replace a dirty sibling.
export function mergeClean<T>(local: T, previous: T, fresh: T): T {
  if (same(local, previous)) return fresh;
  if (!object(local) || !object(previous) || !object(fresh)) return local;
  const result: Record<string, unknown> = {};
  for (const key of new Set([...Object.keys(local), ...Object.keys(fresh)])) {
    const value = mergeClean(local[key], previous[key], fresh[key]);
    if (value !== undefined) result[key] = value;
  }
  return result as T;
}

export function useRefreshableForm<T extends object>(identity: string, source: T | null | undefined, initial: T) {
  const [value, setValue] = useState<T>(source ?? initial);
  const baseline = useRef<T>(source ?? initial);
  const key = useRef(identity);
  useEffect(() => {
    if (key.current !== identity) {
      key.current = identity;
      baseline.current = source ?? initial;
      setValue(source ?? initial);
    } else if (source) {
      const previous = baseline.current;
      baseline.current = source;
      setValue((current) => mergeClean(current, previous, source));
    }
  }, [identity, source]);
  function acknowledge(sent: Partial<T>) {
    baseline.current = { ...baseline.current, ...sent };
  }
  function reset(next: T) { baseline.current = next; setValue(next); }
  return [value, setValue as (next: SetStateAction<T>) => void, acknowledge, reset] as const;
}
