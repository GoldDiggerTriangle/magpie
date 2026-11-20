import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useMobileKeyboard, visibleViewportBottom } from "./useMobileKeyboard";

function Harness() { useMobileKeyboard(); return <><input aria-label="Text" /><input aria-label="Read only" readOnly /><textarea aria-label="Notes" /><select aria-label="Select"><option>One</option></select></>; }
function setup() {
  vi.stubGlobal("innerWidth", 390); vi.stubGlobal("innerHeight", 844);
  const viewport = Object.assign(new EventTarget(), { height: 844, width: 390, offsetTop: 0, scale: 1 });
  vi.stubGlobal("visualViewport", viewport);
  const view = render(<Harness />);
  const change = (values: Partial<typeof viewport>) => act(() => { Object.assign(viewport, values); viewport.dispatchEvent(new Event("resize")); });
  return { ...view, viewport, change };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("writable focus alone, select, read-only and unknown viewport data keep nav visible", () => {
  const view = setup();
  fireEvent.focusIn(view.getByLabelText("Text"));
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
  view.getByLabelText("Select").focus(); view.change({ height: 400 });
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
  view.getByLabelText("Read only").focus();
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
  view.getByLabelText("Text").focus(); view.change({ scale: NaN });
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
});

test("drop plus writable focus hides nav, field switch preserves it and viewport restoration clears it", () => {
  const view = setup();
  act(() => view.getByLabelText("Text").focus()); view.change({ height: 420, offsetTop: 20 });
  expect(document.documentElement.dataset.mobileKeyboard).toBe("open");
  expect(visibleViewportBottom()).toBe(440);
  act(() => view.getByLabelText("Notes").focus());
  expect(document.documentElement.dataset.mobileKeyboard).toBe("open");
  view.change({ height: 844, offsetTop: 0 });
  expect(document.activeElement).toBe(view.getByLabelText("Notes"));
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
});

test("zoom, rotation, desktop and unavailable visualViewport never hide navigation", () => {
  const view = setup(); act(() => view.getByLabelText("Text").focus());
  view.change({ height: 420, scale: 2 });
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
  view.change({ scale: 1 });
  act(() => window.dispatchEvent(new Event("orientationchange")));
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
  vi.stubGlobal("innerWidth", 1000); view.change({ height: 300 });
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
  cleanup(); vi.stubGlobal("visualViewport", undefined); render(<Harness />);
  expect(document.documentElement.dataset.mobileKeyboard).toBeUndefined();
});
