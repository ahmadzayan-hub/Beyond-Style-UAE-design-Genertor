/** Tiny class joiner — no dependency, falsy values dropped. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
