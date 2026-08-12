import { forwardRef, type ButtonHTMLAttributes } from "react";
import { clsx } from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-watari-gold text-watari-bg-dark hover:bg-watari-gold-light focus-visible:ring-watari-gold",
  secondary:
    "bg-watari-bg-dark-tertiary dark:bg-watari-bg-dark-tertiary text-watari-text-dark-primary hover:bg-watari-bg-dark-secondary focus-visible:ring-watari-gold",
  ghost:
    "bg-transparent text-watari-text-dark-primary hover:bg-watari-bg-dark-tertiary focus-visible:ring-watari-gold",
  danger:
    "bg-severity-critical/90 text-white hover:bg-severity-critical focus-visible:ring-severity-critical",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      children,
      ...props
    },
    ref,
  ) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-watari-bg-dark",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" />
      ) : null}
      {children}
    </button>
  ),
);
Button.displayName = "Button";
