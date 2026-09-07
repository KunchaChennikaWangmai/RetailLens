/**
 * Shared display formatters for Retail Lens pages.
 * All currency values come from the backend in INR.
 */

export function formatCurrency(
    value: number | null | undefined,
    opts: { compact?: boolean; decimals?: number } = {}
): string {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    const decimals = opts.decimals ?? (opts.compact ? 0 : 2);
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: decimals,
        minimumFractionDigits: decimals,
    }).format(value);
}

export function formatNumber(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value);
}

/** Parse "YYYY-MM-DD" as a LOCAL date (avoids UTC off-by-one shifts). */
export function parseISODate(iso: string): Date {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, (m ?? 1) - 1, d ?? 1);
}

/** "2026-08-31" → "31 Aug" */
export function formatDate(iso: string | null | undefined): string {
    if (!iso) return "—";
    return parseISODate(iso).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
    });
}

/** "2026-08-31" → "Mon, 31 Aug 2026" */
export function formatDateLong(iso: string | null | undefined): string {
    if (!iso) return "—";
    return parseISODate(iso).toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
    });
}

/** Add (or subtract) days from an ISO date string, returning ISO. */
export function addDaysISO(iso: string, days: number): string {
    const d = parseISODate(iso);
    d.setDate(d.getDate() + days);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
}