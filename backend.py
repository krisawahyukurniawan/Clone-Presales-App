import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. KONEKSI DATABASE
# Pastikan Anda sudah mengatur .streamlit/secrets.toml
conn = st.connection("postgresql", type="sql")

# 2. EMAIL UTILITIES
def send_email_notification(recipient_email, subject, body_html):
    # GANTI DENGAN KREDENSIAL ASLI ANDA (Sama seperti di main.py sebelumnya)
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "krisawahyukurniawan@gmail.com" 
    SENDER_PASSWORD = "wlto qllo miat hljv" # App Password

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return {"status": 200, "message": "Email sent successfully"}
    except Exception as e:
        return {"status": 500, "message": f"Email failed: {str(e)}"}

# 3. MASTER DATA (READ)
def get_master_presales(action):
    # Mapping query persis seperti main.py lama agar frontend tidak error
    queries = {
        "getPresales": "SELECT presales_name as \"PresalesName\", email as \"Email\" FROM presales ORDER BY presales_name",
        "getPAMMapping": "SELECT inputter_name as \"Inputter\", pam_name as \"PAM\" FROM mapping_pam",
        "getBrands": "SELECT brand_name as \"Brand\", channel as \"Channel\" FROM brands WHERE brand_name IS NOT NULL ORDER BY brand_name, channel",
        "getPillars": "SELECT DISTINCT pillar_name as \"Pillar\", solution_name as \"Solution\", service_name as \"Service\" FROM master_pillars ORDER BY pillar_name, solution_name, service_name",
        "getPresalesStages": "SELECT stage_name as \"Stage\" FROM stage_pipeline WHERE stage_type = 'PRESALES' ORDER BY stage_name",
        "getSalesGroups": "SELECT DISTINCT sales_group as \"SalesGroup\" FROM sales_names ORDER BY sales_group",
        "getSalesNames": "SELECT sales_group as \"SalesGroup\", sales_name as \"SalesName\" FROM sales_names ORDER BY sales_name",
        "getResponsibles": "SELECT DISTINCT responsible_name as \"Responsible\" FROM responsible WHERE responsible_name IS NOT NULL",
        "getCompanies": "SELECT DISTINCT company_name as \"Company\", vertical_industry as \"Vertical Industry\" FROM companies ORDER BY company_name",
        "getDistributors": "SELECT DISTINCT distributor_name as \"Distributor\" FROM distributors WHERE distributor_name IS NOT NULL ORDER BY distributor_name",
        "getOpportunities": "SELECT DISTINCT opportunity_name as \"Desc\" FROM opportunities ORDER BY opportunity_name",
        "getActivityLog": "SELECT timestamp as \"Timestamp\", opportunity_name as \"OpportunityName\", user_name as \"User\", action as \"Action\", field as \"Field\", old_value as \"OldValue\", new_value as \"NewValue\" FROM activity_logs ORDER BY timestamp DESC LIMIT 1000"
    }
    
    if action in queries:
        try:
            df = conn.query(queries[action], ttl=60)
            return df.to_dict('records')
        except Exception as e:
            st.error(f"DB Error: {e}")
            return []
    return []

def get_all_leads_presales():
    query = "SELECT * FROM opportunities ORDER BY created_at DESC"
    df = conn.query(query, ttl=0) # TTL 0 agar selalu fresh
    return {"status": 200, "data": df.to_dict('records')}

def get_single_lead(search_params):
    # Search by UID
    if "uid" in search_params:
        uid = search_params["uid"]
        query = "SELECT * FROM opportunities WHERE uid = :uid"
        df = conn.query(query, params={"uid": uid}, ttl=0)
        if not df.empty:
            return {"status": 200, "data": df.to_dict('records')}
    return {"status": 404, "message": "Not Found"}

# 4. WRITE OPERATIONS (INPUT & UPDATE)

def add_multi_line_opportunity(parent_data, product_lines):
    try:
        with conn.session as session:
            # A. Logic Rows ID (Q3xxxx)
            chk_q = text("SELECT rows_id FROM description WHERE description = :desc LIMIT 1")
            res_desc = session.execute(chk_q, {"desc": parent_data['opportunity_name']}).mappings().first()
            
            if res_desc:
                current_rows_id = res_desc['rows_id']
            else:
                # Generate New Q3 ID
                max_q = text("SELECT MAX(rows_id) FROM description")
                max_val = session.execute(max_q).scalar()
                
                prefix = "Q3"
                if max_val:
                    try:
                        num_part = int(max_val.replace(prefix, ""))
                        new_num = num_part + 1
                        current_rows_id = f"{prefix}{new_num:04d}"
                    except:
                        current_rows_id = f"{prefix}{int(time.time())}"
                else:
                    current_rows_id = "Q30000"
                
                # Insert ke tabel description
                ins_desc = text("INSERT INTO description (rows_id, description) VALUES (:rid, :desc)")
                session.execute(ins_desc, {"rid": current_rows_id, "desc": parent_data['opportunity_name']})
            
            # B. Generate Opp ID
            safe_group = parent_data.get('salesgroup_id', 'GEN')
            new_opp_id = f"{safe_group}{current_rows_id}"
            
            timestamp_now = int(time.time())
            created_at = datetime.now()
            created_uids = []
            
            # C. Loop Insert Lines
            for i, line in enumerate(product_lines):
                # Cari IDs
                cat_q = text("SELECT pillar_id, solution_id, service_id FROM master_pillars WHERE pillar_name=:p AND solution_name=:s AND service_name=:svc LIMIT 1")
                cat = session.execute(cat_q, {"p": line['pillar'], "s": line['solution'], "svc": line['service']}).mappings().first()
                
                br_q = text("SELECT brand_code FROM brands WHERE brand_name=:b LIMIT 1")
                br = session.execute(br_q, {"b": line.get('brand')}).mappings().first()
                
                pid = cat['pillar_id'] if cat and cat['pillar_id'] else "GEN"
                sol = str(cat['solution_id']) if cat and cat['solution_id'] else "0"
                svc = str(cat['service_id']) if cat and cat['service_id'] else "S0"
                br_code = br['brand_code'] if br and br['brand_code'] else "GEN"
                
                product_id_code = f"{pid}{sol}{svc}{br_code}".replace(" ", "").upper()
                uid = f"{new_opp_id}-{product_id_code}-{timestamp_now}{i}"
                
                # Insert Opportunity
                ins_opp = text("""
                    INSERT INTO opportunities (
                        uid, opportunity_id, product_id, presales_name, salesgroup_id, sales_name, 
                        responsible_name, opportunity_name, start_date, company_name, 
                        vertical_industry, pillar, solution, service, brand, channel, 
                        distributor_name, cost, notes, stage, created_at, updated_at
                    ) VALUES (
                        :uid, :oid, :pid, :pname, :sgid, :sname, :pam, :oname, :sdate, :cname,
                        :vi, :plr, :sol, :svc, :br, :ch, :dist, :cost, :note, 'Open', :now, :now
                    )
                """)
                
                session.execute(text("""
                    INSERT INTO opportunities (
                        uid, opportunity_id, product_id, presales_name, salesgroup_id, sales_name, 
                        responsible_name, opportunity_name, start_date, company_name, 
                        vertical_industry, pillar, solution, service, brand, channel, 
                        distributor_name, cost, notes, stage, stage_notes, created_at, updated_at
                    ) VALUES (
                        :uid, :oid, :pid, :pname, :sgid, :sname, 
                        :pam, :oname, :sdate, :cname, 
                        :vi, :plr, :sol, :svc, :br, :ch, 
                        :dist, :cost, :note, :stage_val, :s_note, :now, :now
                    )
                """), {
                    "uid": uid, 
                    "oid": new_opp_id, 
                    "pid": product_id_code,
                    "pname": parent_data['presales_name'], 
                    "sgid": parent_data['salesgroup_id'], 
                    "sname": parent_data['sales_name'],
                    "pam": parent_data['responsible_name'], 
                    "oname": parent_data['opportunity_name'], 
                    "sdate": parent_data['start_date'],
                    "cname": parent_data['company_name'], 
                    "vi": parent_data['vertical_industry'],
                    "plr": line['pillar'], 
                    "sol": line['solution'], 
                    "svc": line['service'], 
                    "br": line.get('brand'),
                    "ch": line.get('channel'), 
                    "dist": line.get('distributor_name'), 
                    "cost": line.get('cost', 0),
                    "note": line.get('notes', ''), 
                    "stage_val": parent_data.get('stage', 'Open'),
                    
                    # --- TAMBAHAN BARU ---
                    "s_note": parent_data.get('stage_notes', ''), 
                    
                    "now": created_at
                })
                
                created_uids.append({"uid": uid, "opportunity_id": new_opp_id})
            
            # Log
            log_q = text("INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, new_value) VALUES (:ts, :oname, :user, 'CREATE', 'New Opportunity', :val)")
            session.execute(log_q, {
                "ts": created_at, "oname": parent_data['opportunity_name'], 
                "user": parent_data['presales_name'], "val": f"Created {len(product_lines)} lines. ID: {new_opp_id}"
            })
            
            session.commit()
            return {"status": 200, "message": "Opportunity successfully added!", "data": created_uids}
            
    except Exception as e:
        return {"status": 500, "message": f"Database Error: {str(e)}"}

def update_lead(lead_data):
    # Simple update (Cost/Notes)
    uid = lead_data.get('uid')
    cost = lead_data.get('cost')
    notes = lead_data.get('notes')
    user = lead_data.get('user')
    
    try:
        with conn.session as session:
            old = session.execute(text("SELECT cost, notes FROM opportunities WHERE uid=:u"), {"u": uid}).mappings().first()
            
            upd = text("UPDATE opportunities SET cost=:c, notes=:n, updated_at=NOW() WHERE uid=:u")
            session.execute(upd, {"c": cost, "n": notes, "u": uid})
            
            # Log Cost Change
            if old and float(old['cost'] or 0) != float(cost):
                log = text("INSERT INTO activity_logs (timestamp, user_name, action, field, old_value, new_value) VALUES (NOW(), :u, 'UPDATE', 'Cost', :ov, :nv)")
                session.execute(log, {"u": user, "ov": str(old['cost']), "nv": str(cost)})

            # Log Notes Change
            if old and str(old['notes'] or "") != str(notes):
                log = text("INSERT INTO activity_logs (timestamp, user_name, action, field, old_value, new_value) VALUES (NOW(), :u, 'UPDATE', 'Notes', :ov, :nv)")
                session.execute(log, {"u": user, "ov": str(old['notes']), "nv": str(notes)})
                
            session.commit()
            return {"status": 200, "message": "Updated successfully"}
    except Exception as e:
        return {"status": 500, "message": str(e)}

def update_full_opportunity(payload):
    # Full Edit with Re-ID logic
    uid = payload.get('uid')
    try:
        with conn.session as session:
            old_data = session.execute(text("SELECT * FROM opportunities WHERE uid=:uid"), {"uid": uid}).mappings().first()
            if not old_data: return {"status": 404, "message": "UID not found"}
            
            # 1. Re-calculate ID based on potentially new Sales Group
            rows_id_part = ""
            desc_res = session.execute(text("SELECT rows_id FROM description WHERE description=:d"), {"d": old_data['opportunity_name']}).mappings().first()
            if desc_res:
                rows_id_part = desc_res['rows_id']
            else:
                match = re.search(r'(Q3\d+)', old_data['opportunity_id'])
                rows_id_part = match.group(1) if match else old_data['opportunity_id'][-6:]
            
            new_opp_id = f"{payload['salesgroup_id']}{rows_id_part}"
            
            # 2. Update UID (preserve timestamp part)
            parts = old_data['uid'].split('-')
            ts_part = parts[-1] if len(parts) >=3 else str(int(time.time()))
            new_uid = f"{new_opp_id}-{old_data['product_id']}-{ts_part}"
            
            # 3. Execute Update
            upd_q = text("""
                UPDATE opportunities SET
                    uid=:nuid, opportunity_id=:noid, salesgroup_id=:sg, sales_name=:sn,
                    responsible_name=:pam, pillar=:p, solution=:s, service=:svc,
                    brand=:b, company_name=:cn, vertical_industry=:vi, distributor_name=:dn,
                    updated_at=NOW()
                WHERE uid=:ouid
            """)
            session.execute(upd_q, {
                "nuid": new_uid, "noid": new_opp_id, "sg": payload['salesgroup_id'],
                "sn": payload['sales_name'], "pam": payload['responsible_name'],
                "p": payload['pillar'], "s": payload['solution'], "svc": payload['service'],
                "b": payload['brand'], "cn": payload['company_name'],
                "vi": payload['vertical_industry'], "dn": payload['distributor_name'],
                "ouid": uid
            })
            
            session.commit()
            return {"status": 200, "message": "Full Data Updated!", "data": {"uid": new_uid}}
    except Exception as e:
        return {"status": 500, "message": str(e)}
    
def update_opportunity_stage_bulk(opp_id, new_stage, stage_notes, changed_date, user):
    """
    Mengupdate Stage, Notes, dan Tanggal Perubahan secara manual.
    """
    try:
        with conn.session as session:
            # 1. Ambil stage lama untuk log
            old_res = session.execute(
                text("SELECT stage FROM opportunities WHERE opportunity_id=:oid LIMIT 1"), 
                {"oid": opp_id}
            ).mappings().first()
            old_stage = old_res['stage'] if old_res else "Unknown"

            # 2. Update dengan Tanggal Manual (:s_date)
            query = text("""
                UPDATE opportunities 
                SET stage = :stg, 
                    stage_notes = :note, 
                    stage_changed_date = :s_date, 
                    updated_at = NOW() 
                WHERE opportunity_id = :oid
            """)
            
            session.execute(query, {
                "stg": new_stage, 
                "note": stage_notes, 
                "s_date": changed_date,  # <--- DATA DARI INPUT USER
                "oid": opp_id
            })
            
            # 3. Log Activity
            if old_stage != new_stage:
                log_msg = f"{old_stage} -> {new_stage} | Date: {changed_date} | Note: {stage_notes}"
                session.execute(text("""
                    INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, new_value) 
                    VALUES (NOW(), :oid, :usr, 'UPDATE', 'Stage Progression', :val)
                """), {"oid": opp_id, "usr": user, "val": log_msg})
            
            session.commit()
            return {"status": 200, "message": f"Stage updated to '{new_stage}' on {changed_date}"}
            
    except Exception as e:
        return {"status": 500, "message": str(e)}

def get_opportunity_summary(opp_id):
    """Mengambil ringkasan opportunity berdasarkan ID untuk preview."""
    try:
        # HAPUS 'text()' dan gunakan string biasa (f-string atau string biasa)
        # conn.query lebih suka string murni.
        query_str = """
            SELECT opportunity_name, company_name, stage, stage_notes, COUNT(uid) as total_items 
            FROM opportunities 
            WHERE opportunity_id = :oid 
            GROUP BY opportunity_name, company_name, stage, stage_notes
        """
        
        # Jalankan query dengan string biasa
        df = conn.query(query_str, params={"oid": opp_id}, ttl=0)
        
        if not df.empty:
            return {"status": 200, "data": df.iloc[0].to_dict()}
        else:
            return {"status": 404, "message": "Opportunity ID not found"}
    except Exception as e:
        return {"status": 500, "message": str(e)}
    
def get_lead_by_uid(uid):
    """
    Mengambil data spesifik berdasarkan UID string.
    Berfungsi sebagai wrapper atau direct query.
    """
    # Pastikan query ini sesuai dengan tabel Anda
    query = "SELECT * FROM opportunities WHERE uid = :uid"
    
    # Jalankan query
    df = conn.query(query, params={"uid": uid}, ttl=0)
    
    if not df.empty:
        # Pre-processing datetime objects to string agar JSON serializable (opsional tapi aman)
        data = df.to_dict('records')
        return {"status": 200, "data": data}
    else:
        return {"status": 404, "message": "UID Not Found"}
    
# ==============================================================================
# SECTION 4: CPS OPPORTUNITY LOGIC (NEW TAB 7)
# ==============================================================================

def generate_cps_id(sales_group_id):
    """
    Generate ID dengan format: CPS-{SalesGroup}{Sequence 4 digit}
    Contoh: CPS-ENT10005
    """
    try:
        with conn.session as session:
            # Cari ID terakhir di tabel cps_opportunities
            # Kita ambil angka 4 digit terakhir dari kolom cps_id
            # Asumsi format selalu konsisten CPS-XXX0000
            query = text("SELECT cps_id FROM cps_opportunities ORDER BY created_at DESC LIMIT 1")
            result = session.execute(query).fetchone()
            
            new_sequence = 1
            if result and result[0]:
                last_id = result[0]
                # Ambil 4 karakter terakhir dan ubah ke integer
                try:
                    last_seq = int(last_id[-4:])
                    new_sequence = last_seq + 1
                except:
                    new_sequence = 1
            
            # Format: CPS-SALESGROUP0001
            # Menggunakan zfill(4) untuk padding 0001
            return f"CPS-{sales_group_id}{str(new_sequence).zfill(4)}"
            
    except Exception as e:
        # Fallback jika error, gunakan timestamp agar tidak duplicate
        return f"CPS-{sales_group_id}{int(time.time())}"

def add_cps_opportunity(parent_data, cps_lines):
    """
    Menyimpan data CPS Opportunity dengan Multi-Configuration support.
    Menginsert banyak baris dengan satu CPS ID yang sama.
    """
    try:
        # 1. Generate CPS ID (Satu ID untuk satu batch submission)
        cps_id = generate_cps_id(parent_data['salesgroup_id'])
        
        # Mapping Dictionaries (Dipakai berulang dalam loop)
        ms_map = {"Easy Access": "MS1", "Easy Guard": "MS2", "Easy Connect": "MS3"}
        so_map = {"No Service Offering": "S1", "Full Stack": "S2", "WiFi Only": "S3"}
        p_map = {"Launch": "P1", "Growth": "P2", "Accelerate": "P3"}
        sla_map = {"Core": "SLA1", "Pro": "SLA2", "Elite": "SLA3"}
        se_map = {"Internal": "SE1", "Subcont": "SE2"}
        
        timestamp_now = int(time.time())
        created_at = datetime.now() # Gunakan satu waktu yang sama
        
        with conn.session as session:
            
            # LOOPING SETIAP CONFIGURATION LINE
            for i, line in enumerate(cps_lines):
                # A. Generate UID Unik per Baris
                uid = f"{cps_id}-{timestamp_now}-{i}"
                
                # B. Generate Product ID per Baris
                ms_code = ms_map.get(line['managed_service'], "MS0")
                so_code = so_map.get(line['service_offering'], "S1") 
                p_code = p_map.get(line['package'], "P0")
                sla_code = sla_map.get(line['sla_level'], "SLA0")
                se_code = se_map.get(line['service_execution'], "SE0")
                
                cps_product_id = f"{ms_code}-{so_code}-{p_code}-{sla_code}-{se_code}"
                
                # C. Query Insert
                query = text("""
                    INSERT INTO cps_opportunities (
                        uid, cps_id, cps_product_id,
                        managed_service, service_offering, package, sla_level, service_execution,
                        presales_name, salesgroup_id, sales_name, responsible_name,
                        company_name, vertical_industry, stage,
                        opportunity_name, start_date,
                        cost, notes, created_at, updated_at
                    ) VALUES (
                        :uid, :cps_id, :prod_id,
                        :ms, :so, :pkg, :sla, :se,
                        :pname, :sgid, :sname, :pam,
                        :comp, :vert, :stg,
                        :oname, :sdate,
                        :cost, :note, :now, :now
                    )
                """)
                
                session.execute(query, {
                    "uid": uid,
                    "cps_id": cps_id,
                    "prod_id": cps_product_id,
                    # Data dari Line
                    "ms": line['managed_service'],
                    "so": line['service_offering'],
                    "pkg": line['package'],
                    "sla": line['sla_level'],
                    "se": line['service_execution'],
                    "cost": line['cost'],
                    "note": line['notes'],
                    
                    # Data dari Parent (Header)
                    "pname": parent_data['presales_name'],
                    "sgid": parent_data['salesgroup_id'],
                    "sname": parent_data['sales_name'],
                    "pam": parent_data['responsible_name'],
                    "comp": parent_data['company_name'],
                    "vert": parent_data['vertical_industry'],
                    "stg": parent_data['stage'],
                    "oname": parent_data['opportunity_name'],
                    "sdate": parent_data['start_date'],
                    
                    "now": created_at
                })
            
            # Log Activity (Sekali saja per batch)
            log_msg = f"Created CPS Opp: {cps_id} ({len(cps_lines)} configs)"
            session.execute(text("""
                INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, new_value) 
                VALUES (:now, :oid, :usr, 'CREATE', 'CPS Opportunity', :val)
            """), {"now": created_at, "oid": cps_id, "usr": parent_data['presales_name'], "val": log_msg})
            
            session.commit()
            
        return {"status": 200, "message": f"Success! Generated ID: {cps_id} with {len(cps_lines)} configurations."}

    except Exception as e:
        return {"status": 500, "message": str(e)}
    
    
def update_opportunity_stage_bulk_enhanced(opp_id, new_stage, notes, manual_date, user, closing_reason=None):
    """
    Update stage untuk semua item dalam satu opportunity ID.
    Mendukung input Closing Reason dan Closing Notes.
    """
    try:
        # Konversi tanggal manual ke format timestamp DB
        # Pastikan manual_date dikonversi ke string atau datetime yang sesuai dengan DB Anda
        
        with conn.session as session:
            # 1. Update Tabel Opportunities
            # Jika stage Closed, kita update kolom closing_reason dan closing_notes juga
            # Notes dari UI masuk ke kolom 'stage_notes' atau 'closing_notes' (tergantung preferensi)
            
            # Query Dinamis
            if closing_reason:
                query_upd = text("""
                    UPDATE opportunities 
                    SET stage = :stg, 
                        stage_notes = :note, 
                        closing_reason = :reason,
                        closing_notes = :note, -- Optional: Duplicate note ke kolom closing biar spesifik
                        updated_at = :date
                    WHERE opportunity_id = :oid
                """)
                params = {
                    "stg": new_stage, 
                    "note": notes, 
                    "reason": closing_reason, 
                    "date": manual_date, 
                    "oid": opp_id
                }
            else:
                # Update biasa (Bukan closing)
                query_upd = text("""
                    UPDATE opportunities 
                    SET stage = :stg, 
                        stage_notes = :note,
                        updated_at = :date
                    WHERE opportunity_id = :oid
                """)
                params = {
                    "stg": new_stage, 
                    "note": notes, 
                    "date": manual_date, 
                    "oid": opp_id
                }
            
            session.execute(query_upd, params)

            # 2. Catat Activity Log
            log_msg = f"Stage updated to {new_stage}"
            if closing_reason:
                log_msg += f" (Reason: {closing_reason})"
            
            query_log = text("""
                INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, new_value)
                VALUES (NOW(), :oid, :usr, 'UPDATE', 'Stage', :val)
            """)
            
            session.execute(query_log, {
                "oid": opp_id, 
                "usr": user, 
                "val": log_msg
            })
            
            session.commit()
            
        return {"status": 200, "message": "Stage updated successfully."}

    except Exception as e:
        return {"status": 500, "message": str(e)}