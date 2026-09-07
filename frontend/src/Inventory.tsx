import { useEffect, useState } from "react";
import {
    fetchReplenishmentRisk,
    fetchStock,
    fetchSupply,
    ReplenishmentRiskResponse,
    RiskItem,
    StockResponse,
    SupplyResponse,
} from "./services/api";
import { formatDate, formatNumber } from "./utils/format";

type StockStatus = "low" | "monitor" | "ok" | "unknown";

function stockStatus(stock: number | null, reorder: number | null): StockStatus {
    if (stock === null || reorder === null) return "unknown";
    if (stock < reorder) return "low";
    if (stock < reorder * 1.25) return "monitor";
    return "ok";
}

const STATUS_LABEL: Record<StockStatus, string> = {
    low: "Low Stock",
    monitor: "Monitor",
    ok: "OK",
    unknown: "No Stock Record",
};

function StatusBadge({ status }: { status: StockStatus }) {
    const cls =
        status === "low"
            ? "badge badge-danger"
            : status === "monitor"
              ? "badge badge-warning"
              : status === "ok"
                ? "badge badge-success"
                : "badge badge-muted";
    return <span className={cls}>{STATUS_LABEL[status]}</span>;
}

/** Products that are not "OK" — the shopkeeper's reorder shortlist,
 *  already priority-ordered by the backend (below-reorder first,
 *  then essentiality, then daily demand). */
function needingAttention(products: RiskItem[]): RiskItem[] {
    return products.filter((p) => {
        const status = stockStatus(p.stock_on_hand, p.reorder_level);
        return status === "low" || status === "monitor";
    });
}

function Inventory() {
    const [risk, setRisk] = useState<ReplenishmentRiskResponse | null>(null);
    const [stock, setStock] = useState<StockResponse | null>(null);
    const [supply, setSupply] = useState<SupplyResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        setError(null);
        Promise.all([fetchReplenishmentRisk(30), fetchStock(), fetchSupply()])
            .then(([r, s, sup]) => {
                setRisk(r);
                setStock(s);
                setSupply(sup);
            })
            .catch((err: Error) => setError(err.message))
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="page">
                <div className="page-header">
                    <h1>Inventory</h1>
                    <p>Stock levels, replenishment priorities and incoming supply.</p>
                </div>
                <div className="state-box">
                    <div className="loading-spinner"></div>
                    <div className="state-desc">Loading inventory data...</div>
                </div>
            </div>
        );
    }

    if (error || !risk || !stock || !supply) {
        return (
            <div className="page">
                <div className="page-header">
                    <h1>Inventory</h1>
                    <p>Stock levels, replenishment priorities and incoming supply.</p>
                </div>
                <div className="state-box error-box">
                    <div className="state-icon">⚠️</div>
                    <div className="state-title">Could not load inventory data</div>
                    <div className="state-desc">{error || "No data returned."}</div>
                </div>
            </div>
        );
    }

    const withIncoming = supply.products.filter(
        (p) => p.incoming_quantity !== null && p.incoming_quantity > 0
    );
    const nextDelivery = supply.products
        .map((p) => p.expected_delivery_date)
        .filter((d): d is string => !!d)
        .sort()[0];
    const attention = needingAttention(risk.products);

    return (
        <div className="page">
            <div className="page-header">
                <h1>Inventory</h1>
                <p>
                    Stock levels, replenishment priorities and incoming supply
                    (demand based on last {30} days of sales).
                </p>
            </div>

            <div className="metric-grid" style={{ marginBottom: "1.5rem" }}>
                <div className="metric">
                    <div className="metric-label">Products Tracked</div>
                    <div className="metric-value">{formatNumber(stock.total_products)}</div>
                </div>
                <div className="metric">
                    <div className="metric-label">Below Reorder Level</div>
                    <div className="metric-value">{formatNumber(stock.below_reorder_count)}</div>
                </div>
                <div className="metric">
                    <div className="metric-label">With Incoming Supply</div>
                    <div className="metric-value">{formatNumber(withIncoming.length)}</div>
                </div>
                <div className="metric">
                    <div className="metric-label">Next Expected Delivery</div>
                    <div className="metric-value" style={{ fontSize: "1.1rem", paddingTop: "0.35rem" }}>
                        {nextDelivery ? formatDate(nextDelivery) : "—"}
                    </div>
                </div>
            </div>

            {/* --- Reorder priorities --- */}
            <div className="card" style={{ marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                    <h3 className="section-title" style={{ margin: 0 }}>Needs Attention First</h3>
                    <span className="badge badge-muted">Prioritised by urgency</span>
                </div>
                {attention.length === 0 ? (
                    <div className="state-box" style={{ border: "none" }}>
                        <div className="state-icon">✅</div>
                        <div className="state-title">All products are adequately stocked</div>
                        <div className="state-desc">Nothing is at or below its reorder level right now.</div>
                    </div>
                ) : (
                    <div style={{ overflowX: "auto" }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Category</th>
                                    <th>Stock</th>
                                    <th>Reorder Level</th>
                                    <th>Incoming</th>
                                    <th>Coverage</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {attention.map((p) => (
                                    <tr key={p.product_id}>
                                        <td>{p.product_name || p.product_id}</td>
                                        <td>{p.category || "—"}</td>
                                        <td>{p.stock_on_hand ?? "—"}</td>
                                        <td>{p.reorder_level ?? "—"}</td>
                                        <td>{p.incoming_quantity ?? "—"}</td>
                                        <td>
                                            {p.stock_coverage_days !== null
                                                ? `${p.stock_coverage_days} days`
                                                : "No recent sales"}
                                        </td>
                                        <td>
                                            <StatusBadge status={stockStatus(p.stock_on_hand, p.reorder_level)} />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                <p className="subtle" style={{ marginTop: "0.75rem" }}>
                    Coverage = days of stock left at the average daily sales rate of the last 30 days.
                </p>
            </div>

            {/* --- Current stock --- */}
            <div className="card" style={{ marginBottom: "1.5rem" }}>
                <h3 className="section-title" style={{ marginBottom: "1rem" }}>Current Stock</h3>
                {stock.products.length === 0 ? (
                    <div className="state-box" style={{ border: "none" }}>
                        <div className="state-icon">📦</div>
                        <div className="state-title">No stock records</div>
                    </div>
                ) : (
                    <div style={{ overflowX: "auto" }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Category</th>
                                    <th>Stock on Hand</th>
                                    <th>Reorder Level</th>
                                    <th>Status</th>
                                    <th>Last Updated</th>
                                </tr>
                            </thead>
                            <tbody>
                                {stock.products.map((p) => (
                                    <tr key={p.product_id}>
                                        <td>{p.product_name || p.product_id}</td>
                                        <td>{p.category || "—"}</td>
                                        <td>{formatNumber(p.stock_on_hand)}</td>
                                        <td>{formatNumber(p.reorder_level)}</td>
                                        <td>
                                            <StatusBadge status={stockStatus(p.stock_on_hand, p.reorder_level)} />
                                        </td>
                                        <td className="subtle">{p.last_updated ? formatDate(p.last_updated.slice(0, 10)) : "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* --- Incoming supply --- */}
            <div className="card" style={{ marginBottom: "1.5rem" }}>
                <h3 className="section-title" style={{ marginBottom: "1rem" }}>Incoming Supply</h3>
                {supply.products.length === 0 ? (
                    <div className="state-box" style={{ border: "none" }}>
                        <div className="state-icon">🚚</div>
                        <div className="state-title">No incoming supply orders</div>
                    </div>
                ) : (
                    <div style={{ overflowX: "auto" }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Category</th>
                                    <th>Supplier</th>
                                    <th>Incoming Qty</th>
                                    <th>Lead Time</th>
                                    <th>Expected Delivery</th>
                                </tr>
                            </thead>
                            <tbody>
                                {supply.products.map((p) => (
                                    <tr key={p.product_id}>
                                        <td>{p.product_name || p.product_id}</td>
                                        <td>{p.category || "—"}</td>
                                        <td>{p.supplier_id || "—"}</td>
                                        <td>{p.incoming_quantity ?? "—"}</td>
                                        <td>{p.supplier_lead_time_days !== null ? `${p.supplier_lead_time_days} days` : "—"}</td>
                                        <td>{p.expected_delivery_date ? formatDate(p.expected_delivery_date) : "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

export default Inventory;