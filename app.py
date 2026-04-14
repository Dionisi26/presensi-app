import streamlit as st
import pandas as pd
import os
from datetime import datetime
from supabase import create_client
import smtplib
from email.message import EmailMessage

# ================= INIT =================
st.set_page_config(page_title="Sistem Presensi", layout="wide")

# ================= SUPABASE =================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= EMAIL =================
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_ADMIN = os.getenv("EMAIL_ADMIN")

def kirim_email(nama, nim, matkul):
    try:
        msg = EmailMessage()
        msg['Subject'] = '📩 Laporan Presensi Baru'
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_ADMIN

        msg.set_content(f"""
Laporan baru masuk:

Nama: {nama}
NIM: {nim}
Matkul: {matkul}
""")

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"Email gagal: {e}")

# ================= LOAD MAHASISWA =================
df_mhs = pd.read_excel("data/mahasiswa.xlsx")
df_mhs.columns = ["kode_mk", "mata_kuliah", "kelas", "nim", "nama"]

# ================= LOAD DATA =================
def load_data():
    try:
        res = supabase.table("laporan").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("🔐 Login Sistem Presensi")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == "admin" and password == "superadmin123":
            st.session_state.role = "admin"
            st.session_state.username = username
            st.session_state.logged_in = True
            st.rerun()

        elif username in df_mhs["nim"].astype(str).values and password == username:
            st.session_state.role = "mahasiswa"
            st.session_state.username = username
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Login gagal")

    st.stop()

# ================= SIDEBAR =================
st.sidebar.write(f"Login: {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

role = st.session_state.role

# ================= MAHASISWA =================
if role == "mahasiswa":
    df = load_data()

    st.title("📩 Lapor Kendala")

    nim = st.session_state.username
    data_mhs = df_mhs[df_mhs["nim"].astype(str) == str(nim)]
    nama = data_mhs.iloc[0]["nama"]

    with st.form("form"):
        matkul = st.selectbox("Mata Kuliah", data_mhs["mata_kuliah"].unique())
        kelas = st.selectbox("Kelas", data_mhs["kelas"].unique())
        pertemuan = st.number_input("Pertemuan Ke-", 1, 16)
        tanggal = st.date_input("Tanggal")

        jenis = st.selectbox("Jenis Kendala", ["Gagal Scan","Sistem Error","Lupa Presensi","Lainnya"])
        deskripsi = st.text_area("Deskripsi")
        bukti = st.file_uploader("Upload Bukti")

        submit = st.form_submit_button("Kirim")

        if submit:
            if deskripsi.strip() == "":
                st.warning("Isi deskripsi")
            else:
                # upload ke storage
                file_url = ""
                if bukti:
                    filename = f"{datetime.now().timestamp()}_{bukti.name}"
                    supabase.storage.from_("bukti").upload(filename, bukti.getvalue())
                    file_url = f"{SUPABASE_URL}/storage/v1/object/public/bukti/{filename}"

                data = {
                    "nama": nama,
                    "nim": nim,
                    "mata_kuliah": matkul,
                    "kelas": kelas,
                    "pertemuan_ke": pertemuan,
                    "tanggal_pertemuan": str(tanggal),
                    "tanggal_laporan": datetime.now().isoformat(),
                    "jenis_kendala": jenis,
                    "deskripsi": deskripsi,
                    "bukti": file_url,
                    "status": "Menunggu"
                }

                supabase.table("laporan").insert(data).execute()
                kirim_email(nama, nim, matkul)
                st.success("Terkirim!")
                st.rerun()

    # RIWAYAT
    st.subheader("📋 Riwayat")
    df_user = df[df["nim"] == nim] if not df.empty else pd.DataFrame()

    if df_user.empty:
        st.info("Belum ada laporan")
    else:
        st.dataframe(df_user[["mata_kuliah","kelas","pertemuan_ke","status"]])

# ================= ADMIN =================
elif role == "admin":
    df = load_data()

    st.title("📊 Dashboard")

    if df.empty:
        st.warning("Belum ada data")
    else:
        for _, row in df.iterrows():
            st.markdown("---")
            st.write(f"{row['nama']} ({row['nim']})")
            st.write(row["mata_kuliah"], row["kelas"])

            if row["bukti"]:
                st.link_button("Lihat Bukti", row["bukti"])

            # status visual
            if row["status"] == "Menunggu":
                st.warning("Menunggu")
            elif row["status"] == "Disetujui":
                st.success("Disetujui")
            else:
                st.error("Ditolak")

            if st.button("Approve", key=f"a{row['id']}"):
                supabase.table("laporan").update({"status": "Disetujui"}).eq("id", row["id"]).execute()
                st.rerun()

            if st.button("Reject", key=f"r{row['id']}"):
                supabase.table("laporan").update({"status": "Ditolak"}).eq("id", row["id"]).execute()
                st.rerun()
