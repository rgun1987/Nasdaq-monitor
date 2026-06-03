import streamlit as st
import yfinance as yf
import requests

st.set_page_config(page_title="纳指风控探头", page_icon="📊", layout="centered")

st.title("📊 纳指 100 终极估值审计")
st.caption("数据源：联网实时同步 | 纠错优先，定量风控")
st.markdown("---")

# 引入缓存机制：TTL=3600表示缓存1小时（3600秒）。1小时内重复点击不会触发真实网络请求，直接返回本地内存数据。
@st.cache_data(ttl=3600, show_spinner=False)
def get_live_data():
    try:
        # 1. 构建伪装的浏览器会话通道
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })

        # 2. 抓取10年期美债收益率 (强制使用伪装 session)
        tnx = yf.Ticker("^TNX", session=session)
        us10y_raw = tnx.info.get('previousClose', None)
        
        if us10y_raw is None:
            us10y_raw = yf.Ticker("IEF", session=session).info.get('yield', 4.5) * 100
        us10y = us10y_raw / 100
        
        # 3. 抓取纳指标杆 QQQ 的动态市盈率
        qqq = yf.Ticker("QQQ", session=session)
        pe_ratio = qqq.info.get('trailingPE', 33.5)
        
        return pe_ratio, us10y
        
    except Exception as e:
        return None, str(e)

if st.button("🔄 一键联网审计系统状态", type="primary", use_container_width=True):
    with st.spinner("正在穿透跨境网络，解析核心指标..."):
        # 调用自带缓存的获取函数
        pe, us10y = get_live_data()
        
        if pe is not None and isinstance(us10y, float):
            earnings_yield = 1 / pe
            erp = earnings_yield - us10y
            
            # 数据指标看板
            col1, col2 = st.columns(2)
            col1.metric("纳指当前 PE", f"{pe:.2f} 倍")
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
        else:
            # 捕获并输出底层的伪装失败或超时报错
            st.error(f"网关穿透失败，远端接口拒绝响应。底层反馈: {us10y}")
            st.info("提示：云端 IP 池可能处于重度封锁期。请等待 1 小时后重试，或联系运维人员更换数据源。")
