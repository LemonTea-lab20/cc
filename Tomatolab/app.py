import base64
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from auth_gate import security_gate
from sheets_utils import save_log_to_sheet
import os, base64

# ==============================================================================
# 0. 基本設定
# ==============================================================================
st.set_page_config(
    layout="wide",
    page_title="Tomato AI",
    initial_sidebar_state="collapsed",
)
load_dotenv()

ACCENT_COLOR = "#00C8FF"
MAX_CHAT_LIMIT = 5
MAX_IMAGE_LIMIT = 2

BASE_DIR = Path(__file__).parent
PARTICLE_IMG_DARK = "ro.png"  
PARTICLE_IMG_LIGHT = "ba.png"  
WALLPAPER_IMG_DARK = None     
WALLPAPER_IMG_LIGHT = None

security_gate() 

# ==============================================================================
# セッション初期化
# ==============================================================================
if "chat_count" not in st.session_state:
    st.session_state.chat_count = 0
if "image_count" not in st.session_state:
    st.session_state.image_count = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

license_type = st.session_state.license_type  # "student" or "admin"
student_id = st.session_state.student_id

# OpenAI クライアント準備
try:
    from openai import OpenAI

    api_key = st.secrets.get("OPENAI_API_KEY")
    has_openai_lib = True
except ImportError:
    has_openai_lib = False
    api_key = None


# ==============================================================================
# 3. 画像読み込み（粒子用/壁紙用）
# ==============================================================================
def get_image_base64(filename: str) -> str:
    """
    app.py と同じフォルダ、または相対パスで指定された画像を
    base64 data URL に変換して返す。
    """
    if not filename:
        return ""
    full_path = BASE_DIR / filename
    if full_path.exists():
        with open(full_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    print(f"[WARN] image not found: {full_path}")
    return ""


# ==============================================================================
# 4. サイドバー
# ==============================================================================
def toggle_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode


with st.sidebar:
    st.title("　ㅇࡇㅇ?　")
    st.markdown(f"**ID:** `{student_id}`")

    license_label = "ADMIN" if license_type == "admin" else "STUDENT"
    st.markdown(f"**License:** `{license_label}`")

    # usage_count は auth_gate 側で初期化・更新される
    remaining = MAX_CHAT_LIMIT - st.session_state.get("usage_count", 0)
    if remaining < 0:
        remaining = 0
    if license_type == "admin":
        st.metric("Remaining Chats", "∞")
    else:
        st.metric("Remaining Chats", f"{remaining} / {MAX_CHAT_LIMIT}")

    is_dark_mode = st.toggle(
        "Dark Mode",
        value=st.session_state.dark_mode,
        key="mode_toggle",
        on_change=toggle_mode,
    )

    st.divider()
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        st.image(uploaded_file, caption="Preview", use_column_width=True)

    if st.button("Logout"):
        st.session_state.messages = []
        st.session_state.logged_in = False
        st.session_state.student_id = None
        st.session_state.license_type = "student"
        st.rerun()


# ==============================================================================
# 5. 背景（パーティクル＋CSS）
# ==============================================================================
if st.session_state.dark_mode:
    particle_src = get_image_base64(PARTICLE_IMG_DARK)
    wallpaper_src = get_image_base64(WALLPAPER_IMG_DARK) if WALLPAPER_IMG_DARK else ""
    bg_color = "#000000"
    p_color_main = "#ffffff"
    p_color_sub = "#444444"
    css_text_color = "#eeeeee"
    css_bg_rgba = "rgba(0, 0, 0, 0.6)"
    css_input_bg = "rgba(10, 10, 10, 0.9)"
    css_border_color = "rgba(255, 255, 255, 0.1)"
    css_mask_color = "#000000"
else:
    particle_src = get_image_base64(PARTICLE_IMG_LIGHT)
    wallpaper_src = get_image_base64(WALLPAPER_IMG_LIGHT) if WALLPAPER_IMG_LIGHT else ""
    bg_color = "#ffffff"
    p_color_main = "#000000"
    p_color_sub = "#cccccc"
    css_text_color = "#333333"
    css_bg_rgba = "rgba(255, 255, 255, 0.7)"
    css_input_bg = "rgba(245, 245, 245, 0.95)"
    css_border_color = "rgba(0, 0, 0, 0.1)"
    css_mask_color = "#ffffff"

if wallpaper_src:
    bg_style = (
        f"background-image: url('{wallpaper_src}');"
        "background-size: cover; background-position: center;"
    )
else:
    bg_style = f"background-color: {bg_color};"

html_template = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>
        body { margin: 0; overflow: hidden; width: 100vw; height: 100vh; __BG_STYLE__ transition: background 0.5s ease; }
        canvas { display: block; width: 100%; height: 100%; }
    </style>
</head>
<body>
    <canvas id="canvas"></canvas>
   ＃＃粒子
    <script>
        const CONFIG = {
            particleSize: 4,
            particleMargin: 1,
            repulsionRadius: 80,
            repulsionForce: 3.0,
            friction: 0.12,
            returnSpeed: 0.02,
            samplingStep: 2,
            maxDisplayRatio:0.65
        };
        let particles = [], mouse = { x: -1000, y: -1000 };
        const canvas = document.getElementById('canvas'), ctx = canvas.getContext('2d');
        const imageSrc = "__PARTICLE_SRC__";
        class Particle {
            constructor(x, y, colorType) {
                this.originalX = x; this.originalY = y;
                this.x = x; this.y = y;
                this.vx = 0; this.vy = 0;
                this.baseColor = colorType === 'main' ? '__P_COLOR_1__' : '__P_COLOR_2__';
            }
            update() {
                const dx = this.x - mouse.x, dy = this.y - mouse.y;
                const dist = Math.sqrt(dx*dx + dy*dy);
                if (dist < CONFIG.repulsionRadius) {
                    const angle = Math.atan2(dy, dx);
                    const force = (CONFIG.repulsionRadius - dist) / CONFIG.repulsionRadius;
                    const rep = force * force * CONFIG.repulsionForce;
                    this.vx += Math.cos(angle) * rep;
                    this.vy += Math.sin(angle) * rep;
                }
                this.vx += (this.originalX - this.x) * CONFIG.returnSpeed;
                this.vy += (this.originalY - this.y) * CONFIG.returnSpeed;
                this.vx *= (1 - CONFIG.friction);
                this.vy *= (1 - CONFIG.friction);
                this.x += this.vx;
                this.y += this.vy;
            }
            draw() {
                ctx.fillStyle = this.baseColor;
                ctx.beginPath();
                ctx.arc(this.x, this.y, CONFIG.particleSize/2, 0, Math.PI*2);
                ctx.fill();
            }
        }
        function init() {
            window.addEventListener('resize', resize);
            window.addEventListener('mousemove', e => {
                mouse.x = e.clientX; mouse.y = e.clientY;
            });
            window.addEventListener('touchmove', e => {
                mouse.x = e.touches[0].clientX; mouse.y = e.touches[0].clientY;
            });
            if (imageSrc) {
                const img = new Image();
                img.src = imageSrc;
                img.onload = () => { resize(); generateParticles(img); };
            }
        }
        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        function generateParticles(img) {
            particles = [];
            const temp = document.createElement('canvas');
            const tCtx = temp.getContext('2d');
            const tW = window.innerWidth * CONFIG.maxDisplayRatio;
            const tH = window.innerHeight * CONFIG.maxDisplayRatio;
            const scale = Math.min(tW / img.width, tH / img.height);
            const w = Math.floor(img.width * scale);
            const h = Math.floor(img.height * scale);
            temp.width = w; temp.height = h;
            tCtx.drawImage(img, 0, 0, w, h);
            const data = tCtx.getImageData(0, 0, w, h).data;
            const offX = (window.innerWidth - w) / 2;
            const offY = (window.innerHeight - h) / 2;
            for (let y = 0; y < h; y += CONFIG.samplingStep) {
                for (let x = 0; x < w; x += CONFIG.samplingStep) {
                    const i = (y * w + x) * 4;
                    if (data[i + 3] > 128) {
                        const b = (data[i] + data[i+1] + data[i+2]) / 3;
                        particles.push(new Particle(x+offX, y+offY, b > 128 ? 'main' : 'sub'));
                    }
                }
            }
            animate();
        }
        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach(p => { p.update(); p.draw(); });
            requestAnimationFrame(animate);
        }
        init();
    </script>
</body>
</html>
"""

final_html = (
    html_template
    .replace("__PARTICLE_SRC__", particle_src)
    .replace("__BG_STYLE__", bg_style)
    .replace("__P_COLOR_1__", p_color_main)
    .replace("__P_COLOR_2__", p_color_sub)
)
components.html(final_html, height=0)

st.markdown(f"""
<style>
    iframe[data-testid="stIFrame"] {{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 0 !important;
        border: none !important;
        pointer-events: auto !important;
    }}

    .stApp {{ background: transparent !important; }}
    header, header > div {{ background: transparent !important; }}

    button[data-testid="stSidebarCollapsedControl"] {{
        color: {css_text_color} !important;
        background-color: {css_bg_rgba} !important;
        border-radius: 5px;
        margin-top: 10px; margin-left: 10px;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {css_input_bg} !important;
        border-right: 1px solid {css_border_color};
    }}
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {{
        color: {css_text_color} !important;
    }}
    .title-mask {{
        position: fixed; top: 0; left: 0;
        width: 100%; height: 120px;
        background: {css_mask_color};
        z-index: 998; pointer-events: none;
        background: linear-gradient(to bottom, {css_mask_color} 80%, transparent);
    }}
    h1 {{
        position: fixed !important;
        top: 30px; left: 60px; margin: 0 !important;
        font-family: 'Arial', sans-serif;
        font-weight: 900; font-size: 2.5rem !important;
        letter-spacing: 2px;
        color: {css_text_color} !important;
        text-shadow: 0 0 10px rgba(128,128,128,0.3);
        z-index: 1000; pointer-events: none;
    }}
    div[data-testid="stBottom"] {{
        background: {css_mask_color} !important;
        border-top: none {css_border_color};
        z-index: 998;
        padding-top: 20px; padding-bottom: 20px;
    }}
    div[data-testid="stBottom"] > div {{
        background: transparent !important;
    }}
    div[data-testid="stChatInput"] {{
        width: 60% !important;
        margin: 0 auto !important;
        position: relative; z-index: 1000;
    }}
    .stTextInput input, .stTextInput textarea {{
        background-color: {css_input_bg} !important;
        color: {css_text_color} !important;
        border: 1px solid {css_border_color} !important;
        border-radius: 12px !important;
    }}
    .block-container {{
        padding-top: 140px !important;
        padding-bottom: 120px !important;
        pointer-events: none;
    }}
    div[data-testid="stChatMessage"] {{
        background-color: {css_bg_rgba} !important;
        border: 1px solid {css_border_color};
        border-left: 3px solid {ACCENT_COLOR} !important;
        border-radius: 4px;
        backdrop-filter: blur(5px);
        width: 70%; margin: 0 auto;
        position: relative; z-index: 997;
        pointer-events: none !important;
    }}
    div[data-testid="stChatMessage"] div,
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] code {{
        color: {css_text_color} !important;
        pointer-events: auto !important;
    }}
    .katex {{ color: {css_text_color} !important; pointer-events: auto !important; }}
    .katex-display {{ pointer-events: auto !important; }}
    .prts-status {{
        position: fixed !important;
        bottom: 20px; right: 30px;
        font-family: 'Courier New', monospace;
        color: {css_text_color} !important;
        z-index: 1000;
        pointer-events: none;
        text-align: right; font-size: 0.8em;
        opacity: 0.8;
    }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 6. チャットUI
# ==============================================================================
st.markdown('<div class="title-mask"></div>', unsafe_allow_html=True)
st.title("TOMATO LAB NETWORK ")

license_label = "ADMIN" if license_type == "admin" else "STUDENT"
status_text = (
    f"Agent ID: {student_id}\n"
    f"License: {license_label}\n"
    f"Img: {MAX_IMAGE_LIMIT - st.session_state.image_count} | "
    f"Chat: {MAX_CHAT_LIMIT - st.session_state.get('usage_count', 0)}\n"
    f"Ver 20.0.0 // PRTS Online"
)
st.markdown(
    f'<div class="prts-status" style="white-space: pre-line;">{status_text}</div>',
    unsafe_allow_html=True,
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("type") == "image":
            st.image(msg["content"])
        else:
            st.markdown(msg["content"])

IMG_PASSWORD = st.secrets.get("IMG_PASSWORD", None)

if prompt := st.chat_input("Command..."):
    is_gen_img_req = prompt.startswith("/img ")
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_file and not is_gen_img_req:
            st.image(uploaded_file, caption="Visual Data", width=200)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        ai_response_content = ""

        # 使用回数・画像回数チェック
        if is_gen_img_req and st.session_state.image_count >= MAX_IMAGE_LIMIT:
            error_msg = "⚠️ Image generation limit reached."
            message_placeholder.error(error_msg)
            ai_response_content = error_msg

        elif (
            not is_gen_img_req
            and license_type != "admin"
            and st.session_state.get("usage_count", 0) >= MAX_CHAT_LIMIT
        ):
            error_msg = "⚠️ Daily chat limit reached. (本日の制限回数を超えました)"
            message_placeholder.error(error_msg)
            ai_response_content = error_msg

                elif api_key and has_openai_lib:
            try:
                client = OpenAI(api_key=api_key)

                # ===== 画像生成モード =====
                if is_gen_img_req:

                    def has_img_key(text: str) -> bool:
                        if not IMG_PASSWORD:
                            return False
                        key1 = f"key:{IMG_PASSWORD}"
                        key2 = f"キー:{IMG_PASSWORD}"
                        return (key1 in text) or (key2 in text)

                    if not has_img_key(prompt):
                        error_msg = "🔒 画像生成キーが正しくありません。"
                        message_placeholder.error(error_msg)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": error_msg}
                        )
                        ai_response_content = error_msg
                    else:
                        clean = prompt
                        if IMG_PASSWORD:
                            clean = clean.replace(f"key:{IMG_PASSWORD}", "")
                            clean = clean.replace(f"キー:{IMG_PASSWORD}", "")
                        clean_prompt = clean.replace("/img", "").strip()

                        message_placeholder.markdown(
                            f"Generating visual data for '{clean_prompt}'..."
                        )
                        response = client.images.generate(
                            model="dall-e-3",
                            prompt=f"Arknights style, anime art, {clean_prompt}",
                            size="1024x1024",
                            quality="standard",
                            n=1,
                        )
                        image_url = response.data[0].url
                        message_placeholder.empty()
                        st.image(image_url, caption=f"Generated: {clean_prompt}")
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": image_url,
                                "type": "image",
                            }
                        )
                        st.session_state.image_count += 1
                        ai_response_content = f"<Image Generated: {image_url}>"

                # ===== 通常チャットモード =====
                else:
                    # ここで先生モード / 生徒モードで性格を分岐
                    if license_type == "admin":
                        # 先生モード
                        system_prompt = """
あなたは中学校教員のための授業設計・教材作成支援AI「Mr.トマト（先生モード）」です。

- 相手は中学校の先生が想定される。専門的な用語を使ってよいが、必要に応じて簡単な説明もそえる。
- 授業アイデア・ワークシート・評価規準・コメント文など、教員向けのアウトプットを丁寧に提案する。
- 生徒情報や個人情報に関わる内容は、具体名を出さずに一般化した形でアドバイスする。
- 文章のトーンは「落ち着いた大人向け」で、敬体（です・ます）を基本とする。
- Helpful, logical, concise. Use $...$ for math equations.
"""
                    else:
                        # 生徒モード
                        system_prompt = """
あなたは中学校の授業で使う学習支援AI「Mr.トマト」です。

- 口調は丁寧だがフランクで、中学生にもわかりやすい表現を使う。
- 回答は基本的に日本語で行う（ユーザーが英語で質問したときは英語も可）。
- 宿題やテスト問題は、答えだけではなく「考え方のステップ」を重視して説明する。
- 暴力・差別・個人情報など、不適切な内容には丁寧にお断りし、安全な話題や学びに誘導する。
- Helpful, logical, concise. Use $...$ for math equations。
"""

                    messages_payload = [
                        {"role": "system", "content": system_prompt}
                    ]
                    for m in st.session_state.messages:
                        if m.get("type") != "image":
                            messages_payload.append(
                                {"role": m["role"], "content": m["content"]}
                            )

                    if uploaded_file:
                        b64_img = base64.b64encode(
                            uploaded_file.read()
                        ).decode("utf-8")
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_img}"
                                },
                            },
                        ]
                        messages_payload.pop()
                        messages_payload.append(
                            {"role": "user", "content": user_content}
                        )

                    stream = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_payload,
                        stream=True,
                    )
                    for chunk in stream:
                        if chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_response}
                    )

                    if license_type == "student":
                        st.session_state["usage_count"] = (
                            st.session_state.get("usage_count", 0) + 1
                        )
                        if student_id:
                            save_log_to_sheet(student_id, prompt, full_response)

                    ai_response_content = full_response

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                message_placeholder.error(error_msg)
                ai_response_content = error_msg
