import { clsx } from "clsx";
import type { HTMLAttributes } from "react";

export function Skeleton({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx(
        "animate-pulse rounded-md bg-watari-bg-dark-tertiary/80 dark:bg-watari-bg-dark-tertiary",
        className,
      )}
      {...props}
    />
  );
}
