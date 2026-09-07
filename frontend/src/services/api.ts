/**
 * Retail Lens frontend API service.
 *
 * The frontend must NOT connect directly to BigQuery, MCP Toolbox, or Gemini.
 * - Structured page data:  GET /api/...  → FastAPI → BigQuery (deterministic)
 * - AI chat:               POST /api/chat → FastAPI → ADK agents
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

// ---------------------------------------------------------------------------
// Shared types — mirror app/schemas/*.py
// ---------------------------------------------------------------------------

export interface DailySummaryData {
    sales_date: string;
    total_bills: number;
    transaction_lines: number;
    total_units_sold: number;
    total_revenue: number;
    average_bill_value: number;
}

export interface DailySummaryResponse {
    date_label: string;
    summary: DailySummaryData | null;
    message: string | null;
}

export interface TrendDay {
    sales_date: string;
    bills: number;
    units_sold: number;
    revenue: number;
}

export interface SalesTrendResponse {
    start_date: string;
    end_date: string;
    trend: TrendDay[];
}

export interface StockItem {
    product_id: string;
    product_name: string | null;
    category: string | null;
    stock_on_hand: number;
    reorder_level: number;
    last_updated: string | null;
}

export interface StockResponse {
    products: StockItem[];
    total_products: number;
    below_reorder_count: number;
}

export interface SupplyItem {
    product_id: string;
    product_name: string | null;
    category: string | null;
    supplier_id: string | null;
    supplier_lead_time_days: number | null;
    incoming_quantity: number | null;
    expected_delivery_date: string | null;
    last_updated: string | null;
}

export interface SupplyResponse {
    products: SupplyItem[];
}

export interface RiskItem {
    product_id: string;
    product_name: string | null;
    category: string | null;
    essentiality_tier: number | null;
    perishability_class: string | null;
    shelf_life_days: number | null;
    stock_on_hand: number | null;
    reorder_level: number | null;
    incoming_quantity: number | null;
    expected_delivery_date: string | null;
    supplier_id: string | null;
    supplier_lead_time_days: number | null;
    units_sold_in_period: number;
    average_daily_demand: number | null;
    stock_coverage_days: number | null;
    days_until_expected_delivery: number | null;
}

export interface ReplenishmentRiskResponse {
    start_date: string;
    end_date: string;
    products: RiskItem[];
    below_reorder_count: number;
}

export interface EmployeeRecord {
    employee_name: string;
    shifts_worked: number;
    scheduled_hours: number;
    actual_hours: number | null;
    total_wages_inr: number;
    average_hours_per_shift: number;
    check_in_count: number;
    late_check_in_count: number;
    early_departure_count: number;
    overtime_shift_count: number;
}

export interface WorkforceResponse {
    start_date: string;
    end_date: string;
    total_labour_cost: number;
    total_shifts: number;
    employees: EmployeeRecord[];
}

export interface CustomerRecord {
    customer_id: string;
    customer_name: string;
    bill_count: number;
    total_spend: number;
    average_bill_value: number;
    total_units: number;
    first_purchase_date: string | null;
    last_purchase_date: string | null;
    active_purchase_days: number;
    purchase_frequency_pct: number | null;
}

export interface CustomerBehaviorResponse {
    start_date: string;
    end_date: string;
    total_customers: number;
    repeat_customers: number;
    total_bills: number;
    average_bill_value: number;
    customers: CustomerRecord[];
}

export interface ProfitabilityItem {
    product_id: string;
    product_name: string | null;
    category: string | null;
    units_sold: number;
    revenue: number;
    cost_of_goods_sold: number;
    gross_profit: number;
    gross_margin_pct: number | null;
}

export interface ProfitabilityResponse {
    start_date: string;
    end_date: string;
    total_revenue: number;
    total_cogs: number;
    gross_profit: number;
    gross_margin_pct: number;
    products: ProfitabilityItem[];
}

// ---------------------------------------------------------------------------
// Request helper
// ---------------------------------------------------------------------------

async function request<T>(
    path: string,
    params?: Record<string, string | number | undefined>
): Promise<T> {
    const search = new URLSearchParams();
    if (params) {
        for (const [key, value] of Object.entries(params)) {
            if (value !== undefined && value !== null && value !== "") {
                search.set(key, String(value));
            }
        }
    }
    const qs = search.toString();
    let response: Response;
    try {
        response = await fetch(`${API_BASE_URL}${path}${qs ? `?${qs}` : ""}`);
    } catch {
        throw new Error("Cannot reach the Retail Lens backend. Is it running?");
    }
    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`;
        try {
            const body = await response.json();
            if (body?.detail) detail = String(body.detail);
        } catch {
            /* keep status-based detail */
        }
        throw new Error(detail);
    }
    return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Structured endpoints (Milestone 15)
// ---------------------------------------------------------------------------

export function fetchHomeSummary(date?: string): Promise<DailySummaryResponse> {
    return request<DailySummaryResponse>("/home/summary", { date });
}

export function fetchSalesTrend(days = 30): Promise<SalesTrendResponse> {
    return request<SalesTrendResponse>("/home/sales-trend", { days });
}

export function fetchReplenishmentRisk(days = 30): Promise<ReplenishmentRiskResponse> {
    return request<ReplenishmentRiskResponse>("/inventory/replenishment-risk", { days });
}

export function fetchStock(): Promise<StockResponse> {
    return request<StockResponse>("/inventory/stock");
}

export function fetchSupply(): Promise<SupplyResponse> {
    return request<SupplyResponse>("/inventory/supply");
}

export function fetchEmployeesSummary(days = 30): Promise<WorkforceResponse> {
    return request<WorkforceResponse>("/employees/summary", { days });
}

export function fetchCustomersBehavior(days = 30): Promise<CustomerBehaviorResponse> {
    return request<CustomerBehaviorResponse>("/customers/behavior", { days });
}

export function fetchProfitability(days = 30): Promise<ProfitabilityResponse> {
    return request<ProfitabilityResponse>("/profitability/products", { days });
}

// ---------------------------------------------------------------------------
// Daily advice (Milestone 24)
// ---------------------------------------------------------------------------

export interface AdviceData {
    headline: string;
    detail: string;
    category: string; // "sales" | "inventory" | "products"
    tone: string; // "positive" | "neutral" | "warning"
}

export interface DailyAdviceResponse {
    business_date: string | null; // latest business day with data
    block_index: number; // 0-3, which 6-hour block this advice belongs to
    next_update: string; // "HH:MM" local time of the next rotation
    advice: AdviceData | null;
    message: string | null;
}

export function fetchHomeAdvice(): Promise<DailyAdviceResponse> {
    return request<DailyAdviceResponse>("/home/advice");
}

// ---------------------------------------------------------------------------
// AI Chat
// ---------------------------------------------------------------------------

export type ChatMessage = {
    role: "user" | "ai";
    content: string;
};

export async function sendChatMessage(message: string): Promise<string> {
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message }),
        });

        if (!response.ok) {
            if (response.status === 503) {
                throw new Error(
                    "The AI service is busy right now. Please try again in a moment."
                );
            }
            if (response.status === 504) {
                throw new Error(
                    "The AI agent took too long to respond. Please try rephrasing your question."
                );
            }
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data.response;
    } catch (err: any) {
        // Fallback for disconnected backend state
        throw new Error(err.message || "Backend not connected yet.");
    }
}