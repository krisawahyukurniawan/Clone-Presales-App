import streamlit as st
import pandas as pd
import numpy as np
import utils

# ==============================================================================
# KONFIGURASI HALAMAN (WAJIB PERTAMA)
# ==============================================================================
# st.set_page_config(
#     page_title="Presales App - SISINDOKOM",
#     page_icon=":clipboard:",
#     initial_sidebar_state="expanded",
#     layout="wide"
# )

import backend as db

# ==============================================================================
# STATE & NOTIFIKASI
# ==============================================================================

if 'product_lines' not in st.session_state: st.session_state.product_lines = [{"id": 0}]
if 'submission_message' not in st.session_state: st.session_state.submission_message = None
if 'new_uids' not in st.session_state: st.session_state.new_uids = None
if 'edit_submission_message' not in st.session_state: st.session_state.edit_submission_message = None
if 'edit_new_uid' not in st.session_state: st.session_state.edit_new_uid = None
if 'selected_kanban_opp_id' not in st.session_state: st.session_state.selected_kanban_opp_id = None
if 'update_dismissed_v1_5' not in st.session_state: st.session_state.update_dismissed_v1_5 = False

if not st.session_state.update_dismissed_v1_5:
    with st.container(border=True):
        st.subheader("🚀 Update Terbaru Aplikasi! (v2.0 - PostgreSQL Version)")
        st.markdown("""
        #### 📊 Migrasi Database Selesai!
        Aplikasi ini sekarang berjalan menggunakan **PostgreSQL Direct Connection**.
        
        * **Lebih Cepat:** Tidak ada delay request API.
        * **Lebih Stabil:** Koneksi langsung ke database kantor.
        * **Fitur Sama:** Tampilan dan cara input tetap sama persis seperti sebelumnya.
        """)
        if st.button("Dismiss", key="dismiss_update_v1_5"):
            st.session_state.update_dismissed_v1_5 = True
            st.rerun()
    st.markdown("---")

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def format_number(number):
    """Mengubah angka menjadi string dengan pemisah titik."""
    try:
        num = int(float(number))
        return f"{num:,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


# ==============================================================================
# DATA LOADER (REPLACED API CALLS WITH BACKEND.PY)
# ==============================================================================

@st.cache_data(ttl=900)
def get_master(action: str):
    """Mengambil data master dari Backend Python Langsung."""
    return db.get_master_presales(action)

# Helper functions for Dropdowns (Sama seperti logika asli)
@st.cache_data(ttl=1800)
def get_pillars():
    data = get_master('getPillars')
    if not data: return []
    df = pd.DataFrame(data)
    return sorted(df['Pillar'].dropna().unique().tolist()) if 'Pillar' in df.columns else []

def get_solutions(pillar):
    data = get_master('getPillars')
    if not data: return []
    df = pd.DataFrame(data)
    return sorted(df[df['Pillar'] == pillar]['Solution'].unique().tolist()) if 'Solution' in df.columns else []

def get_services(solution):
    data = get_master('getPillars')
    if not data: return []
    df = pd.DataFrame(data)
    return sorted(df[df['Solution'] == solution]['Service'].unique().tolist()) if 'Service' in df.columns else []

def get_channels(brand):
    data = get_master('getBrands')
    if not data: return []
    df = pd.DataFrame(data)
    return sorted(df[df['Brand'] == brand]['Channel'].unique().tolist()) if 'Channel' in df.columns else []

def get_sales_groups():
    data = get_master('getSalesGroups')
    if not data: return []
    df = pd.DataFrame(data)
    return sorted(df['SalesGroup'].dropna().unique().tolist()) if 'SalesGroup' in df.columns else []

def get_sales_name_by_sales_group(sales_group):
    data = get_master('getSalesNames')
    if not data: return []
    df = pd.DataFrame(data)
    if sales_group:
        return sorted(df[df['SalesGroup'] == sales_group]['SalesName'].unique().tolist())
    return sorted(df['SalesName'].unique().tolist())

def get_pam_mapping_dict():
    data = get_master('getPAMMapping')
    if not data: return {}
    return {item['Inputter']: item['PAM'] for item in data}

# ==============================================================================
# ANTARMUKA UTAMA
# ==============================================================================

st.title("Presales App - SISINDOKOM")
st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Add Opportunity", "View Opportunities", "Search Opportunity", 
    "Update Opportunity", "Edit Opportunity", "Activity Log"
])

# ==============================================================================
# TAB 1: ADD OPPORTUNITY (MULTI-SOLUTION)
# ==============================================================================
with tab1:
    utils.tab1()

# ------------------------------------------------------------------------------
# TAB 2: KANBAN VIEW
# ------------------------------------------------------------------------------
with tab2:
    utils.tab2()
    
# ==============================================================================
# TAB 3: INTERACTIVE DASHBOARD & SEARCH (VISUAL RESTORED)
# ==============================================================================
with tab3:
    utils.tab3()

# ==============================================================================
# TAB 4: UPDATE OPPORTUNITY (REVISED: NO COMPETITOR PROMPT)
# ==============================================================================
# ==============================================================================
# TAB 4: UPDATE OPPORTUNITY (WITH ITEM DETAILS)
# ==============================================================================
with tab4:
    utils.tab4()

# ==============================================================================
# TAB 5: EDIT DATA ENTRY (FULL CORRECTION) - VISUAL RESTORED
# ==============================================================================
with tab5:
    utils.tab5()

# ==============================================================================
# TAB 6: ACTIVITY LOG / AUDIT TRAIL - VISUAL RESTORED
# ==============================================================================
with tab6:
    utils.tab6()