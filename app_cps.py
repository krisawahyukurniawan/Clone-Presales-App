import streamlit as st
import pandas as pd
import time
from datetime import datetime

# ==============================================================================
# KONFIGURASI HALAMAN
# ==============================================================================
st.set_page_config(
    page_title="CPS Tracker - SISINDOKOM",
    page_icon="📡", 
    layout="wide"
)

import backend as db

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def format_number(number):
    """Format angka ke format Rupiah (tanpa simbol Rp di return value agar fleksibel)."""
    try:
        num = int(float(number))
        return f"{num:,}".replace(",", ".")
    except: return "0"

@st.cache_data(ttl=900)
def get_master(action: str):
    """Wrapper untuk memanggil backend dengan caching."""
    return db.get_master_presales(action)

def get_sales_groups():
    data = get_master('getSalesGroups')
    df = pd.DataFrame(data) if data else pd.DataFrame()
    return sorted(df['SalesGroup'].dropna().unique().tolist()) if 'SalesGroup' in df.columns else []

def get_sales_name_by_sales_group(sales_group):
    data = get_master('getSalesNames')
    df = pd.DataFrame(data) if data else pd.DataFrame()
    if sales_group:
        return sorted(df[df['SalesGroup'] == sales_group]['SalesName'].unique().tolist())
    return sorted(df['SalesName'].unique().tolist())

def get_pam_mapping_dict():
    data = get_master('getPAMMapping')
    return {item['Inputter']: item['PAM'] for item in data} if data else {}

# ==============================================================================
# MAIN APP LOGIC
# ==============================================================================

st.title("📡 CPS Tracker Webapp")
st.markdown("---")

# 1. State Management
if 'cps_lines' not in st.session_state:
    st.session_state.cps_lines = [{"id": 0}]

# 2. Load Data Master
inputter_map_cps = get_pam_mapping_dict()
presales_list_cps = get_master('getPresales')
all_companies_cps = get_master('getCompanies')
companies_df_cps = pd.DataFrame(all_companies_cps)

# --- STEP 1: HEADER (PARENT DATA) ---
st.subheader("Step 1: Opportunity & Customer Info")
col_p1, col_p2 = st.columns(2)

with col_p1:
    # Inputter
    cps_presales_obj = st.selectbox(
        "Inputter", 
        presales_list_cps, 
        format_func=lambda x: x.get("PresalesName", "Unknown"), 
        key="cps_presales"
    )
    cps_inputter_name = cps_presales_obj.get("PresalesName", "") if cps_presales_obj else ""

    # PAM Logic
    cps_pam_rule = inputter_map_cps.get(cps_inputter_name, "Not Assigned")
    if cps_pam_rule == "FLEKSIBEL":
        cps_pam_obj = st.selectbox(
            "PAM", 
            get_master('getResponsibles'), 
            format_func=lambda x: x.get("Responsible"), 
            key="cps_pam_flex"
        )
        cps_pam_final = cps_pam_obj.get('Responsible') if cps_pam_obj else ""
    else:
        cps_pam_final = cps_pam_rule
        st.text_input("PAM", value=cps_pam_final, disabled=True, key="cps_pam_fixed")
        
    # Sales Info
    cps_sales_group = st.selectbox("Sales Group", get_sales_groups(), key="cps_sg")
    cps_sales_options = get_sales_name_by_sales_group(cps_sales_group)
    cps_sales_name = st.selectbox("Sales Name", cps_sales_options, key="cps_sn")

with col_p2:
    # Opportunity Info
    cps_opp_name = st.text_input("Opportunity Name", placeholder="e.g., Managed Wifi - Bank ABC - Jan 2025", key="cps_opp_name")
    cps_start_date = st.date_input("Start Date", key="cps_start_date")

    st.markdown("---")
    
    # Company Info
    cps_is_listed = st.radio("Is the company listed?", ("Yes", "No"), key="cps_is_comp_listed", horizontal=True)
    
    cps_company_name = ""
    cps_vertical = ""

    if cps_is_listed == "Yes":
        cps_company_obj = st.selectbox(
            "Choose Company", 
            all_companies_cps, 
            format_func=lambda x: x.get("Company", ""), 
            key="cps_comp_select"
        )
        if cps_company_obj:
            cps_company_name = cps_company_obj.get("Company")
            cps_vertical = cps_company_obj.get("Vertical Industry")
        st.text_input("Vertical Industry", value=cps_vertical, disabled=True, key="cps_vert_disabled")
    else:
        cps_company_name = st.text_input("Company Name (Manual Input)", key="cps_comp_manual")
        unique_verts_cps = sorted(companies_df_cps['Vertical Industry'].dropna().unique().tolist()) if not companies_df_cps.empty else []
        cps_vertical = st.selectbox("Choose Vertical Industry", unique_verts_cps, key="cps_vert_select")

    # Stage
    stage_raw_cps = get_master('getPresalesStages')
    stage_opts_cps = sorted([s['Stage'] for s in stage_raw_cps])
    try: def_idx = stage_opts_cps.index("Open")
    except: def_idx = 0
    cps_stage = st.selectbox("Stage", stage_opts_cps, index=def_idx, key="cps_stage")

st.markdown("---")

# --- STEP 2: CPS CONFIGURATIONS (LOOPING WITH LOGIC) ---
st.subheader("Step 2: CPS Configurations")

for i, line in enumerate(st.session_state.cps_lines):
    with st.container(border=True):
        cols_header = st.columns([0.9, 0.1])
        cols_header[0].markdown(f"**Configuration #{i+1}**")
        
        # Tombol Remove Line
        if len(st.session_state.cps_lines) > 1:
            if cols_header[1].button("❌", key=f"remove_cps_{line['id']}"):
                st.session_state.cps_lines.pop(i)
                st.rerun()

        col_prod1, col_prod2 = st.columns(2)
        
        with col_prod1:
            # 1. Managed Service (MS)
            ms_options = ["Easy Access", "Easy Guard", "Easy Connect"]
            line['managed_service'] = st.selectbox(
                "Managed Service (MS)", 
                ms_options, 
                key=f"cps_ms_{line['id']}"
            )
            
            # 2. Service Offering (SO) - DEPENDENT LOGIC
            # Karena tidak pakai form, perubahan MS di atas langsung memicu rerun,
            # sehingga logic if-else di bawah ini langsung tereksekusi dan UI terupdate.
            
            current_ms = line.get('managed_service')
            
            if current_ms == "Easy Access":
                so_options = ["Full Stack", "WiFi Only"]
            else:
                so_options = ["No Service Offering"]
            
            line['service_offering'] = st.selectbox(
                "Service Offering (SO)", 
                so_options, 
                key=f"cps_so_{line['id']}"
            )
            
            # 3. Package
            p_options = ["Launch", "Growth", "Accelerate"]
            line['package'] = st.selectbox("Package", p_options, key=f"cps_pkg_{line['id']}")

            # 4. Cost
            st.markdown("#### Financials")
            line['cost'] = st.number_input(
                "Cost Estimation (IDR)", 
                min_value=0.0, step=1000000.0, 
                key=f"cps_cost_{line['id']}"
            )
            st.caption(f"Reads: Rp {format_number(line.get('cost', 0))}")
        
        with col_prod2:
            # 5. SLA
            sla_options = ["Core", "Pro", "Elite"]
            line['sla_level'] = st.selectbox("SLA Level", sla_options, key=f"cps_sla_{line['id']}")
            
            # 6. Service Execution
            se_options = ["Internal", "Subcont"]
            line['service_execution'] = st.selectbox("Service Execution", se_options, key=f"cps_se_{line['id']}")
            
            # 7. Notes
            st.markdown("#### Remarks")
            line['notes'] = st.text_area(
                "Notes", height=108, 
                placeholder="Tech details...", 
                key=f"cps_notes_{line['id']}"
            )

# Tombol Add Configuration
if st.button("➕ Add Another Configuration"):
    new_id = max(l['id'] for l in st.session_state.cps_lines) + 1 if st.session_state.cps_lines else 0
    st.session_state.cps_lines.append({"id": new_id})
    st.rerun()

st.markdown("---")

# --- STEP 3: SUBMIT ---
st.subheader("Step 3: Submit Opportunity")

email_map_cps = {p['PresalesName']: p['Email'] for p in presales_list_cps if p.get('Email')}
cps_selected_emails = st.multiselect("Notify Presales", sorted(email_map_cps.keys()), key="cps_email_notify")

if st.button("💾 Save CPS Opportunity", type="primary"):
    if not cps_inputter_name or not cps_company_name or not cps_opp_name:
        st.error("Inputter, Opportunity Name, and Company Name are required.")
    else:
        # Construct Payload
        parent_data = {
            "presales_name": cps_inputter_name,
            "responsible_name": cps_pam_final,
            "salesgroup_id": cps_sales_group,
            "sales_name": cps_sales_name,
            "company_name": cps_company_name,
            "vertical_industry": cps_vertical,
            "stage": cps_stage,
            "opportunity_name": cps_opp_name,
            "start_date": cps_start_date.strftime("%Y-%m-%d")
        }
        
        with st.spinner("Saving CPS Data..."):
            res = db.add_cps_opportunity(parent_data, st.session_state.cps_lines)
            
            if res['status'] == 200:
                st.success(f"✅ {res['message']}")
                
                # Send Email
                if cps_selected_emails:
                    count_sent = 0
                    for name in cps_selected_emails:
                        email_addr = email_map_cps.get(name)
                        if email_addr:
                            db.send_email_notification(
                                email_addr, 
                                f"New CPS Opp: {cps_opp_name}", 
                                f"<h3>New CPS Opportunity</h3><p>{cps_opp_name}</p>"
                            )
                            count_sent += 1
                    st.info(f"📧 Emails sent to {count_sent} recipient(s).")

                st.balloons()
                st.session_state.cps_lines = [{"id": 0}] # Reset State
                time.sleep(2)
                st.rerun()
            else:
                st.error(f"Failed: {res['message']}")