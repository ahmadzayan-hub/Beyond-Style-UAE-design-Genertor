"use client";

import {
  forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";
import { cx } from "./cx";

const CONTROL =
  "w-full rounded-xl border border-ink-200 bg-white px-3.5 text-ink-900 placeholder:text-ink-400 transition-[border-color,box-shadow] duration-150 focus:border-gold-500 focus:outline-none focus:ring-2 focus:ring-gold-500/25 disabled:bg-cream-100 disabled:text-ink-400";

/** Label + control + hint. The hint is tied to the control with
 *  aria-describedby when an id is supplied. */
export function Field({
  label, hint, error, children, className, htmlFor,
}: { label?: ReactNode; hint?: ReactNode; error?: ReactNode; children: ReactNode; className?: string; htmlFor?: string }) {
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-sm font-medium text-ink-800">
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-danger-600" role="alert">{error}</p>
      ) : hint ? (
        <p className="text-xs text-ink-500">{hint}</p>
      ) : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, Omit<InputHTMLAttributes<HTMLInputElement>, "size"> & { size?: "md" | "lg" }>(
  function Input({ className, size = "md", ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={cx(CONTROL, size === "lg" ? "h-14 text-lg" : "h-11 text-sm", className)}
        {...rest}
      />
    );
  },
);

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function TextArea({ className, ...rest }, ref) {
    return <textarea ref={ref} className={cx(CONTROL, "py-2.5 text-sm", className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select ref={ref} className={cx(CONTROL, "h-11 appearance-none pe-9 text-sm", className)} {...rest}>
        {children}
      </select>
    );
  },
);

/** Range with the current value echoed; the value label is required so a
 *  slider is never a mystery control. */
export function Range({
  label, valueLabel, className, ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; valueLabel: ReactNode }) {
  return (
    <label className={cx("block text-xs text-ink-700", className)}>
      <span className="flex items-center justify-between">
        <span>{label}</span>
        <span className="tabular-nums font-semibold text-ink-900">{valueLabel}</span>
      </span>
      <input type="range" className="mt-1 w-full accent-gold-500" {...rest} />
    </label>
  );
}

export function Checkbox({
  className, label, ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return (
    <label className={cx("flex cursor-pointer items-start gap-3 text-sm font-medium text-ink-800", className)}>
      <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 rounded accent-gold-500" {...rest} />
      <span>{label}</span>
    </label>
  );
}
