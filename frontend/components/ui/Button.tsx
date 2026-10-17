"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

export type ButtonVariant = "primary" | "gold" | "secondary" | "ghost" | "success" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-ink-900 text-cream-50 hover:bg-ink-800 shadow-soft",
  gold: "bg-gold-500 text-white hover:bg-gold-600 shadow-gold",
  secondary: "border border-gold-500 bg-white text-gold-700 hover:bg-gold-50",
  ghost: "text-ink-600 hover:bg-cream-200",
  success: "bg-ok-600 text-white hover:bg-ok-800",
  danger: "bg-danger-600 text-white hover:bg-danger-800",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm rounded-lg gap-1.5",
  md: "h-11 px-4 text-sm rounded-xl gap-2",
  lg: "h-14 px-6 text-base rounded-2xl gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Stretch to the container width (mobile primary actions). */
  block?: boolean;
  /** Shows a spinner and disables the control; the label stays visible so
   *  the customer knows which action is running. */
  loading?: boolean;
}

/** One button for the whole app. Every data-testid used by the E2E suite
 *  passes straight through `...rest`, so re-skinning never breaks a test. */
const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", block, loading, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex select-none items-center justify-center font-semibold transition-[background-color,box-shadow,transform] duration-150 ease-out-soft active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40",
        VARIANT[variant],
        SIZE[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden
          className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
});

export default Button;
