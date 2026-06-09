import { Camera, Upload } from "lucide-react";

interface PhotoUploaderProps {
  files: File[];
  onFiles: (files: File[]) => void;
  compact?: boolean;
}

export function PhotoUploader({ files, onFiles, compact = false }: PhotoUploaderProps) {
  return (
    <label className="block">
      <span className={compact ? "btn-secondary inline-flex cursor-pointer items-center gap-2" : "flex cursor-pointer flex-col items-center justify-center rounded border border-dashed border-slate-700 bg-slate-900 p-6 text-center text-slate-300"}>
        {compact ? <Upload className="h-4 w-4" aria-hidden="true" /> : <Camera className="mb-3 h-8 w-8 text-slate-400" aria-hidden="true" />}
        <span>{compact ? "Upload" : "Add photos"}</span>
      </span>
      <input
        className="sr-only"
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        onChange={(event) => onFiles(Array.from(event.target.files ?? []))}
      />
      {files.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {files.map((file) => (
            <span key={`${file.name}-${file.size}`} className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
              {file.name}
            </span>
          ))}
        </div>
      ) : null}
    </label>
  );
}
