import { useState } from "react";
import Home from "./Home";
import Chat from "./Chat";
import Inventory from "./Inventory";
import Employees from "./Employees";
import Customers from "./Customers";
import Profitability from "./Profitability";
import Analytics from "./Analytics";
import Data from "./Data";

const NAV_ITEMS = [
    { id: "home", label: "Home", icon: "🏠" },
    { id: "chat", label: "AI Chat", icon: "💬" },
    { id: "analytics", label: "Analytics", icon: "📈" },
    { id: "inventory", label: "Inventory", icon: "📦" },
    { id: "employees", label: "Employees", icon: "👥" },
    { id: "customers", label: "Customers", icon: "🛍️" },
    { id: "profitability", label: "Profitability", icon: "💰" },
    { id: "data", label: "Data", icon: "📊" },
];

function ComingSoon({ title }: { title: string }) {
    return (
        <div className="page" style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
            <div className="state-box" style={{ width: "100%", maxWidth: "400px" }}>
                <div className="state-icon">🚧</div>
                <h2 className="state-title">{title}</h2>
                <div className="state-desc" style={{ marginTop: "0.5rem" }}>
                    This module is coming soon in a future milestone.
                </div>
            </div>
        </div>
    );
}

function App() {
    const [currentView, setCurrentView] = useState("home");
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [pendingChatMessage, setPendingChatMessage] = useState<string | null>(null);

    const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

    // Jump to AI Chat with a pre-filled question (e.g. Home → "1 Month Summary").
    const askChat = (message: string) => {
        setPendingChatMessage(message);
        setCurrentView("chat");
    };

    const activeItem = NAV_ITEMS.find((item) => item.id === currentView);

    return (
        <div className="app-layout">
            <div className="mobile-topbar">
                <div className="mobile-topbar-brand">
                    Retail<span>Lens</span>
                </div>
                <button className="hamburger" onClick={toggleSidebar}>
                    ☰
                </button>
            </div>

            <div
                className={`sidebar-overlay ${isSidebarOpen ? "open" : ""}`}
                onClick={() => setIsSidebarOpen(false)}
            ></div>

            <aside className={`sidebar ${isSidebarOpen ? "open" : ""}`}>
                <div className="sidebar-brand">
                    Retail<span>Lens</span>
                </div>
                <nav className="sidebar-nav">
                    {NAV_ITEMS.map((item) => (
                        <a
                            key={item.id}
                            href={`#${item.id}`}
                            className={`nav-item ${currentView === item.id ? "active" : ""}`}
                            onClick={(e) => {
                                e.preventDefault();
                                setCurrentView(item.id);
                                setIsSidebarOpen(false);
                            }}
                        >
                            <span className="nav-icon">{item.icon}</span>
                            {item.label}
                        </a>
                    ))}
                </nav>
                <div className="sidebar-footer">
                    <div>© 2026 Retail Lens</div>
                    <div style={{ marginTop: "4px" }}>Version 0.1.0 (Alpha)</div>
                </div>
            </aside>

            <main className="main-content">
                {currentView === "home" ? (
                    <Home onAskChat={askChat} />
                ) : currentView === "chat" ? (
                    <Chat
                        pendingMessage={pendingChatMessage}
                        onPendingConsumed={() => setPendingChatMessage(null)}
                    />
                ) : currentView === "inventory" ? (
                    <Inventory />
                ) : currentView === "employees" ? (
                    <Employees />
                ) : currentView === "customers" ? (
                    <Customers />
                ) : currentView === "profitability" ? (
                    <Profitability />
                ) : currentView === "analytics" ? (
                    <Analytics />
                ) : currentView === "data" ? (
                    <Data />
                ) : (
                    <ComingSoon title={activeItem?.label || "Unknown"} />
                )}
            </main>
        </div>
    );
}

export default App;
