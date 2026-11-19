import { act, renderHook } from "@testing-library/react";
import { expect, test } from "vitest";
import { mergeClean, useRefreshableForm } from "./useRefreshableForm";

test("refresh merges clean siblings but preserves dirty fields and nested schema attributes", () => {
  const old = { title: "Saved", attributes: { metal: "gold", weight: "1" }, notes: "" };
  const local = { ...old, title: "Typing", attributes: { ...old.attributes, metal: "mine" } };
  expect(mergeClean(local, old, { ...old, title: "Remote", notes: "New note", attributes: { metal: "silver", weight: "2" } }))
    .toEqual({ title: "Typing", notes: "New note", attributes: { metal: "mine", weight: "2" } });
});

test("acknowledging a save does not overwrite typing performed while it was pending", () => {
  const first = { title: "Saved", notes: "" };
  const hook = renderHook(({ source, id }) => useRefreshableForm(id, source, first), { initialProps: { source: first, id: "one" } });
  act(() => hook.result.current[1]({ ...first, title: "Sent" }));
  act(() => hook.result.current[1]({ ...first, title: "Still typing" }));
  act(() => hook.result.current[2]({ title: "Sent" }));
  hook.rerender({ source: { ...first, title: "Normalised sent", notes: "Fresh clean note" }, id: "one" });
  expect(hook.result.current[0]).toEqual({ title: "Still typing", notes: "Fresh clean note" });
  hook.rerender({ source: { title: "Other item", notes: "" }, id: "two" });
  expect(hook.result.current[0].title).toBe("Other item");
});

test("clean saved fields accept canonical refreshed values without dropping unsaved siblings", () => {
  const first = { title: "Old", notes: "" };
  const hook = renderHook(({ source }) => useRefreshableForm("one", source, first), { initialProps: { source: first } });
  act(() => hook.result.current[1]({ title: "Sent", notes: "unsaved" }));
  act(() => hook.result.current[2]({ title: "Sent" }));
  hook.rerender({ source: { title: "Canonical", notes: "remote" } });
  expect(hook.result.current[0]).toEqual({ title: "Canonical", notes: "unsaved" });
});
