import { useEffect, useState } from "react";
import { EmployeeRecord, fetchEmployeesSummary, WorkforceResponse } from "./services/api";
import { formatCurrency, formatDate, formatNumber } from "./utils/format";

const RANGE_OPTIONS = [
    { days: 7, label: "Last 7 Days" },
    { days: 30, label: "Last 30 Days" },
    { days: 90, label: "Last 90 Days" },
];

function Employees() {
    const [days, setDays] = useState(30);
    const [data, setData] = useState<WorkforceResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetchEmployeesSummary(days)
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

    const totalScheduled = data
        ? data.employees.reduce((sum, e) => sum + (e.scheduled_hours ?? 0), 0)
        : 0;
    const totalActual = data
        ? data.employees.reduce((sum, e) => sum + (e.actual_hours ?? 0), 0)
        : 0;

    return (
        <div className="page">
            <div className="page-header">
                <h1>Employees</h1>
                <p>Attendance and payroll summary for your team.</p>
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
                    <div className="state-desc">Loading workforce data...</div>
                </div>
            ) : error ? (
                <div className="state-box error-box">
                    <div className="state-icon">⚠️</div>
                    <div className="state-title">Could not load workforce data</div>
                    <div className="state-desc">{error}</div>
                </div>
            ) : !data || data.employees.length === 0 ? (
                <div className="state-box">
                    <div className="state-icon">👥</div>
                    <div className="state-title">No shifts recorded</div>
                    <div className="state-desc">
                        No employee shifts were found for this period.
                    </div>
                </div>
            ) : (
                <>
                    <p className="subtle" style={{ marginBottom: "0.75rem" }}>
                        Period: <strong>{formatDate(data.start_date)} – {formatDate(data.end_date)}</strong>
                    </p>
                    <div className="metric-grid" style={{ marginBottom: "1.5rem" }}>
                        <div className="metric">
                            <div className="metric-label">Total Labour Cost</div>
                            <div className="metric-value">{formatCurrency(data.total_labour_cost, { decimals: 0 })}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Total Shifts</div>
                            <div className="metric-value">{formatNumber(data.total_shifts)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Scheduled Hours</div>
                            <div className="metric-value">{formatNumber(totalScheduled)}</div>
                        </div>
                        <div className="metric">
                            <div className="metric-label">Actual Hours</div>
                            <div className="metric-value">{formatNumber(totalActual)}</div>
                        </div>
                    </div>

                    <div className="card" style={{ marginBottom: "1.5rem" }}>
                        <h3 className="section-title" style={{ marginBottom: "1rem" }}>Employee Summary</h3>
                        <div style={{ overflowX: "auto" }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Employee</th>
                                        <th>Shifts</th>
                                        <th>Scheduled</th>
                                        <th>Actual</th>
                                        <th>Wages</th>
                                        <th>Avg / Shift</th>
                                        <th>Late In</th>
                                        <th>Early Out</th>
                                        <th>Overtime</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.employees.map((e: EmployeeRecord) => (
                                        <tr key={e.employee_name}>
                                            <td>{e.employee_name}</td>
                                            <td>{formatNumber(e.shifts_worked)}</td>
                                            <td>{e.scheduled_hours !== null ? `${formatNumber(e.scheduled_hours)} h` : "—"}</td>
                                            <td>{e.actual_hours !== null ? `${formatNumber(e.actual_hours)} h` : "—"}</td>
                                            <td>{formatCurrency(e.total_wages_inr, { decimals: 0 })}</td>
                                            <td>{e.average_hours_per_shift !== null ? `${e.average_hours_per_shift} h` : "—"}</td>
                                            <td>{e.late_check_in_count > 0 ? <span className="badge badge-warning">{e.late_check_in_count}</span> : "0"}</td>
                                            <td>{e.early_departure_count > 0 ? <span className="badge badge-warning">{e.early_departure_count}</span> : "0"}</td>
                                            <td>{e.overtime_shift_count > 0 ? <span className="badge badge-success">{e.overtime_shift_count}</span> : "0"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="card">
                        <h3 className="section-title" style={{ marginBottom: "0.5rem" }}>About this data</h3>
                        <ul className="note-list">
                            <li>Scheduled hours are the rostered hours recorded for each shift; wages = rostered hours × hourly wage.</li>
                            <li>Actual hours come from check-in/check-out timestamps; shifts without them show "—".</li>
                            <li>Late = checking in more than 5 minutes after the scheduled start (Morning 9 AM, Evening 5 PM).</li>
                            <li>Early out = leaving more than 5 minutes before the scheduled end (Morning 5 PM, Evening 10 PM).</li>
                            <li>Overtime = working more than 15 minutes beyond the scheduled shift length.</li>
                        </ul>
                    </div>
                </>
            )}
        </div>
    );
}

export default Employees;