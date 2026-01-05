import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- KONFIGURASI PENGIRIM ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "krisawahyukurniawan@gmail.com"     # GANTI INI
SENDER_PASSWORD = "wlto qllo miat hljv"   # GANTI DENGAN APP PASSWORD 16 DIGIT
RECIPIENT_EMAIL = "krisa.kurniawan@sisindokom.com" # GANTI KE EMAIL ANDA SENDIRI UNTUK TES

def test_send_email():
    print("1. Menyiapkan pesan...")
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = "Test Email dari Python - Presales App"
    
    body = "Halo, ini adalah tes email. Jika Anda menerima ini, berarti konfigurasi SMTP sukses."
    msg.attach(MIMEText(body, 'plain'))

    try:
        print(f"2. Menghubungkan ke {SMTP_SERVER}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Upgrade koneksi ke aman (TLS)
        
        print("3. Login...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        print("4. Mengirim email...")
        server.send_message(msg)
        server.quit()
        
        print("✅ SUKSES! Email terkirim. Cek inbox Anda.")
    except Exception as e:
        print(f"❌ GAGAL: {e}")

if __name__ == "__main__":
    test_send_email()