import streamlit as st
import pandas as pd
import os
from datetime import datetime
from supabase import create_client
import requests

# ================= INIT =================
st.set_page_config(page_title="Sistem Presensi", layout="wide")

# ================= SUPABASE =================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= FONNTE =================
FONNTE_TOKEN = os.getenv("FONNTE_TOKEN")

# ================= FORMAT NOMOR =================
def format_nomor(nomor):
    nomor = str(nomor)
    nomor = nomor.replace(" ", "").replace("-", "").replace("+", "")

    if nomor.startswith("08"):
        nomor = "62" + nomor[1:]
    elif nomor.startswith("628"):
        pass
    else:
        nomor = "62" + nomor

    return nomor

# ================= KIRIM WA =================
def kirim_wa_auto(nomor, pesan):
    try:
        nomor = format_nomor(nomor)

        url = "https://api.fonnte.com/send"
        headers = {"Authorization": FONNTE_TOKEN}
        data = {"target": nomor, "message": pesan}

        res = requests.post(url, headers=headers, data=data)

        if res.status_code != 200:
            st.warning(f"WA gagal: {res.text}")

    except Exception as e:
        st.warning(f"Gagal kirim WA: {e}")

# ================= LOAD MAHASISWA =================
df_mhs = pd.read_excel("data/mahasiswa.xlsx")
df_mhs.columns = ["kode_mk", "mata_kuliah", "kelas", "nim", "nama", "no_hp"]

# ================= LOAD DATA =================
def load_data():
    res = supabase.table("laporan").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.title("🔐 Login Sistem")

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

    nim = st.session_state.username
    data_mhs = df_mhs[df_mhs["nim"].astype(str) == str(nim)]

    nama = data_mhs.iloc[0]["nama"]
    no_hp = data_mhs.iloc[0]["no_hp"]

    st.title("📩 Lapor Kendala Presensi")

    with st.form("form"):
        matkul = st.selectbox("Mata Kuliah", data_mhs["mata_kuliah"].unique())
        kelas = st.selectbox("Kelas", data_mhs["kelas"].unique())
        pertemuan = st.number_input("Pertemuan Ke", 1, 16)
        tanggal = st.date_input("Tanggal")

        jenis = st.selectbox("Jenis Kendala", ["Gagal Scan","Error Sistem","Lupa Presensi","Lainnya"])
        deskripsi = st.text_area("Deskripsi")

        submit = st.form_submit_button("Kirim")

        if submit:
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
                "status": "Menunggu"
            }

            supabase.table("laporan").insert(data).execute()

            pesan = f"""
Halo {nama},

Laporan presensi berhasil dikirim.

Matkul: {matkul}
Status: Menunggu

Terima kasih.
"""
            kirim_wa_auto(no_hp, pesan)

            st.success("Laporan terkirim")
            st.rerun()

    # ================= RIWAYAT =================
    st.subheader("📋 Riwayat Laporan")

    df_user = df[df["nim"] == nim] if not df.empty else pd.DataFrame()

    if df_user.empty:
        st.info("Belum ada laporan")
    else:
        st.dataframe(df_user[["mata_kuliah","kelas","pertemuan_ke","status"]])

# ================= ADMIN =================
elif role == "admin":
    df = load_data()

    st.title("📊 Dashboard Admin")

    if df.empty:
        st.warning("Belum ada data")
        st.stop()

    # ================= FILTER =================
    st.subheader("🔍 Filter")

    status_filter = st.selectbox("Status", ["Semua","Menunggu","Disetujui","Ditolak"])
    matkul_filter = st.selectbox("Mata Kuliah", ["Semua"] + list(df["mata_kuliah"].unique()))
    search_nim = st.text_input("Cari NIM")

    df_filtered = df.copy()

    if status_filter != "Semua":
        df_filtered = df_filtered[df_filtered["status"] == status_filter]

    if matkul_filter != "Semua":
        df_filtered = df_filtered[df_filtered["mata_kuliah"] == matkul_filter]

    if search_nim:
        df_filtered = df_filtered[df_filtered["nim"].astype(str).str.contains(search_nim)]

    # ================= DASHBOARD GRAFIK =================
    st.subheader("📊 Dashboard Grafik")

    if not df_filtered.empty:

        st.markdown("### 📌 Distribusi Status")
        st.bar_chart(df_filtered["status"].value_counts())

        st.markdown("### 🎓 Mata Kuliah Terbanyak")
        st.bar_chart(df_filtered["mata_kuliah"].value_counts().head(10))

        st.markdown("### ⚠️ Jenis Kendala")
        st.bar_chart(df_filtered["jenis_kendala"].value_counts())

        st.markdown("### 📈 Tren Laporan")

        df_filtered["tanggal_pertemuan"] = pd.to_datetime(
            df_filtered["tanggal_pertemuan"], errors="coerce"
        )

        df_filtered["bulan"] = df_filtered["tanggal_pertemuan"].dt.to_period("M").astype(str)

        tren = df_filtered.groupby("bulan").size()
        st.line_chart(tren)

    else:
        st.info("Tidak ada data")

    # ================= EXPORT =================
    st.subheader("📥 Export Excel")

    df_filtered.to_excel("laporan.xlsx", index=False)
    with open("laporan.xlsx", "rb") as f:
        st.download_button("Download Excel", f, file_name="laporan.xlsx")

    # ================= DATA =================
    for _, row in df_filtered.iterrows():
        st.markdown("---")
        st.write(f"{row['nama']} ({row['nim']})")
        st.write(row["mata_kuliah"], row["kelas"])

        mhs = df_mhs[df_mhs["nim"].astype(str) == str(row["nim"])]
        no_hp = mhs.iloc[0]["no_hp"] if not mhs.empty else ""

        if row["status"] == "Menunggu":
            st.warning("Menunggu")
        elif row["status"] == "Disetujui":
            st.success("Disetujui")
        else:
            st.error("Ditolak")

        if st.button("Approve", key=f"a{row['id']}"):
            supabase.table("laporan").update({
                "status": "Disetujui"
            }).eq("id", row["id"]).execute()

            pesan = f"""
Halo {row['nama']},

Laporan Anda DISETUJUI ✅

Matkul: {row['mata_kuliah']}
"""
            kirim_wa_auto(no_hp, pesan)

            st.rerun()

        if st.button("Reject", key=f"r{row['id']}"):
            supabase.table("laporan").update({
                "status": "Ditolak"
            }).eq("id", row["id"]).execute()

            pesan = f"""
Halo {row['nama']},

Laporan Anda DITOLAK ❌

Matkul: {row['mata_kuliah']}
"""
            kirim_wa_auto(no_hp, pesan)

            st.rerun()
