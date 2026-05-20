import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config.settings import settings


def send_email_alert(subject, body_html):
    """Send an email alert."""
    email_user = getattr(settings, "EMAIL_USER", "") or ""
    email_pass = getattr(settings, "EMAIL_PASSWORD", "") or ""
    email_to = getattr(settings, "EMAIL_TO", "") or ""

    if not email_user or not email_pass or not email_to:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_user
        msg["To"] = email_to

        html_part = MIMEText(body_html, "html")
        msg.attach(html_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_to, msg.as_string())

        print(f"  [EMAIL] Alert sent to {email_to}")
        return True

    except Exception as e:
        print(f"  [EMAIL] Failed: {e}")
        return False


def format_signal_email(signal):
    """Format a signal as an HTML email."""
    color = "#00ffa3" if signal.get("signal_type") == "BUY" else "#ff4466" if signal.get("signal_type") == "SELL" else "#ffaa00"
    confidence = signal.get("confidence", 0)

    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0d111b; color: #e8ecf4; border-radius: 12px; overflow: hidden;">
        <div style="background: linear-gradient(135deg, #00ffa3, #00cc82); padding: 20px; text-align: center;">
            <h1 style="margin: 0; color: #080b14; font-size: 24px;">⚡ EdgeSignal Alert</h1>
        </div>

        <div style="padding: 24px;">
            <div style="display: inline-block; background: {color}22; color: {color}; border: 1px solid {color}55; padding: 4px 16px; border-radius: 6px; font-weight: 700; font-size: 14px; margin-bottom: 16px;">
                {signal.get('signal_type', 'ALERT')}
            </div>

            <h2 style="margin: 8px 0; color: #fff; font-size: 28px;">{signal.get('ticker', 'N/A')}</h2>
            <p style="color: #8892a4; margin: 4px 0; font-size: 13px;">{signal.get('asset_type', '').upper()}</p>

            <h3 style="color: #fff; margin: 16px 0 8px;">{signal.get('headline', '')}</h3>
            <p style="color: #b0b8c8; line-height: 1.6; font-size: 14px;">{signal.get('analysis', '')}</p>

            <div style="background: #1a1f2e; border-radius: 8px; padding: 16px; margin-top: 20px;">
                <table style="width: 100%; color: #e8ecf4; font-size: 14px;">
                    <tr>
                        <td style="padding: 6px 0; color: #8892a4;">Confidence</td>
                        <td style="padding: 6px 0; text-align: right; font-weight: 700;">{confidence}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #8892a4;">Entry Price</td>
                        <td style="padding: 6px 0; text-align: right; font-weight: 700;">${signal.get('entry_price', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #8892a4;">Stop Loss</td>
                        <td style="padding: 6px 0; text-align: right; color: #ff4466;">${signal.get('stop_loss', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #8892a4;">Take Profit</td>
                        <td style="padding: 6px 0; text-align: right; color: #00ffa3;">${signal.get('take_profit', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #8892a4;">Timeframe</td>
                        <td style="padding: 6px 0; text-align: right;">{signal.get('timeframe', 'N/A')}</td>
                    </tr>
                </table>
            </div>

            <!-- Confidence Bar -->
            <div style="margin-top: 16px;">
                <div style="background: #1a1f2e; border-radius: 4px; height: 8px; overflow: hidden;">
                    <div style="width: {confidence}%; height: 100%; background: {color}; border-radius: 4px;"></div>
                </div>
            </div>
        </div>

        <div style="padding: 16px 24px; border-top: 1px solid #ffffff11; text-align: center; font-size: 12px; color: #8892a455;">
            EdgeSignal v0.1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
        </div>
    </div>
    """
    return html


def format_daily_email(analysis_result, portfolio_summary=None):
    """Format the daily briefing as an HTML email."""
    summary = analysis_result.get("market_summary", "")
    signals = analysis_result.get("signals", [])
    cross = analysis_result.get("cross_asset_insights", "")
    risks = analysis_result.get("risk_warnings", "")

    signals_html = ""
    for s in signals:
        color = "#00ffa3" if s.get("signal_type") == "BUY" else "#ff4466" if s.get("signal_type") == "SELL" else "#ffaa00"
        signals_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ffffff08;">
                <span style="color: {color}; font-weight: 700;">{s.get('signal_type', '')}</span>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #ffffff08; font-weight: 600;">{s.get('ticker', '')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ffffff08;">{s.get('confidence', 0)}%</td>
            <td style="padding: 8px; border-bottom: 1px solid #ffffff08; color: #8892a4;">{s.get('headline', '')}</td>
        </tr>
        """

    portfolio_html = ""
    if portfolio_summary:
        total_pnl = portfolio_summary.get("total_open_pnl", 0)
        pnl_color = "#00ffa3" if total_pnl >= 0 else "#ff4466"
        portfolio_html = f"""
        <div style="background: #1a1f2e; border-radius: 8px; padding: 16px; margin-top: 20px;">
            <h3 style="margin: 0 0 12px; color: #fff;">💼 Portfolio</h3>
            <div style="font-size: 28px; font-weight: 800; color: {pnl_color};">${total_pnl:+.2f}</div>
            <div style="color: #8892a4; font-size: 12px;">Winners: {portfolio_summary.get('winners', 0)} | Losers: {portfolio_summary.get('losers', 0)}</div>
        </div>
        """

    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 700px; margin: 0 auto; background: #0d111b; color: #e8ecf4; border-radius: 12px; overflow: hidden;">
        <div style="background: linear-gradient(135deg, #00ffa3, #00cc82); padding: 24px; text-align: center;">
            <h1 style="margin: 0; color: #080b14; font-size: 24px;">📊 EdgeSignal Daily Brief</h1>
            <p style="margin: 4px 0 0; color: #080b14aa; font-size: 14px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
        </div>

        <div style="padding: 24px;">
            <h3 style="color: #fff; margin: 0 0 8px;">Market Summary</h3>
            <p style="color: #b0b8c8; line-height: 1.6;">{summary}</p>

            {portfolio_html}

            <h3 style="color: #fff; margin: 20px 0 12px;">🚨 Signals ({len(signals)})</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px; color: #e8ecf4;">
                <tr style="color: #8892a4; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">
                    <td style="padding: 8px;">Type</td>
                    <td style="padding: 8px;">Ticker</td>
                    <td style="padding: 8px;">Conf</td>
                    <td style="padding: 8px;">Headline</td>
                </tr>
                {signals_html}
            </table>

            <div style="background: #1a1f2e; border-radius: 8px; padding: 16px; margin-top: 20px;">
                <h3 style="margin: 0 0 8px; color: #fff;">🔗 Cross-Asset Insights</h3>
                <p style="color: #b0b8c8; line-height: 1.6; font-size: 14px; margin: 0;">{cross or 'None detected'}</p>
            </div>

            <div style="background: #1a1f2e; border-radius: 8px; padding: 16px; margin-top: 12px;">
                <h3 style="margin: 0 0 8px; color: #fff;">⚠️ Risk Warnings</h3>
                <p style="color: #b0b8c8; line-height: 1.6; font-size: 14px; margin: 0;">{risks or 'None'}</p>
            </div>
        </div>

        <div style="padding: 16px 24px; border-top: 1px solid #ffffff11; text-align: center; font-size: 12px; color: #8892a455;">
            EdgeSignal v0.1.0 — AI Trading Intelligence
        </div>
    </div>
    """
    return html


def send_signal_alert(signal):
    """Send a signal as an email."""
    subject = f"⚡ EdgeSignal {signal.get('signal_type', 'ALERT')}: {signal.get('ticker', 'N/A')} ({signal.get('confidence', 0)}%)"
    body = format_signal_email(signal)
    return send_email_alert(subject, body)


def send_daily_briefing(analysis_result, portfolio_summary=None):
    """Send daily briefing as email."""
    subject = f"📊 EdgeSignal Daily Brief — {datetime.now().strftime('%b %d, %Y')}"
    body = format_daily_email(analysis_result, portfolio_summary)
    return send_email_alert(subject, body)


if __name__ == "__main__":
    # Test with a dummy signal
    test_signal = {
        "signal_type": "BUY",
        "ticker": "AAPL",
        "asset_type": "stock",
        "confidence": 82,
        "headline": "Test signal — Apple showing strength",
        "analysis": "This is a test email alert.",
        "entry_price": 190.50,
        "stop_loss": 185.00,
        "take_profit": 200.00,
        "timeframe": "swing_2_5_days",
    }

    result = send_signal_alert(test_signal)
    if result:
        print("✅ Test email sent!")
    else:
        print("❌ Email not configured. Add EMAIL_USER, EMAIL_PASSWORD, EMAIL_TO to .env")