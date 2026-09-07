import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage, sendChatMessage } from "./services/api";

const EXAMPLE_QUESTIONS = [
    "Which product sold the most yesterday?",
    "Which products should I restock first?",
    "How much did I pay my employees last month?",
    "Who were my highest-spending customers?",
];

export default function Chat({
    pendingMessage,
    onPendingConsumed,
}: {
    pendingMessage?: string | null;
    onPendingConsumed?: () => void;
}) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputValue, setInputValue] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading]);

    // Auto-send a question handed over from another page (e.g. Home summaries).
    const consumedRef = useRef<string | null>(null);
    useEffect(() => {
        if (pendingMessage && pendingMessage !== consumedRef.current) {
            consumedRef.current = pendingMessage;
            onPendingConsumed?.();
            handleSend(pendingMessage);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pendingMessage]);

    const handleSend = async (text: string) => {
        const trimmed = text.trim();
        if (!trimmed || isLoading) return;

        // Add user message immediately
        const userMsg: ChatMessage = { role: "user", content: trimmed };
        setMessages((prev) => [...prev, userMsg]);
        setInputValue("");
        setIsLoading(true);

        try {
            // Attempt to send to our API boundary
            const aiResponseText = await sendChatMessage(trimmed);
            const aiMsg: ChatMessage = { role: "ai", content: aiResponseText };
            setMessages((prev) => [...prev, aiMsg]);
        } catch (error: any) {
            // Handle disconnected backend state gracefully
            const errorMsg: ChatMessage = {
                role: "ai",
                content: error.message || "An unexpected error occurred communicating with the backend."
            };
            setMessages((prev) => [...prev, errorMsg]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend(inputValue);
        }
    };

    return (
        <div className="page" style={{ height: "100%", display: "flex", flexDirection: "column", paddingBottom: "1.5rem" }}>
            <div className="page-header" style={{ marginBottom: "1rem" }}>
                <h1>AI Chat</h1>
                <p>Ask anything about your business.</p>
            </div>

            {messages.length === 0 && (
                <div className="chip-row">
                    {EXAMPLE_QUESTIONS.map((q, idx) => (
                        <div key={idx} className="chip" onClick={() => handleSend(q)}>
                            {q}
                        </div>
                    ))}
                </div>
            )}

            <div className="card chat-container" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "0" }}>
                <div className="chat-messages" style={{ flex: 1, padding: "1.25rem", overflowY: "auto" }}>
                    {messages.length === 0 ? (
                        <div className="state-box" style={{ height: "100%", border: "none" }}>
                            <div className="state-icon">💬</div>
                            <h3 className="state-title">No messages yet</h3>
                            <div className="state-desc">Select an example above or type a question to begin analyzing your data.</div>
                        </div>
                    ) : (
                        messages.map((msg, idx) => (
                            <div key={idx} className={`chat-msg ${msg.role === "user" ? "user" : msg.role === "ai" && msg.content.includes("not connected") ? "error" : "ai"}`}>
                                {msg.role === "user" ? (
                                    msg.content
                                ) : (
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {msg.content}
                                    </ReactMarkdown>
                                )}
                            </div>
                        ))
                    )}

                    {isLoading && (
                        <div className="chat-msg ai" style={{ opacity: 0.7 }}>
                            <div className="loading-spinner" style={{ width: "16px", height: "16px", borderWidth: "2px", margin: 0, display: "inline-block", verticalAlign: "middle", marginRight: "8px" }}></div>
                            Analyzing data...
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                <div className="chat-input-row" style={{ padding: "1.25rem", borderTop: "1px solid var(--border)", background: "var(--surface)", margin: 0 }}>
                    <textarea
                        className="chat-input"
                        placeholder="Type your question..."
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isLoading}
                        style={{ height: "44px", minHeight: "44px", maxHeight: "120px" }}
                    />
                    <button
                        className="btn btn-primary"
                        onClick={() => handleSend(inputValue)}
                        disabled={!inputValue.trim() || isLoading}
                        style={{ alignSelf: "flex-end" }}
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}
