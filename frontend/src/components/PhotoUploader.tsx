import { Camera, Upload } from "lucide-react";

interface PhotoUploaderProps {
  files: File[];
  onFiles: (files: File[]) => void;
  compact?: boolean;
}

export function PhotoUploader({ files, onFiles, compact = false }: PhotoUploaderProps) {
  function addFiles(selected: File[]) {
    if (!selected.length) {
      return;
    }
    onFiles([...files, ...selected]);
  }

  return (
    <div className="block">
      <div className={compact ? "flex flex-wrap gap-2" : "grid gap-3 rounded border border-dashed border-slate-300 bg-white p-4 text-slate-950 sm:grid-cols-2"}>
        <label className={compact ? "btn-secondary inline-flex cursor-pointer items-center gap-2" : "flex min-h-24 cursor-pointer flex-col items-center justify-center rounded border border-slate-400 bg-slate-50 p-4 text-center font-semibold text-slate-950"}>
          <Camera className={compact ? "h-4 w-4" : "mb-2 h-7 w-7 text-slate-800"} aria-hidden="true" />
          <span>Take photo</span>
          <input
            aria-label="Take photo"
            className="sr-only"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(event) => {
              addFiles(Array.from(event.target.files ?? []));
              event.currentTarget.value = "";
            }}
          />
        </label>
        <label className={compact ? "btn-secondary inline-flex cursor-pointer items-center gap-2" : "flex min-h-24 cursor-pointer flex-col items-center justify-center rounded border border-slate-400 bg-slate-50 p-4 text-center font-semibold text-slate-950"}>
          <Upload className={compact ? "h-4 w-4" : "mb-2 h-7 w-7 text-slate-800"} aria-hidden="true" />
          <span>Choose from library</span>
          <input
            aria-label="Choose from library"
            className="sr-only"
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => {
              addFiles(Array.from(event.target.files ?? []));
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      {files.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {files.map((file) => (
            <span key={`${file.name}-${file.size}`} className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
              {file.name}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
