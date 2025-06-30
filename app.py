import streamlit as st
import pandas as pd
import plotly.express as px
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Dict, Any
import json
from datetime import datetime
import os
import uuid

# --- CONFIGURATION ---
DATA_FILE = "finance_data.json"

# --- PYDANTIC MODELS (Our Data Structure) ---
# Unchanged
class Investment(BaseModel):
    type: Literal["SIP", "Hedge", "Saving", "Emergency Fund"]
    amount: float = Field(..., ge=0)
    details: Dict[str, Any]

class Allocations(BaseModel):
    life_expenses: float = Field(..., ge=0)
    self_supply: float = Field(..., ge=0)
    investments: List[Investment]

class IncomeSource(BaseModel):
    type: Literal["salary", "bonus", "teaching", "others"]
    amount: float = Field(..., gt=0)

class FinanceTransaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    income_source: IncomeSource
    allocations: Allocations

    @field_validator('allocations')
    def check_allocations_sum(cls, v, values):
        if 'income_source' in values.data:
            income_amount = values.data['income_source'].amount
            total_investment_amount = sum(inv.amount for inv in v.investments)
            total_allocated = v.life_expenses + v.self_supply + total_investment_amount
            if not abs(income_amount - total_allocated) < 0.01:
                raise ValueError(f"Sum of allocations ({total_allocated:,.0f}) must equal income amount ({income_amount:,.0f})")
        return v

# --- DATA HANDLING FUNCTIONS ---
# Unchanged
def load_data(filepath: str) -> List[Dict]:
    if not os.path.exists(filepath): return []
    with open(filepath, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return []

def save_data(filepath: str, data: List[Dict]):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

# --- STREAMLIT UI ---
st.set_page_config(layout="wide", page_title="Personal Finance Dashboard")
st.title("My Personal Finance Dashboard")

# --- STATE INITIALIZATION AND FORM RESET LOGIC ---
# This block runs at the top of every script run.

# 1. Initialize the session state for the dynamic list of investments
if 'investments' not in st.session_state:
    st.session_state.investments = []

# 2. Check for the reset flag. If it's set, clear the form values and then unset the flag.
if st.session_state.get('form_reset_flag', False):
    st.session_state.income_type = "salary"
    st.session_state.income_amount = 0.0
    st.session_state.life_expenses = 0.0
    st.session_state.self_supply = 0.0
    st.session_state.investments = []
    # Unset the flag
    st.session_state.form_reset_flag = False

# --- SIDEBAR FOR DATA ENTRY ---
with st.sidebar:
    st.header("Add New Transaction")

    st.subheader("1. Income Source")
    st.selectbox("Income Type", ["salary", "teaching", "bonus", "others"], key='income_type')
    st.number_input("Income Amount (VND)", min_value=0.0, step=100000.0, format="%f", key='income_amount')

    st.subheader("2. Allocations")
    st.number_input("Life Expenses", min_value=0.0, step=50000.0, format="%f", key='life_expenses')
    st.number_input("Self Supply (Lifestyle, etc.)", min_value=0.0, step=50000.0, format="%f", key='self_supply')
    
    st.subheader("3. Saving & Investments (S&I)")

    button_cols = st.columns(2)
    if button_cols[0].button("➕ Add Investment Row"):
        st.session_state.investments.append({'type': 'SIP', 'amount': 0.0})
        st.rerun()

    if button_cols[1].button("➖ Remove Last Row"):
        if st.session_state.investments:
            st.session_state.investments.pop()
            st.rerun()

    for i, inv in enumerate(st.session_state.investments):
        st.markdown(f"---")
        st.markdown(f"**Investment #{i+1}**")
        
        cols = st.columns(2)
        inv['type'] = st.selectbox(f"Type", ["SIP", "Hedge", "Saving", "Emergency Fund"], key=f"type_{i}", index=["SIP", "Hedge", "Saving", "Emergency Fund"].index(inv.get('type', 'SIP')))
        inv['amount'] = st.number_input(f"Amount", min_value=0.0, step=50000.0, format="%f", key=f"amount_{i}", value=inv.get('amount', 0.0))
        
        if inv['type'] == 'SIP':
            d_cols = st.columns(2)
            inv['fund_name'] = d_cols[0].text_input("Fund Name", value=inv.get('fund_name', ''), key=f"fund_name_{i}")
            inv['platform'] = d_cols[1].text_input("Platform", value=inv.get('platform', ''), key=f"platform_{i}")
        elif inv['type'] == 'Hedge':
            d_cols = st.columns(2)
            inv['asset_type'] = d_cols[0].selectbox("Asset Type", ["Gold", "USD", "Other"], key=f"asset_type_{i}", index=["Gold", "USD", "Other"].index(inv.get('asset_type', 'Gold')))
            inv['description'] = d_cols[1].text_input("Description", value=inv.get('description', ''), key=f"description_{i}")
        elif inv['type'] in ['Saving', 'Emergency Fund']:
            inv['destination_account'] = st.text_input("Destination Account", value=inv.get('destination_account', ''), key=f"dest_acct_{i}")

    st.divider()

    if st.button("SAVE TRANSACTION", type="primary"):
        try:
            investment_list = []
            for inv_state in st.session_state.investments:
                if inv_state.get('amount', 0) > 0:
                    details_dict = {}
                    inv_type = inv_state.get('type')
                    if inv_type == 'SIP': details_dict = {'fund_name': inv_state.get('fund_name'), 'platform': inv_state.get('platform')}
                    elif inv_type == 'Hedge': details_dict = {'asset_type': inv_state.get('asset_type'), 'description': inv_state.get('description')}
                    elif inv_type in ['Saving', 'Emergency Fund']: details_dict = {'destination_account': inv_state.get('destination_account')}
                    investment_list.append(Investment(type=inv_type, amount=inv_state['amount'], details=details_dict))
            
            new_transaction = FinanceTransaction(
                income_source=IncomeSource(type=st.session_state.income_type, amount=st.session_state.income_amount),
                allocations=Allocations(
                    life_expenses=st.session_state.life_expenses,
                    self_supply=st.session_state.self_supply,
                    investments=investment_list)
            )
            
            all_data = load_data(DATA_FILE)
            all_data.append(new_transaction.model_dump(mode='json'))
            save_data(DATA_FILE, all_data)
            
            # Set the flag to reset the form on the next run
            st.session_state.form_reset_flag = True
            st.success("Transaction saved successfully!")
            st.rerun()

        except ValueError as e:
            st.error(f"Validation Error: {e}")
        except Exception as e:
            st.error(f"An error occurred: {e}")

# --- DASHBOARD DISPLAY ---
# This entire section has been updated to include filtering logic

all_transactions = load_data(DATA_FILE)

if not all_transactions:
    st.warning("No data yet. Please add a transaction using the form on the left.")
else:
    # --- 1. Data Processing and Preparation ---
    df = pd.DataFrame(all_transactions)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month

    # --- 2. Time Filter Widgets ---
    st.header("Dashboard Overview")
    
    st.markdown("#### Filter Data")
    filter_cols = st.columns(3)
    
    years_with_data = sorted(df['year'].unique(), reverse=True)
    year_options = ["All Time"] + years_with_data
    selected_year = filter_cols[0].selectbox("Select Year", options=year_options)

    month_map = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 
                 7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
    month_options_formatted = ["All Time"] + [f"{k} - {v}" for k, v in month_map.items()]
    selected_month_formatted = filter_cols[1].selectbox("Select Month", options=month_options_formatted)
    selected_month = int(selected_month_formatted.split(' ')[0]) if selected_month_formatted != "All Time" else "All Time"

    # --- 3. Apply Time Filter ---
    df_selection = df.copy()
    if selected_year != "All Time":
        df_selection = df_selection[df_selection['year'] == selected_year]
    if selected_month != "All Time":
        df_selection = df_selection[df_selection['month'] == selected_month]

    # --- 4. Process Investment Data from the time-filtered `df_selection` ---
    temp_invest_list = []
    if not df_selection.empty:
        for index, row in df_selection.iterrows():
            if isinstance(row.get('allocations'), dict) and isinstance(row['allocations'].get('investments'), list):
                for inv in row['allocations']['investments']:
                    inv_copy = inv.copy(); inv_copy['transaction_id'] = row['transaction_id']
                    details = inv_copy.pop('details', {}); 
                    for k, v in details.items(): inv_copy[f"detail_{k}"] = v
                    temp_invest_list.append(inv_copy)

    invest_df_period = pd.DataFrame(temp_invest_list).fillna('') if temp_invest_list else pd.DataFrame()

    # --- 5. Investment Type Filter (Modified) ---
    if not invest_df_period.empty and 'type' in invest_df_period.columns:
        investment_types = sorted(invest_df_period['type'].unique())
    else:
        investment_types = []
    
    type_options = ["All Investment Types"] + investment_types
    selected_type = filter_cols[2].selectbox("Filter by Investment Type", options=type_options)

    # --- 6. Apply Investment Type Filter ---
    invest_df_display = invest_df_period.copy()
    if selected_type != "All Investment Types":
        invest_df_display = invest_df_display[invest_df_display['type'] == selected_type]

    # --- 7. Calculate and Display ---
    if df_selection.empty:
        st.warning(f"No transactions found for the selected period ({selected_month_formatted}, {selected_year}).")
    else:
        # Calculate overview metrics based on the time filter
        total_income = df_selection['income_source'].apply(lambda x: x.get('amount', 0)).sum()
        total_life_expenses = df_selection['allocations'].apply(lambda x: x.get('life_expenses', 0)).sum()
        total_self_supply = df_selection['allocations'].apply(lambda x: x.get('self_supply', 0)).sum()
        total_invested_period = invest_df_period['amount'].sum() if not invest_df_period.empty else 0

        st.markdown("---")
        metric_cols = st.columns(3)
        metric_cols[0].metric("Total Income (for period)", f"{total_income:,.0f} VND")
        metric_cols[1].metric("Total Invested (for period)", f"{total_invested_period:,.0f} VND")
        if total_income > 0:
            invest_rate = (total_invested_period / total_income) * 100
            metric_cols[2].metric("Investment Rate (for period)", f"{invest_rate:.2f}%")

        st.divider()
        chart_cols = st.columns(2)
        
        with chart_cols[0]:
            st.subheader("Main Income Allocation")
            allocation_summary = {
                'Life Expenses': total_life_expenses,
                'Self Supply': total_self_supply,
                'Savings & Investments': total_invested_period
            }
            alloc_df = pd.DataFrame(allocation_summary.items(), columns=['Category', 'Amount'])
            alloc_df = alloc_df[alloc_df['Amount'] > 0]
            if not alloc_df.empty:
                fig_pie = px.pie(alloc_df, names='Category', values='Amount', title="Allocation of Total Income (for period)")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No allocation data for this period.")

        # --- START OF MODIFIED CHART LOGIC ---
        with chart_cols[1]:
            st.subheader("Investment Portfolio Breakdown")
            if not invest_df_display.empty:
                # Default case: Show breakdown by type
                if selected_type == "All Investment Types":
                    invest_summary = invest_df_display.groupby('type')['amount'].sum().reset_index()
                    x_axis, title = 'type', "Allocation by Investment Type"
                # SIP case: Show breakdown by fund name
                elif selected_type == "SIP":
                    invest_summary = invest_df_display.groupby('detail_fund_name')['amount'].sum().reset_index()
                    x_axis, title = 'detail_fund_name', "Breakdown of SIP Investments"
                # Hedge case: Show breakdown by asset type
                elif selected_type == "Hedge":
                    invest_summary = invest_df_display.groupby('detail_asset_type')['amount'].sum().reset_index()
                    x_axis, title = 'detail_asset_type', "Breakdown of Hedge Investments"
                # Saving case: Show breakdown by account
                elif selected_type in ["Saving", "Emergency Fund"]:
                    invest_summary = invest_df_display.groupby('detail_destination_account')['amount'].sum().reset_index()
                    x_axis, title = 'detail_destination_account', "Breakdown of Savings"
                
                # Plot the chart based on the logic above
                max_y_value = invest_summary['amount'].max()
                fig_bar = px.bar(invest_summary, x=x_axis, y='amount', title=f"{title} (for period)", text_auto='.2s')
                fig_bar.update_traces(textposition='outside')
                fig_bar.update_layout(yaxis_range=[0, max_y_value * 1.15])
                st.plotly_chart(fig_bar, use_container_width=True)

            else:
                st.info("No investment data for this selection.")
        # --- END OF MODIFIED CHART LOGIC ---

        st.divider()
        with st.expander("Show Detailed Investment Data (Filtered)"):
            st.dataframe(invest_df_display)
        with st.expander("Show All Raw Transaction Data (Unfiltered)"):
            st.dataframe(df)
