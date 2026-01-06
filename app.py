import streamlit as st
import pandas as pd
import numpy as np
import utils

# ==============================================================================
# KONFIGURASI HALAMAN (WAJIB PERTAMA)
# ==============================================================================
st.set_page_config(
    page_title="Presales App - SISINDOKOM",
    page_icon=":clipboard:",
    initial_sidebar_state="expanded",
    layout="wide"
)

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