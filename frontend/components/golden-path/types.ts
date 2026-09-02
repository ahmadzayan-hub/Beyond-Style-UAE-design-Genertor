import { Lang, STRINGS } from "@/lib/i18n";

/** The localized string table for the active language. */
export type Strings = (typeof STRINGS)[Lang];
