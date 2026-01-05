from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re


# --- 1. KONFIGURASI DATABASE ---
# Pastikan password dan host sesuai
DB_URL = "postgresql://admin:bzftDFqgCxGg0gQ@36.67.62.245:8088/dbpresales"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


app = FastAPI(title="Presales API System")

# Dependency untuk mendapatkan koneksi DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 2. DATA MODELS (Pydantic) ---
class ParentData(BaseModel):
    presales_name: Optional[str] = None
    salesgroup_id: Optional[str] = None
    sales_name: Optional[str] = None
    responsible_name: Optional[str] = None
    opportunity_name: str
    start_date: Optional[str] = None
    company_name: Optional[str] = None
    vertical_industry: Optional[str] = None

class ProductLine(BaseModel):
    pillar: Optional[str] = None
    solution: Optional[str] = None
    service: Optional[str] = None
    brand: Optional[str] = None
    channel: Optional[str] = None
    distributor_name: Optional[str] = None # Pastikan key ini sama dengan Streamlit
    cost: Optional[float] = 0
    notes: Optional[str] = ""
    
class EmailPayload(BaseModel):
    recipient_email: str
    subject: str
    body_html: str

class MultiLinePayload(BaseModel):
    parent_data: ParentData
    product_lines: List[ProductLine]
    
class UpdateLinePayload(BaseModel):
    uid: str
    cost: float
    notes: str
    user: str

class UpdateFullPayload(BaseModel):
    uid: str
    user: str
    salesgroup_id: str
    sales_name: str
    responsible_name: str
    pillar: str
    solution: str
    service: str
    brand: str
    company_name: str
    vertical_industry: str
    distributor_name: str

# --- 3. ENDPOINTS ---

@app.get("/")
def root():
    return {"message": "Presales API is running!"}

# --- GET LEADS (View Opportunities) ---
@app.get("/leads")
def get_leads(db: Session = Depends(get_db)):
    try:
        # Mengambil semua data untuk tabel utama
        query = text("SELECT * FROM opportunities ORDER BY created_at DESC")
        result = db.execute(query).mappings().all()
        return {"status": 200, "data": result}
    except Exception as e:
        return {"status": 500, "message": str(e)}

# --- GET SINGLE LEAD (Search & Edit) ---
@app.get("/lead")
def get_lead(uid: str = None, db: Session = Depends(get_db)):
    try:
        if uid:
            query = text("SELECT * FROM opportunities WHERE uid = :uid")
            result = db.execute(query, {"uid": uid}).mappings().all()
            return {"status": 200, "data": result}
        return {"status": 404, "message": "UID required"}
    except Exception as e:
        return {"status": 500, "message": str(e)}

# --- MASTER DATA ENDPOINTS (Dropdowns) ---
@app.get("/master")
def get_master_data(action: str, db: Session = Depends(get_db)):
    try:
        data = []
        
        # 1. Presales Names (Dropdown Inputter)
        if action == "getPresales":
            # Ambil dari tabel master_users (atau opportunities jika user belum lengkap)
            query = text("SELECT presales_name as \"PresalesName\", email as \"Email\" FROM presales ORDER BY presales_name")
            data = db.execute(query).mappings().all()
        
        elif action == "getPAMMapping":
            # Kita gunakan Alias "Inputter" dan "PAM" agar cocok dengan kode app.py Anda:
            # pam_map[item.get("Inputter")] = item.get("PAM")
            query = text("SELECT inputter_name as \"Inputter\", pam_name as \"PAM\" FROM mapping_pam")
            data = db.execute(query).mappings().all()
        
        # 2. Brands (Dropdown Brand)
        elif action == "getBrands":
            # REVISI: Ambil Brand DAN Channel dari tabel master_brands
            # Kita tidak pakai DISTINCT di awal query agar bisa mengambil pasangan Brand-Channel
            query = text("""
                SELECT 
                    brand_name as "Brand", 
                    channel as "Channel" 
                FROM brands 
                WHERE brand_name IS NOT NULL
                ORDER BY brand_name, channel
            """)
            data = db.execute(query).mappings().all()
            
        # 3. Pillars -> Solutions -> Services (Cascade Dropdown)
        elif action == "getPillars":
            # INI PERBAIKAN UTAMA: Query ke 'master_catalog'
            # Menggunakan Alias agar key JSON menjadi huruf Besar (Pillar, Solution) sesuai Streamlit
            query = text("""
                SELECT DISTINCT 
                    pillar_name as "Pillar", 
                    solution_name as "Solution", 
                    service_name as "Service" 
                FROM master_pillars 
                ORDER BY pillar_name, solution_name, service_name
            """)
            data = db.execute(query).mappings().all()
            
        # 4. Sales Groups (Dropdown Sales Group)
        elif action == "getSalesGroups":
            query = text("SELECT DISTINCT sales_group as \"SalesGroup\" FROM sales_names ORDER BY sales_group")
            data = db.execute(query).mappings().all()
            
        # 5. Sales Names (Dropdown Sales Name)
        elif action == "getSalesNames":
            query = text("SELECT sales_group as \"SalesGroup\", sales_name as \"SalesName\" FROM sales_names ORDER BY sales_name")
            data = db.execute(query).mappings().all()
            
        # 6. Responsibles (Dropdown PAM)
        elif action == "getResponsibles":
            # Jika tabel responsibles belum ada, ambil dari master_users atau hardcode sementara
            query = text("SELECT DISTINCT responsible_name as \"Responsible\" FROM responsible WHERE responsible_name IS NOT NULL")
            data = db.execute(query).mappings().all()
            
        # 7. Companies (Dropdown Company)
        elif action == "getCompanies":
            query = text("SELECT DISTINCT company_name as \"Company\", vertical_industry as \"Vertical Industry\" FROM companies ORDER BY company_name")
            data = db.execute(query).mappings().all()
            
        # 8. Distributors (Dropdown Distributor)
        elif action == "getDistributors":
            query = text("SELECT DISTINCT distributor_name as \"Distributor\" FROM distributors WHERE distributor_name IS NOT NULL ORDER BY distributor_name")
            data = db.execute(query).mappings().all()
            
        # 9. Activity Logs
        elif action == "getActivityLog":
            # Pastikan tabel activity_logs sudah ada (dari script migrate_logs.py)
            query = text("""
                SELECT 
                    timestamp as "Timestamp", 
                    opportunity_name as "OpportunityName", 
                    user_name as "User", 
                    action as "Action", 
                    field as "Field", 
                    old_value as "OldValue", 
                    new_value as "NewValue" 
                FROM activity_logs 
                ORDER BY timestamp DESC LIMIT 1000
            """)
            data = db.execute(query).mappings().all()
            
        # 10. Opportunities List (Untuk Dropdown Nama Oppty saat Search Log)
        elif action == "getOpportunities":
             query = text("SELECT DISTINCT opportunity_name as \"Desc\" FROM opportunities ORDER BY opportunity_name")
             data = db.execute(query).mappings().all()

        return {"status": 200, "data": data}
        
    except Exception as e:
        # Tampilkan error detail di response untuk debugging
        return {"status": 500, "message": f"Server Error [{action}]: {str(e)}"}
    
@app.post("/sendEmail")
def send_email_endpoint(payload: EmailPayload):
    try:
        # Konfigurasi SMTP (Pastikan variabel ini sudah didefinisikan di atas)
        # Jika belum, definisikan lagi di sini atau di global scope
        SMTP_SERVER = "smtp.gmail.com"
        SMTP_PORT = 587
        SENDER_EMAIL = "krisawahyukurniawan@gmail.com" # Ganti dengan email Anda
        SENDER_PASSWORD = "wlto qllo miat hljv"          # Ganti dengan App Password

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = payload.recipient_email
        msg['Subject'] = payload.subject
        msg.attach(MIMEText(payload.body_html, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"📧 Email successfully sent to {payload.recipient_email}")
        return {"status": 200, "message": "Email sent successfully"}

    except Exception as e:
        print(f"⚠️ Email Error: {str(e)}")
        # Kita return 200 atau 500 tergantung kebutuhan, 
        # tapi return 500 biar frontend tahu kalau gagal.
        return {"status": 500, "message": f"Failed to send email: {str(e)}"}

@app.post("/update")
def update_line_item(payload: UpdateLinePayload, db: Session = Depends(get_db)):
    try:
        # 1. Cek Data Lama (Untuk validasi & logging)
        check_query = text("SELECT opportunity_name, cost, notes FROM opportunities WHERE uid = :uid")
        current_data = db.execute(check_query, {"uid": payload.uid}).mappings().first()
        
        if not current_data:
            return {"status": 404, "message": f"UID {payload.uid} not found."}

        timestamp_now = datetime.now()

        # 2. Lakukan Update ke Database
        update_query = text("""
            UPDATE opportunities 
            SET cost = :c, notes = :n, updated_at = :t
            WHERE uid = :u
        """)
        
        db.execute(update_query, {
            "c": payload.cost,
            "n": payload.notes,
            "t": timestamp_now,
            "u": payload.uid
        })

        # 3. Log Activity (Mencatat perubahan Cost/Notes)
        # Log Cost change jika berubah
        if float(current_data.cost or 0) != float(payload.cost):
            log_query = text("""
                INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, old_value, new_value)
                VALUES (:ts, :opp, :user, 'UPDATE', 'Cost', :old, :new)
            """)
            db.execute(log_query, {
                "ts": timestamp_now,
                "opp": current_data.opportunity_name,
                "user": payload.user,
                "old": str(current_data.cost),
                "new": str(payload.cost)
            })

        # Log Notes change jika berubah
        if str(current_data.notes or "") != str(payload.notes):
             log_query = text("""
                INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, old_value, new_value)
                VALUES (:ts, :opp, :user, 'UPDATE', 'Notes', :old, :new)
            """)
             db.execute(log_query, {
                "ts": timestamp_now,
                "opp": current_data.opportunity_name,
                "user": payload.user,
                "old": str(current_data.notes or ""),
                "new": str(payload.notes)
            })

        db.commit()
        return {"status": 200, "message": "Opportunity line updated successfully!"}

    except Exception as e:
        db.rollback()
        print(f"UPDATE ERROR: {e}")
        return {"status": 500, "message": f"Server Error: {str(e)}"}

# --- INPUT DATA (Submit) ---
@app.post("/addMultiLineOpportunity")
def add_multi_line(payload: MultiLinePayload, db: Session = Depends(get_db)):
    parent = payload.parent_data
    lines = payload.product_lines
    
    try:
        # --- 1. LOGIKA HANDLING OPPORTUNITY NAME & ROWS_ID ---
        
        # Cek apakah Opportunity Name sudah ada di tabel description
        check_desc_query = text("SELECT rows_id FROM description WHERE description = :desc LIMIT 1")
        existing_desc = db.execute(check_desc_query, {"desc": parent.opportunity_name}).mappings().first()
        
        current_rows_id = ""
        
        if existing_desc:
            # SKENARIO A: Nama Opportunity Sudah Ada -> Pakai rows_id lama
            current_rows_id = existing_desc.rows_id
        else:
            # SKENARIO B: Nama Opportunity Baru -> Generate rows_id baru & Insert
            # 1. Ambil rows_id terakhir (Contoh: Q30004)
            get_max_id = text("SELECT MAX(rows_id) FROM description")
            max_id_val = db.execute(get_max_id).scalar()
            
            if max_id_val:
                # Asumsi format "Q3xxxx" -> Ambil angka di belakang "Q3"
                # Q30004 -> 0004 -> int 4
                try:
                    prefix = "Q3"
                    number_part = int(max_id_val.replace(prefix, ""))
                    new_number = number_part + 1
                    # Format balik ke Q3xxxx (4 digit padding)
                    current_rows_id = f"{prefix}{new_number:04d}"
                except ValueError:
                    # Fallback jika format di DB acak, pakai timestamp
                    current_rows_id = f"Q3{int(time.time())}"
            else:
                # Jika tabel kosong sama sekali
                current_rows_id = "Q30000"
            
            # 2. Simpan Nama Baru ke Tabel Description
            insert_desc = text("INSERT INTO description (rows_id, description) VALUES (:rid, :desc)")
            db.execute(insert_desc, {"rid": current_rows_id, "desc": parent.opportunity_name})
            # Kita commit parsial atau biarkan satu transaksi besar di akhir
            
        # --- 2. GENERATE OPPORTUNITY ID (SalesGroup + RowsID) ---
        # Contoh: ENT1 + Q30005 = ENT1Q30005
        safe_group_id = parent.salesgroup_id if parent.salesgroup_id else "GEN"
        new_opp_id = f"{safe_group_id}{current_rows_id}"
        
        values_to_insert = []
        created_at = datetime.now()
        timestamp_now = int(time.time())
        
        for i, line in enumerate(lines):
            # --- 3. GENERATE PRODUCT ID (LOGIKA LAMA TETAP DIPAKAI) ---
            
            # A. Cari Pillar ID, Solution ID, Service ID
            cat_query = text("""
                SELECT pillar_id, solution_id, service_id
                FROM master_pillars
                WHERE pillar_name = :p 
                  AND solution_name = :s 
                  AND service_name = :svc
                LIMIT 1
            """)
            
            cat_res = db.execute(cat_query, {
                "p": line.pillar, 
                "s": line.solution, 
                "svc": line.service
            }).mappings().first()
            
            # B. Cari Brand Code
            brand_code = "GEN"
            if line.brand:
                brand_query = text("SELECT brand_code FROM brands WHERE brand_name = :b LIMIT 1")
                brand_res = db.execute(brand_query, {"b": line.brand}).mappings().first()
                if brand_res and brand_res.brand_code:
                    brand_code = brand_res.brand_code
            
            # C. Rakit Product ID
            # Format: [PillarID][SolutionID][ServiceID][BrandCode] -> Contoh: NW16S1DEL
            part_pillar = cat_res.pillar_id if (cat_res and cat_res.pillar_id) else "GEN"
            part_sol = str(cat_res.solution_id) if (cat_res and cat_res.solution_id) else "0"
            part_svc = str(cat_res.service_id) if (cat_res and cat_res.service_id) else "S0"
            
            product_id_code = f"{part_pillar}{part_sol}{part_svc}{brand_code}".replace(" ", "").upper()

            # 4. GENERATE UID FINAL
            # Format: OppID - ProductID - Timestamp
            # Contoh: ENT1Q30005-NW16S1DEL-17653393920
            uid = f"{new_opp_id}-{product_id_code}-{timestamp_now}{i}"
            
            # Query Insert ke Table opportunities
            query = text("""
                INSERT INTO opportunities (
                    uid, opportunity_id, product_id, presales_name, salesgroup_id, sales_name, 
                    responsible_name, opportunity_name, start_date, company_name, 
                    vertical_industry, pillar, solution, service, brand, channel, 
                    distributor_name, cost, notes, stage, created_at, updated_at
                ) VALUES (
                    :uid, :opp_id, :prod_id, :pname, :sgid, :sname, 
                    :resp, :oppname, :sdate, :cname, 
                    :vi, :pillar, :sol, :svc, :brand, :channel,
                    :dist, :cost, :notes, 'Open', :created_at, :created_at
                )
            """)
            
            params = {
                "uid": uid,
                "opp_id": new_opp_id,
                "prod_id": product_id_code, 
                "pname": parent.presales_name,
                "sgid": parent.salesgroup_id,
                "sname": parent.sales_name,
                "resp": parent.responsible_name,
                "oppname": parent.opportunity_name,
                "sdate": parent.start_date, 
                "cname": parent.company_name,
                "vi": parent.vertical_industry,
                "pillar": line.pillar,
                "sol": line.solution,
                "svc": line.service,
                "brand": line.brand,
                "channel": line.channel,
                "dist": line.distributor_name,
                "cost": line.cost,
                "notes": line.notes,
                "created_at": created_at
            }
            
            db.execute(query, params)
            values_to_insert.append({"uid": uid, "opportunity_id": new_opp_id})
            
            # Log Activity
            log_query = text("""
                INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, new_value)
                VALUES (:ts, :oppname, :user, 'CREATE', 'Opportunity Created', :uid)
            """)
            db.execute(log_query, {
                "ts": created_at, 
                "oppname": parent.opportunity_name, 
                "user": parent.presales_name, 
                "uid": f"UID: {uid}"
            })
        
        # Commit transaksi (Opportunities + Description baru jika ada)
        db.commit()
        return {"status": 200, "message": "Opportunity successfully added!", "data": values_to_insert}
        
    except Exception as e:
        db.rollback()
        print(f"ERROR INSERT: {str(e)}")
        return {"status": 500, "message": f"Database Error: {str(e)}"}

# --- UPDATE FULL OPPORTUNITY ---
@app.post("/updateFullOpportunity")
def update_full_opportunity(payload: UpdateFullPayload, db: Session = Depends(get_db)):
    try:
        # 1. AMBIL DATA LAMA
        check_query = text("""
            SELECT uid, opportunity_id, product_id, salesgroup_id, opportunity_name 
            FROM opportunities 
            WHERE uid = :uid
        """)
        old_data = db.execute(check_query, {"uid": payload.uid}).mappings().first()
        
        if not old_data:
            return {"status": 404, "message": "UID not found"}
            
        # ==============================================================================
        # [REVISI] LOGIKA GENERATE OPPORTUNITY ID (SALESGROUP + ROWS_ID)
        # ==============================================================================
        
        rows_id_part = ""
        
        # CARA A (UTAMA): Ambil Rows ID asli dari tabel 'description' berdasarkan Nama Opportunity
        # Ini adalah cara paling aman agar ID tetap konsisten (misal: Q30005)
        desc_query = text("SELECT rows_id FROM description WHERE description = :desc LIMIT 1")
        desc_res = db.execute(desc_query, {"desc": old_data.opportunity_name}).mappings().first()
        
        if desc_res and desc_res.rows_id:
            rows_id_part = desc_res.rows_id
        
        # CARA B (BACKUP): Jika tidak ketemu di tabel description, gunakan Regex untuk ekstrak Q3xxxxx dari ID lama
        if not rows_id_part:
            # Cari pola "Q3" diikuti angka (Q30005, Q312345, dll)
            match = re.search(r'(Q3\d+)', old_data.opportunity_id)
            if match:
                rows_id_part = match.group(1)
            else:
                # Fallback terakhir: Ambil 6 digit terakhir string
                rows_id_part = old_data.opportunity_id[-6:]

        # RAKIT OPPORTUNITY ID BARU
        # Gabungkan SalesGroup BARU (dari payload) + Rows ID ASLI
        new_opp_id = f"{payload.salesgroup_id}{rows_id_part}"

        # ==============================================================================
        # [TETAP] LOGIKA GENERATE PRODUCT ID (PILLAR + SOLUTION + SERVICE + BRAND)
        # ==============================================================================
        
        # A. Cari Pillar, Solution, & Service ID Baru
        cat_query = text("""
            SELECT pillar_id, solution_id, service_id
            FROM master_pillars
            WHERE pillar_name = :p 
              AND solution_name = :s 
              AND service_name = :svc
            LIMIT 1
        """)
        cat_res = db.execute(cat_query, {
            "p": payload.pillar, 
            "s": payload.solution, 
            "svc": payload.service
        }).mappings().first()
        
        # B. Cari Brand Code Baru
        brand_code = "GEN"
        if payload.brand:
            brand_query = text("SELECT brand_code FROM brands WHERE brand_name = :b LIMIT 1")
            brand_res = db.execute(brand_query, {"b": payload.brand}).mappings().first()
            if brand_res and brand_res.brand_code:
                brand_code = brand_res.brand_code
        
        # C. Rakit Product ID Baru
        part_pillar = cat_res.pillar_id if (cat_res and cat_res.pillar_id) else "GEN"
        part_sol = str(cat_res.solution_id) if (cat_res and cat_res.solution_id) else "0"
        part_svc = str(cat_res.service_id) if (cat_res and cat_res.service_id) else "S0"
        
        new_product_id = f"{part_pillar}{part_sol}{part_svc}{brand_code}".replace(" ", "").upper()

        # ==============================================================================
        # [TETAP] LOGIKA GENERATE UID FINAL
        # ==============================================================================
        
        # Ambil timestamp dari UID lama
        parts = old_data.uid.split('-')
        if len(parts) >= 3:
            timestamp_part = parts[-1] 
        else:
            timestamp_part = str(int(time.time())) + "0"
            
        new_uid = f"{new_opp_id}-{new_product_id}-{timestamp_part}"

        # ==============================================================================
        # UPDATE DATABASE
        # ==============================================================================
        update_query = text("""
            UPDATE opportunities 
            SET uid = :new_uid,
                opportunity_id = :new_opp_id,
                product_id = :new_prod_id,
                salesgroup_id = :sg, 
                sales_name = :sn, 
                responsible_name = :rn, 
                pillar = :p, 
                solution = :sol, 
                service = :svc, 
                brand = :b, 
                company_name = :cn, 
                vertical_industry = :vi, 
                distributor_name = :dn,
                updated_at = :ts
            WHERE uid = :old_uid
        """)
        
        timestamp_now = datetime.now()
        
        db.execute(update_query, {
            "new_uid": new_uid,
            "new_opp_id": new_opp_id,
            "new_prod_id": new_product_id,
            "sg": payload.salesgroup_id,   # <--- PENTING: SalesGroup Baru masuk ke DB
            "sn": payload.sales_name,
            "rn": payload.responsible_name,
            "p": payload.pillar,
            "sol": payload.solution,
            "svc": payload.service,
            "b": payload.brand,
            "cn": payload.company_name,
            "vi": payload.vertical_industry,
            "dn": payload.distributor_name,
            "ts": timestamp_now,
            "old_uid": payload.uid 
        })

        # Log perubahan ID
        log_msg = f"Update Info & Regenerate IDs. OppID: {old_data.opportunity_id} -> {new_opp_id}. UID: {payload.uid} -> {new_uid}"
        log_query = text("""
            INSERT INTO activity_logs (timestamp, opportunity_name, user_name, action, field, new_value)
            VALUES (:ts, :opp, :user, 'UPDATE', 'ID Regeneration', :msg)
        """)
        
        db.execute(log_query, {
            "ts": timestamp_now,
            "opp": old_data.opportunity_name,
            "user": payload.user,
            "msg": log_msg
        })

        db.commit()
        
        return {
            "status": 200, 
            "message": "Data updated successfully!", 
            "data": {"uid": new_uid} 
        }

    except Exception as e:
        db.rollback()
        print(f"FULL UPDATE ERROR: {e}")
        return {"status": 500, "message": f"Server Error: {str(e)}"}