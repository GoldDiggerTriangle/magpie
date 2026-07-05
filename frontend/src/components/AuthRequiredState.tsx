interface AuthRequiredStateProps {
  detail: string;
  returnTo?: string;
}

export function AuthRequiredState({ detail, returnTo }: AuthRequiredStateProps) {
  const next = returnTo ?? currentPath();
  const loginHref = `/admin/login/?next=${encodeURIComponent(next)}`;

  return (
    <div className="rounded border border-blue-700 bg-blue-50 p-6 text-left text-slate-950">
      <p className="text-base font-semibold">Sign in required</p>
      <p className="mt-2 text-sm leading-6 text-slate-800">{detail}</p>
      <a className="btn-secondary mt-4 inline-flex" href={loginHref}>
        Open admin login
      </a>
    </div>
  );
}

function currentPath() {
  if (typeof window === "undefined") return "/";
  return `${window.location.pathname || "/"}${window.location.search || ""}`;
}
