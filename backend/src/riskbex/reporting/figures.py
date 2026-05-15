import pandas as pd
import matplotlib.pyplot as plt


def generate_chapter2_figures(master_df, output_dir):
    master_df = master_df.copy()
    master_df["date"] = pd.to_datetime(master_df["date"])

    # 1. Daily returns
    plt.figure(figsize=(12, 5))
    plt.plot(master_df["date"], master_df["ret_1d"], linewidth=0.8)
    plt.title("Daily log returns of the IBEX 35")
    plt.xlabel("Date")
    plt.ylabel("Log return")
    plt.tight_layout()
    plt.savefig(output_dir / "daily_returns_ibex35.png", dpi=300)
    plt.close()

    # 2. Volatility vs downside volatility
    plt.figure(figsize=(12, 5))
    plt.plot(master_df["date"], master_df["vol_60d"], label="Volatility (60d)", linewidth=1)
    plt.plot(master_df["date"], master_df["downside_vol_60d"], label="Downside volatility (60d)", linewidth=1)
    plt.title("Volatility and downside volatility of the IBEX 35 (60-day window)")
    plt.xlabel("Date")
    plt.ylabel("Volatility")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "volatility_vs_downside_60d.png", dpi=300)
    plt.close()

    # 3. Drawdown
    plt.figure(figsize=(12, 5))
    plt.plot(master_df["date"], master_df["drawdown"], linewidth=1)
    plt.title("Market drawdown of the IBEX 35")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.ylim(master_df["drawdown"].min() * 1.05, 0.05)
    plt.tight_layout()
    plt.savefig(output_dir / "drawdown_ibex35.png", dpi=300)
    plt.close()

    # 4. VaR vs CVaR
    plt.figure(figsize=(12, 5))
    plt.plot(master_df["date"], master_df["var_95_60d"], label="VaR 95% (60d)", linewidth=1)
    plt.plot(master_df["date"], master_df["cvar_95_60d"], label="CVaR 95% (60d)", linewidth=1)
    plt.title("VaR and CVaR of the IBEX 35 (95%, 60-day window)")
    plt.xlabel("Date")
    plt.ylabel("Risk measure")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "var_cvar_60d.png", dpi=300)
    plt.close()

    # 5. Skewness
    plt.figure(figsize=(10, 4))
    plt.plot(master_df["date"], master_df["skew_60d"])
    plt.title("Rolling skewness (60d)")
    plt.xlabel("Date")
    plt.ylabel("Skewness")
    plt.axhline(0, linestyle="--")
    plt.tight_layout()
    plt.savefig(output_dir / "skew_60d_series.png", dpi=300)
    plt.close()

    # 6. Risk-adjusted return
    plt.figure(figsize=(8, 5))
    plt.plot(master_df["date"], master_df["ret_risk_60d"])
    plt.title("Risk-adjusted return (60-day window) of the IBEX 35")
    plt.xlabel("Date")
    plt.ylabel("Return / Volatility (60d)")
    plt.tight_layout()
    plt.savefig(output_dir / "ret_risk_60d_series.png", dpi=300)
    plt.close()
