import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- 1. 页面配置 ---
st.set_page_config(page_title="澳盛集团Sally房产投资计算器", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #333; margin-bottom: 0px; }
    .sub-header { font-size: 1rem; color: #666; margin-top: -5px; margin-bottom: 25px; padding-left: 5px; border-left: 4px solid #d93025; }
    button[data-baseweb="tab"] { font-size: 16px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. 侧边栏：全能版参数输入 (保持不变) ---
with st.sidebar:
    st.header("⚙️ 投资参数设定")
    
    with st.expander("1. 购房与贷款 (Purchase & Loan)", expanded=True):
        buy_price = st.number_input("房产价格 ($)", value=650000, step=10000)
        stamp_duty = st.number_input("印花税及杂费 ($)", value=35000, step=1000, help="维州通常约为房价的5.5%")
        loan_ratio = st.slider("贷款比例 (LVR %)", 0, 100, 80) / 100
        interest_rate = st.number_input("年利率 (%)", value=6.1, step=0.1) / 100
        loan_term = 30 
        repayment_type = st.radio("还款方式", ["只还利息 (IO)", "本息同还 (P&I)"], index=0)

    with st.expander("2. 租金与增长 (Income & Growth)", expanded=True):
        weekly_rent = st.number_input("周租金预测 ($)", value=650, step=10)
        vacancy_rate = st.slider("年空置率 (%)", 0, 20, 4) / 100 
        rental_yield = (weekly_rent * 52) / buy_price 
        
        capital_growth = st.slider("房价年增长率 (%)", 0.0, 12.0, 5.0, 0.1) / 100
        rental_growth = st.slider("租金年增长率 (%)", 0.0, 10.0, 3.5, 0.1) / 100
        cpi = 0.03 

    with st.expander("3. 持有成本 (Expenses)", expanded=True):
        st.caption("以下为年费用估算：")
        council_rates = st.number_input("市政费 (Council Rates)", value=1500, step=100)
        water_rates = st.number_input("水费 (Water Rates)", value=1000, step=100)
        strata_fees = st.number_input("物业费 (Body Corp/Strata)", value=2500, step=100)
        insurance = st.number_input("保险费 (Landlord Insurance)", value=1800, step=100)
        land_tax = st.number_input("土地税 (Land Tax)", value=1200, step=100)
        
        mgmt_fee_pct = st.slider("中介管理费 (%)", 0.0, 10.0, 6.6, 0.1) / 100
        maintain_pct = st.slider("维修预留 (占租金 %)", 0.0, 5.0, 1.0, 0.1) / 100

    with st.expander("4. 税务与折旧 (Tax & Depreciation)", expanded=True):
        tax_rate = st.selectbox("个人税率等级", [0.325, 0.37, 0.45], index=1)
        depreciation_first_year = st.number_input("首年折旧抵税额 ($)", value=8000, step=1000)

# --- 辅助函数：计算PMT (替代 numpy.pmt) ---
def calculate_pmt(rate, nper, pv):
    """
    计算每年还款额 (本息同还)
    rate: 年利率 (小数)
    nper: 剩余年限
    pv: 现值 (贷款余额)
    """
    if rate == 0:
        return pv / nper
    return (rate * pv) / (1 - (1 + rate) ** -nper)

# --- 3. 核心计算逻辑 ---
def calculate_data(years=30):
    data = []
    
    current_value = buy_price
    loan_amount = buy_price * loan_ratio
    current_weekly_rent = weekly_rent
    cumulative_cashflow = 0
    current_depreciation = depreciation_first_year
    initial_cash_invested = (buy_price - loan_amount) + stamp_duty
    
    expenses_base = {
        'council': council_rates, 'water': water_rates, 'strata': strata_fees, 
        'insurance': insurance, 'land_tax': land_tax
    }

    for year in range(1, years + 1):
        annual_rent_gross = current_weekly_rent * 52
        vacancy_loss = annual_rent_gross * vacancy_rate
        effective_rent = annual_rent_gross - vacancy_loss
        
        if repayment_type == "只还利息 (IO)":
            interest_payment = loan_amount * interest_rate
            principal_payment = 0
        else: 
            years_remain = loan_term - (year - 1)
            if years_remain > 0:
                # 修复点：使用自定义函数替代 np.pmt
                annual_repayment = calculate_pmt(interest_rate, years_remain, loan_amount)
                interest_payment = loan_amount * interest_rate
                principal_payment = annual_repayment - interest_payment
            else:
                interest_payment = 0
                principal_payment = 0
                
        inflation_multiplier = (1 + cpi) ** (year - 1)
        current_fixed_expenses = sum(expenses_base.values()) * inflation_multiplier
        mgmt_fee = effective_rent * mgmt_fee_pct
        maintenance = effective_rent * maintain_pct
        
        total_cash_expenses = interest_payment + principal_payment + current_fixed_expenses + mgmt_fee + maintenance
        pre_tax_cashflow = effective_rent - total_cash_expenses
        
        tax_deductible_expenses = interest_payment + current_fixed_expenses + mgmt_fee + maintenance + current_depreciation
        taxable_income = effective_rent - tax_deductible_expenses
        tax_impact = taxable_income * tax_rate
        post_tax_cashflow = pre_tax_cashflow - tax_impact
        
        cumulative_cashflow += post_tax_cashflow
        loan_amount -= principal_payment
        current_value = current_value * (1 + capital_growth)
        net_wealth = (current_value - loan_amount) - initial_cash_invested + cumulative_cashflow
        
        data.append({
            "Year": year,
            "Market Value": int(current_value),
            "Annual Rent": int(effective_rent),
            "Annual Cashflow": int(post_tax_cashflow),
            "Cumulative Cashflow": int(cumulative_cashflow),
            "Real Total Return": int(net_wealth)
        })
        
        current_weekly_rent *= (1 + rental_growth)
        current_depreciation *= 0.9 

    return pd.DataFrame(data)

df = calculate_data(30)

# --- 4. 页面主体内容 ---
st.markdown('<div class="main-header">🏡 澳盛集团Sally房产投资计算器</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">从首付到财富自由的推演工具。融合税务、折旧与复利效应，用真实数据辅助您的每一次置业决策。</div>', unsafe_allow_html=True)

st.markdown("### 📊 投资周期概览")
col_btns, col_empty = st.columns([3, 1])
with col_btns:
    selected_year = st.radio(
        "查看年份节点：", [5, 10, 15, 20, 30], index=1, horizontal=True, format_func=lambda x: f"{x}年期"
    )

target_row = df[df["Year"] == selected_year].iloc[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(label=f"第 {selected_year} 年 市场价", value=f"${target_row['Market Value']:,.0f}")
with c2:
    st.metric(label=f"第 {selected_year} 年 总收益 (真实价值)", value=f"${target_row['Real Total Return']:,.0f}", delta="扣除成本后")
with c3:
    cash_val = target_row['Cumulative Cashflow']
    st.metric(label=f"第 {selected_year} 年 累计现金流", value=f"${cash_val:,.0f}", delta="现金盈余" if cash_val > 0 else "现金投入", delta_color="normal" if cash_val > 0 else "inverse")
with c4:
    st.metric(label=f"第 {selected_year} 年 净租金收入", value=f"${target_row['Annual Rent']:,.0f}")

st.divider()

# --- 5. 图表区域 (修正图例为中文) ---
st.markdown("### 📈 价值走势图")

tab1, tab2 = st.tabs(["总收益走势 (回本分析)", "现金流分析"])

with tab1:
    # 准备数据
    chart_df_1 = df[["Year", "Market Value", "Real Total Return"]].melt('Year', var_name='Type', value_name='Amount')
    
    # 修复点：将数据中的英文标签替换为中文，这样图例就会自动显示中文
    type_mapping = {
        "Market Value": "市场价 (账面)",
        "Real Total Return": "真实总收益 (净值)"
    }
    chart_df_1['Type'] = chart_df_1['Type'].map(type_mapping)
    
    # 定义图例的颜色和线型映射 (使用中文Key)
    domain = ["市场价 (账面)", "真实总收益 (净值)"]
    range_color = ['gray', '#d93025']  # 灰色，红色
    range_dash = [[5, 5], [0]]        # 虚线，实线

    # 基础图表
    chart1 = alt.Chart(chart_df_1).encode(
        x=alt.X('Year', title='年份'),
        y=alt.Y('Amount', title='金额 ($)', axis=alt.Axis(format='~s')),
        
        # 核心修改：Scale Domain 使用中文，Legend Title 设为 None 让它看起来更干净
        color=alt.Color('Type', scale=alt.Scale(domain=domain, range=range_color), legend=alt.Legend(title=None, orient="top-left")),
        strokeDash=alt.StrokeDash('Type', scale=alt.Scale(domain=domain, range=range_dash), legend=alt.Legend(title=None, orient="top-left")),
        
        tooltip=['Year', 'Type', alt.Tooltip('Amount', format='$,.0f')]
    ).mark_line(strokeWidth=3).interactive()

    st.altair_chart(chart1, use_container_width=True)
    st.caption("图例说明：灰色虚线为房产市场面值，红色实线为扣除所有成本后的真实净值。")

with tab2:
    bar_chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('Year', title='年份'),
        y=alt.Y('Annual Cashflow', title='年现金流 ($)'),
        color=alt.condition(alt.datum['Annual Cashflow'] > 0, alt.value("green"), alt.value("#d93025")),
        tooltip=['Year', alt.Tooltip('Annual Cashflow', format='$,.0f')]
    ).interactive()
    st.altair_chart(bar_chart, use_container_width=True)

# --- 6. 详细数据表 ---
st.divider()
st.markdown("### 📋 详细数据表")

# 为了展示美观，复制一份数据并重命名列
display_df = df.copy()
display_df = display_df[["Year", "Market Value", "Annual Rent", "Annual Cashflow", "Cumulative Cashflow", "Real Total Return"]]
display_df.columns = ["年份", "市场估值", "年净租金", "年现金流 (税后)", "累计现金流", "真实总收益 (净值)"]

# 格式化数字，让表格看起来更像 Excel
st.dataframe(
    display_df.style.format("${:,.0f}", subset=["市场估值", "年净租金", "年现金流 (税后)", "累计现金流", "真实总收益 (净值)"]),
    use_container_width=True,
    hide_index=True
)