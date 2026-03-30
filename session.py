def init_session():
    import streamlit as st

    defaults = {
        "role": None,
        "username": None,
        "logged_in": False
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value