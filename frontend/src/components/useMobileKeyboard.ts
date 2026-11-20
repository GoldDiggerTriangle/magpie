import { useEffect } from "react";

const textTypes = new Set(["text", "search", "email", "password", "tel", "url", "number"]);

export function writableTextFocus() {
  const field = document.activeElement;
  return field instanceof HTMLTextAreaElement ? !field.disabled && !field.readOnly
    : field instanceof HTMLInputElement && textTypes.has(field.type) && !field.disabled && !field.readOnly;
}

export function layoutViewportHeight() { return document.documentElement.clientHeight || window.innerHeight; }

export function visibleViewportBottom() {
  const viewport = window.visualViewport;
  return window.innerWidth < 768 && viewport && Math.abs(viewport.scale - 1) < 0.05
    && Number.isFinite(viewport.height) && Number.isFinite(viewport.offsetTop) && viewport.height > 0
    ? Math.min(layoutViewportHeight(), viewport.offsetTop + viewport.height) : layoutViewportHeight();
}

export function useMobileKeyboard() {
  useEffect(() => {
    const root = document.documentElement;
    const viewport = window.visualViewport;
    let baseline: { width: number; height: number } | null = null;
    let frame = 0;
    const show = (hidden: boolean) => {
      const previous = root.dataset.mobileKeyboard === "open";
      if (hidden) root.dataset.mobileKeyboard = "open";
      else delete root.dataset.mobileKeyboard;
      if (hidden !== previous) window.dispatchEvent(new Event("magpie:viewport-changed"));
    };
    const measure = () => {
      if (window.innerWidth >= 768 || !viewport || !Number.isFinite(viewport.height) || viewport.height <= 0) {
        baseline = null; show(false); return;
      }
      if (!Number.isFinite(viewport.scale) || Math.abs(viewport.scale - 1) >= 0.05) { show(false); return; }
      if (baseline && Math.abs(baseline.width - window.innerWidth) > 2) baseline = null;
      const focused = writableTextFocus();
      if (!focused) {
        // Browser chrome/blur animations must not lower the known keyboard-closed baseline.
        baseline = { width: window.innerWidth, height: Math.max(baseline?.height ?? 0, viewport.height) };
      }
      const drop = baseline ? baseline.height - viewport.height : 0;
      show(Boolean(focused && baseline && drop > Math.max(150, baseline.height * 0.2)));
    };
    const blur = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure); };
    const rotate = () => { baseline = null; measure(); };
    measure();
    document.addEventListener("focusin", measure);
    document.addEventListener("focusout", blur);
    window.addEventListener("resize", measure);
    window.addEventListener("orientationchange", rotate);
    viewport?.addEventListener("resize", measure);
    viewport?.addEventListener("scroll", measure);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("focusin", measure);
      document.removeEventListener("focusout", blur);
      window.removeEventListener("resize", measure);
      window.removeEventListener("orientationchange", rotate);
      viewport?.removeEventListener("resize", measure);
      viewport?.removeEventListener("scroll", measure);
      show(false);
    };
  }, []);
}
