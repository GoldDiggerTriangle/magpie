import { ImageIcon } from "lucide-react";

export function PhotoThumb({ src, alt }: { src: string | null; alt: string }) {
  if (!src) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center bg-slate-800 text-slate-500">
        <ImageIcon className="h-8 w-8" aria-hidden="true" />
      </div>
    );
  }

  return <img className="aspect-[4/3] h-full w-full object-cover" src={src} alt={alt} />;
}
