import { Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { layoutViewportHeight, visibleViewportBottom } from "./useMobileKeyboard";

export function ListingSaveBar({ state, disabled, onSave }: { state: string; disabled: boolean; onSave: () => void }) {
  const slot = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ bottom: 0, left: 0, width: 0, height: 0, visible: true });
  useEffect(() => {
    const nav = document.querySelector(".mobile-bottom-nav");
    const editor = slot.current?.closest(".listing-editor");
    const measure = () => {
      const rect = editor?.getBoundingClientRect();
      if (!rect?.width) return;
      const visibleBottom = visibleViewportBottom();
      const navVisible = nav && getComputedStyle(nav).visibility !== "hidden" && getComputedStyle(nav).display !== "none";
      const navHeight = navVisible ? nav.getBoundingClientRect().height : 0;
      const bottom = Math.max(0, layoutViewportHeight() - visibleBottom) + navHeight;
      const height = bar.current?.getBoundingClientRect().height ?? 0;
      const next = { bottom, left: rect.left, width: rect.width, height, visible: rect.top < visibleBottom - navHeight && rect.bottom > (window.visualViewport?.offsetTop ?? 0) };
      setPosition((previous) => Object.keys(next).every((key) => previous[key as keyof typeof next] === next[key as keyof typeof next]) ? previous : next);
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    if (nav) observer?.observe(nav);
    if (editor) observer?.observe(editor);
    if (bar.current) observer?.observe(bar.current);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("magpie:viewport-changed", measure);
    window.visualViewport?.addEventListener("resize", measure);
    window.visualViewport?.addEventListener("scroll", measure);
    return () => {
      observer?.disconnect(); window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure);
      window.removeEventListener("magpie:viewport-changed", measure);
      window.visualViewport?.removeEventListener("resize", measure);
      window.visualViewport?.removeEventListener("scroll", measure);
    };
  }, []);
  // A wrapped fixed bar must reserve its full height above the editor's end.
  return <div ref={slot} className="listing-save-slot" style={{ minHeight: position.height || undefined }}><div ref={bar} className="listing-save-bar" style={{ bottom: position.bottom, left: position.left, width: position.width || undefined, display: position.visible ? "flex" : "none" }}>
    <span role="status" className="min-w-0 break-words">{state === "Saved locally" ? "Saved" : state}</span>
    <button className="btn-primary gap-2" disabled={disabled} onClick={onSave} type="button"><Save size={18} />Save</button>
  </div></div>;
}
