import * as D from "@radix-ui/react-dialog";
import { clsx } from "clsx";
import type { ReactNode } from "react";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: DialogProps) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
        <D.Content
          className={clsx(
            "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border border-watari-bg-dark-tertiary bg-watari-bg-dark-secondary p-5 shadow-2xl",
            className,
          )}
        >
          <D.Title className="text-lg font-semibold text-watari-text-dark-primary">
            {title}
          </D.Title>
          {description ? (
            <D.Description className="mt-1 text-sm text-watari-text-dark-secondary">
              {description}
            </D.Description>
          ) : null}
          <div className="mt-4">{children}</div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export const DialogClose = D.Close;
