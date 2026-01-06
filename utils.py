import streamlit as st
import pandas as pd
import time
import backend as db

def format_number(number):
    """Mengubah angka menjadi string dengan pemisah titik."""
    try:
        num = int(float(number))
        return f"{num:,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

@st.cache_data(ttl=900)
def get_master(action: str):
    """Mengambil data master dari Backend Python Langsung."""
    return db.get_master_presales(action)

def get_pam_mapping_dict():
    data = get_master('getPAMMapping')
    if not data: return {}
    return {item['Inputter']: item['PAM'] for item in data}

def get_channels(brand):
    data = get_master('getBrands')
    if not data: return []
    df = pd.DataFrame(data)
    return sorted(df[df['Brand'] == brand]['Channel'].unique().tolist()) if 'Channel' in df.columns else []

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

def clean_data_for_display(data):
    """Membersihkan dan memformat data untuk st.dataframe."""
    # 1. Handle Input Type
    if isinstance(data, pd.DataFrame):
        if data.empty: return pd.DataFrame()
        df = data.copy()
    elif not data:
        return pd.DataFrame()
    else:
        df = pd.DataFrame(data)

    desired_order = [
        'uid', 'presales_name', 'responsible_name','salesgroup_id','sales_name', 'company_name', 
        'opportunity_name', 'start_date', 'pillar', 'solution', 'service', 'brand', 
        'channel', 'distributor_name', 'cost', 'stage', 'notes', 'sales_notes', 'created_at', 'updated_at'
    ]
    
    # Filter kolom yang ada saja
    existing_cols = [col for col in desired_order if col in df.columns]
    if not existing_cols: return pd.DataFrame()
    
    df = df[existing_cols].copy()

    # 2. Format Angka (Cost)
    for col in ['cost', 'selling_price']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            df[col] = df[col].apply(lambda x: f"Rp {format_number(x)}")

    # 3. Format Tanggal (PERBAIKAN ERROR TIMEZONE DISINI)
    for date_col in ['start_date', 'created_at', 'updated_at']:
        if date_col in df.columns:
            # Pastikan format datetime
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            
            if date_col == 'start_date':
                # Start date biasanya hanya tanggal, tidak butuh jam/timezone
                df[date_col] = df[date_col].dt.strftime('%d-%m-%Y')
            else:
                # Untuk created_at dan updated_at yang butuh jam
                try:
                    # Coba convert langsung (jika data sudah punya timezone/aware)
                    df[date_col] = df[date_col].dt.tz_convert('Asia/Jakarta')
                except TypeError:
                    # Jika error "tz-naive", berarti data polos.
                    # Kita anggap data DB adalah UTC, lalu convert ke Jakarta.
                    # Jika data DB Anda sebenarnya sudah WIB, ganti 'UTC' jadi 'Asia/Jakarta'
                    df[date_col] = df[date_col].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
                
                # Format string akhir
                df[date_col] = df[date_col].dt.strftime('%d-%m-%Y %H:%M')
            
            # Bersihkan nilai error/kosong (NaT)
            df[date_col] = df[date_col].replace('NaT', '', regex=False)

    return df

@st.fragment
def tab1():
    st.header("Add New Opportunity (Multi-Solution)")
    st.info("Fill out the main details once, then add one or more solutions below.")
    
    # Load Helper Data
    inputter_to_pam_map = get_pam_mapping_dict()
    DEFAULT_PAM = "Not Assigned"

    # --- STEP 1: PARENT DATA (HEADER) ---
    st.subheader("Step 1: Main Opportunity Details")
    parent_col1, parent_col2 = st.columns(2)
    
    with parent_col1:
        # 1. Inputter
        presales_list = get_master('getPresales')
        presales_name_obj = st.selectbox(
            "Inputter", 
            presales_list, 
            format_func=lambda x: x.get("PresalesName", "Unknown"), 
            key="parent_presales_name"
        )
        selected_inputter_name = presales_name_obj.get("PresalesName", "") if presales_name_obj else ""
        
        # 2. PAM Logic
        pam_rule = inputter_to_pam_map.get(selected_inputter_name, DEFAULT_PAM)
        
        if pam_rule == "FLEKSIBEL":
            pam_object = st.selectbox(
                "Choose Presales Account Manager", 
                get_master('getResponsibles'), 
                format_func=lambda x: x.get("Responsible", "Unknown"), 
                key="pam_flexible_choice"
            )
            responsible_name_final = pam_object.get('Responsible', '') if pam_object else ""
        else:
            responsible_name_final = pam_rule
            st.text_input("Presales Account Manager", value=responsible_name_final, disabled=True)

        # 3. Sales Group
        salesgroup_id = st.selectbox("Choose Sales Group", get_sales_groups(), key="parent_salesgroup_id")
        
        # 4. Sales Name
        sales_name_options = get_sales_name_by_sales_group(salesgroup_id)
        sales_name = st.selectbox("Choose Sales Name", sales_name_options, key="parent_sales_name")

        # 5. STAGE (Dropdown yang sudah ada)
        stage_raw = get_master('getPresalesStages') 
        stage_options = sorted([s.get("Stage") for s in stage_raw if s.get("Stage")])
        default_idx = stage_options.index("Open") if "Open" in stage_options else 0
        
        selected_stage = st.selectbox(
            "Current Stage", 
            stage_options, 
            index=default_idx,
            key="parent_stage_select"
        )

        # --- [BARU] STAGE NOTES UNTUK LLM ---
        stage_notes = st.text_area(
            "Stage Notes (Context for AI)",
            placeholder="Jelaskan apa yang terjadi di stage ini (misal: User minta revisi BoQ, menunggu budget approval, dll)...",
            height=100,
            key="parent_stage_notes",
            help="Catatan ini akan digunakan oleh AI untuk menganalisis konteks history opportunity."
        )

    with parent_col2:
        # 6. Opportunity Name
        opp_raw = get_master('getOpportunities')
        opp_options = sorted([opt.get("Desc") for opt in opp_raw if opt.get("Desc")])
        
        opportunity_name = st.selectbox(
            "Opportunity Name", 
            opp_options, 
            key="parent_opportunity_name", 
            accept_new_options=True, 
            index=None, 
            placeholder="Choose or type new..."
        )
        
        st.warning("""
        Format Opportunity Name:
        - If direct: End User - Opportunity Name - Month Year
        - If via B2B Channel: [B2B Channel] End User - Opportunity Name - Month Year
        """)
        
        start_date = st.date_input("Start Date", key="parent_start_date")
        
        # 7. Company & Vertical
        all_companies = get_master('getCompanies')
        companies_df = pd.DataFrame(all_companies)
        
        is_company_listed = st.radio("Is the company listed?", ("Yes", "No"), key="parent_is_company_listed", horizontal=True)
        company_name_final = ""
        vertical_industry_final = ""

        if is_company_listed == "Yes":
            company_obj = st.selectbox(
                "Choose Company", 
                all_companies, 
                format_func=lambda x: x.get("Company", ""), 
                key="parent_company_select"
            )
            if company_obj:
                company_name_final = company_obj.get("Company", "")
                vertical_industry_final = company_obj.get("Vertical Industry", "")
            
            st.text_input("Vertical Industry", value=vertical_industry_final, disabled=True)
        else:
            company_name_final = st.text_input("Company Name (if not listed)", key="parent_company_text_input")
            if not companies_df.empty and 'Vertical Industry' in companies_df.columns:
                unique_verts = sorted(companies_df['Vertical Industry'].dropna().astype(str).unique().tolist())
            else:
                unique_verts = []
            vertical_industry_final = st.selectbox("Choose Vertical Industry", unique_verts, key="parent_vertical_industry_select")

    # --- STEP 2: DYNAMIC PRODUCT LINES ---
    st.markdown("---")
    st.subheader("Step 2: Add Solutions")
    
    brand_data_raw = get_master('getBrands')
    unique_brands_list = sorted(list(set([b.get('Brand') for b in brand_data_raw if b.get('Brand')])))
    dist_data_raw = get_master('getDistributors')
    dist_list = sorted([d.get("Distributor") for d in dist_data_raw if d.get("Distributor")])

    for i, line in enumerate(st.session_state.product_lines):
        with st.container(border=True):
            cols = st.columns([0.9, 0.1])
            cols[0].markdown(f"**Solution {i+1}**")
            
            if len(st.session_state.product_lines) > 1:
                if cols[1].button("❌", key=f"remove_{line['id']}"):
                    st.session_state.product_lines.pop(i)
                    st.rerun()

            lc1, lc2 = st.columns(2)
            with lc1:
                line['pillar'] = st.selectbox("Pillar", get_pillars(), key=f"pillar_{line['id']}")
                line['solution'] = st.selectbox("Solution", get_solutions(line['pillar']), key=f"solution_{line['id']}")
                line['service'] = st.selectbox("Service", get_services(line['solution']), key=f"service_{line['id']}")
            
            with lc2:
                line['brand'] = st.selectbox("Brand", unique_brands_list, key=f"brand_{line['id']}")
                line['channel'] = st.selectbox("Channel", get_channels(line.get('brand')), key=f"channel_{line['id']}")
                line['cost'] = st.number_input("Cost", min_value=0, step=1000000, key=f"cost_{line['id']}", format="%d")
                st.caption(f"Reads: Rp {format_number(line.get('cost', 0))}")
                
                note_message = "Note: All values must be in Indonesian Rupiah (IDR). (e.g., 1 USD = 16,500 IDR)."
                if line.get("brand") == "Cisco":
                    note_message += " For Cisco only: First, apply a 50% discount to the price, then multiply by the IDR exchange rate."
                st.info(note_message)
                
                is_via = st.radio("Via Distributor?", ("Yes", "No"), index=1, key=f"is_via_{line['id']}", horizontal=True)
                if is_via == "Yes":
                    line['distributor_name'] = st.selectbox("Distributor", dist_list, key=f"dist_{line['id']}")
                else:
                    line['distributor_name'] = "Not via distributor"
            
            line['notes'] = st.text_area("Notes", key=f"notes_{line['id']}", height=100)

    if st.button("➕ Add Another Solution"):
        new_id = max(line['id'] for line in st.session_state.product_lines) + 1 if st.session_state.product_lines else 0
        st.session_state.product_lines.append({"id": new_id})
        st.rerun()

    # --- STEP 3: SUBMIT ---
    st.markdown("---")
    st.subheader("Step 3: Submit Opportunity")
    
    email_map = {p['PresalesName']: p['Email'] for p in presales_list if p.get('Email')}
    selected_emails = st.multiselect("Tag Presales for Notification (Optional)", sorted(email_map.keys()))
    
    if st.button("Submit Opportunity and All Solutions", type="primary"):
        if not opportunity_name or not company_name_final:
            st.error("Opportunity Name and Company are required.")
        else:
            parent_data = {
                "presales_name": selected_inputter_name, 
                "responsible_name": responsible_name_final,
                "salesgroup_id": salesgroup_id, 
                "sales_name": sales_name,
                "opportunity_name": opportunity_name, 
                "start_date": start_date.strftime("%Y-%m-%d"),
                "company_name": company_name_final, 
                "vertical_industry": vertical_industry_final,
                "stage": selected_stage,
                "stage_notes": stage_notes
            }
            
            with st.spinner("Submitting to Database..."):
                res = db.add_multi_line_opportunity(parent_data, st.session_state.product_lines)
                
                if res['status'] == 200:
                    st.session_state.submission_message = res['message']
                    st.session_state.new_uids = [x['uid'] for x in res['data']]
                    
                    if selected_emails:
                        count_sent = 0
                        for name in selected_emails:
                            email_addr = email_map.get(name)
                            if email_addr:
                                db.send_email_notification(
                                    email_addr, 
                                    f"New Opp: {opportunity_name}", 
                                    f"<h3>New Opportunity</h3><p><b>Stage:</b> {selected_stage}</p><p><b>Client:</b> {company_name_final}</p>"
                                )
                                count_sent += 1
                        st.session_state.submission_message += f" | Emails sent to {count_sent} recipient(s)."
                    
                    st.session_state.product_lines = [{"id": 0}]
                    st.rerun()
                else:
                    st.error(f"Failed to submit: {res['message']}")

    if st.session_state.submission_message:
        st.success(st.session_state.submission_message)
        if st.session_state.new_uids: 
            st.info(f"Generated UIDs: {st.session_state.new_uids}")
        st.session_state.submission_message = None
        st.session_state.new_uids = None

@st.fragment
def tab2():
    st.header("Kanban View by Opportunity Stage")
    
    with st.spinner("Fetching leads..."):
        res = db.get_all_leads_presales() # Backend call
        
    if not res['data']:
        st.info("No data found.")
    else:
        df_master = pd.DataFrame(res['data'])
        
        # --- FILTERS (DENGAN FIX SORTING) ---
        st.markdown("---")
        st.subheader("Filters")
        
        # Handle NULL agar sorted() tidak error
        df_master['presales_name'] = df_master['presales_name'].fillna("Unknown").astype(str)
        df_master['responsible_name'] = df_master['responsible_name'].fillna("Unknown").astype(str)
        df_master['salesgroup_id'] = df_master['salesgroup_id'].fillna("Unknown").astype(str)
        
        c1, c2, c3 = st.columns(3)
        with c1: 
            sel_inputter = st.multiselect("Filter by Inputter", sorted(df_master['presales_name'].unique()))
        with c2: 
            sel_pam = st.multiselect("Filter by PAM", sorted(df_master['responsible_name'].unique()))
        with c3: 
            sel_group = st.multiselect("Filter by Sales Group", sorted(df_master['salesgroup_id'].unique()))
            
        # Apply Filters
        df_filtered = df_master.copy()
        if sel_inputter: df_filtered = df_filtered[df_filtered['presales_name'].isin(sel_inputter)]
        if sel_pam: df_filtered = df_filtered[df_filtered['responsible_name'].isin(sel_pam)]
        if sel_group: df_filtered = df_filtered[df_filtered['salesgroup_id'].isin(sel_group)]
        
        st.markdown("---")
        
        # --- DETAIL VIEW LOGIC ---
        if st.session_state.selected_kanban_opp_id:
            sel_id = st.session_state.selected_kanban_opp_id
            if st.button("⬅️ Back to Kanban View"):
                st.session_state.selected_kanban_opp_id = None
                st.rerun()
            
            # Get Details
            detail_df = df_filtered[df_filtered['opportunity_id'] == sel_id]
            if detail_df.empty:
                st.error("Details not found (might be hidden by filter).")
            else:
                header = detail_df.iloc[0]
                st.header(f"Detail for: {header['opportunity_name']}")
                st.subheader(f"Client: {header['company_name']}")
                st.markdown("---")
                
                k1, k2 = st.columns(2)
                with k1:
                    st.markdown(f"**Inputter:** {header['presales_name']}")
                    st.markdown(f"**PAM:** {header['responsible_name']}")
                    st.markdown(f"**Start Date:** {header['start_date']}")
                with k2:
                    st.markdown(f"**Stage:** {header.get('stage', 'Open')}")
                    st.markdown(f"**Opp ID:** {header['opportunity_id']}")
                
                st.subheader("Solution Details")
                st.dataframe(clean_data_for_display(detail_df), use_container_width=True)

        # --- KANBAN BOARD LOGIC ---
        else:
            if df_filtered.empty:
                st.warning("No data after filter.")
            else:
                # Calculate Cost
                if 'cost' not in df_filtered.columns: df_filtered['cost'] = 0
                df_filtered['cost'] = pd.to_numeric(df_filtered['cost'], errors='coerce').fillna(0)
                
                # 1. Aggregasi per Opportunity ID (Total Cost)
                # Group by ID, ambil first untuk metadata, sum untuk cost
                df_opps = df_filtered.groupby('opportunity_id').agg({
                    'opportunity_name': 'first',
                    'company_name': 'first',
                    'presales_name': 'first',
                    'stage': 'first',
                    'cost': 'sum'
                }).reset_index()
                
                # Handle Stage Empty
                df_opps['stage'] = df_opps['stage'].fillna('Open')
                
                # Split Stages
                open_opps = df_opps[df_opps['stage'] == 'Open']
                won_opps = df_opps[df_opps['stage'] == 'Closed Won']
                lost_opps = df_opps[df_opps['stage'] == 'Closed Lost']
                
                # Totals
                tot_open = open_opps['cost'].sum()
                tot_won = won_opps['cost'].sum()
                tot_lost = lost_opps['cost'].sum()
                
                k1, k2, k3 = st.columns(3)
                
                def render_card(row):
                    with st.container(border=True):
                        st.markdown(f"**{row['opportunity_name']}**")
                        st.caption(f"{row['company_name']}")
                        st.caption(f"👤 {row['presales_name']}")
                        st.markdown(f"💰 **Rp {format_number(row['cost'])}**")
                        if st.button("View Details", key=f"btn_{row['opportunity_id']}"):
                            st.session_state.selected_kanban_opp_id = row['opportunity_id']
                            st.rerun()

                with k1:
                    st.markdown(f"### 🧊 Open ({len(open_opps)})")
                    st.markdown(f"**Rp {format_number(tot_open)}**")
                    st.divider()
                    for _, r in open_opps.iterrows(): render_card(r)
                
                with k2:
                    st.markdown(f"### ✅ Won ({len(won_opps)})")
                    st.markdown(f"**Rp {format_number(tot_won)}**")
                    st.divider()
                    for _, r in won_opps.iterrows(): render_card(r)
                    
                with k3:
                    st.markdown(f"### ❌ Lost ({len(lost_opps)})")
                    st.markdown(f"**Rp {format_number(tot_lost)}**")
                    st.divider()
                    for _, r in lost_opps.iterrows(): render_card(r)


@st.fragment
def tab3():
    st.header("Interactive Dashboard & Search")
    
    # 1. Ambil semua data (Cached via Backend)
    with st.spinner("Loading dataset..."):
        response = db.get_all_leads_presales() # Direct DB Call
    
    if not response or response.get("status") != 200:
        st.error("Failed to load data.")
    else:
        raw_data = response.get("data", [])
        if not raw_data:
            st.info("No opportunity data available.")
        else:
            # Buat Master DataFrame
            df = pd.DataFrame(raw_data)
            
            # --- PRE-PROCESSING DATA (Agar filter & sort aman) ---
            
            # 1. Konversi Angka (Cost)
            if 'cost' in df.columns:
                df['cost'] = pd.to_numeric(df['cost'], errors='coerce').fillna(0)
            
            # 2. Konversi Tanggal (Prioritas start_date, fallback created_at)
            date_col = 'start_date' if 'start_date' in df.columns else 'created_at'
            if date_col in df.columns:
                df['start_date_dt'] = pd.to_datetime(df[date_col], errors='coerce')
            
            # 3. Handle NULL values agar Multiselect & Sorting tidak error
            # Daftar kolom yang akan dijadikan filter
            filter_cols = [
                'presales_name', 'responsible_name', 'salesgroup_id', 
                'channel', 'distributor_name', 'brand', 'pillar', 
                'solution', 'company_name', 'vertical_industry', 
                'stage', 'opportunity_name'
            ]
            
            for col in filter_cols:
                if col in df.columns:
                    df[col] = df[col].fillna("Unknown").astype(str)

            # =================================================================
            # 🎛️ FILTER PANEL (SLICERS) - LAYOUT ASLI (5-5-3)
            # =================================================================
            with st.container(border=True):
                st.subheader("🔍 Filter Panel (Slicers)")
                
                # Helper untuk mengambil unique values yang sudah di-sort
                def get_opts(col_name):
                    if col_name in df.columns:
                        return sorted(df[col_name].unique().tolist())
                    return []

                # --- BARIS 1: Inputter, PAM, Group, Channel, Distributor ---
                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    sel_inputter = st.multiselect("Inputter", get_opts('presales_name'), placeholder="All Inputters")
                with c2:
                    sel_pam = st.multiselect("Presales Account Manager", get_opts('responsible_name'), placeholder="All PAMs")
                with c3:
                    sel_group = st.multiselect("Sales Group", get_opts('salesgroup_id'), placeholder="All Groups")
                with c4:
                    sel_channel = st.multiselect("Channel", get_opts('channel'), placeholder="All Channels")
                with c5:
                    sel_distributor = st.multiselect("Distributor", get_opts('distributor_name'), placeholder="All Distributors")

                # --- BARIS 2: Brand, Pillar, Solution, Client, Vertical ---
                c6, c7, c8, c9, c10 = st.columns(5)
                with c6:
                    sel_brand = st.multiselect("Brand", get_opts('brand'), placeholder="All Brands")
                with c7:
                    sel_pillar = st.multiselect("Pillar", get_opts('pillar'), placeholder="All Pillars")
                with c8:
                    sel_solution = st.multiselect("Solution", get_opts('solution'), placeholder="All Solutions")
                with c9:
                    sel_client = st.multiselect("Company / Client", get_opts('company_name'), placeholder="All Clients")
                with c10:
                    sel_vertical = st.multiselect("Vertical Industry", get_opts('vertical_industry'), placeholder="All Industries")

                # --- BARIS 3: Stage, Date Range, Opportunity Name ---
                c11, c12, c13 = st.columns([1, 2, 3])
                with c11:
                    sel_stage = st.multiselect("Stage", get_opts('stage'), placeholder="All Stages")
                with c12:
                    # Filter Tanggal
                    min_date = df['start_date_dt'].min().date() if 'start_date_dt' in df.columns and not df['start_date_dt'].isnull().all() else None
                    max_date = df['start_date_dt'].max().date() if 'start_date_dt' in df.columns and not df['start_date_dt'].isnull().all() else None
                    
                    date_range = st.date_input(
                        "Start Date Range",
                        value=(min_date, max_date) if min_date and max_date else None,
                        help="Filter berdasarkan rentang tanggal Start Date"
                    )
                with c13:
                    sel_opportunity = st.multiselect("Opportunity Name", get_opts('opportunity_name'), placeholder="All Opportunities")

            # =================================================================
            # 🔄 LOGIKA FILTERING (ENGINE)
            # =================================================================
            df_filtered = df.copy()

            # Mapping Filter Widget ke Kolom DataFrame
            filters = {
                'presales_name': sel_inputter,
                'responsible_name': sel_pam,
                'salesgroup_id': sel_group,
                'channel': sel_channel,
                'distributor_name': sel_distributor,
                'brand': sel_brand,
                'pillar': sel_pillar,
                'solution': sel_solution,
                'company_name': sel_client,
                'vertical_industry': sel_vertical,
                'stage': sel_stage,
                'opportunity_name': sel_opportunity
            }

            # Terapkan Filter Bertahap
            for col, selection in filters.items():
                if selection and col in df_filtered.columns:
                    df_filtered = df_filtered[df_filtered[col].isin(selection)]
            
            # Filter Tanggal (Hanya jika range lengkap start & end dipilih)
            if isinstance(date_range, tuple) and len(date_range) == 2 and 'start_date_dt' in df_filtered.columns:
                start_d, end_d = date_range
                # Pastikan kolom tidak kosong sebelum compare
                mask = (df_filtered['start_date_dt'].dt.date >= start_d) & (df_filtered['start_date_dt'].dt.date <= end_d)
                df_filtered = df_filtered[mask]

            # =================================================================
            # 📊 KPI CARDS (Summary Metrics)
            # =================================================================
            st.markdown("### Summary")
            
            # Hitung metrik dari data yang SUDAH difilter
            total_opps = len(df_filtered)
            
            # Hitung Opportunity Unik (Berdasarkan ID agar akurat)
            total_unique_opps = df_filtered['opportunity_id'].nunique() if 'opportunity_id' in df_filtered.columns else 0

            # Hitung Customer Unik
            total_unique_customers = df_filtered['company_name'].nunique() if 'company_name' in df_filtered.columns else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Solutions Line", f"{total_opps}")
            m2.metric("Total Unique Opportunities", f"{total_unique_opps}")
            m3.metric("Total Customers", f"{total_unique_customers}") 

            st.markdown("---")

            # =================================================================
            # 📋 DATA TABLE
            # =================================================================
            st.subheader(f"Detailed Data ({total_opps} rows)")
            
            if not df_filtered.empty:
                # Gunakan fungsi cleaning global untuk format tampilan akhir
                st.dataframe(clean_data_for_display(df_filtered), use_container_width=True)
            else:
                st.warning("Tidak ada data yang cocok dengan kombinasi filter di atas.")

@st.fragment
def tab4():
    st.header("Update Opportunity")
    
    # Pilihan Mode Update
    update_mode = st.radio(
        "Select Update Type:", 
        ["🛠️ Update Solution Details (Cost/Notes)", "📈 Update Stage (Business Progression)"],
        horizontal=True
    )
    
    st.markdown("---")

    # ==========================================================================
    # MODE 1: UPDATE SOLUTION DETAILS (Cost/Notes)
    # ==========================================================================
    if update_mode == "🛠️ Update Solution Details (Cost/Notes)":
        st.subheader("Update Specific Solution Line")
        uid_in = st.text_input("Enter UID to search", key="uid_update_sol", help="Paste UID unik dari item solusi di sini.")
        
        if 'lead_sol_update' not in st.session_state: st.session_state.lead_sol_update = None

        if st.button("Get Solution Data"):
            res = db.get_lead_by_uid(uid_in)
            if res['status'] == 200:
                st.session_state.lead_sol_update = res['data'][0]
            else:
                st.error("UID Not Found. Please check the UID again.")
                st.session_state.lead_sol_update = None

        if st.session_state.lead_sol_update:
            lead = st.session_state.lead_sol_update
            
            # --- [BARU] TAMPILAN DETAIL ITEM ---
            with st.container(border=True):
                st.markdown(f"#### 📋 Item Details: `{lead.get('product_id')}`")
                
                # Baris 1: Info Opportunity
                st.info(f"**Opportunity:** {lead.get('opportunity_name')} | **Client:** {lead.get('company_name')}")
                
                # Baris 2: Detail Teknis (Grid Layout)
                d1, d2, d3, d4 = st.columns(4)
                d1.markdown(f"**Pillar:**\n{lead.get('pillar')}")
                d2.markdown(f"**Solution:**\n{lead.get('solution')}")
                d3.markdown(f"**Service:**\n{lead.get('service')}")
                d4.markdown(f"**Brand:**\n{lead.get('brand')}")
                
                st.divider()
                
                # Baris 3: Info Sales & Distributor
                d5, d6, d7, d8 = st.columns(4)
                d5.markdown(f"**Distributor:**\n{lead.get('distributor_name')}")
                d6.markdown(f"**Presales Account Manager:**\n{lead.get('responsible_name')}")
                d7.markdown(f"**Sales:**\n{lead.get('sales_name')}")
                d8.markdown(f"**Inputter:**\n{lead.get('presales_name')}")
            # -----------------------------------
            
            st.markdown("### ✏️ Edit Values")
            
            c1, c2 = st.columns(2)
            with c1:
                new_cost = st.number_input(
                    "Cost (IDR)", 
                    value=float(lead.get('cost') or 0), 
                    step=1000000.0, 
                    key="num_upd_cost",
                    help="Update harga modal/cost di sini."
                )
                st.caption(f"Reads: Rp {format_number(new_cost)}")
            with c2:
                new_notes = st.text_area(
                    "Technical/Item Notes", 
                    value=lead.get('notes', ''),
                    help="Update catatan teknis spesifik untuk item ini."
                )
            
            if st.button("Save Solution Update"):
                res = db.update_lead({
                    "uid": lead['uid'], 
                    "cost": new_cost, 
                    "notes": new_notes, 
                    "user": lead['presales_name']
                })
                if res['status'] == 200:
                    st.success("✅ Item Updated Successfully!")
                    st.session_state.lead_sol_update = None
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(res['message'])

    # ==========================================================================
    # MODE 2: UPDATE STAGE (BUSINESS PROGRESSION) - (LOGIKA FINAL)
    # ==========================================================================
    else:
        st.subheader("Update Opportunity Stage & Context")
        st.info("Update stage untuk seluruh item dalam Opportunity ini.")
        
        opp_id_in = st.text_input("Enter Opportunity ID (e.g., ENT1Q30005)", key="oid_update_stg")
        
        if 'opp_stage_data' not in st.session_state: st.session_state.opp_stage_data = None

        if st.button("Get Opportunity Status"):
            res = db.get_opportunity_summary(opp_id_in)
            if res['status'] == 200:
                st.session_state.opp_stage_data = res['data']
            else:
                st.error(res['message'])
                st.session_state.opp_stage_data = None

        if st.session_state.opp_stage_data:
            opp_data = st.session_state.opp_stage_data
            
            # Info Card
            with st.container(border=True):
                c_info1, c_info2 = st.columns(2)
                c_info1.write(f"**Opportunity:** {opp_data['opportunity_name']}")
                c_info1.write(f"**Client:** {opp_data['company_name']}")
                c_info2.write(f"**Current Stage:** {opp_data['stage']}")
                if opp_data.get('closing_reason'):
                    c_info2.info(f"**Last Reason:** {opp_data.get('closing_reason')}")

            st.markdown("### 📝 Update Status Details")
            
            c_form1, c_form2 = st.columns(2)
            
            with c_form1:
                # 1. Logic Dropdown Stage (Inject Closed Won/Lost)
                stage_raw = get_master('getPresalesStages')
                stage_opts = [s['Stage'] for s in stage_raw]
                
                # Manual Injection: Paksa munculkan opsi Closed
                for s in ["Closed Won", "Closed Lost"]:
                    if s not in stage_opts:
                        stage_opts.append(s)
                stage_opts = sorted(stage_opts)

                # Set Default Index
                try: curr_idx = stage_opts.index(opp_data['stage'])
                except: curr_idx = 0    
                
                new_stage_val = st.selectbox("New Stage", stage_opts, index=curr_idx)

            with c_form2:
                # 2. Tanggal Manual
                manual_date = st.date_input("Stage Changed Date", value="today")

            # --- LOGIC CLOSING CATEGORY (WON vs LOST) ---
            closing_reason_val = None 
            
            # Jika user memilih stage Closed Won atau Closed Lost
            if new_stage_val in ["Closed Won", "Closed Lost"]:
                st.markdown("---")
                
                if new_stage_val == "Closed Won":
                    st.success(f"🎉 Closing Deal: **{new_stage_val}**")
                    reason_opts = [
                        "Commercial / Price Strategy",
                        "Technical Solution Fit",
                        "Relationship / Trust",
                        "Delivery / Timeline",
                        "After-Sales Service",
                        "Other Winning Factors"
                    ]
                    label_text = "Winning Factor (Why did we win?)"
                else:
                    st.error(f"💀 Closing Deal: **{new_stage_val}**")
                    reason_opts = [
                        "Price / Budget Constraint",
                        "Competitor - Technical",
                        "Competitor - Price",
                        "Feature Gap / Spec Mismatch",
                        "Late Proposal Submission",
                        "Project Cancelled",
                        "Lost to Incumbent",
                        "No Decision"
                    ]
                    label_text = "Loss Reason (Why did we lose?)"

                # Dropdown Kategori (Full Width)
                closing_reason_val = st.selectbox(label_text, reason_opts, key="close_reason_cat")
                
                # Text Area untuk Detail
                new_stage_notes = st.text_area(
                    "Closing Remarks / Post-Mortem", 
                    placeholder="Ceritakan detail, kendala teknis, atau feedback user (tanpa perlu menyebut detail kompetitor jika tidak tahu)...",
                    height=150
                )

            else:
                # Jika Stage Masih Berjalan (Open, Proposal, dll)
                new_stage_notes = st.text_area(
                    "Stage Context / Reason", 
                    placeholder="Example: Client approved BoQ on meeting yesterday...",
                    height=100
                )

            # --- SUBMIT BUTTON ---
            if st.button("🚀 Update Stage Progression", type="primary"):
                updater_name = "Presales User" 
                
                with st.spinner("Updating Pipeline..."):
                    res = db.update_opportunity_stage_bulk_enhanced(
                        opp_id_in, 
                        new_stage_val, 
                        new_stage_notes, 
                        manual_date, 
                        updater_name,
                        closing_reason_val
                    )
                    
                    if res['status'] == 200:
                        st.success(f"✅ Success! {res['message']}")
                        st.session_state.opp_stage_data = None # Reset
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"Failed: {res['message']}")
                        
@st.fragment
def tab5():
    st.header("Edit Data Entry (Error Correction)")
    st.warning("Use this page to correct input errors. Please be aware that changing the Sales Group will generate a new UID.")
    
    # State Management untuk Tab Ini
    if 'lead_to_edit' not in st.session_state:
        st.session_state.lead_to_edit = None
    if 'edit_submission_message' not in st.session_state:
        st.session_state.edit_submission_message = None
    if 'edit_new_uid' not in st.session_state:
        st.session_state.edit_new_uid = None

    # --- BAGIAN 1: CARI DATA ---
    uid_to_find = st.text_input("Enter the UID of the opportunity to be corrected:", key="uid_finder_edit")
    
    if st.button("Find Data to Edit"):
        st.session_state.lead_to_edit = None
        st.session_state.edit_submission_message = None
        st.session_state.edit_new_uid = None
        
        if uid_to_find:
            with st.spinner("Fetching data..."):
                # Panggil Backend
                response = db.get_single_lead({"uid": uid_to_find})
                
                if response and response.get("status") == 200 and response.get("data"):
                    st.session_state.lead_to_edit = response.get("data")[0]
                    st.success("Data found. Please edit the form below.")
                else:
                    st.error("UID not found. Please double-check the UID and try again.")
        else:
            st.warning("Please enter a UID.")
    
    # Tampilkan Pesan Sukses Update (jika ada)
    if st.session_state.edit_submission_message:
        st.success(st.session_state.edit_submission_message)
        if st.session_state.edit_new_uid:
            st.info(f"IMPORTANT: The UID has been updated. The new UID is: {st.session_state.edit_new_uid}")
        # Reset pesan agar tidak muncul terus
        st.session_state.edit_submission_message = None
        st.session_state.edit_new_uid = None

    # --- BAGIAN 2: FORM EDIT ---
    if st.session_state.lead_to_edit:
        lead = st.session_state.lead_to_edit
        st.markdown("---")
        st.subheader(f"Step 2: Edit Data for '{lead.get('opportunity_name', '')}'")

        # Helper untuk mencari index default dropdown
        def get_index(data_list, value, key=None):
            try:
                if key: 
                    # Jika list of dicts
                    vals = [item.get(key) for item in data_list]
                    return vals.index(value)
                else: 
                    # Jika list of strings
                    return data_list.index(value)
            except (ValueError, TypeError, IndexError): 
                return 0
        
        # Load Master Data untuk Dropdown
        all_sales_groups = get_sales_groups()
        all_responsibles = get_master('getResponsibles')
        all_pillars = get_pillars() # List of strings
        all_brands = get_master('getBrands') # List of dicts
        all_companies_data = get_master('getCompanies')
        all_distributors = get_master('getDistributors')

        # Layout 2 Kolom
        col1, col2 = st.columns(2)
        
        with col1:
            # 1. Sales Group
            # Ambil index dari data lama
            current_sg = lead.get('salesgroup_id')
            edited_sales_group = st.selectbox(
                "Sales Group", 
                all_sales_groups, 
                index=get_index(all_sales_groups, current_sg), 
                key="edit_sales_group"
            )
            
            # 2. Sales Name (Filter berdasarkan Sales Group yang dipilih di atas)
            sales_name_options = get_sales_name_by_sales_group(st.session_state.edit_sales_group)
            edited_sales_name = st.selectbox(
                "Sales Name", 
                sales_name_options, 
                index=get_index(sales_name_options, lead.get('sales_name')), 
                key="edit_sales_name"
            )

            # 3. PAM
            edited_responsible = st.selectbox(
                "Presales Account Manager", 
                all_responsibles, 
                index=get_index(all_responsibles, lead.get('responsible_name'), 'Responsible'), 
                format_func=lambda x: x.get("Responsible", ""), 
                key="edit_responsible"
            )
        
            # 4. Pillar
            edited_pillar = st.selectbox(
                "Pillar", 
                all_pillars, 
                index=get_index(all_pillars, lead.get('pillar')), 
                key="edit_pillar"
            )
            
            # 5. Solution (Dependent on Pillar)
            solution_options = get_solutions(st.session_state.edit_pillar)
            edited_solution = st.selectbox(
                "Solution", 
                solution_options, 
                index=get_index(solution_options, lead.get('solution')), 
                key="edit_solution"
            )

        with col2:
            # 6. Company
            edited_company = st.selectbox(
                "Company", 
                all_companies_data, 
                index=get_index(all_companies_data, lead.get('company_name'), 'Company'), 
                format_func=lambda x: x.get("Company", ""), 
                key="edit_company"
            )
            
            # 7. Vertical (Auto-filled & Disabled)
            derived_vertical_industry = ""
            if st.session_state.edit_company:
                derived_vertical_industry = st.session_state.edit_company.get('Vertical Industry', '')
                
            st.text_input("Vertical Industry", value=derived_vertical_industry, key="edit_vertical", disabled=True)
            
            # 8. Service (Dependent on Solution)
            service_options = get_services(st.session_state.edit_solution)
            edited_service = st.selectbox(
                "Service", 
                service_options, 
                index=get_index(service_options, lead.get('service')), 
                key="edit_service"
            )
            
            # 9. Brand
            edited_brand = st.selectbox(
                "Brand", 
                all_brands, 
                index=get_index(all_brands, lead.get('brand'), 'Brand'), 
                format_func=lambda x: x.get("Brand", ""), 
                key="edit_brand"
            )
            
            # 10. Distributor Logic
            current_dist = lead.get('distributor_name', 'Not via distributor')
            is_via_distributor_default = 0 if current_dist != "Not via distributor" else 1
            
            is_via_distributor_choice = st.radio(
                "Via Distributor?", 
                ("Yes", "No"), 
                index=is_via_distributor_default, 
                key="edit_is_via_distributor", 
                horizontal=True
            )
            
            if is_via_distributor_choice == "Yes":
                edited_distributor = st.selectbox(
                    "Distributor", 
                    all_distributors, 
                    index=get_index(all_distributors, current_dist, 'Distributor'), 
                    format_func=lambda x: x.get("Distributor", ""), 
                    key="edit_distributor_select"
                )
            else:
                edited_distributor = "Not via distributor"

        # --- BAGIAN 3: SUBMIT ---
        if st.button("Save Changes", type="primary"):
            # Kumpulkan semua data yang diubah
            # Handle object selects (Distributor/Company/Brand/PAM) -> ambil valuenya
            pam_val = edited_responsible.get('Responsible') if isinstance(edited_responsible, dict) else edited_responsible
            brand_val = edited_brand.get('Brand') if isinstance(edited_brand, dict) else edited_brand
            comp_val = edited_company.get('Company') if isinstance(edited_company, dict) else edited_company
            dist_val = edited_distributor.get('Distributor') if isinstance(edited_distributor, dict) else edited_distributor

            update_payload = {
                "uid": lead.get('uid'),
                "user": lead.get('presales_name'), # User pengupdate dianggap presales asli
                "salesgroup_id": st.session_state.edit_sales_group,
                "sales_name": st.session_state.edit_sales_name,
                "responsible_name": pam_val,
                "pillar": st.session_state.edit_pillar,
                "solution": st.session_state.edit_solution,
                "service": st.session_state.edit_service,
                "brand": brand_val,
                "company_name": comp_val,
                "vertical_industry": st.session_state.edit_vertical,
                "distributor_name": dist_val
            }
            
            with st.spinner(f"Updating opportunity..."):
                # Panggil Backend
                update_response = db.update_full_opportunity(update_payload)
                
                if update_response and update_response.get("status") == 200:
                    st.session_state.edit_submission_message = update_response.get("message")
                    
                    # Cek apakah UID berubah
                    new_uid = update_response.get("data", {}).get("uid")
                    if new_uid and new_uid != uid_to_find:
                        st.session_state.edit_new_uid = new_uid
                    
                    st.session_state.lead_to_edit = None # Reset form agar bersih
                    st.rerun()
                else:
                    error_message = update_response.get("message", "Failed to update.") if update_response else "Failed to update."
                    st.error(error_message)
   
@st.fragment
def tab6():
    st.header("Activity Log / Audit Trail")
    st.info("This log records all creations and changes made to the opportunity data.")

    # Tombol Refresh Cache
    if st.button("Refresh Log"):
        st.cache_data.clear() 
    
    with st.spinner("Fetching activity log..."):
        # Panggil Backend (bukan API)
        log_data = get_master('getActivityLog') 
        
        if log_data:
            df_log = pd.DataFrame(log_data)
            
            # --- 1. LOGIKA DROPDOWN FILTER ---
            
            # Cek apakah kolom OpportunityName ada
            if 'OpportunityName' in df_log.columns and not df_log.empty:
                
                # Ambil daftar unik nama opportunity, handle nilai kosong
                # fillna("Unknown") penting agar sorted tidak error
                unique_ops = sorted(df_log['OpportunityName'].fillna("Unknown").astype(str).unique().tolist())
                unique_ops.insert(0, "All Opportunities")

                # Tampilkan Widget
                selected_opportunity = st.selectbox(
                    "Select an Opportunity Name to track",
                    options=unique_ops,
                    key="log_opportunity_filter"
                )

                # Filter DataFrame
                if selected_opportunity != "All Opportunities":
                    df_to_display = df_log[df_log['OpportunityName'] == selected_opportunity]
                else:
                    df_to_display = df_log
            else:
                df_to_display = df_log

            # --- 2. FORMATTING TAMPILAN ---
            
            if not df_to_display.empty:
                # Copy agar tidak memodifikasi data asli cache
                df_display = df_to_display.copy()

                # A. Format Waktu (Timestamp) dengan Timezone Safe
                if 'Timestamp' in df_display.columns:
                    # Konversi ke datetime object
                    df_display['Timestamp'] = pd.to_datetime(df_display['Timestamp'], errors='coerce')
                    
                    try:
                        # Coba convert langsung (jika data DB sudah ada TZ info)
                        df_display['Timestamp'] = df_display['Timestamp'].dt.tz_convert('Asia/Jakarta')
                    except TypeError:
                        # Jika error (tz-naive), anggap UTC lalu convert ke Jakarta
                        df_display['Timestamp'] = df_display['Timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
                    
                    # Format String Akhir
                    df_display['Timestamp'] = df_display['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

                # B. Ubah tipe data OldValue/NewValue ke string agar aman ditampilkan
                for col in ['OldValue', 'NewValue']:
                    if col in df_display.columns:
                        df_display[col] = df_display[col].astype(str)

                # Tampilkan
                st.write(f"Found {len(df_display)} log entries for the selected filter.")
                st.dataframe(df_display, use_container_width=True)
            else:
                st.info("No log data found for the selected Opportunity Name.")

        else:
            st.warning("No activity log has been recorded yet.")
