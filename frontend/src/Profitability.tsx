import { useEffect, useMemo, useState } from "react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { fetchProfitability, ProfitabilityItem } from "./services/api";
import { formatCurrency, formatDate, formatNumber } from "./utils/format";

const RANGE_OPTIONS = [
    { days: 7, label: "Last 7 Days" },
    { days: 30, label: "Last 30 Days" },
    { days: 90, label: "Last 90 Days" },
];

interface CategoryRow {
    category: string;
    revenue: number;
    cogs: number;
    gross_profit: number;
    margin_pct: number;
}

/** Deterministic client-side grouping of the same backend product rows. */
function byCategory(products: ProfitabilityItem[]): CategoryRow[] {
    const map = new Map<string, CategoryRow>();
    for (const p of products) {
        const key = p.category || "Uncategorised";
        const row =
            map.get(key) ?? { category: key, revenue: 0, cogs: 0, gross_profit: 0, margin_pct: 0 };
        row.revenue += p.revenue;
        row.cogs += p.cost_of_goods_sold;
        row.gross_profit += p.gross_profit;
        map.set(key, row);
    }
    const rows = [...map.values()].map((r) => ({
        ...r,
        margin_pct: r.revenue > 0 ? Math.round((r.gross_profit / r.revenue) * 10000) / 100 : 0,
    }));
    rows.sort((a, b) => b.gross_profit - a.gross_profit);
    return rows;
}

function Profitability() {
    const [days, setDays] = useState(30);
    const [data, setData] = useState<Awaited<ReturnType<typeof fetchProfitability>> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetchProfitability(days)
            .then((res) => {
                if (!cancelled) setData(res);
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
    }, [days]);

    const categories = useMemo(() => (data ? byCategory(data.products) : []), [data]);
    const topProducts = useMemo(
        () => (data ? [...data.products].sort((a, b) => b.gross_profit - a.gross_profit).slice(0, 10) : []),
        [data]
    );

    return (
        <div className="page">
            <div className="page-header">
                <h1>Profitability</h1>
                <p>Which products and categories actually make you money.</p>
            </div>

            <div className="state-box disclaimer-box" style={{ marginBottom: "1.5rem" }}>
                <div className="state-icon">ℹ️</div>
                <div>
                    <div className="state-title">Gross profit, not net profit</div>
                    <div className="state-desc">
                        These figures show gross profit — revenue minus cost of goods sold. Operating
                        expenses such as rent, utilities, and labour are not included. Net profit data
                        is not available in this system.
                    </div>
                </div>
            </div>

            <div className="chip-row">
                {RANGE_OPTIONS.map((opt) => (
                    <button
                        key={opt.days}
                        className={`chip ${days === opt.days ? "chip-active" : ""}`}
                        onClick={() => setDays(opt.days)}
                    >
                        {opt.label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="state-box">
                    <div className="loading-spinner"></div>
                    <div className="state-desc">Loading profitability data...</div>
                </div>
            ) : error ? (
                <div className="state-box error-box">
                    <div className="state-icon">⚠️</div>
                    <div className="state-title">Could not load profitability data</div>
                    <div className="state-desc">{error}</div>
                </div>
            ) : !data || data.products.length === 0 ? (
                <div className="state-box">
                    <div className="state-icon">💰</div>
                    <div className="state-title">No sales in this period</div>
                    <div className="state-desc">Profitability appears once products are sold.</div>
                </div>
            ) : (
                <>
                    <p className="subtle" style={{ marginBottom: "0.75rem" }}>
                        Period: <strong>{formatDate(data.start_date)} – {formatDate(data.end_date)}</strong>
                    </p>
                    <div className="metric-grid" style={{ marginBottom: "1.5rem" }}>
                        <div className="metric">
                            <div className="metric-label">Revenue</div>
                            <div className="metric-value">{formatCurrency(data.total_revenue, { decimals: 0 })}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Cost of Goods Sold</div>
                            <div className="metric-value">{formatCurrency(data.total_cogs, { decimals: 0 })}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Gross Profit</div>
                            <div className="metric-value">{formatCurrency(data.gross_profit, { decimals: 0 })}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Gross Margin</div>
                            <div className="metric-value">{data.gross_margin_pct}%</div>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: "1.5rem" }}>
                        <h3 className="section-title" style={{ marginBottom: "1rem" }}>Top Products by Gross Profit</h3>
                        <div style={{ height: Math.max(220, topProducts.length * 38), width: "100%" }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={topProducts} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 0 }}>
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
                                        dataKey="product_name"
                                        width={220}
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: "#374151", fontSize: 12 }}
                                        tickFormatter={(v: string) => (v.length > 28 ? `${v.slice(0, 27)}…` : v)}
                                    />
                                    <Tooltip
                                        contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb" }}
                                        formatter={(value: number) => [formatCurrency(value, { decimals: 0 }), "Gross Profit"]}
                                    />
                                    <Bar dataKey="gross_profit" fill="#2563eb" radius={[0, 4, 4, 0]} barSize={18} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: "1.5rem" }}>
                        <h3 className="section-title" style={{ marginBottom: "1rem" }}>Product Profitability</h3>
                        <div style={{ overflowX: "auto" }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Product</th>
                                        <th>Category</th>
                                        <th>Units Sold</th>
                                        <th>Revenue</th>
                                        <th>COGS</th>
                                        <th>Gross Profit</th>
                                        <th>Margin</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.products.map((p) => (
                                        <tr key={p.product_id}>
                                            <td>{p.product_name || p.product_id}</td>
                                            <td>{p.category || "—"}</td>
                                            <td>{formatNumber(p.units_sold)}</td>
                                            <td>{formatCurrency(p.revenue, { decimals: 0 })}</td>
                                            <td>{formatCurrency(p.cost_of_goods_sold, { decimals: 0 })}</td>
                                            <td>{formatCurrency(p.gross_profit, { decimals: 0 })}</td>
                                            <td>{p.gross_margin_pct !== null ? `${p.gross_margin_pct}%` : "—"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="card">
                        <h3 className="section-title" style={{ marginBottom: "1rem" }}>Category Summary</h3>
                        <div style={{ overflowX: "auto" }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Category</th>
                                        <th>Revenue</th>
                                        <th>COGS</th>
                                        <th>Gross Profit</th>
                                        <th>Margin</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {categories.map((c) => (
                                        <tr key={c.category}>
                                            <td>{c.category}</td>
                                            <td>{formatCurrency(c.revenue, { decimals: 0 })}</td>
                                            <td>{formatCurrency(c.cogs, { decimals: 0 })}</td>
                                            <td>{formatCurrency(c.gross_profit, { decimals: 0 })}</td>
                                            <td>{c.margin_pct}%</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default Profitability;