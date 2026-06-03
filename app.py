import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

st.set_page_config(page_title="纳指风控探头", page_icon="📊", layout="centered")

st.title("📊 纳指 100 终极估值审计")
st.caption("数据源：底层 API 降级容错机制 | 纠错优先，定量风控")
st.markdown("---")

@st.cache_data(ttl=3600, show_spinner=False)
def get_robust_data():
    us10y = None
    pe_ratio = 33.8  # 设置当前纳指 PE 的静态锚点（PE变动缓慢，作为极端防断网后备）
    
    try:
        # 战术 1：放弃极易被封的 .info，改用高容忍度的 .download() 获取实时美债收益率
        # progress=False 关闭下载进度条防止终端报错
        tnx_data = yf.download("^TNX", period="5d", progress=False)
        if not tnx_data.empty:
            # 提取最后一条有效收盘价
            us10y_raw = float(tnx_data['Close'].iloc[-1].squeeze())
            us10y = us10y_raw / 100
            
    except Exception as e:
        us10y = "ERROR"
        
    try:
        # 战术 2：尝试获取 PE，如果被封杀（429），直接捕获异常不让系统崩溃
        qqq = yf.Ticker("QQQ")
        live_pe = qqq.info.get('trailingPE', None)
        if live_pe and live_pe > 0:
            pe_ratio = live_pe
    except Exception:
        pass # 沉默捕获，使用上方的静态锚点兜底

    return pe_ratio, us10y

if st.button("🔄 一键联网审计系统状态", type="primary", use_container_width=True):
    with st.spinner("正在绕过公共节点防火墙，解析核心指标..."):
        pe, us10y = get_robust_data()
        
        if us10y != "ERROR" and us10y is not None:
            earnings_yield = 1 / pe
            erp = earnings_yield - us10y
            
            # 数据指标看板
            col1, col2 = st.columns(2)
            # 如果使用的是兜底 PE，加上 * 号提示
            pe_label = f"{pe:.2f} 倍*" if pe == 33.8 else f"{pe:.2f} 倍"
            col1.metric("纳指当前 PE", pe_label)
            col2.metric("美债无风险利率", f"{us10y:.2%}")
            
            st.markdown("---")
            st.subheader(f"股权风险溢价 (ERP): `{erp:.2%}`")
            
            # 核心风控熔断判定
            if erp > 0.03:
                st.success("🟢 🟢 🟢 绿灯状态：系统处于极度冰点，风险溢价丰厚。策略：允许开启多通道并联建仓。")
            elif erp > 0:
                st.warning("🟡 黄灯状态：估值处于合理中枢。策略：建议保持单日极小额探测性定投。")
            else:
                st.error("🔴 🔴 🔴 红灯警报！风险溢价为负，系统严重超频。策略：切断所有资金流入，捂紧口袋死等！")
                
            st.caption("*注：若带星号，表示云端节点遭遇 API 封锁，自动启用了本周最新静态 PE 进行模糊测算。美债利率为实时获取。")
        else:
            st.error("彻底断网：Streamlit 云端节点已被数据源全面物理拉黑。")
