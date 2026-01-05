from sqlalchemy import create_engine, text

# Gunakan koneksi yang sama
DB_URL = "postgresql://admin:bzftDFqgCxGg0gQ@36.67.62.245:8088/dbpresales"
engine = create_engine(DB_URL)

def check_tables():
    print("Mengecek daftar tabel di database...")
    with engine.connect() as conn:
        # Query untuk melihat semua tabel di public schema
        query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        result = conn.execute(query).fetchall()
        
    print("\nTabel yang ditemukan:")
    if not result:
        print("⚠️ TIDAK ADA TABEL SAMA SEKALI. Migrasi data mungkin gagal.")
    else:
        for row in result:
            print(f"- {row[0]}")

if __name__ == "__main__":
    check_tables()