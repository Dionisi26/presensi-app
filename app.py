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

# ================= WA FONNTE =================
FONNTE_TOKEN = os.getenv("FONNTE_TOKEN")

def kirim_wa_auto(nomor, pesan):
    try:
        nomor = str(nomor).strip()

        # ubah 08 → 628
        if nomor.startswith("0"):
            nomor = "62" + nomor[1:]

        url = "https://api.fonnte.com/send"
        headers = {
            "Authorization": FONNTE_TOKEN
        }
        data = {
            "target": nomor,
            "message": pesan
        }

        requests.post(url, headers=headers, data=data)

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
    st.title("Login")

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

    st.title("Lapor Kendala")

    with st.form("form"):
        matkul = st.selectbox("Mata Kuliah", data_mhs["mata_kuliah"].unique())
        kelas = st.selectbox("Kelas", data_mhs["kelas"].unique())
        pertemuan = st.number_input("Pertemuan", 1, 16)
        tanggal = st.date_input("Tanggal")

        jenis = st.selectbox("Jenis", ["Gagal Scan","Error","Lupa","Lainnya"])
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

            # WA NOTIF SUBMIT
            pesan = f"""
Halo {nama},

Laporan presensi berhasil dikirim.

Matkul: {matkul}
Status: Menunggu

Terima kasih.
"""
            kirim_wa_auto(no_hp, pesan)

            st.success("Terkirim")
            st.rerun()

# ================= ADMIN =================
elif role == "admin":
    df = load_data()

    st.title("Dashboard")

    if df.empty:
        st.warning("Belum ada data")
    else:
        for _, row in df.iterrows():
            st.markdown("---")
            st.write(f"{row['nama']} ({row['nim']})")
            st.write(row["mata_kuliah"], row["kelas"])

            # ambil nomor dari excel
            mhs = df_mhs[df_mhs["nim"].astype(str) == str(row["nim"])]
            no_hp = mhs.iloc[0]["no_hp"] if not mhs.empty else ""

            # status
            if row["status"] == "Menunggu":
                st.warning("Menunggu")
            elif row["status"] == "Disetujui":
                st.success("Disetujui")
            else:
                st.error("Ditolak")

            # APPROVE
            if st.button("Approve", key=f"a{row['id']}"):
                supabase.table("laporan").update({
                    "status": "Disetujui"
                }).eq("id", row["id"]).execute()

                pesan = f"""
Halo {row['nama']},

Laporan Anda DISETUJUI.

Matkul: {row['mata_kuliah']}
"""
                kirim_wa_auto(no_hp, pesan)

                st.rerun()

            # REJECT
            if st.button("Reject", key=f"r{row['id']}"):
                supabase.table("laporan").update({
                    "status": "Ditolak"
                }).eq("id", row["id"]).execute()

                pesan = f"""
Halo {row['nama']},

Laporan Anda DITOLAK.

Matkul: {row['mata_kuliah']}
"""
                kirim_wa_auto(no_hp, pesan)

                st.rerun()
