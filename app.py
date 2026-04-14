import streamlit as st
import pandas as pd
import os
from datetime import datetime

from session import init_session
init_session()

st.set_page_config(page_title="Sistem Presensi", layout="wide")

# ================= UI STYLE =================
st.markdown("""
<style>
.main {background-color: #0e1117;}
h1, h2, h3 {color: #ffffff;}
.block-container {padding-top: 2rem;}

div[data-testid="stMetric"] {
    background: #1c1f26;
    padding: 15px;
    border-radius: 10px;
    text-align: center;
}

.stButton>button {
    border-radius: 8px;
    background: #4CAF50;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ================= PATH =================
DATA_PATH = "data/laporan.csv"
UPLOAD_PATH = "uploads"
os.makedirs(UPLOAD_PATH, exist_ok=True)

# ================= LOAD DATA =================
try:
    df_mhs = pd.read_excel("data/mahasiswa.xlsx")
    df_mhs.columns = ["kode_mk", "mata_kuliah", "kelas", "nim", "nama"]
except:
    st.error("File mahasiswa.xlsx tidak ditemukan / rusak")
    st.stop()

if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=[
        "nama","nim","mata_kuliah","kelas","pertemuan_ke",
        "tanggal_pertemuan","tanggal_laporan",
        "jenis_kendala","deskripsi","bukti","status"
    ]).to_csv(DATA_PATH, index=False)

df = pd.read_csv(DATA_PATH)
df["tanggal_pertemuan"] = pd.to_datetime(df.get("tanggal_pertemuan"), errors="coerce")

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
st.sidebar.write(f"Login sebagai: {st.session_state.username}")

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
        st.success(f"Login sebagai: {nama}")

        with st.form("form"):
            matkul = st.selectbox("Mata Kuliah", data_mhs["mata_kuliah"].unique())
            kelas = st.selectbox("Kelas", data_mhs["kelas"].unique())
            pertemuan = st.number_input("Pertemuan Ke-", 1, 16)
            tanggal_pertemuan = st.date_input("Tanggal Pertemuan")

            jenis = st.selectbox("Jenis Kendala", [
                "Gagal Scan","Sistem Error","Lupa Presensi",
                "Lokasi Tidak Terdeteksi","Lainnya"
            ])

            deskripsi = st.text_area("Deskripsi Kendala")
            bukti = st.file_uploader("Upload Bukti", type=["png","jpg","jpeg","pdf"])

            submit = st.form_submit_button("Kirim")

            if submit:
                if deskripsi.strip() == "":
                    st.warning("Deskripsi tidak boleh kosong")
                else:
                    cek = df[
                        (df["nim"].astype(str) == str(nim)) &
                        (df["mata_kuliah"] == matkul) &
                        (df["pertemuan_ke"] == pertemuan)
                    ]

                    if not cek.empty:
                        st.error("❌ Sudah pernah submit di pertemuan ini")
                        st.stop()

                    filename = ""
                    if bukti:
                        filename = f"{datetime.now().timestamp()}_{bukti.name}"
                        with open(os.path.join(UPLOAD_PATH, filename), "wb") as f:
                            f.write(bukti.getbuffer())

                    new_data = {
                        "nama": nama,
                        "nim": nim,
                        "mata_kuliah": matkul,
                        "kelas": kelas,
                        "pertemuan_ke": pertemuan,
                        "tanggal_pertemuan": tanggal_pertemuan,
                        "tanggal_laporan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "jenis_kendala": jenis,
                        "deskripsi": deskripsi,
                        "bukti": filename,
                        "status": "Menunggu"
                    }

                    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    df.to_csv(DATA_PATH, index=False)

                    st.success("✅ Laporan berhasil dikirim!")
                    st.rerun()

# ================= ADMIN =================
elif role == "admin":
    st.title("🎓 Dashboard Akademik")
    st.caption("Monitoring Kendala Presensi Mahasiswa")

    if not df.empty:

        # KPI
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df))
        col2.metric("Disetujui", len(df[df["status"] == "Disetujui"]))
        col3.metric("Ditolak", len(df[df["status"] == "Ditolak"]))

        # ================= INSIGHT BULANAN =================
        st.subheader("📊 Tren Kendala Bulanan")
        df_month = df.copy()
        df_month["bulan"] = df_month["tanggal_pertemuan"].dt.to_period("M").astype(str)
        st.line_chart(df_month.groupby("bulan").size())

        st.subheader("🏫 Kelas Paling Bermasalah")
        st.bar_chart(df["kelas"].value_counts())

        st.subheader("⚠️ Jenis Kendala Terbanyak")
        st.bar_chart(df["jenis_kendala"].value_counts())

        # ================= PDF EXPORT =================
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
        from reportlab.lib import colors

        def generate_pdf(dataframe):
            file_path = "laporan.pdf"
            doc = SimpleDocTemplate(file_path)

            data = [dataframe.columns.tolist()] + dataframe.values.tolist()

            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.grey),
                ('GRID',(0,0),(-1,-1),1,colors.black)
            ]))

            doc.build([table])
            return file_path

        if st.button("📄 Export PDF"):
            pdf = generate_pdf(df)
            with open(pdf, "rb") as f:
                st.download_button("Download PDF", f, "laporan.pdf")

        # ================= DATA =================
        for i, row in df.iterrows():
            with st.container():
                st.markdown("---")
                st.write(f"👤 {row['nama']} ({row['nim']})")
                st.write(f"📚 {row['mata_kuliah']} | {row['kelas']}")
                st.write(f"📘 Pertemuan {row['pertemuan_ke']}")
                st.write(f"⚠️ {row['jenis_kendala']}")

                if st.button("Approve", key=f"a{i}"):
                    df.loc[i, "status"] = "Disetujui"
                    df.to_csv(DATA_PATH, index=False)
                    st.rerun()

                if st.button("Reject", key=f"r{i}"):
                    df.loc[i, "status"] = "Ditolak"
                    df.to_csv(DATA_PATH, index=False)
                    st.rerun()
