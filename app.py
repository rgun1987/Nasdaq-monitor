import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="全球资产探头", page_icon="📡", layout="centered")

st.title("📡 全球核心资产监控系统")
st.caption("架构：单路并发批量抓取 | 规避 429 熔断 | 数据源：Yahoo")
st.markdown("---")

# 定义资产池：指数 + 核心权重股 (这里以美股七巨头+台积电+博通为代表，可自行增删)
INDEX_TICKERS = {"QQQ": "纳指100", "SPY": "标普500", "ONEQ": "纳斯达克综合"}
STOCK_TICKERS = {"AAPL": "苹果", "MSFT": "微软", "NVDA": "英伟达", "GOOGL": "谷歌", 
                 "AMZN": "亚马逊", "META": "Meta", "TSLA": "特斯拉", "TSM": "台积电", "AVGO": "博通"}

ALL_TICKERS = list(INDEX_TICKERS.keys()) + list(STOCK_TICKERS.keys()) + ["^TNX"]

@st.cache_data(ttl=1800, show_spinner=False)  # 缓存 30 分钟
def fetch_batch_data():
    try:
        # 【核心优化】：将所有股票代码拼成一个字符串，只发送 1 次网络请求！
        ticker_str = " ".join(ALL_TICKERS)
        # 获取过去 5 天的收盘价
        data = yf.download(ticker_str, period="5d", progress=False)['Close']
        
        if data.empty:
            return None, "获取历史数据失败"

        # 解析数据
        results = []
        # 获取最新一天和上一天的有效数据
        latest_prices = data.iloc[-1]
        prev_prices = data.iloc[-2]

        for ticker in ALL_TICKERS:
            if ticker == "^TNX": continue
            
            latest_px = latest_prices[ticker]
            prev_px = prev_prices[ticker]
            
            # 计算涨跌幅
            pct_change = ((latest_px - prev_px) / prev_px) * 100 if prev_px > 0 else 0
            
            # 匹配中文名称
            name = INDEX_TICKERS.get(ticker, STOCK_TICKERS.get(ticker, ticker))
            
            results.append({
                "资产": name,
                "代码": ticker,
                "最新价 ($)": round(latest_px, 2),
                "涨跌幅 (%)": round(pct_change, 2)
            })
            
        # 单独提取美债
        us10y = float(latest_prices["^TNX"]) / 100
        
        return pd.DataFrame(results), us10y

    except Exception as e:
        return None, str(e)

# 抓取纳指 PE 的兜底函数保留
@st.cache_data(ttl=3600, show_spinner=False)
def get_qqq_pe():
    try:
        pe = yf.Ticker("QQQ").info.get('trailingPE', 33.8)
        return pe if pe else 33.8
    except:
        return 33.8

if st.button("🔄 并发拉取全球数据", type="primary", use_container_width=True):
    with st.spinner("系统正在建立单条数据火线，请稍候..."):
        df, us10y = fetch_batch_data()
        
        if df is not None:
            # 获取纳指 PE
            pe = get_qqq_pe()
            earnings_yield = 1 / pe
            erp = earnings_yield - us10y
            
            # 使用 Tabs 隔离 UI，适配手机屏幕
            tab1, tab2 = st.tabs(["🚦 宏观风控 (ERP)", "📈 底层资产看板"])
            
            with tab1:
                col1, col2 = st.columns(2)
                col1.metric("纳指当前 PE", f"{pe:.2f} 倍")
                col2.metric("美债无风险利率", f"{us10y:.2%}")
                
                st.markdown("---")
                st.subheader(f"股权风险溢价 (ERP): `{erp:.2%}`")
                
                if erp > 0.03:
                    st.success("🟢 极度冰点：允许建仓。")
                elif erp > 0:
                    st.warning("🟡 合理中枢：谨慎定投。")
                else:
                    st.error("🔴 系统严重超频。切断资金流入！")
                    
            with tab2:
                st.markdown("##### 🌐 核心指数")
                # 过滤出指数并展示
                index_df = df[df['代码'].isin(INDEX_TICKERS.keys())].reset_index(drop=True)
                st.dataframe(index_df.style.map(lambda x: 'color: red' if x > 0 else 'color: green', subset=['涨跌幅 (%)']), use_container_width=True)
                
                st.markdown("##### 💻 核心权重股 (Top 算力)")
                stock_df = df[df['代码'].isin(STOCK_TICKERS.keys())].reset_index(drop=True)
                # 使用 Streamlit 样式将上涨标红，下跌标绿 (美股习惯)
                st.dataframe(stock_df.style.map(lambda x: 'color: green' if x > 0 else 'color: red', subset=['涨跌幅 (%)']), use_container_width=True)
                
        else:
            st.error(f"批量抓取失败。底层报错: {us10y}")
