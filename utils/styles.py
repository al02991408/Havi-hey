import streamlit as st


def apply_custom_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&display=swap');

        :root {
            --creme: #fbf8f2;
            --white: #FFFFFF;
            --light-grey: #eeeef0;
            --charcoal: #212023;
            --muted: #49494e;
            --positive: #00b478;
            --negative: #fa94ae;
            --info: #a0cff0;
            --earth: #8b6f43;
            --clay: #964831;
            --navy: #2b497d;
            --olive: #546436;
            --journey-accent: #212023;
            --journey-surface: #fbf8f2;
            --journey-badge: #a0cff0;
        }

        .stApp {
            background: var(--creme);
            color: var(--charcoal);
            font-family: 'Inter', 'SF Pro Display', 'San Francisco', sans-serif;
        }

        .block-container {
            max-width: 1160px;
            padding-top: 0.65rem;
            padding-bottom: 1.6rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        [data-testid="stHeader"], footer {
            visibility: hidden;
        }

        .hero-wrap {
            padding: 0.15rem 0 0.75rem;
        }

        .hero-brand {
            color: var(--charcoal);
            font-size: 1rem;
            font-weight: 900;
            margin-bottom: 0.9rem;
        }

        .hero-headline {
            max-width: 820px;
            color: var(--charcoal);
            font-size: clamp(3.4rem, 7vw, 5.4rem);
            font-weight: 900;
            line-height: 0.92;
            letter-spacing: 0;
        }

        .hero-italic {
            font-style: italic;
            font-weight: 400;
        }

        .hero-subtitle {
            max-width: 680px;
            margin-top: 0.85rem;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.55;
        }

        .section-label {
            margin: 0.9rem 0 0.5rem;
            color: var(--charcoal);
            font-size: 0.88rem;
            font-weight: 700;
        }

        .kpi-card {
            background: var(--white);
            border-radius: 8px;
            padding: 0.85rem 0.95rem 0.8rem;
            border: 1px solid rgba(33, 32, 35, 0.06);
            border-bottom-width: 4px;
            min-height: 122px;
        }

        .kpi-positive {
            border-bottom-color: var(--positive);
        }

        .kpi-negative {
            border-bottom-color: var(--negative);
        }

        .kpi-info {
            border-bottom-color: var(--info);
        }

        .kpi-label {
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 0.28rem;
        }

        .kpi-value {
            color: var(--charcoal);
            font-size: 2.15rem;
            font-weight: 900;
            line-height: 1;
        }

        .kpi-delta {
            margin-top: 0.42rem;
            font-size: 0.82rem;
            color: var(--muted);
            line-height: 1.35;
        }

        .profile-card {
            background: var(--white);
            border: 1px solid rgba(33, 32, 35, 0.08);
            border-radius: 8px;
            padding: 1.1rem 1rem;
        }

        .profile-eyebrow {
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .profile-name {
            color: var(--charcoal);
            font-size: 1.32rem;
            font-weight: 900;
        }

        .profile-tier {
            color: var(--muted);
            font-size: 0.9rem;
            font-weight: 700;
            margin-top: 0.15rem;
        }

        .profile-status {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            margin: 0.8rem 0 0.65rem;
            padding: 0.38rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--charcoal);
            background: rgba(160, 207, 240, 0.22);
        }

        .status-dot {
            width: 9px;
            height: 9px;
            border-radius: 999px;
            background: currentColor;
            display: inline-block;
        }

        .profile-line {
            color: var(--muted);
            font-size: 0.88rem;
            line-height: 1.5;
        }

        .journey-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.34rem 0.72rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
            color: var(--charcoal);
            background: color-mix(in srgb, var(--journey-badge) 22%, white);
            border: 1px solid color-mix(in srgb, var(--journey-badge) 45%, white);
        }

        .tone-positive {
            color: #067552 !important;
            background: rgba(0, 180, 120, 0.14) !important;
        }

        .tone-negative {
            color: #b74d6a !important;
            background: rgba(250, 148, 174, 0.24) !important;
        }

        .tone-info {
            color: #36637d !important;
            background: rgba(160, 207, 240, 0.24) !important;
        }

        [data-testid="stChatMessage"] {
            background: transparent;
            border: none;
            box-shadow: none;
            padding: 0.1rem 0;
        }

        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            margin-left: auto;
            max-width: 82%;
        }

        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
            margin-right: auto;
            max-width: 86%;
        }

        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
            background: var(--light-grey);
            color: var(--charcoal);
            border: none;
            border-radius: 18px;
            padding: 0.9rem 1rem;
        }

        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"] {
            background: var(--white);
            color: var(--charcoal);
            border: 1px solid var(--info);
            border-radius: 18px;
            padding: 0.9rem 1rem;
        }

        [data-testid="stChatMessageAvatarUser"] + div {
            margin-left: auto;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] ol {
            color: var(--charcoal);
            line-height: 1.55;
        }

        [data-testid="stMarkdownContainer"] ul,
        [data-testid="stMarkdownContainer"] ol {
            margin-top: 0.15rem;
            margin-bottom: 0.3rem;
            padding-left: 1.1rem;
        }

        [data-testid="stDataFrame"], iframe {
            border-radius: 8px;
        }

        .stButton > button {
            min-height: 3rem;
            border-radius: 8px;
            border: 1px solid var(--journey-accent);
            background: var(--journey-surface);
            color: var(--journey-accent);
            font-weight: 700;
            transition: all 0.18s ease;
        }

        .stButton > button:hover {
            background: var(--journey-accent);
            color: var(--creme);
            border-color: var(--journey-accent);
        }

        [data-testid="stChatInput"] textarea {
            background: var(--white);
            color: var(--charcoal);
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }

            .hero-headline {
                font-size: 3.4rem;
            }

            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
            [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
                max-width: 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
