import { clsx } from "clsx";
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

interface LabelProps {
  children: ReactNode;
  required?: boolean;
  className?: string;
}

export function FieldLabel({ children, required, className }: LabelProps) {
  return (
    <span
      className={clsx(
        "text-xs uppercase tracking-wider text-watari-text-dark-secondary",
        className,
      )}
    >
      {children}
      {required ? (
        <span className="ml-0.5 text-severity-critical">*</span>
      ) : null}
    </span>
  );
}

const inputBase =
  "mt-1 w-full rounded-md border border-watari-bg-dark-tertiary bg-watari-bg-dark px-3 py-2 text-sm outline-none focus:border-watari-gold disabled:opacity-50";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const { className, ...rest } = props;
  return <input className={clsx(inputBase, className)} {...rest} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className, ...rest } = props;
  return (
    <textarea className={clsx(inputBase, "resize-y", className)} {...rest} />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const { className, ...rest } = props;
  return <select className={clsx(inputBase, className)} {...rest} />;
}

export function Field({
  label,
  required,
  children,
  error,
}: {
  label: string;
  required?: boolean;
  children: ReactNode;
  error?: string | null;
}) {
  return (
    <label className="block">
      <FieldLabel required={required}>{label}</FieldLabel>
      {children}
      {error ? (
        <p className="mt-1 text-xs text-severity-critical">{error}</p>
      ) : null}
    </label>
  );
}
