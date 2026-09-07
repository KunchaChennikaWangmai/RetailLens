import { useEffect, useMemo, useState } from "react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import {
    fetchProfitability,
    fetchSalesTrend,
    ProfitabilityItem,
    SalesTrendResponse,
} from "./services/api";
import { formatCurrency, formatDate, formatDateLong } from "./utils/format";

type PresetId = "trend-30" | "trend-90" | "top-products" | "profit-category";

const PRESETS: { id: PresetId; label: string; description: string }[] = [
    { id: "trend-30", label: "Sales Trend — 30 Days", description: "Daily revenue over the last 30 days of sales." },
    { id: "trend-90", label: "Sales Trend — 90 Days", description: "Daily revenue over the last 90 days of sales." },
    { id: "top-products", label: "Top Products by Revenue", description: "Ten highest-revenue products in the last 30 days." },
    { id: "profit-category", label: "Gross Profit by Category", description: "Gross profit (revenue − COGS) per category in the last 30 days." },
];

interface CategoryRow {
    category: string;
    gross_profit: number;
}

function categoryProfit(products: ProfitabilityItem[]): CategoryRow[] {
    const map = new Map<string, number>();
    for (const p of products) {
        const key = p.category || "Uncategorised";
        map.set(key, (map.get(key) ?? 0) + p.gross_profit);
    }
    const rows = [...map.entries()].map(([category, gross_profit]) => ({ category, gross_profit }));
    rows.sort((a, b) => b.gross_profit - a.gross_profit);
    return rows;
}

function Analytics() {
    const [preset, setPreset] = useState<PresetId>("trend-30");

    const [trend30, setTrend30] = useState<SalesTrendResponse | null>(null);
    const [trend90, setTrend90] = useState<SalesTrendResponse | null>(null);
    const [profitability, setProfitability] = useState<Awaited<ReturnType<typeof fetchProfitability>> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Fetch all preset data up front (3 deterministic calls), then switching
    // presets is instant and offline.
    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        Promise.all([fetchSalesTrend(30), fetchSalesTrend(90), fetchProfitability(30)])
            .then(([t30, t90, prof]) => {
                if (cancelled) return;
                setTrend30(t30);
                setTrend90(t90);
                setProfitability(prof);
            })
            .catch((err: Error) => {
                if (!cancelled) setError(err.message);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const activePreset = PRESETS.find((p) => p.id === preset) ?? PRESETS[0];

    const chartData = useMemo(() => {
        if (preset === "trend-30") return trend30?.trend ?? [];
        if (preset === "trend-90") return trend90?.trend ?? [];
        if (preset === "top-products")
            return profitability
                ? [...profitability.products]
                      .sort((a, b) => b.revenue - a.revenue)
                      .slice(0, 10)
                      .map((p) => ({ name: p.product_name || p.product_id, revenue: p.revenue }))
                : [];
        return profitability ? categoryProfit(profitability.products).map((c) => ({ name: c.category, gross_profit: c.gross_profit })) : [];
    }, [preset, trend30, trend90, profitability]);

    const isEmpty = !loading && !error && chartData.length === 0;

    return (
        <div className="page">
            <div className="page-header">
                <h1>Analytics</h1>
                <p>On-demand business charts, one at a time.</p>
            </div>

            <div className="chip-row">
                {PRESETS.map((p) => (
                    <button
                        key={p.id}
                        className={`chip ${preset === p.id ? "chip-active" : ""}`}
                        onClick={() => setPreset(p.id)}
                    >
                        {p.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="state-box">
                    <div className="loading-spinner"></div>
                    <div className="state-desc">Loading analysis data...</div>
                </div>
            ) : error ? (
                <div className="state-box error-box">
                    <div className="state-icon">⚠️</div>
                    <div className="state-title">Could not load analysis data</div>
                    <div className="state-desc">{error}</div>
                </div>
            ) : isEmpty ? (
                <div className="state-box">
                    <div className="state-icon">📈</div>
                    <div className="state-title">No data for this analysis</div>
                    <div className="state-desc">There is no data available for the selected period.</div>
                </div>
            ) : (
                <div className="card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap", gap: "0.5rem" }}>
                        <h3 className="section-title" style={{ margin: 0 }}>{activePreset.label}</h3>
                        <span className="badge badge-muted">{activePreset.description}</span>
                    </div>
                    <div style={{ height: "360px", width: "100%" }}>
                        <ResponsiveContainer width="100%" height="100%">
                            {preset === "trend-30" || preset === "trend-90" ? (
                                <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                                    <XAxis
                                        dataKey="sales_date"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: "#6b7280", fontSize: 12 }}
                                        dy={10}
                                        tickFormatter={(value: string) => formatDate(value)}
                                        minTickGap={24}
                                    />
                                    <YAxis
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: "#6b7280", fontSize: 12 }}
                                        tickFormatter={(value: number) => `₹${Number(value).toLocaleString("en-IN")}`}
                                        dx={-10}
                                        width={80}
                                    />
                                    <Tooltip
                                        contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb" }}
                                        formatter={(value: number) => [formatCurrency(value, { decimals: 0 }), "Revenue"]}
                                        labelFormatter={(label: string) => formatDateLong(label)}
                                    />
                                    <Line type="monotone" dataKey="revenue" stroke="#2563eb" strokeWidth={3} dot={false} />
                                </LineChart>
                            ) : (
                                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
                                    <XAxis
                                        type="number"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: "#6b7280", fontSize: 12 }}
                                        tickFormatter={(v: number) => `₹${Number(v).toLocaleString("en-IN")}`}
                                    />
                                    <YAxis
                                        type="category"
                                        dataKey="name"
                                        width={220}
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: "#374151", fontSize: 12 }}
                                        tickFormatter={(v: string) => (v.length > 28 ? `${v.slice(0, 27)}…` : v)}
                                    />
                                    <Tooltip
                                        contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb" }}
                                        formatter={(value: number, name: string) => [
                                            formatCurrency(value, { decimals: 0 }),
                                            name === "revenue" ? "Revenue" : "Gross Profit",
                                        ]}
                                    />
                                    <Bar
                                        dataKey={preset === "top-products" ? "revenue" : "gross_profit"}
                                        fill="#2563eb"
                                        radius={[0, 4, 4, 0]}
                                        barSize={18}
                                    />
                                </BarChart>
                            )}
                        </ResponsiveContainer>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Analytics;