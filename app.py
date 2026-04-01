import streamlit as st
import pandas as pd
import os
from datetime import datetime

from session import init_session
init_session()

st.set_page_config(page_title="Sistem Presensi", layout="wide")

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

# INIT CSV
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=[
        "nama","nim","mata_kuliah","kelas","pertemuan_ke",
        "tanggal_pertemuan","tanggal_laporan",
        "jenis_kendala","deskripsi","bukti","status"
    ]).to_csv(DATA_PATH, index=False)

df = pd.read_csv(DATA_PATH)

# FIX DATE
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
st.sidebar.title("📌 Sistem Presensi")
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

    if data_mhs.empty:
        st.error("Data mahasiswa tidak ditemukan")
    else:
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
                    # VALIDASI DUPLIKASI
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

                    df_new = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                    df_new.to_csv(DATA_PATH, index=False)

                    st.success("✅ Laporan berhasil dikirim!")
                    st.rerun()

        # RIWAYAT
        st.subheader("📄 Riwayat Laporan")
        st.dataframe(df[df["nim"].astype(str) == str(nim)])

# ================= ADMIN =================
elif role == "admin":
    st.title("📊 Dashboard Admin")

    if df.empty:
        st.warning("Belum ada laporan")
    else:
        # FILTER
        colf1, colf2 = st.columns(2)
        kelas_filter = colf1.selectbox("Filter Kelas", ["Semua"] + list(df["kelas"].dropna().unique()))
        matkul_filter = colf2.selectbox("Filter Matkul", ["Semua"] + list(df["mata_kuliah"].dropna().unique()))

        df_view = df.copy()

        if kelas_filter != "Semua":
            df_view = df_view[df_view["kelas"] == kelas_filter]

        if matkul_filter != "Semua":
            df_view = df_view[df_view["mata_kuliah"] == matkul_filter]

        # KPI
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", len(df_view))
        col2.metric("Disetujui", len(df_view[df_view["status"] == "Disetujui"]))
        col3.metric("Ditolak", len(df_view[df_view["status"] == "Ditolak"]))

        # ================= INSIGHT =================
        st.subheader("📈 Tren Mingguan")
        df_week = df.copy()
        df_week["minggu"] = df_week["tanggal_pertemuan"].dt.to_period("W").astype(str)
        st.line_chart(df_week.groupby("minggu").size())

        st.subheader("📊 Performa Presensi")
        total = len(df)
        approve = len(df[df["status"] == "Disetujui"])
        rate = (approve / total * 100) if total > 0 else 0
        st.metric("Tingkat Keberhasilan", f"{rate:.1f}%")

        st.subheader("📚 Mata Kuliah Bermasalah")
        st.bar_chart(df["mata_kuliah"].value_counts())

        # ================= DATA =================
        for i, row in df_view.iterrows():
            with st.container():
                st.markdown("---")
                col1, col2 = st.columns([3,1])

                with col1:
                    st.subheader(f"{row.get('nama')} ({row.get('nim')})")
                    st.write(f"📚 {row.get('mata_kuliah')}")
                    st.write(f"🏫 Kelas: {row.get('kelas')}")
                    st.write(f"📘 Pertemuan: {row.get('pertemuan_ke')}")
                    st.write(f"📅 {row.get('tanggal_pertemuan')}")
                    st.write(f"⚠️ {row.get('jenis_kendala')}")
                    st.write(f"📝 {row.get('deskripsi')}")
                    st.write(f"⏱️ {row.get('tanggal_laporan')}")

                    bukti_file = str(row.get("bukti"))
                    if bukti_file != "nan" and bukti_file != "":
                        file_path = os.path.join(UPLOAD_PATH, bukti_file)
                        if os.path.exists(file_path):
                            if file_path.endswith(("png","jpg","jpeg")):
                                st.image(file_path, width=200)
                            else:
                                st.write(f"📎 {bukti_file}")

                with col2:
                    st.write(f"Status: **{row.get('status')}**")

                    if st.button("✅ Approve", key=f"a{i}"):
                        df.loc[i, "status"] = "Disetujui"
                        df.to_csv(DATA_PATH, index=False)
                        st.rerun()

                    if st.button("❌ Reject", key=f"r{i}"):
                        df.loc[i, "status"] = "Ditolak"
                        df.to_csv(DATA_PATH, index=False)
                        st.rerun()

        # DOWNLOAD
        st.download_button(
            "📥 Download CSV",
            df.to_csv(index=False),
            "laporan.csv",
            "text/csv"
        )
