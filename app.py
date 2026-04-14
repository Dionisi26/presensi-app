import streamlit as st
import pandas as pd
import os
from datetime import datetime
from supabase import create_client
import smtplib
from email.message import EmailMessage

# ================= INIT =================
st.set_page_config(page_title="Sistem Presensi", layout="wide")

# ================= FOLDER =================
os.makedirs("uploads", exist_ok=True)

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
    except Exception as e:
        st.warning(f"Email gagal dikirim: {e}")

# ================= LOAD MAHASISWA =================
try:
    df_mhs = pd.read_excel("data/mahasiswa.xlsx")
    df_mhs.columns = ["kode_mk", "mata_kuliah", "kelas", "nim", "nama"]
except:
    st.error("File mahasiswa.xlsx error")
    st.stop()

# ================= LOAD DATA =================
def load_data():
    try:
        res = supabase.table("laporan").select("*").execute()

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
        st.error(f"Load Error: {e}")
        return pd.DataFrame()

df = load_data()

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

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
                    cek = df[
                        (df["nim"] == nim) &
                        (df["mata_kuliah"] == matkul) &
                        (df["pertemuan_ke"] == pertemuan)
                    ] if not df.empty else pd.DataFrame()

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
                        res = supabase.table("laporan").insert(new_data).execute()

                        if hasattr(res, "error") and res.error:
                            st.error(f"Gagal insert: {res.error}")
                        else:
                            kirim_email(nama, nim, matkul)
                            st.success("Laporan terkirim!")
                            st.rerun()

                    except Exception as e:
                        st.error(f"Insert Error: {e}")

# ================= ADMIN =================
elif role == "admin":
    st.title("🎓 Dashboard Akademik")

    if df.empty:
        st.warning("Belum ada data")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df))
        col2.metric("Disetujui", len(df[df["status"] == "Disetujui"]))
        col3.metric("Ditolak", len(df[df["status"] == "Ditolak"]))

        st.subheader("📊 Tren Bulanan")
        df["bulan"] = df["tanggal_pertemuan"].dt.to_period("M").astype(str)
        st.line_chart(df.groupby("bulan").size())

        st.subheader("🏫 Kelas Bermasalah")
        st.bar_chart(df["kelas"].value_counts())

        st.subheader("⚠️ Jenis Kendala")
        st.bar_chart(df["jenis_kendala"].value_counts())

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

            if st.button("Reject", key=f"r{row['id']}"):
                try:
                    supabase.table("laporan") \
                        .update({"status": "Ditolak"}) \
                        .eq("id", row["id"]) \
                        .execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Update Error: {e}")
