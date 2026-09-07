const PIPELINE_STEPS = [
    "POS / ERP",
    "Data Pipeline",
    "BigQuery",
    "MCP Toolbox",
    "AI Agents",
    "Retail Lens",
];

const TABLES: { name: string; description: string }[] = [
    {
        name: "sales_transactions",
        description:
            "One row per bill line: product, quantity, prices, bill number and timestamp. Powers revenue, units sold and trend analyses.",
    },
    {
        name: "customer_bills",
        description:
            "One row per bill with the linked customer (id, name, phone). Powers customer spending and visit behaviour.",
    },
    {
        name: "inventory_stock",
        description:
            "Current stock on hand and reorder level per product, with the time it was last updated.",
    },
    {
        name: "inventory_supply",
        description:
            "Incoming supply orders: supplier, ordered quantity, lead time and expected delivery date.",
    },
    {
        name: "inventory_metadata",
        description:
            "Product master data: name, category, cost and retail price, essentiality tier, perishability and shelf life.",
    },
    {
        name: "workforce_shifts",
        description:
            "One row per scheduled shift: employee, timing, rostered hours, hourly wage and check-in/out timestamps.",
    },
];

function Data() {
    return (
        <div className="page">
            <div className="page-header">
                <h1>Data</h1>
                <p>Where Retail Lens gets its numbers, and what kind of data this is.</p>
            </div>

            <div className="card" style={{ marginBottom: "1.5rem" }}>
                <h3 className="section-title" style={{ marginBottom: "1rem" }}>How data flows</h3>
                <div className="flow-diagram">
                    {PIPELINE_STEPS.map((step, i) => (
                        <span key={step} style={{ display: "contents" }}>
                            {i > 0 && <span className="flow-arrow">→</span>}
                            <span className="flow-node">{step}</span>
                        </span>
                    ))}
                </div>
                <p className="subtle" style={{ marginTop: "0.75rem" }}>
                    Point-of-sale or ERP data is loaded into BigQuery. The MCP Toolbox exposes
                    curated queries over that data, AI agents use those tools to answer
                    questions, and Retail Lens presents everything in one place.
                </p>
            </div>

            <div className="card" style={{ marginBottom: "1.5rem" }}>
                <h3 className="section-title" style={{ marginBottom: "1rem" }}>Tables in this system</h3>
                <div style={{ overflowX: "auto" }}>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Table</th>
                                <th>What it contains</th>
                            </tr>
                        </thead>
                        <tbody>
                            {TABLES.map((t) => (
                                <tr key={t.name}>
                                    <td style={{ whiteSpace: "nowrap", fontWeight: 600 }}>{t.name}</td>
                                    <td>{t.description}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="card" style={{ marginBottom: "1.5rem" }}>
                <h3 className="section-title" style={{ marginBottom: "1rem" }}>About this data</h3>
                <ul className="note-list">
                    <li>
                        <strong>Realistic demo data.</strong> The transaction, bill and shift
                        records follow realistic retail patterns (daily and weekly rhythms,
                        plausible basket sizes and prices) so the app behaves like it would in a
                        real shop.
                    </li>
                    <li>
                        <strong>Synthetic demo data.</strong> All of it is machine-generated for
                        this demo — no real customer, employee or business is behind these rows.
                        Treat every number you see as illustrative, not factual.
                    </li>
                    <li>
                        <strong>Coverage.</strong> Sales span May–August 2026; bills, shifts and
                        stock cover August 2026; expected deliveries run into early September
                        2026. Pages show the most recent dates that actually have data.
                    </li>
                </ul>
            </div>

            <div className="card">
                <h3 className="section-title" style={{ marginBottom: "1rem" }}>In production</h3>
                <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", margin: 0 }}>
                    In a live deployment, the same pipeline would run on a schedule: the shop's
                    POS/ERP would push each day's transactions into BigQuery (incrementally, so
                    only new data is transferred), stock and supply records would sync from the
                    inventory system, and shift records would come from the rostering tool. Retail
                    Lens itself needs no changes — pages would simply show that day's real
                    numbers, and the AI agents would answer questions over live data.
                </p>
            </div>
        </div>
    );
}

export default Data;