import { useEffect, useState } from "react";
import { CustomerRecord, fetchCustomersBehavior } from "./services/api";
import { formatCurrency, formatDate, formatNumber } from "./utils/format";

const RANGE_OPTIONS = [
    { days: 7, label: "Last 7 Days" },
    { days: 30, label: "Last 30 Days" },
    { days: 90, label: "Last 90 Days" },
];

function Customers() {
    const [days, setDays] = useState(30);
    const [data, setData] = useState<Awaited<ReturnType<typeof fetchCustomersBehavior>> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetchCustomersBehavior(days)
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

    return (
        <div className="page">
            <div className="page-header">
                <h1>Customers</h1>
                <p>Who is buying, how often, and how much they spend.</p>
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
                    <div className="state-desc">Loading customer data...</div>
                </div>
            ) : error ? (
                <div className="state-box error-box">
                    <div className="state-icon">⚠️</div>
                    <div className="state-title">Could not load customer data</div>
                    <div className="state-desc">{error}</div>
                </div>
            ) : !data || data.customers.length === 0 ? (
                <div className="state-box">
                    <div className="state-icon">🛍️</div>
                    <div className="state-title">No customer activity</div>
                    <div className="state-desc">No bills were recorded in this period.</div>
                </div>
            ) : (
                <>
                    <p className="subtle" style={{ marginBottom: "0.75rem" }}>
                        Period: <strong>{formatDate(data.start_date)} – {formatDate(data.end_date)}</strong>
                    </p>
                    <div className="metric-grid" style={{ marginBottom: "1.5rem" }}>
                        <div className="metric">
                            <div className="metric-label">Unique Customers</div>
                            <div className="metric-value">{formatNumber(data.total_customers)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Total Bills</div>
                            <div className="metric-value">{formatNumber(data.total_bills)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Average Bill Value</div>
                            <div className="metric-value">{formatCurrency(data.average_bill_value)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Repeat Customers</div>
                            <div className="metric-value">{formatNumber(data.repeat_customers)}</div>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: "1.5rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                            <h3 className="section-title" style={{ margin: 0 }}>Top Customers</h3>
                            <span className="badge badge-muted">Ranked by total spend</span>
                        </div>
                        <div style={{ overflowX: "auto" }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Rank</th>
                                        <th>Customer</th>
                                        <th>Visits</th>
                                        <th>Total Spend</th>
                                        <th>Avg / Visit</th>
                                        <th>Last Visit</th>
                                        <th>Purchase Frequency</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.customers.map((c: CustomerRecord, i: number) => (
                                        <tr key={c.customer_id}>
                                            <td>{i + 1}</td>
                                            <td>{c.customer_name}</td>
                                            <td>{formatNumber(c.bill_count)}</td>
                                            <td>{formatCurrency(c.total_spend, { decimals: 0 })}</td>
                                            <td>{formatCurrency(c.average_bill_value)}</td>
                                            <td>{c.last_purchase_date ? formatDate(c.last_purchase_date) : "—"}</td>
                                            <td>
                                                {c.purchase_frequency_pct !== null
                                                    ? `${c.purchase_frequency_pct}%`
                                                    : "—"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="card">
                        <h3 className="section-title" style={{ marginBottom: "0.5rem" }}>About this data</h3>
                        <ul className="note-list">
                            <li>A "visit" is one bill with this customer's ID attached.</li>
                            <li>Purchase frequency = the share of days in the period on which this customer made a purchase.</li>
                            <li>Customers without a linked ID on a bill cannot be attributed and are not listed.</li>
                            <li>This system does not track customer preferences, lifetime value (CLV) or segments.</li>
                        </ul>
                    </div>
                </>
            )}
        </div>
    );
}

export default Customers;