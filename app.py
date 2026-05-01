"""
app.py — PFA testing UI
Run with:  streamlit run app.py
"""

import os
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="PFA Testing UI", layout="wide")

# ---------------------------------------------------------------------------
# Cached resources (loaded once, shared across all reruns)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading pipeline — first run takes ~30s…")
def _pipeline():
    import chat_pipeline as p
    return p


@st.cache_resource(show_spinner="Connecting to LM Studio…")
def _bare_client():
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.environ.get("LLM_API_KEY", "lm-studio"),
    )
    models = client.models.list().data
    model_id = models[0].id if models else ""
    return client, model_id


def _bare_call(query: str) -> str:
    client, model_id = _bare_client()
    resp = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": "You are a mental health information assistant. Answer accurately and concisely."},
            {"role": "user", "content": query},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Auth sidebar
# ---------------------------------------------------------------------------

def _auth_sidebar():
    with st.sidebar:
        st.title("PFA Testing UI")

        if st.session_state.get("user"):
            user = st.session_state["user"]
            st.success(f"{user.email}")
            st.caption(f"Age {user.age} · Mood baseline {user.mood_baseline}/10")
            st.caption(f"Goals: {', '.join(user.goals)}")
            if st.button("Log out"):
                st.session_state.clear()
                st.rerun()
            return

        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            if st.button("Login"):
                from session.users import UserStore
                user = UserStore().authenticate(email, password)
                if user:
                    _init_session(user)
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

        with tab_register:
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_pw")
            age = st.number_input("Age", min_value=13, max_value=100, value=25, key="reg_age")
            mood = st.slider("Mood baseline (1–10)", 1, 10, 5, key="reg_mood",
                             help="Your typical day-to-day mood level")
            goals_raw = st.text_area("Goals (one per line)", key="reg_goals",
                                     placeholder="manage anxiety\nreduce isolation")
            country = st.text_input("Country (optional)", key="reg_country")
            if st.button("Create account"):
                goals = [g.strip() for g in goals_raw.splitlines() if g.strip()]
                if not goals:
                    st.error("Enter at least one goal.")
                else:
                    from session.users import UserStore
                    try:
                        user = UserStore().create_user(
                            email=email,
                            password=password,
                            age=age,
                            mood_baseline=mood,
                            goals=goals,
                            country=country or None,
                        )
                        _init_session(user)
                        st.success("Account created!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


def _init_session(user):
    p = _pipeline()
    st.session_state["user"] = user
    st.session_state["session_id"] = p.create_session(user.user_id)
    st.session_state["chat_messages"] = []


# ---------------------------------------------------------------------------
# Chat tab
# ---------------------------------------------------------------------------

def _chat_tab():
    if not st.session_state.get("user"):
        st.info("Log in or register in the sidebar to start chatting.")
        return

    p = _pipeline()
    session_id = st.session_state["session_id"]

    for msg in st.session_state.get("chat_messages", []):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("passages"):
                with st.expander(f"Retrieved passages ({len(msg['passages'])})"):
                    for i, passage in enumerate(msg["passages"], 1):
                        st.caption(f"Passage {i}")
                        preview = passage[:400] + "…" if len(passage) > 400 else passage
                        st.text(preview)

    if user_input := st.chat_input("Type a message…"):
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner(""):
                result = p.run(user_input, session_id)
            st.write(result.text)

            passages = None
            if not result.is_crisis:
                rag = p._get_rag()
                passages = getattr(rag, "_last_passages", None)
            if passages:
                with st.expander(f"Retrieved passages ({len(passages)})"):
                    for i, passage in enumerate(passages, 1):
                        st.caption(f"Passage {i}")
                        preview = passage[:400] + "…" if len(passage) > 400 else passage
                        st.text(preview)

        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": result.text,
            "passages": passages,
        })


# ---------------------------------------------------------------------------
# Compare tab
# ---------------------------------------------------------------------------

def _compare_tab():
    if not st.session_state.get("user"):
        st.info("Log in or register in the sidebar first.")
        return

    p = _pipeline()
    user = st.session_state["user"]

    st.caption("Each run uses a fresh isolated session so comparisons don't bleed into each other.")

    query = st.text_area("Test message", height=100,
                         placeholder="e.g. I've been feeling really low lately and can't seem to shake it.")

    if st.button("Run comparison", disabled=not query.strip(), type="primary"):
        # Fresh throwaway session per comparison run — no history contamination
        temp_session = p.create_session(user.user_id)

        col_bare, col_pipeline = st.columns(2)

        with col_bare:
            st.markdown("#### Bare LLM")
            with st.spinner(""):
                t0 = time.time()
                bare_ans = _bare_call(query)
                bare_t = time.time() - t0
            st.caption(f"{bare_t:.1f}s")
            st.write(bare_ans)

        with col_pipeline:
            st.markdown("#### RAG + Profile")
            with st.spinner(""):
                t0 = time.time()
                result = p.run(query, temp_session)
                pipeline_t = time.time() - t0
            label = f"{pipeline_t:.1f}s"
            if result.is_crisis:
                label += " · ⚠ crisis intercepted"
            st.caption(label)
            st.write(result.text)

        # Debug panels
        from chat_pipeline import (
            SYSTEM_PROMPT_COMPANION, SYSTEM_PROMPT_INFORMATIONAL,
            _is_informational, _build_profile_block,
        )
        is_info = _is_informational(query)
        base = SYSTEM_PROMPT_INFORMATIONAL if is_info else SYSTEM_PROMPT_COMPANION

        with st.expander("System prompt sent to LLM"):
            st.text(base + "\n\n" + _build_profile_block(user))

        if not result.is_crisis:
            rag = p._get_rag()
            passages = getattr(rag, "_last_passages", None)
            if passages:
                with st.expander(f"Retrieved passages ({len(passages)})"):
                    for i, passage in enumerate(passages, 1):
                        st.caption(f"Passage {i}")
                        preview = passage[:500] + "…" if len(passage) > 500 else passage
                        st.text(preview)


# ---------------------------------------------------------------------------
# Profile tab
# ---------------------------------------------------------------------------

def _profile_tab():
    if not st.session_state.get("user"):
        st.info("Log in or register in the sidebar first.")
        return

    user = st.session_state["user"]
    st.subheader("User profile")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Registration fields**")
        st.metric("Age", user.age)
        st.metric("Mood baseline", f"{user.mood_baseline}/10")
        if user.country:
            st.write(f"Country: {user.country}")
        st.write("**Goals**")
        for g in user.goals:
            st.write(f"- {g}")

    with col2:
        st.markdown("**Passively extracted fields**")
        rows = [
            ("Job", user.job),
            ("Relationship status", user.relationship_status),
        ]
        for label, value in rows:
            if value:
                st.write(f"- {label}: **{value}**")
            else:
                st.write(f"- {label}: _not yet extracted_")

        if user.profile_complete:
            st.success("Profile complete")
        else:
            missing = sum(1 for _, v in rows if v is None)
            st.warning(f"{missing} field(s) not yet extracted from conversation")

    with st.expander("Profile block injected into system prompt"):
        from chat_pipeline import _build_profile_block
        st.text(_build_profile_block(user))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_auth_sidebar()

if st.session_state.get("user"):
    tab_chat, tab_compare, tab_profile = st.tabs(["Chat", "Compare", "Profile"])
    with tab_chat:
        _chat_tab()
    with tab_compare:
        _compare_tab()
    with tab_profile:
        _profile_tab()
else:
    st.markdown("## PFA Testing UI")
    st.write("Log in or create an account in the sidebar to get started.")
