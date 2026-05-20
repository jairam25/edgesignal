import { useState, useEffect, useCallback } from "react";

const API = "http://localhost:8000/api";

// ─── Animated Number ──────────────────────────────────
function AnimNum({ value, prefix = "", suffix = "", decimals = 2, colorize = false }) {
    const [display, setDisplay] = useState(value);
    const [flash, setFlash] = useState("");

    useEffect(() => {
        if (value !== display) {
            setFlash(value > display ? "flash-green" : "flash-red");
            const steps = 12;
            const diff = (value - display) / steps;
            let step = 0;
            const iv = setInterval(() => {
                step++;
                setDisplay((d) => d + diff);
                if (step >= steps) {
                    clearInterval(iv);
                    setDisplay(value);
                    setTimeout(() => setFlash(""), 600);
                }
            }, 30);
            return () => clearInterval(iv);
        }
    }, [value]);

    const color = colorize
        ? display >= 0 ? "#00ffa3" : "#ff4466"
        : "inherit";

    return (
        <span className={flash} style={{ color, transition: "color 0.3s" }}>
            {prefix}
            {typeof display === "number" ? display.toLocaleString(undefined, {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals,
            }) : display}
            {suffix}
        </span>
    );
}

// ─── Sparkline ────────────────────────────────────────
function Spark({ value, max = 100 }) {
    const pct = Math.min(Math.abs(value) / max * 100, 100);
    const color = value >= 0 ? "#00ffa3" : "#ff4466";
    return (
        <div style={{ width: 60, height: 6, background: "#1a1f2e", borderRadius: 3, overflow: "hidden" }}>
            <div style={{
                width: `${pct}%`, height: "100%", background: color,
                borderRadius: 3, transition: "width 0.8s ease"
            }} />
        </div>
    );
}

// ─── Badge ────────────────────────────────────────────
function Badge({ type }) {
    const styles = {
        BUY: { bg: "#00ffa322", color: "#00ffa3", border: "#00ffa355" },
        SELL: { bg: "#ff446622", color: "#ff4466", border: "#ff446655" },
        ALERT: { bg: "#ffaa0022", color: "#ffaa00", border: "#ffaa0055" },
        EDGE: { bg: "#aa66ff22", color: "#aa66ff", border: "#aa66ff55" },
    };
    const s = styles[type] || styles.ALERT;
    return (
        <span style={{
            background: s.bg, color: s.color, border: `1px solid ${s.border}`,
            padding: "2px 10px", borderRadius: 4, fontSize: 11, fontWeight: 700,
            letterSpacing: 1, textTransform: "uppercase"
        }}>{type}</span>
    );
}

// ─── Mini Card ────────────────────────────────────────
function MiniCard({ label, value, sub, icon }) {
    return (
        <div style={{
            background: "linear-gradient(135deg, #12162200, #1a1f2e88)",
            border: "1px solid #ffffff0d", borderRadius: 12, padding: "16px 20px",
            flex: "1 1 200px", minWidth: 180, animation: "fadeSlideUp 0.6s ease both",
        }}>
            <div style={{ fontSize: 12, color: "#8892a4", marginBottom: 6, letterSpacing: 1.2, textTransform: "uppercase" }}>
                <span style={{ marginRight: 6 }}>{icon}</span>{label}
            </div>
            <div style={{ fontSize: 26, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
            {sub && <div style={{ fontSize: 12, color: "#8892a4", marginTop: 4 }}>{sub}</div>}
        </div>
    );
}

// ─── Asset Row ────────────────────────────────────────
function AssetRow({ ticker, price, change, volume, delay = 0 }) {
    const isUp = change >= 0;
    return (
        <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 16px", borderBottom: "1px solid #ffffff08",
            animation: `fadeSlideUp 0.5s ease ${delay}ms both`,
            transition: "background 0.2s",
            cursor: "pointer",
        }}
            onMouseEnter={(e) => e.currentTarget.style.background = "#ffffff06"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
        >
            <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                <div style={{
                    width: 36, height: 36, borderRadius: 8,
                    background: isUp ? "#00ffa315" : "#ff446615",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 13, fontWeight: 700, color: isUp ? "#00ffa3" : "#ff4466",
                    fontFamily: "'JetBrains Mono', monospace",
                    border: `1px solid ${isUp ? "#00ffa322" : "#ff446622"}`
                }}>
                    {ticker?.substring(0, 2)}
                </div>
                <div>
                    <div style={{ fontWeight: 600, fontSize: 14, letterSpacing: 0.5 }}>{ticker}</div>
                    <div style={{ fontSize: 11, color: "#8892a4" }}>
                        Vol: {volume ? (volume > 1e6 ? (volume / 1e6).toFixed(1) + "M" : (volume / 1e3).toFixed(0) + "K") : "—"}
                    </div>
                </div>
            </div>
            <div style={{ textAlign: "right", display: "flex", alignItems: "center", gap: 16 }}>
                <Spark value={change} max={5} />
                <div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 600 }}>
                        ${typeof price === "number" ? price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : price}
                    </div>
                    <div style={{
                        fontSize: 12, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace",
                        color: isUp ? "#00ffa3" : "#ff4466",
                    }}>
                        {isUp ? "▲" : "▼"} {Math.abs(change || 0).toFixed(2)}%
                    </div>
                </div>
            </div>
        </div>
    );
}

// ─── Signal Card ──────────────────────────────────────
function SignalCard({ signal, delay = 0 }) {
    return (
        <div style={{
            background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 12,
            padding: 16, animation: `fadeSlideUp 0.5s ease ${delay}ms both`,
            borderLeft: `3px solid ${signal.signal_type === "BUY" ? "#00ffa3" : signal.signal_type === "SELL" ? "#ff4466" : "#ffaa00"}`,
        }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Badge type={signal.signal_type} />
                    <span style={{ fontWeight: 700, fontSize: 15, fontFamily: "'JetBrains Mono', monospace" }}>
                        {signal.ticker}
                    </span>
                </div>
                <div style={{ fontSize: 12, color: "#8892a4" }}>{signal.asset_type}</div>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{signal.headline}</div>
            {/* Confidence bar */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10 }}>
                <div style={{ fontSize: 11, color: "#8892a4", minWidth: 32 }}>{signal.confidence}%</div>
                <div style={{ flex: 1, height: 4, background: "#1a1f2e", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                        width: `${signal.confidence}%`, height: "100%", borderRadius: 2,
                        background: signal.confidence >= 80 ? "#00ffa3" : signal.confidence >= 60 ? "#ffaa00" : "#ff4466",
                        transition: "width 1s ease",
                    }} />
                </div>
            </div>
        </div>
    );
}

// ─── Polymarket Card ──────────────────────────────────
function PolyCard({ contract, delay = 0 }) {
    const prob = contract.market_price ? (contract.market_price * 100) : null;
    return (
        <div style={{
            background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 12,
            padding: 14, animation: `fadeSlideUp 0.5s ease ${delay}ms both`,
        }}>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 10, lineHeight: 1.4 }}>
                {contract.question?.substring(0, 100)}{contract.question?.length > 100 ? "…" : ""}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {prob !== null && (
                        <>
                            <div style={{
                                width: 44, height: 44, borderRadius: "50%", position: "relative",
                                background: `conic-gradient(#aa66ff ${prob * 3.6}deg, #1a1f2e 0deg)`,
                                display: "flex", alignItems: "center", justifyContent: "center",
                            }}>
                                <div style={{
                                    width: 34, height: 34, borderRadius: "50%", background: "#0d111b",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    fontSize: 11, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: "#aa66ff"
                                }}>
                                    {prob.toFixed(0)}%
                                </div>
                            </div>
                        </>
                    )}
                </div>
                <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 12, color: "#8892a4" }}>Volume</div>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                        ${contract.volume ? (contract.volume > 1e6 ? (contract.volume / 1e6).toFixed(1) + "M" : (contract.volume / 1e3).toFixed(0) + "K") : "0"}
                    </div>
                </div>
            </div>
        </div>
    );
}

// ─── Tabs ─────────────────────────────────────────────
function Tabs({ tabs, active, onChange }) {
    return (
        <div style={{ display: "flex", gap: 2, background: "#0d111b", borderRadius: 10, padding: 3, marginBottom: 20 }}>
            {tabs.map((t) => (
                <button
                    key={t.id}
                    onClick={() => onChange(t.id)}
                    style={{
                        flex: 1, padding: "10px 16px", borderRadius: 8, border: "none",
                        background: active === t.id ? "#1a1f2e" : "transparent",
                        color: active === t.id ? "#fff" : "#8892a4",
                        fontSize: 13, fontWeight: 600, cursor: "pointer",
                        transition: "all 0.3s ease", letterSpacing: 0.5,
                    }}
                >
                    <span style={{ marginRight: 6 }}>{t.icon}</span>{t.label}
                </button>
            ))}
        </div>
    );
}

// ─── MAIN DASHBOARD ───────────────────────────────────
export default function EdgeSignalDashboard() {
    const [tab, setTab] = useState("overview");
    const [stocks, setStocks] = useState([]);
    const [crypto, setCrypto] = useState([]);
    const [commodities, setCommodities] = useState([]);
    const [macro, setMacro] = useState([]);
    const [signals, setSignals] = useState([]);
    const [polymarket, setPolymarket] = useState([]);
    const [sentiment, setSentiment] = useState([]);
    const [overview, setOverview] = useState(null);
    const [portfolio, setPortfolio] = useState([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [pulse, setPulse] = useState(false);

    const fetchData = useCallback(async () => {
        setPulse(true);
        try {
            const endpoints = ["stocks", "crypto", "commodities", "macro", "signals", "polymarket", "sentiment", "overview", "portfolio"];
            const results = await Promise.allSettled(
                endpoints.map((e) => fetch(`${API}/${e}`).then((r) => r.json()))
            );
            const get = (i) => results[i].status === "fulfilled" ? results[i].value : [];

            setStocks(get(0));
            setCrypto(get(1));
            setCommodities(get(2));
            setMacro(get(3));
            setSignals(get(4));
            setPolymarket(get(5));
            setSentiment(get(6));
            setOverview(results[7].status === "fulfilled" ? results[7].value : null);
            setPortfolio(get(8));
            setLastUpdate(new Date());
        } catch (e) {
            console.error("Fetch error:", e);
        }
        setLoading(false);
        setTimeout(() => setPulse(false), 1000);
    }, []);

    useEffect(() => {
        fetchData();
        const iv = setInterval(fetchData, 60000);
        return () => clearInterval(iv);
    }, [fetchData]);

    const totalPnl = portfolio.filter(p => p.status === "OPEN").reduce((s, p) => s + (p.pnl || 0), 0);
    const openPositions = portfolio.filter(p => p.status === "OPEN");

    const tabs = [
        { id: "overview", label: "Overview", icon: "📊" },
        { id: "stocks", label: "Stocks", icon: "📈" },
        { id: "crypto", label: "Crypto", icon: "🪙" },
        { id: "commodities", label: "Commodities", icon: "🛢" },
        { id: "signals", label: "Signals", icon: "🚨" },
        { id: "portfolio", label: "Portfolio", icon: "💼" },
        { id: "polymarket", label: "Polymarket", icon: "🎯" },
    ];

    return (
        <div style={{
            minHeight: "100vh", background: "#080b14", color: "#e8ecf4",
            fontFamily: "'Satoshi', 'Inter', -apple-system, sans-serif",
        }}>
            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');

        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes gradientMove {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        @keyframes glowPulse {
          0%, 100% { box-shadow: 0 0 20px #00ffa322; }
          50% { box-shadow: 0 0 40px #00ffa344; }
        }
        .flash-green { animation: flashG 0.6s ease; }
        .flash-red { animation: flashR 0.6s ease; }
        @keyframes flashG { 0% { background: #00ffa322; } 100% { background: transparent; } }
        @keyframes flashR { 0% { background: #ff446622; } 100% { background: transparent; } }

        .glow-border {
          position: relative;
        }
        .glow-border::before {
          content: '';
          position: absolute;
          top: -1px; left: -1px; right: -1px; bottom: -1px;
          background: linear-gradient(135deg, #00ffa344, #aa66ff44, #00ffa344);
          background-size: 200% 200%;
          animation: gradientMove 4s ease infinite;
          border-radius: 16px;
          z-index: -1;
        }

        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #080b14; }
        ::-webkit-scrollbar-thumb { background: #1a1f2e; border-radius: 3px; }
      `}</style>

            {/* ─── Header ───────────────────────────── */}
            <div style={{
                padding: "20px 28px", borderBottom: "1px solid #ffffff0a",
                display: "flex", justifyContent: "space-between", alignItems: "center",
                background: "linear-gradient(180deg, #0d111b 0%, #080b1400 100%)",
                animation: "fadeSlideUp 0.4s ease both",
            }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div style={{
                        width: 40, height: 40, borderRadius: 12,
                        background: "linear-gradient(135deg, #00ffa3, #00cc82)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 20, fontWeight: 800, color: "#080b14",
                        animation: pulse ? "glowPulse 1s ease" : "none",
                    }}>E</div>
                    <div>
                        <div style={{
                            fontSize: 20, fontWeight: 800, letterSpacing: -0.5,
                            fontFamily: "'Outfit', sans-serif",
                            background: "linear-gradient(135deg, #e8ecf4, #8892a4)",
                            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
                        }}>
                            EdgeSignal
                        </div>
                        <div style={{ fontSize: 11, color: "#8892a455", letterSpacing: 2, textTransform: "uppercase" }}>
                            AI Trading Intelligence
                        </div>
                    </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <div style={{
                        width: 8, height: 8, borderRadius: "50%",
                        background: pulse ? "#ffaa00" : "#00ffa3",
                        boxShadow: `0 0 12px ${pulse ? "#ffaa00" : "#00ffa3"}88`,
                        transition: "all 0.3s",
                    }} />
                    <div style={{ fontSize: 12, color: "#8892a4", fontFamily: "'JetBrains Mono', monospace" }}>
                        {lastUpdate ? lastUpdate.toLocaleTimeString() : "..."}
                    </div>
                    <button
                        onClick={fetchData}
                        style={{
                            background: "#1a1f2e", border: "1px solid #ffffff11", borderRadius: 8,
                            color: "#8892a4", padding: "6px 14px", fontSize: 12, cursor: "pointer",
                            transition: "all 0.2s",
                        }}
                        onMouseEnter={(e) => { e.target.style.background = "#252b3d"; e.target.style.color = "#fff"; }}
                        onMouseLeave={(e) => { e.target.style.background = "#1a1f2e"; e.target.style.color = "#8892a4"; }}
                    >
                        ↻ Refresh
                    </button>
                </div>
            </div>

            {/* ─── Content ──────────────────────────── */}
            <div style={{ padding: "20px 28px", maxWidth: 1400, margin: "0 auto" }}>
                <Tabs tabs={tabs} active={tab} onChange={setTab} />

                {loading ? (
                    <div style={{ textAlign: "center", padding: 60, animation: "pulse 1.5s infinite" }}>
                        <div style={{ fontSize: 40, marginBottom: 12 }}>⚡</div>
                        <div style={{ color: "#8892a4" }}>Loading EdgeSignal data...</div>
                    </div>
                ) : (
                    <>
                        {/* ════ OVERVIEW ════ */}
                        {tab === "overview" && (
                            <div style={{ animation: "fadeSlideUp 0.5s ease both" }}>
                                {/* Stat cards */}
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginBottom: 24 }}>
                                    <MiniCard icon="📈" label="Stocks Tracked" value={stocks.length} sub="Live prices" />
                                    <MiniCard icon="🪙" label="Crypto Pairs" value={crypto.length} sub="24h data" />
                                    <MiniCard icon="🚨" label="Signals Today" value={overview?.signals_today || 0} sub="AI generated" />
                                    <MiniCard icon="💼" label="Portfolio P&L"
                                        value={<AnimNum value={totalPnl} prefix="$" colorize decimals={2} />}
                                        sub={`${openPositions.length} open positions`}
                                    />
                                </div>

                                {/* Two columns */}
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                                    {/* Top Gainers */}
                                    <div style={{
                                        background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14, overflow: "hidden",
                                    }}>
                                        <div style={{ padding: "14px 16px", borderBottom: "1px solid #ffffff08", fontSize: 13, fontWeight: 700, letterSpacing: 0.5 }}>
                                            🟢 Top Gainers
                                        </div>
                                        {overview?.top_gainers?.map((s, i) => (
                                            <AssetRow key={s.ticker} ticker={s.ticker} price={s.price} change={s.change_pct} delay={i * 80} />
                                        ))}
                                        {(!overview?.top_gainers || overview.top_gainers.length === 0) && (
                                            <div style={{ padding: 20, color: "#8892a4", textAlign: "center", fontSize: 13 }}>No data yet — run the data fetchers</div>
                                        )}
                                    </div>

                                    {/* Top Losers */}
                                    <div style={{
                                        background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14, overflow: "hidden",
                                    }}>
                                        <div style={{ padding: "14px 16px", borderBottom: "1px solid #ffffff08", fontSize: 13, fontWeight: 700, letterSpacing: 0.5 }}>
                                            🔴 Top Losers
                                        </div>
                                        {overview?.top_losers?.map((s, i) => (
                                            <AssetRow key={s.ticker} ticker={s.ticker} price={s.price} change={s.change_pct} delay={i * 80} />
                                        ))}
                                        {(!overview?.top_losers || overview.top_losers.length === 0) && (
                                            <div style={{ padding: 20, color: "#8892a4", textAlign: "center", fontSize: 13 }}>No data yet</div>
                                        )}
                                    </div>
                                </div>

                                {/* Latest Signals */}
                                {signals.length > 0 && (
                                    <div style={{ marginTop: 24 }}>
                                        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, letterSpacing: 0.5 }}>🚨 Latest Signals</div>
                                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                                            {signals.slice(0, 4).map((s, i) => (
                                                <SignalCard key={s.id || i} signal={s} delay={i * 100} />
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Macro Strip */}
                                {macro.length > 0 && (
                                    <div style={{ marginTop: 24 }}>
                                        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, letterSpacing: 0.5 }}>🏛 Macro Indicators</div>
                                        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                                            {macro.map((m, i) => (
                                                <div key={m.series_name} style={{
                                                    background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 10,
                                                    padding: "12px 16px", animation: `fadeSlideUp 0.5s ease ${i * 60}ms both`,
                                                    flex: "1 1 160px", minWidth: 140,
                                                }}>
                                                    <div style={{ fontSize: 11, color: "#8892a4", marginBottom: 4 }}>{m.series_name}</div>
                                                    <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
                                                        {typeof m.value === "number" ? m.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : m.value}
                                                    </div>
                                                    <div style={{ fontSize: 10, color: "#8892a455" }}>{m.date}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ════ STOCKS ════ */}
                        {tab === "stocks" && (
                            <div style={{
                                background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                overflow: "hidden", animation: "fadeSlideUp 0.5s ease both",
                            }}>
                                <div style={{ padding: "14px 16px", borderBottom: "1px solid #ffffff08", display: "flex", justifyContent: "space-between" }}>
                                    <span style={{ fontWeight: 700, letterSpacing: 0.5 }}>📈 Stocks & ETFs</span>
                                    <span style={{ fontSize: 12, color: "#8892a4" }}>{stocks.length} assets</span>
                                </div>
                                <div style={{ maxHeight: 600, overflowY: "auto" }}>
                                    {stocks.map((s, i) => (
                                        <AssetRow key={s.ticker} ticker={s.ticker} price={s.price} change={s.change_pct} volume={s.volume} delay={i * 40} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* ════ CRYPTO ════ */}
                        {tab === "crypto" && (
                            <div style={{
                                background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                overflow: "hidden", animation: "fadeSlideUp 0.5s ease both",
                            }}>
                                <div style={{ padding: "14px 16px", borderBottom: "1px solid #ffffff08", display: "flex", justifyContent: "space-between" }}>
                                    <span style={{ fontWeight: 700, letterSpacing: 0.5 }}>🪙 Crypto</span>
                                    <span style={{ fontSize: 12, color: "#8892a4" }}>{crypto.length} pairs</span>
                                </div>
                                {crypto.map((c, i) => (
                                    <AssetRow key={c.pair} ticker={c.pair} price={c.price} change={c.change_pct_24h} volume={c.volume_24h} delay={i * 60} />
                                ))}
                            </div>
                        )}

                        {/* ════ COMMODITIES ════ */}
                        {tab === "commodities" && (
                            <div style={{
                                background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                overflow: "hidden", animation: "fadeSlideUp 0.5s ease both",
                            }}>
                                <div style={{ padding: "14px 16px", borderBottom: "1px solid #ffffff08", fontWeight: 700, letterSpacing: 0.5 }}>
                                    🛢 Commodities
                                </div>
                                {commodities.map((c, i) => (
                                    <AssetRow key={c.ticker} ticker={c.name} price={c.price} change={c.change_pct} volume={c.volume} delay={i * 60} />
                                ))}
                            </div>
                        )}

                        {/* ════ SIGNALS ════ */}
                        {tab === "signals" && (
                            <div style={{ animation: "fadeSlideUp 0.5s ease both" }}>
                                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, letterSpacing: 0.5 }}>
                                    🚨 AI Trading Signals
                                </div>
                                {signals.length === 0 ? (
                                    <div style={{
                                        background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                        padding: 40, textAlign: "center", color: "#8892a4"
                                    }}>
                                        No signals yet — run the AI analyst first
                                    </div>
                                ) : (
                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                                        {signals.map((s, i) => (
                                            <SignalCard key={s.id || i} signal={s} delay={i * 80} />
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ════ PORTFOLIO ════ */}
                        {tab === "portfolio" && (
                            <div style={{ animation: "fadeSlideUp 0.5s ease both" }}>
                                {/* Portfolio Summary */}
                                <div className="glow-border" style={{
                                    background: "#0d111b", borderRadius: 14, padding: 24, marginBottom: 20,
                                    position: "relative", zIndex: 1,
                                }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                        <div>
                                            <div style={{ fontSize: 12, color: "#8892a4", letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 }}>
                                                Total P&L
                                            </div>
                                            <div style={{
                                                fontSize: 42, fontWeight: 800, fontFamily: "'JetBrains Mono', monospace",
                                                color: totalPnl >= 0 ? "#00ffa3" : "#ff4466",
                                                textShadow: `0 0 30px ${totalPnl >= 0 ? "#00ffa333" : "#ff446633"}`,
                                            }}>
                                                <AnimNum value={totalPnl} prefix={totalPnl >= 0 ? "+$" : "-$"} decimals={2} />
                                            </div>
                                        </div>
                                        <div style={{ textAlign: "right" }}>
                                            <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
                                                {openPositions.length}
                                            </div>
                                            <div style={{ fontSize: 12, color: "#8892a4" }}>Open Positions</div>
                                        </div>
                                    </div>
                                </div>

                                {/* Position List */}
                                {openPositions.length === 0 ? (
                                    <div style={{
                                        background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                        padding: 40, textAlign: "center", color: "#8892a4"
                                    }}>
                                        No open positions — signals will populate here when you start tracking trades
                                    </div>
                                ) : (
                                    <div style={{
                                        background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                        overflow: "hidden",
                                    }}>
                                        {/* Header */}
                                        <div style={{
                                            display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr 1fr",
                                            padding: "12px 16px", borderBottom: "1px solid #ffffff08",
                                            fontSize: 11, color: "#8892a4", textTransform: "uppercase", letterSpacing: 1,
                                        }}>
                                            <div>Asset</div><div>Side</div><div>Entry</div><div>Current</div><div>Qty</div><div style={{ textAlign: "right" }}>P&L</div>
                                        </div>
                                        {openPositions.map((p, i) => {
                                            const isUp = (p.pnl || 0) >= 0;
                                            return (
                                                <div key={p.id} style={{
                                                    display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr 1fr",
                                                    padding: "12px 16px", borderBottom: "1px solid #ffffff06",
                                                    animation: `fadeSlideUp 0.5s ease ${i * 60}ms both`,
                                                    alignItems: "center",
                                                }}>
                                                    <div style={{ fontWeight: 600, fontSize: 14 }}>{p.ticker}</div>
                                                    <div>
                                                        <span style={{
                                                            background: p.side === "LONG" ? "#00ffa322" : "#ff446622",
                                                            color: p.side === "LONG" ? "#00ffa3" : "#ff4466",
                                                            padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                                                        }}>{p.side}</span>
                                                    </div>
                                                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>
                                                        ${p.entry_price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                                    </div>
                                                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>
                                                        ${p.current_price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                                    </div>
                                                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>{p.quantity}</div>
                                                    <div style={{
                                                        textAlign: "right", fontFamily: "'JetBrains Mono', monospace",
                                                        fontSize: 14, fontWeight: 700,
                                                        color: isUp ? "#00ffa3" : "#ff4466",
                                                    }}>
                                                        {isUp ? "+" : ""}{(p.pnl || 0).toFixed(2)}
                                                        <div style={{ fontSize: 11, fontWeight: 400 }}>
                                                            {isUp ? "▲" : "▼"} {Math.abs(p.pnl_pct || 0).toFixed(2)}%
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* ════ POLYMARKET ════ */}
                        {tab === "polymarket" && (
                            <div style={{ animation: "fadeSlideUp 0.5s ease both" }}>
                                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, letterSpacing: 0.5 }}>
                                    🎯 Polymarket Prediction Markets
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                                    {polymarket.map((c, i) => (
                                        <PolyCard key={c.condition_id || i} contract={c} delay={i * 60} />
                                    ))}
                                </div>
                                {polymarket.length === 0 && (
                                    <div style={{
                                        background: "#0d111b", border: "1px solid #ffffff0d", borderRadius: 14,
                                        padding: 40, textAlign: "center", color: "#8892a4"
                                    }}>
                                        No Polymarket data — run the Polymarket fetcher
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* ─── Footer ───────────────────────────── */}
            <div style={{
                padding: "16px 28px", borderTop: "1px solid #ffffff08",
                display: "flex", justifyContent: "space-between",
                fontSize: 11, color: "#8892a433", marginTop: 40,
            }}>
                <span>EdgeSignal v0.1.0</span>
                <span>AI-Powered Trading Intelligence</span>
            </div>
        </div>
    );
}