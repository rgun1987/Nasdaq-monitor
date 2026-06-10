import streamlit as st
import yfinance as yf
import pandas as pd

# ==========================================
# 1. 全局配置与底层资产池定义
# ==========================================
st.set_page_config(page_title="全球资产探头", page_icon="📡", layout="centered")

st.title("📡 全球核心资产风控系统")
st.caption("架构：双重网关 (宏观 ERP 估值 + 微观 Gamma 期权墙) | 定量风控")
st.markdown("---")

INDEX_TICKERS = {"QQQ": "纳指100", "SPY": "标普500", "ONEQ": "纳斯达克综合"}
STOCK_TICKERS = {"AAPL": "苹果", "MSFT": "微软", "NVDA": "英伟达", "GOOGL": "谷歌", 
                 "AMZN": "亚马逊", "META": "Meta", "TSLA": "特斯拉", "TSM": "台积电", "AVGO": "博通"}

# 合并请求列表，^TNX 为 10 年期美债收益率
ALL_TICKERS = list(INDEX_TICKERS.keys()) + list(STOCK_TICKERS.keys()) + ["^TNX"]

# ==========================================
# 2. 核心数据抓取与计算引擎 (带严格缓存隔离)
# ==========================================

@st.cache_data(ttl=1800, show_spinner=False)  # 缓存 30 分钟，防 429 熔断
def fetch_batch_data():
    """并发批量抓取基础现价与涨跌幅"""
    try:
        ticker_str = " ".join(ALL_TICKERS)
        data = yf.download(ticker_str, period="5d", progress=False)['Close']
        
        if data.empty:
            return None, "获取历史数据失败"

        results = []
        latest_prices = data.iloc[-1]
        prev_prices = data.iloc[-2]

        for ticker in ALL_TICKERS:
            if ticker == "^TNX": continue
            
            latest_px = latest_prices[ticker]
            prev_px = prev_prices[ticker]
            pct_change = ((latest_px - prev_px) / prev_px) * 100 if prev_px > 0 else 0
            name = INDEX_TICKERS.get(ticker, STOCK_TICKERS.get(ticker, ticker))
            
            results.append({
                "资产": name,
                "代码": ticker,
                "最新价 ($)": round(latest_px, 2),
                "涨跌幅 (%)": round(pct_change, 2)
            })
            
        us10y = float(latest_prices["^TNX"]) / 100
        return pd.DataFrame(results), us10y

    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=3600, show_spinner=False) # 缓存 1 小时，.info 是高危接口
def get_qqq_pe():
    """抓取纳指 PE，自带备用锚点兜底"""
    try:
        pe = yf.Ticker("QQQ").info.get('trailingPE', 33.8)
        return pe if pe else 33.8
    except:
        return 33.8

@st.cache_data(ttl=3600, show_spinner=False) # 期权数据重负载，缓存 1 小时
def fetch_options_risk(ticker="QQQ"):
    """抓取期权微观结构，带深度异常捕获机制"""
    try:
        tk = yf.Ticker(ticker)
        dates = tk.options
        
        if not dates:
            # 捕获空数据
            return None, "数据阻断", "雅虎未返回交割日列表 (可能触发反爬或代码失效)"

        target_date = dates[0] 
        chain = tk.option_chain(target_date)
        puts = chain.puts
        
        if puts.empty or 'openInterest' not in puts.columns:
            return None, target_date, "OI字段丢失或表单为空"
            
        max_oi_idx = puts['openInterest'].idxmax()
        put_wall_strike = float(puts.loc[max_oi_idx, 'strike'])
        
        return put_wall_strike, target_date, "Success"

    except Exception as e:
        # 将最底层的真实报错抓取出来
        return None, "API 熔断", f"底层异常日志: {str(e)}"

# ==========================================
# 3. 前端 UI 渲染与逻辑判定
# ==========================================

if st.button("🔄 启动双核审计扫描", type="primary", use_container_width=True):
    with st.spinner("正在穿透公网节点，解析底层宏观与期权数据..."):
        df, us10y = fetch_batch_data()
        
        if df is not None:
            # --- 数据准备 ---
            pe = get_qqq_pe()
            earnings_yield = 1 / pe
            erp = earnings_yield - us10y
            
            put_wall, opex_date, put_oi = fetch_options_risk("QQQ")
            qqq_px = df[df['代码'] == 'QQQ']['最新价 ($)'].values[0]
            
            # --- 选项卡隔离 ---
            tab1, tab2 = st.tabs(["🚦 双核风控 (ERP & Gamma)", "📈 底层资产看板"])
            
            with tab1:
                # 【模块 A：宏观 ERP 估值探头】
                col1, col2 = st.columns(2)
                col1.metric("纳指100 (QQQ) 动态 PE", f"{pe:.2f} 倍")
                col2.metric("美债无风险利率 (10Y)", f"{us10y:.2%}")
                
                st.markdown("<h3 style='text-align: center;'>当前股权风险溢价 (ERP)</h3>", unsafe_allow_html=True)
                
                if erp > 0.03:
                    erp_color = "#00C853" 
                    status_text = "🟢 极度低估：系统冰点，估值健康，建议开启定投。"
                elif erp > 0:
                    erp_color = "#FFD600" 
                    status_text = "🟡 估值合理：正常估值中枢，保持探测性买入。"
                else:
                    erp_color = "#D50000" 
                    status_text = "🔴 系统超载：估值极度透支，随时崩盘，强制空仓死等！"
                    
                st.markdown(f"<h1 style='text-align: center; color: {erp_color};'>{erp:.2%}</h1>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; font-size: 1.1rem; color: #E0E0E0;'>{status_text}</p>", unsafe_allow_html=True)
                
                st.markdown("---")
                
                # 【模块 B：微观期权结构探头 (防负 Gamma 踩踏)】
                st.markdown("### 🕸️ 期权微观结构 (负 Gamma 监控)")
                
                # 重新映射返回值：put_oi 变量现在承载的是具体的报错信息 (error_log)
                if put_wall is not None:
                    distance = ((qqq_px - put_wall) / qqq_px) * 100
                    
                    col3, col4 = st.columns(2)
                    col3.metric("看跌期权墙 (Put Wall)", f"${put_wall:.2f}", f"距离现价: {distance:.2f}%", delta_color="off")
                    col4.metric("下个交割释放日 (OpEx)", opex_date)
                    
                    st.warning(f"**微观审计结论**：当前 QQQ 价格为 **${qqq_px:.2f}**。如果跌破 Put Wall **${put_wall:.2f}**，将触发期权做市商的强制砸盘（负 Gamma 死亡螺旋）。该踩踏危机大概率需等待 **{opex_date}** 交割日结算后方可解除。期间绝对禁止抢反弹。")
                else:
                    # 触发降级机制：直接将底层的 Python 报错信息打印在屏幕上
                    st.warning(f"⚠️ **微观探头离线**：期权数据通道被雅虎防火墙物理切断。")
                    st.code(f"状态: {opex_date}\n{put_oi}", language="bash")
                    st.caption("*系统注：期权微观通道阻断不影响上方核心 ERP 宏观指标的测算。请依赖 ERP 指标进行定投决策。")
                
                st.markdown("---")
                
                # 算法释义卡片
                st.info("""
                **📐 核心物理架构释义**
                * **宏观 ERP**：`ERP = (1 / 纳指PE) - 10年期美债收益率`。当 ERP ≤ 0 时，买股预期收益不如买国债，属于“超频运载”。
                * **微观 Put Wall**：未平仓合约最多的看跌期权行权价。跌破此价，做市商算法将强制抛售正股，形成纯机械式的无脑砸盘。
                """)
                    
            with tab2:
                # 核心资产展示逻辑 (美股习惯：绿涨红跌)
                st.markdown("##### 🌐 核心指数")
                index_df = df[df['代码'].isin(INDEX_TICKERS.keys())].reset_index(drop=True)
                st.dataframe(index_df.style.map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['涨跌幅 (%)']), use_container_width=True)
                
                st.markdown("##### 💻 核心算力权重股")
                stock_df = df[df['代码'].isin(STOCK_TICKERS.keys())].reset_index(drop=True)
                st.dataframe(stock_df.style.map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['涨跌幅 (%)']), use_container_width=True)
                
        else:
            st.error(f"系统网关穿透失败。报错日志: {us10y}")
