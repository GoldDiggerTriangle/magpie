import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  detail?: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  detail,
  confirmLabel = "Delete",
  danger = true,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
      <div className="w-full max-w-sm rounded border border-slate-700 bg-slate-900 p-5 shadow-xl">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-300" aria-hidden="true" />
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
        </div>
        {detail ? <p className="mt-3 text-sm text-slate-300">{detail}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-secondary" onClick={onCancel} type="button">
            Cancel
          </button>
          <button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm} type="button">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
