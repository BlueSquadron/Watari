import { clsx } from "clsx";
import type { MouseEvent, ReactNode } from "react";

export function Table({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "overflow-hidden rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark",
        className,
      )}
    >
      <table className="w-full border-collapse">{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary text-left text-xs uppercase tracking-wider text-watari-text-dark-secondary">
      {children}
    </thead>
  );
}

export function TH({
  children,
  className,
}: {
  children?: ReactNode;
  className?: string;
}) {
  return <th className={clsx("px-4 py-2 font-medium", className)}>{children}</th>;
}

export function TR({
  children,
  onClick,
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <tr
      onClick={onClick}
      className={clsx(
        "border-b border-watari-bg-dark-tertiary text-sm last:border-none",
        onClick &&
          "cursor-pointer transition-colors hover:bg-watari-bg-dark-tertiary",
        className,
      )}
    >
      {children}
    </tr>
  );
}

export function TD({
  children,
  className,
  title,
  colSpan,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  colSpan?: number;
  onClick?: (event: MouseEvent<HTMLTableCellElement>) => void;
}) {
  return (
    <td
      className={clsx("px-4 py-3", className)}
      title={title}
      colSpan={colSpan}
      onClick={onClick}
    >
      {children}
    </td>
  );
}

export function TableEmpty({
  colSpan,
  children,
}: {
  colSpan: number;
  children: ReactNode;
}) {
  return (
    <tr>
      <td
        colSpan={colSpan}
        className="px-4 py-10 text-center text-sm text-watari-text-dark-secondary"
      >
        {children}
      </td>
    </tr>
  );
}
