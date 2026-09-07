import { useCallback, useEffect, useState } from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";
import {
    DailySummaryData,
    fetchHomeSummary,
    fetchSalesTrend,
    SalesTrendResponse,
} from "./services/api";
import {
    addDaysISO,
    formatCurrency,
    formatDate,
    formatDateLong,
    formatNumber,
} from "./utils/format";
import AdviceCard from "./AdviceCard";

type RangeKey = "today" | "yesterday";

const MONTH_SUMMARY_PROMPT =
    "Give me a practical summary of my business over the last month: how sales are trending, my best and worst selling products, products I should restock soon, labour costs, and anything notable about my customers.";

const YEAR_SUMMARY_PROMPT =
    "Give me a high-level summary of my business over the last year: sales trend, top products by revenue, gross profit outlook, inventory health, workforce costs and my most valuable customers.";

function Home({ onAskChat }: { onAskChat: (message: string) => void }) {
    const [range, setRange] = useState<RangeKey>("today");

    // Daily summary (Today / Yesterday)
    const [summary, setSummary] = useState<DailySummaryData | null>(null);
    const [summaryMessage, setSummaryMessage] = useState<string | null>(null);
    const [summaryLoading, setSummaryLoading] = useState(true);
    const [summaryError, setSummaryError] = useState<string | null>(null);
    const [anchorDate, setAnchorDate] = useState<string | null>(null); // latest business day with data

    // 30-day sales trend
    const [trend, setTrend] = useState<SalesTrendResponse | null>(null);
    const [trendLoading, setTrendLoading] = useState(true);
    const [trendError, setTrendError] = useState<string | null>(null);

    const loadSummary = useCallback((selected: RangeKey, anchor: string | null) => {
        setSummaryLoading(true);
        setSummaryError(null);
        setSummaryMessage(null);

        if (selected === "yesterday" && !anchor) {
            // Cannot resolve "yesterday" until the latest business day is known.
            setSummaryLoading(false);
            setSummary(null);
            setSummaryMessage("No recent sales data available.");
            return;
        }

        const dateParam =
            selected === "yesterday" && anchor ? addDaysISO(anchor, -1) : undefined;

        fetchHomeSummary(dateParam)
            .then((res) => {
                setSummary(res.summary);
                setSummaryMessage(res.message);
                if (res.summary) setAnchorDate(res.summary.sales_date);
            })
            .catch((err: Error) => setSummaryError(err.message))
            .finally(() => setSummaryLoading(false));
    }, []);

    const loadTrend = useCallback(() => {
        setTrendLoading(true);
        setTrendError(null);
        fetchSalesTrend(30)
            .then((res) => {
                setTrend(res);
                // Fall back to the trend's last day as the "latest data" anchor.
                setAnchorDate((prev) => prev ?? res.end_date);
            })
            .catch((err: Error) => setTrendError(err.message))
            .finally(() => setTrendLoading(false));
    }, []);

    useEffect(() => {
        loadSummary("today", null);
        loadTrend();
    }, [loadSummary, loadTrend]);

    const handleRange = (selected: RangeKey) => {
        if (selected === range) return;
        setRange(selected);
        loadSummary(selected, anchorDate);
    };

    const businessDate = range === "today" ? summary?.sales_date ?? anchorDate : anchorDate ? addDaysISO(anchorDate, -1) : null;

    return (
        <div className="page">
            <div className="page-header">
                <h1>Dashboard</h1>
                <p>Welcome back. Here is what is happening in your shop.</p>
            </div>

            <div className="form-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
                <div className="toggle-group">
                    <button
                        className={`toggle-btn ${range === "today" ? "active" : ""}`}
                        onClick={() => handleRange("today")}
                    >
                        Today
                    </button>
                    <button
                        className={`toggle-btn ${range === "yesterday" ? "active" : ""}`}
                        onClick={() => handleRange("yesterday")}
                        disabled={!anchorDate}
                    >
                        Yesterday
                    </button>
                </div>

                <div className="btn-group">
                    <button className="btn btn-soft" onClick={() => onAskChat(MONTH_SUMMARY_PROMPT)}>
                        1 Month Summary
                    </button>
                    <button className="btn btn-soft" onClick={() => onAskChat(YEAR_SUMMARY_PROMPT)}>
                        1 Year Summary
                    </button>
                </div>
            </div>

            {/* --- KPI cards --- */}
            {summaryLoading ? (
                <div className="state-box" style={{ marginBottom: "1.5rem" }}>
                    <div className="loading-spinner"></div>
                    <div className="state-desc">Loading today's numbers...</div>
                </div>
            ) : summaryError ? (
                <div className="state-box error-box" style={{ marginBottom: "1.5rem" }}>
                    <div className="state-icon">⚠️</div>
                    <div className="state-title">Could not load sales summary</div>
                    <div className="state-desc">{summaryError}</div>
                </div>
            ) : summary ? (
                <>
                    <p className="subtle" style={{ marginBottom: "0.75rem" }}>
                        Business day: <strong>{formatDateLong(businessDate)}</strong>
                    </p>
                    <div className="metric-grid" style={{ marginBottom: "1.5rem" }}>
                        <div className="metric">
                            <div className="metric-label">Revenue</div>
                            <div className="metric-value">{formatCurrency(summary.total_revenue, { decimals: 0 })}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Bills</div>
                            <div className="metric-value">{formatNumber(summary.total_bills)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Units Sold</div>
                            <div className="metric-value">{formatNumber(summary.total_units_sold)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Average Bill Value</div>
                            <div className="metric-value">{formatCurrency(summary.average_bill_value)}</div>
                        </div>
                    </div>
                </>
            ) : (
                <div className="state-box" style={{ marginBottom: "1.5rem" }}>
                    <div className="state-icon">🗓️</div>
                    <div className="state-title">No sales recorded</div>
                    <div className="state-desc">
                        {summaryMessage || "There are no sales recorded for this day."}
                    </div>
                </div>
            )}

            {/* --- Advice of the day --- */}
            <AdviceCard onAskChat={onAskChat} />

            {/* --- 30-day sales trend --- */}
            <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem", flexWrap: "wrap", gap: "0.5rem" }}>
                    <h3 className="section-title" style={{ margin: 0 }}>Sales Trend — Last 30 Days</h3>
                    {trend && !trendLoading && !trendError && (
                        <span className="badge badge-muted">
                            {formatDate(trend.start_date)} – {formatDate(trend.end_date)}
                        </span>
                    )}
                </div>
                {trendLoading ? (
                    <div className="state-box" style={{ border: "none" }}>
                        <div className="loading-spinner"></div>
                        <div className="state-desc">Loading sales trend...</div>
                    </div>
                ) : trendError ? (
                    <div className="state-box error-box" style={{ border: "none" }}>
                        <div className="state-icon">⚠️</div>
                        <div className="state-title">Could not load sales trend</div>
                        <div className="state-desc">{trendError}</div>
                    </div>
                ) : !trend || trend.trend.length === 0 ? (
                    <div className="state-box" style={{ border: "none" }}>
                        <div className="state-icon">📈</div>
                        <div className="state-title">No sales data yet</div>
                        <div className="state-desc">Once sales are recorded, the daily trend will appear here.</div>
                    </div>
                ) : (
                    <div style={{ height: "300px", width: "100%" }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trend.trend} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
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
                                    contentStyle={{ borderRadius: "8px", border: "1px solid #e5e7eb", boxShadow: "0 1px 3px rgba(0,0,0,0.1)" }}
                                    formatter={(value: number, name: string) =>
                                        name === "revenue" ? [formatCurrency(value, { decimals: 0 }), "Revenue"] : [formatNumber(value), name]
                                    }
                                    labelFormatter={(label: string) => formatDateLong(label)}
                                    labelStyle={{ fontWeight: 600, color: "#111827", marginBottom: "4px" }}
                                />
                                <Line
                                    type="monotone"
                                    dataKey="revenue"
                                    stroke="#2563eb"
                                    strokeWidth={3}
                                    dot={false}
                                    activeDot={{ r: 5, fill: "#2563eb", stroke: "#fff", strokeWidth: 2 }}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>
        </div>
    );
}

export default Home;