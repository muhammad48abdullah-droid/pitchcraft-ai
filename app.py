"""PitchCraft AI: turn a one-sentence business idea into a 5-section pitch deck with Gemini."""

import base64
import json
import math
import os
import re
import time
from datetime import datetime
from html import escape

import streamlit as st
from google import genai
from google.genai import errors, types

# Tried in order. If one is overloaded (503) or retired (404), the app moves to the next.
# Google renames/retires models often. To switch models without touching this code, add
# GEMINI_MODEL = "model-name" to your Streamlit Secrets; it is tried first.
DEFAULT_MODEL_CHAIN = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]
RETRYABLE_CODES = {429, 500, 502, 503, 504}
ATTEMPTS_PER_MODEL = 3
BASE_DELAY_SECONDS = 2
MAX_IDEA_CHARS = 300

SECTIONS = [
    ("problem_statement", "1. Problem Statement", "🎯"),
    ("unique_solution", "2. Unique Solution", "💡"),
    ("target_market_analysis", "3. Target Market Analysis", "📊"),
    ("monetization_revenue_model", "4. Monetization & Revenue Model", "💰"),
    ("tagline_and_slogan", "5. Catchy Tagline & Marketing Slogan", "🚀"),
]

PROMPT_TEMPLATE = """You are an experienced startup advisor and pitch-deck writer.
A founder gave you this rough business idea:

\"\"\"{idea}\"\"\"

Write a professional, specific, investor-ready 5-section pitch. Where the idea
mentions a place, tailor the content to that local context (population, habits,
competition, pricing in local currency). Do not invent precise statistics;
use estimates and label them as estimates.

Respond with ONLY a JSON object (no markdown fences) with exactly these keys:
{{
  "startup_name": "a short, memorable name for the startup",
  "problem_statement": "2-3 short paragraphs or bullet lines on the pain point",
  "unique_solution": "what the product is, how it works, and why it is better than alternatives",
  "target_market_analysis": "customer segments, estimated market size, and key competitors",
  "monetization_revenue_model": "revenue streams, pricing ideas, and cost/margin notes",
  "tagline_and_slogan": "one catchy tagline on the first line, then 2 alternative marketing slogans"
}}
Every value must be a plain string. Use "- " for bullet points and no markdown headings."""

# --------------------------------------------------------------------------------------
# Styling (blueprint / electric-blue look)
# --------------------------------------------------------------------------------------

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Space+Mono:wght@400;700&display=swap');
:root { --blue:#0000F2; --line:rgba(255,255,255,.30); --dim:rgba(255,255,255,.78); }
#MainMenu, footer, header, .stAppHeader, .stApp > header, [data-testid="stHeader"], [data-testid="stAppHeader"], [data-testid="stToolbar"], [data-testid="stAppToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none !important; visibility:hidden !important; height:0 !important; min-height:0 !important; border:0 !important; box-shadow:none !important; background:transparent !important; } [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main, .stApp { background-color:var(--blue) !important; border-top:0 !important; } [data-testid="stMainBlockContainer"], .block-container { padding-top:0 !important; }
.stApp { background-color:var(--blue);
  background-image:linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px),linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px);
  background-size:40px 40px; color:#fff; font-family:'Space Mono', monospace; }
.block-container { max-width:1180px; padding:0 2rem 4rem 2rem !important; }
.stApp p, .stApp li, .stApp label, .stApp span, .stApp div { font-family:'Space Mono', monospace; }

.nav { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; padding:1.5rem 2rem; margin:0 -2rem 3rem -2rem; border-bottom:1px solid var(--line); }
.nav-l { display:flex; gap:1.6rem; font-size:.78rem; font-weight:700; letter-spacing:.08em; }
.nav-c { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; text-align:center; font-size:1.9rem; line-height:1.05; letter-spacing:.05em; text-transform:uppercase; }
.nav-c span { display:block; font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:1.25rem; color:#d6d6ff; }
.nav-r { display:flex; justify-content:flex-end; }
.nav-btn { background:#fff; color:var(--blue); padding:.7rem 1.1rem; font-size:.78rem; font-weight:700; letter-spacing:.08em; box-shadow:3px 3px 0 rgba(0,0,0,.35); }

.tag { display:inline-block; border:1px solid var(--line); background:rgba(255,255,255,.12); padding:.4rem .75rem; font-size:.7rem; font-weight:700; letter-spacing:.1em; margin-bottom:1.3rem; }
.hero-title { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:clamp(3.2rem, 7vw, 5.8rem); line-height:.98; text-transform:uppercase; margin:0 0 1.5rem 0; color:#fff; }
.hero-sub { border-left:1px solid rgba(255,255,255,.6); padding-left:1rem; color:#d8d8ff; font-size:1rem; line-height:1.6; max-width:30rem; margin-bottom:2.2rem; }

div[data-testid="stTextInput"] label p { text-transform:uppercase; letter-spacing:.1em; font-size:.75rem !important; font-weight:700; color:#fff !important; }
div[data-baseweb="input"], div[data-baseweb="base-input"] { background:rgba(0,0,0,.18) !important; border-radius:0 !important; }
div[data-baseweb="input"] { border:1px solid rgba(255,255,255,.65) !important; }
div[data-baseweb="input"]:focus-within { border-color:#fff !important; box-shadow:0 0 0 1px #fff !important; }
div[data-baseweb="input"] input { background:transparent !important; color:#fff !important; -webkit-text-fill-color:#fff !important; font-family:'Space Mono', monospace !important; }
div[data-baseweb="input"] input::placeholder { color:rgba(255,255,255,.55) !important; -webkit-text-fill-color:rgba(255,255,255,.55) !important; }
div[data-testid="stTextInputRootElement"] { border-radius:0 !important; }
div[data-testid="InputInstructions"], div[data-testid="InputInstructions"] * { color:var(--dim) !important; }

div[data-testid="stButton"], div[data-testid="stDownloadButton"] { width:100%; }
div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button { width:100%; background:#fff !important; color:var(--blue) !important; border:1px solid #fff !important; border-radius:0 !important; padding:.75rem 1.2rem; box-shadow:4px 4px 0 rgba(0,0,0,.4); transition:transform .1s, box-shadow .1s; }
div[data-testid="stButton"] button p, div[data-testid="stDownloadButton"] button p { color:var(--blue) !important; font-family:'Space Mono', monospace !important; font-weight:700 !important; text-transform:uppercase; letter-spacing:.08em; }
div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover { transform:translate(2px,2px); box-shadow:2px 2px 0 rgba(0,0,0,.4); background:#fff !important; border-color:#fff !important; }
div[data-testid="stButton"] button:active, div[data-testid="stDownloadButton"] button:active { transform:translate(4px,4px); box-shadow:0 0 0 rgba(0,0,0,.4); }

div[data-testid="stAlert"] { background:rgba(0,0,0,.30) !important; border:1px solid #fff !important; border-radius:0 !important; }
div[data-testid="stAlert"] * { color:#fff !important; }
div[data-testid="stSpinner"], div[data-testid="stSpinner"] * { color:#fff !important; }
div[data-testid="stCaptionContainer"], div[data-testid="stCaptionContainer"] * { color:var(--dim) !important; }

.blueprint { border:1px solid var(--line); padding:1rem; background:rgba(0,0,0,.08); }
.blueprint img { width:100%; display:block; }

.result-wrap { margin-top:3.5rem; border-top:1px solid var(--line); padding-top:2.5rem; }
.startup-name { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:clamp(2.6rem, 6vw, 4.8rem); line-height:1; text-transform:uppercase; margin:.2rem 0 .8rem 0; }
.idea-line { border-left:1px solid rgba(255,255,255,.6); padding-left:1rem; color:#d8d8ff; margin-bottom:2rem; }
.cards { display:grid; grid-template-columns:repeat(2, 1fr); gap:1.3rem; margin-bottom:2rem; }
.card { border:1px solid var(--line); background:rgba(0,0,0,.16); padding:1.3rem 1.5rem; }
.card-head { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:1.6rem; text-transform:uppercase; letter-spacing:.03em; line-height:1.1; margin-bottom:.9rem; }
.card-head .idx { font-family:'Space Mono', monospace !important; font-size:.75rem; font-weight:700; letter-spacing:.1em; display:block; color:#cfcfff; margin-bottom:.35rem; }
.card-body { font-size:.92rem; line-height:1.65; }
.card-body p { margin:0 0 .7rem 0; }
.card-body ul { margin:0 0 .7rem 0; padding-left:1.2rem; }
.card-body li { margin-bottom:.35rem; }
.card.accent { grid-column:1 / -1; background:#fff; color:var(--blue); box-shadow:6px 6px 0 rgba(0,0,0,.35); }
.card.accent .card-head, .card.accent .card-head .idx, .card.accent .card-body, .card.accent .card-body * { color:var(--blue) !important; }

.nav a { color:#fff !important; text-decoration:none !important; }
.nav a:hover { opacity:.75; }
.nav-r { align-items:center; gap:1.6rem; font-size:.78rem; font-weight:700; letter-spacing:.08em; }
.nav a.nav-btn { color:var(--blue) !important; opacity:1; }
.cmd-label { font-size:.7rem; font-weight:700; letter-spacing:.1em; margin:2.2rem 0 .6rem 0; color:var(--dim); }
.cmd { border:1px solid var(--line); background:rgba(0,0,0,.22); padding:.9rem 1rem; font-size:.85rem; line-height:1.9; }
.cmd .p { color:#8f8fff; margin-right:.6rem; }
.sec { margin-top:5rem; border-top:1px solid var(--line); padding-top:2.5rem; }
.sec-title { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:clamp(2.4rem, 5vw, 3.8rem); text-transform:uppercase; line-height:1; margin:0 0 2rem 0; }
.feat-grid { display:grid; grid-template-columns:repeat(6, 1fr); gap:1.3rem; }
.feat { grid-column:span 2; border:1px solid var(--line); background:rgba(0,0,0,.16); padding:1.4rem 1.5rem 1.6rem 1.5rem; }
.feat:nth-child(n+4) { grid-column:span 3; }
.feat .num { display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.1em; border:1px solid var(--line); background:rgba(255,255,255,.12); padding:.25rem .55rem; margin-bottom:1.2rem; }
.feat h3 { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:1.7rem; text-transform:uppercase; line-height:1.1; margin:0 0 .7rem 0; padding:0; color:#fff; }
.feat p { font-size:.9rem; line-height:1.65; color:#e4e4ff; margin:0; }
.faq details { border-top:1px solid var(--line); padding:1.2rem 0; }
.faq details:last-child { border-bottom:1px solid var(--line); }
.faq summary { cursor:pointer; list-style:none; display:flex; justify-content:space-between; align-items:center; gap:1rem; font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:1.5rem; text-transform:uppercase; letter-spacing:.02em; }
.faq summary::-webkit-details-marker { display:none; }
.faq summary::after { content:'+'; font-family:'Space Mono', monospace; font-size:1.6rem; }
.faq details[open] summary::after { content:'–'; }
.faq details p { margin:.9rem 0 0 0; max-width:46rem; line-height:1.7; color:#e4e4ff; font-size:.92rem; }
.footer { margin-top:5rem; border-top:1px solid var(--line); padding-top:2rem; }
.foot-word { font-family:'Anton', Impact, 'Arial Narrow', sans-serif !important; font-size:clamp(3.5rem, 13vw, 10rem); line-height:.95; text-transform:uppercase; letter-spacing:.02em; }
.foot-row { display:flex; justify-content:space-between; flex-wrap:wrap; gap:.8rem; margin-top:1.5rem; font-size:.72rem; font-weight:700; letter-spacing:.1em; color:var(--dim); }

@media (max-width:720px) { .nav { grid-template-columns:1fr; } .nav-l, .nav-r { display:none; } .cards { grid-template-columns:1fr; } .feat, .feat:nth-child(n+4) { grid-column:1 / -1; } .feat-grid { grid-template-columns:1fr; } }
"""

NAV_HTML = (
    '<div class="nav">'
    '<div class="nav-l"><span>IDEA → PITCH</span><span>EXPORT .TXT</span></div>'
    '<div class="nav-c">PITCHCRAFT<span>AI</span></div>'
    '<div class="nav-r"><a href="#features">FEATURES</a><a href="#faq">FAQ</a>'
    '<a class="nav-btn" href="#generate">GENERATE PITCH</a></div>'
    "</div>"
)

HERO_HTML = (
    '<div class="tag" id="generate">PITCHCRAFT AI // STARTUP PITCH GENERATOR</div>'
    '<div class="hero-title">One line.<br>Full pitch<br>deck.</div>'
    '<div class="hero-sub">Describe your idea in a single sentence. Gemini drafts the problem, '
    "solution, market, revenue model and tagline for you.</div>"
)


EXAMPLES_HTML = (
    '<div class="cmd-label">TRY AN IDEA LIKE</div>'
    '<div class="cmd">'
    '<div><span class="p">$</span>An app for renting bicycles in Lahore</div>'
    '<div><span class="p">$</span>A cookies branch in Peshawar</div>'
    '<div><span class="p">$</span>A tutoring marketplace for university students</div>'
    "</div>"
)

FEATURES = [
    ("#1 Problem", "Sharp Problem Statement",
     "Names the real pain point your customers feel, framed the way investors expect to hear it."),
    ("#2 Solution", "Unique Solution",
     "Explains what you are building, how it works, and why it beats the alternatives."),
    ("#3 Market", "Target Market Analysis",
     "Customer segments, estimated market size, and the competitors you will face, tailored to your city or region."),
    ("#4 Revenue", "Monetization & Revenue",
     "Revenue streams, pricing ideas, and margin notes you can pressure-test before you pitch."),
    ("#5 Brand", "Tagline & Slogans",
     "A catchy tagline plus alternative marketing slogans, ready to try out."),
]

FAQS = [
    ("How does PitchCraft AI work?",
     "You type your idea in one sentence. The app sends it to Google's Gemini model with a structured "
     "prompt and shows the five sections it returns. You can download them as a .txt file."),
    ("Is it free to use?",
     "Yes. The app runs on its owner's Gemini API key, so if many people use it at once you may see a "
     "&ldquo;busy&rdquo; message. Wait a minute and try again."),
    ("Are the market numbers real?",
     "No. Figures are AI estimates, not researched data. Treat the pitch as a strong first draft and "
     "verify every number before showing it to investors."),
    ("Is my idea saved?",
     "The app does not store ideas or pitches in a database. They exist only in your browser session. "
     "Your text is sent to Google's Gemini API to generate the pitch."),
    ("Can I get a different version?",
     "Yes. Generate again for a fresh take, or edit the downloaded text file to make it your own."),
]


def features_html() -> str:
    cards = "".join(
        f'<div class="feat"><span class="num">{escape(n)}</span><h3>{escape(t)}</h3><p>{escape(d)}</p></div>'
        for n, t, d in FEATURES
    )
    return f'<div class="sec" id="features"><div class="sec-title">Features</div><div class="feat-grid">{cards}</div></div>'


def faq_html() -> str:
    items = "".join(
        f"<details{' open' if i == 0 else ''}><summary>{q}</summary><p>{a}</p></details>"
        for i, (q, a) in enumerate(FAQS)
    )
    return f'<div class="sec" id="faq"><div class="sec-title">FAQs</div><div class="faq">{items}</div></div>'


def footer_html() -> str:
    year = datetime.now().year
    return (
        '<div class="footer"><div class="foot-word">PitchCraft</div>'
        '<div class="foot-row"><span>FROM ONE LINE TO A FULL PITCH</span>'
        f"<span>© {year} PITCHCRAFT AI · POWERED BY GOOGLE GEMINI</span></div></div>"
    )


def minify_css(css: str) -> str:
    """Collapse to one line: a blank line would end Streamlit's HTML block mid-stylesheet."""
    return re.sub(r"\s+", " ", css).strip()


def inject_css():
    st.markdown("<style>" + minify_css(CSS) + "</style>", unsafe_allow_html=True)


def blueprint_html() -> str:
    cx = cy = 200
    rays = "".join(
        f'<line x1="{cx}" y1="{cy}" '
        f'x2="{cx + 185 * math.cos(math.radians(i * 22.5)):.1f}" '
        f'y2="{cy + 185 * math.sin(math.radians(i * 22.5)):.1f}" opacity="0.35"/>'
        for i in range(16)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" fill="none" '
        'stroke="#ffffff" stroke-width="1">'
        '<rect x="10" y="10" width="380" height="380" opacity="0.5"/>'
        f"{rays}"
        '<circle cx="200" cy="200" r="150" stroke-dasharray="2 5" opacity="0.8"/>'
        '<circle cx="200" cy="200" r="105"/>'
        '<circle cx="200" cy="200" r="62" stroke-dasharray="4 4"/>'
        '<circle cx="200" cy="200" r="30"/>'
        '<polygon points="200,150 214,186 252,186 221,208 232,246 200,224 168,246 179,208 148,186 186,186" opacity="0.9"/>'
        '<text x="26" y="36" fill="#ffffff" stroke="none" font-family="monospace" font-size="10" opacity="0.75">MODEL: GEMINI</text>'
        '<text x="374" y="36" fill="#ffffff" stroke="none" font-family="monospace" font-size="10" opacity="0.75" text-anchor="end">[PITCHCRAFT-V1.0]</text>'
        '<text x="26" y="378" fill="#ffffff" stroke="none" font-family="monospace" font-size="10" opacity="0.75">IDEA → PROBLEM → SOLUTION → MARKET → REVENUE → TAGLINE</text>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<div class="blueprint"><img alt="" src="data:image/svg+xml;base64,{b64}"/></div>'


def inline_format(text: str) -> str:
    """Escape, then turn **bold** into <strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(text))


def body_to_html(text: str) -> str:
    """Convert Gemini's plain text (paragraphs and '- ' bullets) into safe HTML."""
    out, in_list = [], False
    for raw in as_text(text).splitlines():
        line = re.sub(r"^#+\s*", "", raw.strip())
        if not line:
            continue
        if line[:2] in ("- ", "* ", "• "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline_format(line[2:].strip())}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{inline_format(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


def results_html(idea: str, pitch: dict) -> str:
    cards = []
    for i, (key, title, _) in enumerate(SECTIONS, start=1):
        label = title.split(". ", 1)[1].upper()
        short = FEATURES[i - 1][0]
        accent = " accent" if i == len(SECTIONS) else ""
        cards.append(
            f'<div class="card{accent}"><div class="card-head">'
            f'<span class="idx">{escape(short.upper())}</span>{escape(label)}</div>'
            f'<div class="card-body">{body_to_html(pitch[key])}</div></div>'
        )
    name = escape(str(pitch.get("startup_name", "Your Startup")))
    return (
        '<div class="result-wrap">'
        '<div class="tag">GENERATED PITCH // 5 SECTIONS</div>'
        f'<div class="startup-name">{name}</div>'
        f'<div class="idea-line">IDEA: {escape(idea)}</div>'
        f'<div class="cards">{"".join(cards)}</div>'
        "</div>"
    )


# --------------------------------------------------------------------------------------
# Gemini
# --------------------------------------------------------------------------------------


def get_api_key():
    """Read the key from Streamlit secrets, falling back to an environment variable."""
    try:
        key = st.secrets["GEMINI_API_KEY"]
        if key:
            return str(key)
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


@st.cache_resource
def get_client(api_key: str):
    return genai.Client(api_key=api_key)


def get_model_chain():
    chain = list(DEFAULT_MODEL_CHAIN)
    override = None
    try:
        override = st.secrets.get("GEMINI_MODEL")
    except Exception:
        override = os.environ.get("GEMINI_MODEL")
    if override and str(override).strip():
        chain = [str(override).strip()] + [m for m in chain if m != str(override).strip()]
    return chain


def _clean_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _request_pitch(client, model: str, idea: str) -> dict:
    response = client.models.generate_content(
        model=model,
        contents=PROMPT_TEMPLATE.format(idea=idea),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    data = _clean_json(response.text)
    if not isinstance(data, dict):
        raise ValueError("Unexpected response format")
    missing = [k for k, _, _ in SECTIONS if not data.get(k)]
    if missing:
        raise ValueError(f"Response was missing sections: {', '.join(missing)}")
    return data


def generate_pitch(client, idea: str) -> dict:
    """Call Gemini with retries on overload (503/429) and fall back to other models."""
    last_error = None
    for model in get_model_chain():
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                return _request_pitch(client, model, idea)
            except errors.APIError as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                if code == 404:
                    break  # this model name isn't available; try the next one
                if code not in RETRYABLE_CODES:
                    raise  # e.g. 400 bad request / 403 bad key: retrying won't help
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc  # malformed output: just ask again
            if attempt < ATTEMPTS_PER_MODEL - 1:
                time.sleep(BASE_DELAY_SECONDS * (2**attempt))  # 2s, 4s
    raise last_error


def as_text(value) -> str:
    """Gemini occasionally returns a list instead of a string; normalise it."""
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value).strip()


def build_text_export(idea: str, pitch: dict) -> str:
    name = pitch.get("startup_name", "Your Startup")
    lines = [
        "=" * 60,
        f"PITCHCRAFT AI - PITCH DECK: {name}",
        "=" * 60,
        f"Original idea: {idea}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for key, title, _ in SECTIONS:
        lines += [title.upper(), "-" * len(title), as_text(pitch[key]), ""]
    lines.append("Generated by PitchCraft AI. AI output is a starting point; verify all figures.")
    return "\n".join(lines)


def safe_filename(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return f"{slug or 'pitch'}_pitch_deck.txt"


# --------------------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title="PitchCraft AI",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    st.markdown(NAV_HTML, unsafe_allow_html=True)

    api_key = get_api_key()
    if not api_key:
        st.error(
            "GEMINI_API_KEY is not set. Add it in Streamlit Cloud → App settings → Secrets, "
            "or in .streamlit/secrets.toml when running locally."
        )
        st.stop()
    client = get_client(api_key)

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.markdown(HERO_HTML, unsafe_allow_html=True)
        idea = st.text_input(
            "Your business idea (one sentence)",
            placeholder="An app for renting bicycles in Lahore",
            max_chars=MAX_IDEA_CHARS,
        )
        clicked = st.button("Generate pitch deck →", type="primary")

        if clicked:
            idea = idea.strip()
            if len(idea) < 8:
                st.warning("Please enter a business idea of at least a few words.")
            else:
                with st.spinner("Crafting your pitch..."):
                    try:
                        st.session_state["pitch"] = generate_pitch(client, idea)
                        st.session_state["idea"] = idea
                    except errors.APIError as exc:
                        code = getattr(exc, "code", None)
                        if code in RETRYABLE_CODES:
                            st.warning(
                                "Gemini is very busy right now (this is on Google's side, not "
                                "a problem with your app). Please wait a minute and try again."
                            )
                        elif code == 404:
                            st.error(
                                "None of the configured Gemini models are available. Google may "
                                "have renamed them. Add GEMINI_MODEL = \"gemini-3.5-flash\" (or a "
                                "current model from ai.google.dev/gemini-api/docs/models) to "
                                "your Streamlit Secrets."
                            )
                        else:
                            st.error(f"Generation failed: {exc}")
                    except (json.JSONDecodeError, ValueError):
                        st.error("Gemini returned an unexpected response. Please try again.")
                    except Exception as exc:
                        st.error(f"Generation failed: {exc}")

        st.markdown(EXAMPLES_HTML, unsafe_allow_html=True)

    with right:
        st.markdown(blueprint_html(), unsafe_allow_html=True)

    pitch = st.session_state.get("pitch")
    if pitch:
        saved_idea = st.session_state.get("idea", "")
        st.markdown(results_html(saved_idea, pitch), unsafe_allow_html=True)
        st.download_button(
            label="Download pitch (.txt)",
            data=build_text_export(saved_idea, pitch),
            file_name=safe_filename(pitch.get("startup_name", "pitch")),
            mime="text/plain",
        )
        st.caption("AI-generated content is a starting point. Verify market figures before presenting.")

    st.markdown(features_html() + faq_html() + footer_html(), unsafe_allow_html=True)


main()
