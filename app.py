import streamlit as st
import pandas as pd
import os
from datetime import datetime
from supabase import create_client
import smtplib
from email.message import EmailMessage
os.makedirs("uploads", exist_ok=True)
# ================= INIT =================
from session import init_session
init_session()

st.set_page_config(page_title="Sistem Presensi", layout="wide")

# ================= SUPABASE =================
SUPABASE_URL = "https://fftmsmfjtxhcoeshdcaw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= EMAIL CONFIG =================
EMAIL_SENDER = "EMAIL_KAMU@gmail.com"
EMAIL_PASS = "APP_PASSWORD"
EMAIL_ADMIN = "EMAIL_ADMIN@gmail.com"

def kirim_email(nama, nim, matkul):
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Laporan Presensi Baru'
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
    except:
        pass

# ================= UI STYLE =================
st.markdown("""
<style>
.main {background-color: #0e1117;}
h1, h2, h3 {color: #ffffff;}
div[data-testid="stMetric"] {
    background: #1c1f26;
    padding: 15px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ================= LOAD MAHASISWA =================
try:
    df_mhs = pd.read_excel("data/mahasiswa.xlsx")
    df_mhs.columns = ["kode_mk", "mata_kuliah", "kelas", "nim", "nama"]
except:
    st.error("File mahasiswa.xlsx error")
    st.stop()

# ================= LOAD DATA SUPABASE =================
def load_data():
    try:
        res = supabase.table("laporan").select("*").execute()

        # DEBUG RESPONSE
        if hasattr(res, "error") and res.error:
            st.error(f"Supabase Error: {res.error}")
            return pd.DataFrame()

        if not res.data:
            return pd.DataFrame()

        df = pd.DataFrame(res.data)

        if "tanggal_pertemuan" in df.columns:
            df["tanggal_pertemuan"] = pd.to_datetime(
                df["tanggal_pertemuan"], errors="coerce"
            )

        return df

    except Exception as e:
        st.error(f"ERROR DETAIL: {e}")
        return pd.DataFrame()

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("🔐 Login Sistem Presensi")

    username = st.text_input("Username (Admin / NIM)")
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
st.sidebar.title("🎓 Sistem Akademik")
st.sidebar.write(f"Login: {st.session_state.username}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

role = st.session_state.role

# ================= MAHASISWA =================
if role == "mahasiswa":
    st.title("📩 Lapor Kendala Presensi")

    nim = st.session_state.username
    data_mhs = df_mhs[df_mhs["nim"].astype(str) == str(nim)]

    if not data_mhs.empty:
        nama = data_mhs.iloc[0]["nama"]

        with st.form("form"):
            matkul = st.selectbox("Mata Kuliah", data_mhs["mata_kuliah"].unique())
            kelas = st.selectbox("Kelas", data_mhs["kelas"].unique())
            pertemuan = st.number_input("Pertemuan Ke-", 1, 16)
            tanggal_pertemuan = st.date_input("Tanggal Pertemuan")

            jenis = st.selectbox("Jenis Kendala", [
                "Gagal Scan","Sistem Error","Lupa Presensi",
                "Lokasi Tidak Terdeteksi","Lainnya"
            ])

            deskripsi = st.text_area("Deskripsi")
            bukti = st.file_uploader("Upload Bukti", type=["png","jpg","jpeg","pdf"])

            submit = st.form_submit_button("Kirim")

            if submit:
                if deskripsi.strip() == "":
                    st.warning("Deskripsi wajib diisi")
                else:
                    # VALIDASI DUPLIKASI
                    cek = df[
                        (df["nim"] == nim) &
                        (df["mata_kuliah"] == matkul) &
                        (df["pertemuan_ke"] == pertemuan)
                    ]

                    if not cek.empty:
                        st.error("Sudah pernah submit")
                        st.stop()

                    filename = ""
                    if bukti:
                        filename = f"{datetime.now().timestamp()}_{bukti.name}"
                        with open(os.path.join("uploads", filename), "wb") as f:
                            f.write(bukti.getbuffer())

                    new_data = {
                        "nama": nama,
                        "nim": nim,
                        "mata_kuliah": matkul,
                        "kelas": kelas,
                        "pertemuan_ke": pertemuan,
                        "tanggal_pertemuan": str(tanggal_pertemuan),
                        "tanggal_laporan": datetime.now().isoformat(),
                        "jenis_kendala": jenis,
                        "deskripsi": deskripsi,
                        "bukti": filename,
                        "status": "Menunggu"
                    }

                    try:
                        insert_res = supabase.table("laporan").insert(new_data).execute()
                
                        if hasattr(insert_res, "error") and insert_res.error:
                            st.error(f"Gagal insert: {insert_res.error}")
                        else:
                            kirim_email(nama, nim, matkul)
                            st.success("Laporan terkirim!")
                            st.rerun()
                
                    except Exception as e:
                        st.error(f"Insert Error: {e}")

                    st.success("Laporan terkirim!")
                    st.rerun()

# ================= ADMIN =================
elif role == "admin":
    st.title("🎓 Dashboard Akademik")

    if not df.empty:
        # KPI
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df))
        col2.metric("Disetujui", len(df[df["status"] == "Disetujui"]))
        col3.metric("Ditolak", len(df[df["status"] == "Ditolak"]))

        # BULANAN
        st.subheader("📊 Tren Bulanan")
        df["bulan"] = df["tanggal_pertemuan"].dt.to_period("M").astype(str)
        st.line_chart(df.groupby("bulan").size())

        st.subheader("🏫 Kelas Bermasalah")
        st.bar_chart(df["kelas"].value_counts())

        st.subheader("⚠️ Jenis Kendala")
        st.bar_chart(df["jenis_kendala"].value_counts())

        # DATA
        for _, row in df.iterrows():
            st.markdown("---")
            st.write(f"{row['nama']} ({row['nim']})")
            st.write(f"{row['mata_kuliah']} | {row['kelas']}")
            st.write(f"Pertemuan {row['pertemuan_ke']}")

            if st.button("Approve", key=f"a{row['id']}"):
                try:
                    supabase.table("laporan") \
                        .update({"status": "Disetujui"}) \
                        .eq("id", row["id"]) \
                        .execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Update Error: {e}")
                st.rerun()

            if st.button("Reject", key=f"r{row['id']}"):
                try:
                supabase.table("laporan") \
                    .update({"status": "Ditolak"}) \
                    .eq("id", row["id"]) \
                    .execute()
                st.rerun()
            except Exception as e:
                st.error(f"Update Error: {e}")
                st.rerun()
