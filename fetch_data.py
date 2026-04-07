#!/usr/bin/env python3
"""
巴菲特/段永平 价值投资分析 — 财务数据采集脚本
buffett-analysis skill 专用数据层

用法：
    python fetch_data.py --stock 600519 --name 贵州茅台
    python fetch_data.py --stock 002230 --name 科大讯飞
    python fetch_data.py --stock 00700  --name 腾讯控股   （港股）
    python fetch_data.py --stock AAPL   --name Apple      （美股）

市场自动推断（A股无需手填）：
    6xxxxx / 900xxx        → sh（上交所）
    000/001/002/003/300/301/688/689 → sz/sh（深交所/科创板）
    5位数字开头（00/01/02/03/06/09）→ 港股
    纯英文字母/数字组合    → 美股

输出内容（供巴菲特框架 6 关使用）：
    - 当前价格 & 总市值
    - 近 5 年净利润 & 年度增速
    - 近 4 期毛利率趋势
    - 近 5 年 ROE
    - 自由现金流（经营CF - 资本支出）近 4 年
    - 分红 & 回购历史
    - 前十大股东（大股东持股比例）
    - 资产负债率（负债健康度）
"""

import argparse
import sys
import warnings
import re

warnings.filterwarnings("ignore")

# ── 市场识别 ──────────────────────────────────────────────────────────────────

def detect_market(stock: str) -> str:
    """返回 'a_share' / 'hk' / 'us'"""
    s = stock.strip().upper()
    # 港股：5位数字（不足5位补零）
    if re.match(r'^\d{5}$', s) or re.match(r'^0\d{4}$', s):
        return 'hk'
    # A股：6位数字
    if re.match(r'^\d{6}$', s):
        return 'a_share'
    # 美股：纯字母或字母+数字（如AAPL, BRK.B）
    if re.match(r'^[A-Z][A-Z0-9\.\-]{0,9}$', s):
        return 'us'
    return 'a_share'  # 默认


def infer_exchange(stock: str) -> str:
    """A股：根据代码前缀推断交易所，返回 'sh' 或 'sz'"""
    sh_prefixes = {"600", "601", "603", "605", "688", "689", "900", "110", "113"}
    prefix3 = stock[:3]
    if prefix3 in sh_prefixes or stock.startswith("6"):
        return "sh"
    return "sz"


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def safe_fetch(label: str, fn):
    try:
        result = fn()
        return result
    except Exception as e:
        print(f"  [WARN] {label} 获取失败: {e}", file=sys.stderr)
        return None


def fmt_yi(val):
    """将数值格式化为亿元"""
    try:
        return f"{val/1e8:.2f}亿"
    except Exception:
        return "—"


def fmt_pct(val):
    try:
        return f"{val:.1f}%"
    except Exception:
        return "—"


# ── A 股数据采集 ───────────────────────────────────────────────────────────────

def collect_a_share(stock: str, name: str):
    try:
        import akshare as ak
    except ImportError:
        print("ERROR: akshare 未安装。请运行: pip3 install akshare")
        sys.exit(1)

    import pandas as pd

    exchange = infer_exchange(stock)
    stock_full = f"{exchange}{stock}"
    today = pd.Timestamp.today().strftime("%Y-%m-%d")

    print("=" * 64)
    print(f"  {name}（{stock}）  |  市场: A股 {exchange.upper()}  |  {today}")
    print("=" * 64)

    # ── 1. 当前价格 & 市值 ─────────────────────────────────────────────────────
    # 注意：stock_zh_valuation_baidu 返回的"总市值"单位已经是【亿元】
    mkt_cap_yi = None   # 亿元单位，用于FCF Yield计算和显示
    cur_price = None

    mkt_df = safe_fetch("总市值", lambda: ak.stock_zh_valuation_baidu(
        symbol=stock, indicator="总市值", period="近五年"))
    if mkt_df is not None:
        mkt_cap_yi = mkt_df["value"].iloc[-1]   # 已是亿元

    pe_df = safe_fetch("PE(TTM)", lambda: ak.stock_zh_valuation_baidu(
        symbol=stock, indicator="市盈率(TTM)", period="近五年"))

    daily_raw = safe_fetch("日K线", lambda: ak.stock_zh_a_daily(
        symbol=stock_full, adjust="qfq"))
    if daily_raw is not None:
        cur_price = daily_raw["close"].iloc[-1]

    print(f"\n【基本信息】")
    print(f"  当前价格：{f'{cur_price:.2f} 元' if cur_price else '—'}")
    print(f"  总市值：{f'{mkt_cap_yi:.0f} 亿元' if mkt_cap_yi else '—'}")

    if pe_df is not None:
        pe_cur = pe_df["value"].iloc[-1]
        pe_lo  = pe_df["value"].min()
        pe_hi  = pe_df["value"].max()
        pe_med = pe_df["value"].median()
        pe_pct = (pe_cur - pe_lo) / (pe_hi - pe_lo) * 100 if (pe_hi - pe_lo) > 0 else 50
        print(f"  PE(TTM)：{pe_cur:.1f}x  5年分位: {pe_pct:.0f}%"
              f"  [低:{pe_lo:.1f} 中:{pe_med:.1f} 高:{pe_hi:.1f}]")

    pb_df = safe_fetch("PB", lambda: ak.stock_zh_valuation_baidu(
        symbol=stock, indicator="市净率", period="近五年"))
    if pb_df is not None:
        pb_cur = pb_df["value"].iloc[-1]
        pb_lo  = pb_df["value"].min()
        pb_hi  = pb_df["value"].max()
        pb_med = pb_df["value"].median()
        pb_pct = (pb_cur - pb_lo) / (pb_hi - pb_lo) * 100 if (pb_hi - pb_lo) > 0 else 50
        print(f"  PB：{pb_cur:.2f}x  5年分位: {pb_pct:.0f}%"
              f"  [低:{pb_lo:.2f} 中:{pb_med:.2f} 高:{pb_hi:.2f}]")

    # ── 2. 利润表：净利润历史 & 毛利率 ─────────────────────────────────────────
    profit_raw = safe_fetch("利润表", lambda: ak.stock_financial_report_sina(
        stock=stock, symbol="利润表"))

    print(f"\n【近5年净利润 & 年度增速】")
    normalized_pe_data = []  # 供归一化PE计算用

    if profit_raw is not None:
        import pandas as pd
        # 取年报（12-31结尾）
        annual = (profit_raw[profit_raw["报告日"].astype(str).str.endswith("1231")]
                  [["报告日", "净利润", "营业总收入"]].head(6).copy())
        annual["净利润_亿"] = annual["净利润"].apply(
            lambda x: round(x / 1e8, 2) if pd.notna(x) else None)
        annual["收入_亿"] = annual["营业总收入"].apply(
            lambda x: round(x / 1e8, 2) if pd.notna(x) else None)
        annual["yoy"] = annual["净利润"].pct_change(-1) * 100

        for _, r in annual.head(5).iterrows():
            yoy_str = f"{r['yoy']:+.1f}%" if pd.notna(r.get("yoy")) else "—"
            print(f"  {r['报告日']}  净利润: {r['净利润_亿']}亿  收入: {r['收入_亿']}亿  同比: {yoy_str}")
            if pd.notna(r["净利润"]) and r["净利润"] > 0:
                normalized_pe_data.append(r["净利润"])

        # 归一化PE（近3-5年均值）
        # normalized_pe_data 单位是元（来自sina利润表），mkt_cap_yi 单位是亿元
        if normalized_pe_data and mkt_cap_yi:
            avg_profit = sum(normalized_pe_data) / len(normalized_pe_data)
            avg_profit_yi = avg_profit / 1e8   # 转为亿元
            norm_pe = mkt_cap_yi / avg_profit_yi if avg_profit_yi > 0 else None
            print(f"\n  归一化PE（近{len(normalized_pe_data)}年均值）：",
                  f"{norm_pe:.1f}x" if norm_pe else "—",
                  f"  均值净利润: {avg_profit_yi:.2f}亿")

        # 毛利率趋势
        cost_cols = [c for c in profit_raw.columns if "营业" in c and "成本" in c]
        if cost_cols:
            annual_gm = profit_raw[profit_raw["报告日"].astype(str).str.endswith("1231")].head(5)
            rev  = pd.to_numeric(annual_gm["营业总收入"], errors="coerce")
            cost = pd.to_numeric(annual_gm[cost_cols[0]], errors="coerce")
            gm   = ((rev - cost) / rev * 100).round(1)
            print(f"\n【毛利率趋势（近5年年报）】")
            for date, val in zip(annual_gm["报告日"], gm):
                trend_marker = ""
                print(f"  {date}: {val}%{trend_marker}")

    # ── 3. ROE ─────────────────────────────────────────────────────────────────
    fin = safe_fetch("ROE", lambda: ak.stock_financial_analysis_indicator(
        symbol=stock, start_year="2019"))
    print(f"\n【近5年ROE（年报）】")
    if fin is not None:
        # 兼容不同akshare版本的列名差异
        roe_col  = next((c for c in fin.columns if "净资产收益率" in c), None)
        date_col = next((c for c in fin.columns if c in ["日期", "报告日"]), None)
        if roe_col and date_col:
            # 日期可能是 "2024-12-31" 或 "20241231" 两种格式
            dates_str = fin[date_col].astype(str)
            annual_roe = fin[dates_str.str.endswith("12-31") | dates_str.str.endswith("1231")].head(5)
            if annual_roe.empty:
                annual_roe = fin.head(5)
            for _, r in annual_roe.iterrows():
                roe_val = pd.to_numeric(r[roe_col], errors="coerce")
                flag = "  ← 优秀(>20%)" if pd.notna(roe_val) and roe_val > 20 else (
                       "  ← 良好(>15%)" if pd.notna(roe_val) and roe_val > 15 else "")
                print(f"  {r[date_col]}: {roe_val:.1f}%{flag}" if pd.notna(roe_val)
                      else f"  {r[date_col]}: —")
        else:
            print(f"  可用列: {list(fin.columns[:8])}")
    else:
        print("  数据获取失败")

    # ── 4. 自由现金流 ──────────────────────────────────────────────────────────
    cash_raw = safe_fetch("现金流量表", lambda: ak.stock_financial_report_sina(
        stock=stock, symbol="现金流量表"))
    print(f"\n【自由现金流（近4年年报）】")
    print(f"  FCF = 经营活动现金净流量 − 购建固定/无形资产支出")

    if cash_raw is not None:
        import pandas as pd
        annual_cf = cash_raw[cash_raw["报告日"].astype(str).str.endswith("1231")].head(4)

        # 查找经营活动现金流列
        op_col = next((c for c in cash_raw.columns
                       if "经营活动" in c and "净额" in c), None)
        # 查找资本支出列（购建固定资产）
        capex_col = next((c for c in cash_raw.columns
                          if "购建固定资产" in c or "购置固定资产" in c), None)

        if op_col:
            print(f"  经营CF列: {op_col}")
        if capex_col:
            print(f"  资本支出列: {capex_col}")

        for _, r in annual_cf.iterrows():
            op_cf   = r.get(op_col) if op_col else None
            capex   = r.get(capex_col) if capex_col else None
            try:
                op_cf_f = float(op_cf) if pd.notna(op_cf) else None
                capex_f = float(capex) if pd.notna(capex) else None
            except (ValueError, TypeError):
                op_cf_f = capex_f = None

            if op_cf_f is not None and capex_f is not None:
                fcf = op_cf_f - abs(capex_f)
                fcf_flag = "  ✅ 正向FCF" if fcf > 0 else "  ❌ 负向FCF"
                print(f"  {r['报告日']}  经营CF: {fmt_yi(op_cf_f)}"
                      f"  资本支出: {fmt_yi(abs(capex_f))}"
                      f"  FCF: {fmt_yi(fcf)}{fcf_flag}")
            elif op_cf_f is not None:
                print(f"  {r['报告日']}  经营CF: {fmt_yi(op_cf_f)}  资本支出: 数据缺失")
            else:
                print(f"  {r['报告日']}  现金流数据缺失")

        # FCF Yield（用最新年度FCF / 总市值）
        # FCF来自sina现金流量表，单位是元；mkt_cap_yi 是亿元
        if mkt_cap_yi and op_col and capex_col:
            first = annual_cf.iloc[0]
            try:
                op_v = float(first.get(op_col, 0))
                cx_v = abs(float(first.get(capex_col, 0)))
                fcf_latest_yi = (op_v - cx_v) / 1e8   # 转换为亿元
                if fcf_latest_yi > 0 and mkt_cap_yi > 0:
                    fcf_yield = fcf_latest_yi / mkt_cap_yi * 100
                    print(f"\n  FCF Yield（最新年度）: {fcf_yield:.1f}%", end="")
                    if fcf_yield > 8:
                        print("  ← 明显低估（>8%）")
                    elif fcf_yield > 5:
                        print("  ← 合理偏低（5-8%）")
                    elif fcf_yield > 3:
                        print("  ← 略贵（3-5%）")
                    else:
                        print("  ← 较贵（<3%）")
            except (ValueError, TypeError):
                pass
    else:
        print("  现金流量表获取失败")

    # ── 5. 分红历史 ────────────────────────────────────────────────────────────
    div = safe_fetch("分红历史", lambda: ak.stock_dividend_cninfo(symbol=stock))
    print(f"\n【分红历史（近5次年报分红）】")
    if div is not None:
        # 筛选年度分红，按日期倒序（最新在前）
        if "分红类型" in div.columns:
            yr_div = div[div["分红类型"] == "年度分红"].copy()
        else:
            yr_div = div.copy()
        # 按公告日期倒序排列（最新在前）
        date_col_div = next((c for c in yr_div.columns
                             if "公告" in c or "日期" in c or "时间" in c), None)
        if date_col_div:
            yr_div = yr_div.sort_values(date_col_div, ascending=False)
        yr_div = yr_div.head(5)
        cols = [c for c in ["实施方案公告日期", "派息比例", "报告时间"] if c in yr_div.columns]
        if cols:
            print(yr_div[cols].to_string(index=False))
        else:
            print(yr_div.head(5).to_string(index=False))
    else:
        print("  数据获取失败")

    # ── 6. 前十大股东 ──────────────────────────────────────────────────────────
    # 尝试 stock_zh_a_share_holder_top10（万得/AKShare 分位不同版本）
    print(f"\n【前十大流通股东（最新一期）】")
    holders = None
    try:
        holders = ak.stock_gdfx_free_top_10_em(symbol=stock, date="20241231")
    except Exception:
        pass
    if holders is None or holders.empty:
        try:
            holders = ak.stock_gdfx_free_top_10_em(symbol=stock, date="20240930")
        except Exception:
            pass
    if holders is None or holders.empty:
        try:
            holders = ak.stock_gdfx_top_10_em(symbol=stock, date="20241231")
        except Exception:
            pass
    if holders is not None and not holders.empty:
        cols_want = [c for c in ["股东名称", "持股比例", "持股数量", "股东类型"]
                     if c in holders.columns]
        if cols_want:
            print(holders[cols_want].head(10).to_string(index=False))
        else:
            print(holders.head(10).to_string(index=False))
    else:
        print(f"  接口暂不可用，请通过以下途径补充：")
        print(f"  WebSearch: '{name} 前十大流通股东 2024年报'")
        print(f"  或查询：东方财富、同花顺 - {stock} 股东信息")

    # ── 7. 资产负债率 ──────────────────────────────────────────────────────────
    balance_raw = safe_fetch("资产负债表", lambda: ak.stock_financial_report_sina(
        stock=stock, symbol="资产负债表"))
    print(f"\n【资产负债率】")
    if balance_raw is not None:
        latest = balance_raw.iloc[0]
        # akshare sina 资产负债表用的列名是 "资产总计" 和 "负债合计"
        ta_col = next((c for c in ["资产总计", "总资产", "资产合计",
                                    "负债和所有者权益(或股东权益)总计"] if c in balance_raw.columns), None)
        tl_col = next((c for c in ["负债合计", "总负债", "负债总计"] if c in balance_raw.columns), None)
        if ta_col and tl_col:
            ta = pd.to_numeric(latest[ta_col], errors="coerce")
            tl = pd.to_numeric(latest[tl_col], errors="coerce")
            if pd.notna(ta) and ta > 0:
                ratio = tl / ta * 100
                flag = "健康(<40%)" if ratio < 40 else ("中等(40-60%)" if ratio < 60 else "偏高(>60%)")
                print(f"  {latest['报告日']}  资产负债率: {ratio:.1f}%  → {flag}")
                print(f"  总资产: {fmt_yi(ta)}  总负债: {fmt_yi(tl)}")
        else:
            print(f"  找不到总资产/总负债列，可用列: {list(balance_raw.columns[-5:])}")
    else:
        print("  数据获取失败")

    print(f"\n{'='*64}")
    print(f"  数据采集完成 | 供巴菲特/段永平框架 6 关评估使用")
    print(f"{'='*64}\n")


# ── 港股数据采集 ───────────────────────────────────────────────────────────────

def collect_hk(stock: str, name: str):
    """港股：尝试用 akshare 港股接口，主要获取估值和基本面数据"""
    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        print("ERROR: akshare 未安装")
        sys.exit(1)

    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    stock_padded = stock.zfill(5)  # 港股代码补零到5位

    print("=" * 64)
    print(f"  {name}（{stock_padded}）  |  市场: 港股  |  {today}")
    print("=" * 64)

    # 港股实时行情
    spot = safe_fetch("港股实时", lambda: ak.stock_hk_spot_em())
    if spot is not None:
        row = spot[spot["代码"].astype(str).str.zfill(5) == stock_padded]
        if not row.empty:
            r = row.iloc[0]
            print(f"\n【基本信息】")
            cur_price = r.get("最新价", "—")
            mkt_cap   = r.get("总市值", None)
            print(f"  当前价格：{cur_price} 港元")
            if mkt_cap:
                print(f"  总市值：{fmt_yi(float(mkt_cap))}")
            pe_val = r.get("市盈率(动)", r.get("市盈率", None))
            pb_val = r.get("市净率", None)
            if pe_val:
                print(f"  PE(TTM)：{pe_val}x")
            if pb_val:
                print(f"  PB：{pb_val}x")
        else:
            print(f"\n  未找到代码 {stock_padded} 的港股行情数据")

    # 港股财务数据（akshare 港股基本面接口）
    fin = safe_fetch("港股财务", lambda: ak.stock_hk_financial_analysis_em(symbol=stock_padded))
    if fin is not None:
        print(f"\n【港股财务指标（akshare）】")
        print(fin.head(5).to_string(index=False))

    print(f"\n【注意】港股详细现金流/分红数据建议从公司官网年报或Bloomberg获取")
    print(f"{'='*64}\n")


# ── 美股数据采集 ───────────────────────────────────────────────────────────────

def collect_us(stock: str, name: str):
    """美股：用 yfinance 获取基本面数据"""
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance 未安装。请运行: pip3 install yfinance")
        sys.exit(1)

    import pandas as pd

    today = pd.Timestamp.today().strftime("%Y-%m-%d")

    print("=" * 64)
    print(f"  {name}（{stock}）  |  市场: 美股  |  {today}")
    print("=" * 64)

    ticker = yf.Ticker(stock)
    info = safe_fetch("基本信息", lambda: ticker.info) or {}

    # ── 基本信息 ──────────────────────────────────────────────────────────────
    print(f"\n【基本信息】")
    cur_price = info.get("currentPrice") or info.get("regularMarketPrice")
    mkt_cap   = info.get("marketCap")
    print(f"  当前价格：${cur_price:.2f}" if cur_price else "  当前价格：—")
    print(f"  总市值：${mkt_cap/1e9:.1f}B ({fmt_yi(mkt_cap)})" if mkt_cap else "  总市值：—")

    trailing_pe = info.get("trailingPE")
    forward_pe  = info.get("forwardPE")
    pb_ratio    = info.get("priceToBook")
    print(f"  PE(TTM)：{trailing_pe:.1f}x" if trailing_pe else "  PE(TTM)：—")
    print(f"  PE(Forward)：{forward_pe:.1f}x" if forward_pe else "  PE(Forward)：—")
    print(f"  PB：{pb_ratio:.2f}x" if pb_ratio else "  PB：—")

    # ── 净利润历史 ────────────────────────────────────────────────────────────
    print(f"\n【近4年净利润 & 收入（年报）】")
    financials = safe_fetch("财务数据", lambda: ticker.financials)
    if financials is not None and not financials.empty:
        net_income_row = None
        revenue_row    = None
        for idx in financials.index:
            if "Net Income" in str(idx):
                net_income_row = financials.loc[idx]
            if "Total Revenue" in str(idx):
                revenue_row = financials.loc[idx]

        for col in financials.columns[:4]:
            yr = str(col)[:10]
            ni = net_income_row[col] if net_income_row is not None else None
            rv = revenue_row[col]    if revenue_row    is not None else None
            ni_str = f"净利润: ${ni/1e9:.2f}B" if ni and not pd.isna(ni) else "净利润: —"
            rv_str = f"收入: ${rv/1e9:.2f}B"   if rv and not pd.isna(rv) else "收入: —"
            print(f"  {yr}  {ni_str}  {rv_str}")

        # 归一化PE
        if net_income_row is not None and mkt_cap:
            valid_ni = [v for v in net_income_row.values[:5]
                        if pd.notna(v) and v > 0]
            if valid_ni:
                avg_ni = sum(valid_ni) / len(valid_ni)
                norm_pe = mkt_cap / avg_ni
                print(f"\n  归一化PE（近{len(valid_ni)}年均值）：{norm_pe:.1f}x  均值净利润: ${avg_ni/1e9:.2f}B")
    else:
        print("  财务数据获取失败")

    # ── 毛利率 ────────────────────────────────────────────────────────────────
    print(f"\n【毛利率趋势（近4年）】")
    if financials is not None and not financials.empty:
        gp_row  = None
        rev_row = None
        for idx in financials.index:
            if "Gross Profit" in str(idx):
                gp_row = financials.loc[idx]
            if "Total Revenue" in str(idx):
                rev_row = financials.loc[idx]
        if gp_row is not None and rev_row is not None:
            for col in financials.columns[:4]:
                yr = str(col)[:10]
                try:
                    gm = gp_row[col] / rev_row[col] * 100
                    print(f"  {yr}: {gm:.1f}%")
                except Exception:
                    print(f"  {yr}: —")
        else:
            print("  毛利率字段未找到")

    # ── ROE ───────────────────────────────────────────────────────────────────
    print(f"\n【ROE（近4年）】")
    balance_sheet = safe_fetch("资产负债表", lambda: ticker.balance_sheet)
    if financials is not None and balance_sheet is not None:
        for col in financials.columns[:4]:
            yr = str(col)[:10]
            try:
                ni = [v for k, v in financials[col].items() if "Net Income" in str(k)]
                eq = [v for k, v in balance_sheet[col].items()
                      if "Stockholders Equity" in str(k) or "Total Equity" in str(k)]
                if ni and eq and eq[0] != 0:
                    roe = ni[0] / eq[0] * 100
                    flag = "  ← 优秀" if roe > 20 else ("  ← 良好" if roe > 15 else "")
                    print(f"  {yr}: {roe:.1f}%{flag}")
                else:
                    print(f"  {yr}: —")
            except Exception:
                print(f"  {yr}: —")
    else:
        print("  数据获取失败")

    # ── 自由现金流 ────────────────────────────────────────────────────────────
    print(f"\n【自由现金流（近4年）】")
    cashflow = safe_fetch("现金流量表", lambda: ticker.cashflow)
    fcf_list = []
    if cashflow is not None and not cashflow.empty:
        op_row    = None
        capex_row = None
        for idx in cashflow.index:
            if "Operating" in str(idx) and "Cash" in str(idx):
                op_row = cashflow.loc[idx]
            if "Capital Expenditure" in str(idx) or "Purchase Of Property" in str(idx):
                capex_row = cashflow.loc[idx]

        for col in cashflow.columns[:4]:
            yr = str(col)[:10]
            try:
                op_cf   = op_row[col]    if op_row    is not None else None
                capex   = capex_row[col] if capex_row is not None else None
                if op_cf is not None and capex is not None and not pd.isna(op_cf):
                    fcf = op_cf - abs(capex) if not pd.isna(capex) else op_cf
                    fcf_list.append(fcf)
                    flag = "  ✅" if fcf > 0 else "  ❌"
                    print(f"  {yr}  经营CF: ${op_cf/1e9:.2f}B"
                          f"  资本支出: ${abs(capex)/1e9:.2f}B"
                          f"  FCF: ${fcf/1e9:.2f}B{flag}")
                elif op_cf is not None and not pd.isna(op_cf):
                    print(f"  {yr}  经营CF: ${op_cf/1e9:.2f}B  资本支出: —")
            except Exception:
                print(f"  {yr}: —")

        # FCF Yield
        if fcf_list and mkt_cap:
            fcf_yield = fcf_list[0] / mkt_cap * 100
            print(f"\n  FCF Yield（最新年度）: {fcf_yield:.1f}%", end="")
            if fcf_yield > 8:
                print("  ← 明显低估（>8%）")
            elif fcf_yield > 5:
                print("  ← 合理偏低（5-8%）")
            elif fcf_yield > 3:
                print("  ← 略贵（3-5%）")
            else:
                print("  ← 较贵（<3%）")
    else:
        print("  现金流数据获取失败")

    # ── 股息历史 ──────────────────────────────────────────────────────────────
    print(f"\n【近3年分红历史】")
    div_yield = info.get("dividendYield")
    div_rate  = info.get("dividendRate")
    payout    = info.get("payoutRatio")
    if div_rate:
        print(f"  年化股息: ${div_rate:.2f}/股"
              f"  股息率: {fmt_pct(div_yield*100) if div_yield else '—'}"
              f"  派息率: {fmt_pct(payout*100) if payout else '—'}")
        dividends = safe_fetch("分红记录", lambda: ticker.dividends)
        if dividends is not None and not dividends.empty:
            recent = dividends.last("3Y")
            print(f"  近3年共分红 {len(recent)} 次")
    else:
        print("  该公司未派发股息（或数据缺失）")

    # ── 主要股东 ──────────────────────────────────────────────────────────────
    print(f"\n【主要机构/内部人股东】")
    holders = safe_fetch("机构股东", lambda: ticker.institutional_holders)
    insiders = safe_fetch("内部人持股", lambda: ticker.insider_transactions)
    if holders is not None and not holders.empty:
        cols = [c for c in ["Holder", "% Out", "Shares", "Date Reported"] if c in holders.columns]
        print(holders[cols].head(8).to_string(index=False) if cols else holders.head(8).to_string(index=False))
    else:
        print("  机构持股数据获取失败")

    print(f"\n{'='*64}")
    print(f"  数据采集完成 | 供巴菲特/段永平框架 6 关评估使用")
    print(f"{'='*64}\n")


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="巴菲特/段永平分析框架 — 财务数据采集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--stock", required=True,
                        help="股票代码：A股6位数字/港股5位数字/美股ticker")
    parser.add_argument("--name",  default="",
                        help="公司名称（可选，仅用于显示）")
    args = parser.parse_args()

    market = detect_market(args.stock)
    name   = args.name or args.stock

    if market == "a_share":
        collect_a_share(args.stock, name)
    elif market == "hk":
        collect_hk(args.stock.zfill(5), name)
    else:  # us
        collect_us(args.stock.upper(), name)
