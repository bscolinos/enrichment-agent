import { HTMLAttributes } from "react";
import clsx from "clsx";

export function Progress({ className, value }: HTMLAttributes<HTMLDivElement> & { value: number }) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={clsx("h-2 w-full rounded-full bg-slate-800", className)}>
      <div
        className="h-2 rounded-full bg-emerald-400"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
