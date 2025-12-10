import base64
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from auth_gate import security_gate
from sheets_utils import save_log_to_sheet

# ==============================================================================
# 0. 基本設定
# ==============================================================================
st.set_page_config(
    layout="wide",
    page_title="Tomato",
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

IMG_PASSWORD = st.secrets.get("IMG_PASSWORD", None)


security_gate()  # ここで st.session_state.logged_in, student_id, license_type, usage_count などが入る想定

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
if "img_mode" not in st.session_state:
    st.session_state.img_mode = False
if "img_unlocked" not in st.session_state:
    st.session_state.img_unlocked = False

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
# 3. 画像読み込み
# ==============================================================================
def get_image_base64(filename: str) -> str:

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
    st.title("　ㅇ‐ㅇ?　")
    st.markdown(f"**ID:** `{student_id}`")

    license_label = "ADMIN" if license_type == "admin" else "STUDENT"
    st.markdown(f"**License:** `{license_label}`")

    remaining = MAX_CHAT_LIMIT - st.session_state.get("usage_count", 0)
    if remaining < 0:
        remaining = 0
    if license_type == "admin":
        st.metric("Remaining Chats", "∞")
    else:
        st.metric("Remaining Chats", f"{remaining} / {MAX_CHAT_LIMIT}")

    st.toggle(
        "Dark Mode",
        value=st.session_state.dark_mode,
        key="mode_toggle",
        on_change=toggle_mode,
    )

    st.divider()

    if IMG_PASSWORD:
        st.subheader("Image Mode")
        if not st.session_state.img_unlocked:
            st.caption("※画像生成を使うにはキー認証が必要です。")

            want_on = st.checkbox(
                "画像生成モード",
                value=False,
                key="img_mode_checkbox",
            )

            if want_on:
                key_input = st.text_input(
                    "画像生成キーを入力",
                    type="password",
                    key="img_key_input",
                )
                if key_input:
                    if key_input == IMG_PASSWORD:
                        st.session_state.img_unlocked = True
                        st.session_state.img_mode = True
                        st.success("画像生成モードが有効になりました。")
                    else:
                        st.session_state.img_mode = False
                        st.error("キーが違います。")
        else:
            st.session_state.img_mode = st.checkbox(
                "画像生成モード",
                value=st.session_state.img_mode,
                key="img_mode_checkbox",
            )
    else:
        st.session_state.img_mode = False
        st.session_state.img_unlocked = False

    st.divider()

    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        st.image(uploaded_file, caption="Preview", use_column_width=True)

    st.divider()

    if st.button("Logout"):
        st.session_state.messages = []
        st.session_state.logged_in = False
        st.session_state.student_id = None
        st.session_state.license_type = "student"
        st.rerun()


# ==============================================================================
# 5. CSS & HTML (Variables definition first!)
# ==============================================================================
# ★ここで変数を定義します（st.markdownより前に置く必要があります）
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

# --- 背景アニメーション HTML ---
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
    <script>
        const CONFIG = {
            particleSize: 5,
            particleMargin: 1,
            repulsionRadius: 80,
            repulsionForce: 2.5,
            friction: 0.12,
            returnSpeed: 0.015,
            samplingStep: 4,
            maxDisplayRatio: 0.7
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

# --- スタイル定義 (変数定義後に実行) ---
st.markdown(
    f"""
<style>
    /* iframe（背景）の設定 */
    iframe[data-testid="stIFrame"] {{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 0 !important;
        border: none !important;
        pointer-events: auto !important; /* ★ここを auto に戻しました（粒子が動くようになります） */
    }}

    /* 全体の背景透明化 */
    .stApp {{ background: transparent !important; }}
    header, header > div {{ background: transparent !important; }}

    /* サイドバー開閉ボタン */
    button[data-testid="stSidebarCollapsedControl"] {{
        color: {css_text_color} !important;
        background-color: {css_bg_rgba} !important;
        border-radius: 5px;
        margin-top: 10px; margin-left: 10px;
        z-index: 1001 !important;
    }}

    /* サイドバー本体 */
    section[data-testid="stSidebar"] {{
        background-color: {css_input_bg} !important;
        border-right: 1px solid {css_border_color};
    }}
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {{
        color: {css_text_color} !important;
    }}

    /* ヘッダー部分のマスク */
    .title-mask {{
        position: fixed; top: 0; left: 0;
        width: 100%; height: 80px; 
        background: {css_mask_color};
        background: linear-gradient(to bottom, {css_mask_color} 60%, transparent);
        z-index: 999; 
        pointer-events: none;
    }}

    /* タイトル文字 */
    h1 {{
        position: fixed !important;
        top: 15px; left: 60px;
        margin: 0 !important;
        font-family: 'Arial', sans-serif;
        font-weight: 900; font-size: 1.8rem !important;
        letter-spacing: 2px;
        color: {css_text_color} !important;
        text-shadow: 0 0 10px rgba(128,128,128,0.3);
        z-index: 1000; pointer-events: none;
    }}
    
    /* 入力欄の背景 */
    div[data-testid="stBottom"] {{
        background: linear-gradient(
            to top,
            {css_mask_color} 40%, 
            transparent 100%
        ) !important;
        z-index: 998;
        padding-bottom: 20px;
    }}

    div[data-testid="stBottom"] > div {{
        background: transparent !important;
    }}
    
    div[data-testid="stChatInput"] {{
        width: 70% !important;
        margin: 0 auto !important;
        position: relative; z-index: 1000;
    }}
    
    .stTextInput input, .stTextInput textarea {{
        background-color: {css_input_bg} !important;
        color: {css_text_color} !important;
        border: 1px solid {css_border_color} !important;
        border-radius: 12px !important;
    }}
    
    /* ★メインコンテナのレイアウト調整 */
    .block-container {{
        padding-top: 120px !important;
        padding-bottom: 240px !important; /* ★ここを増やしました（一番下のメッセージが上がります） */
        max-width: 900px !important;
        pointer-events: none;
    }}
    
    /* チャットメッセージ */
    div[data-testid="stChatMessage"] {{
        background-color: {css_bg_rgba} !important;
        border: 1px solid {css_border_color};
        border-left: 3px solid {ACCENT_COLOR} !important;
        border-radius: 4px;
        backdrop-filter: blur(5px);
        width: 80%; margin: 0 auto;
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
    
    /* ステータス表示 */
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
""",
    unsafe_allow_html=True,
)
# ==============================================================================
# 6. チャットUI
# ==============================================================================
st.markdown('<div class="title-mask"></div>', unsafe_allow_html=True)
st.title("TOMATO LAB ")

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

# ===== ユーザー入力 =====
prompt = st.chat_input("Command...")

if prompt:
    is_gen_img_req = bool(
        st.session_state.img_mode and st.session_state.img_unlocked
    )

    current_image_bytes = None
    if uploaded_file is not None:
        current_image_bytes = uploaded_file.getvalue()

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)
        if (not is_gen_img_req) and (current_image_bytes is not None):
            st.image(current_image_bytes, caption="Visual Data", width=200)

    if (not is_gen_img_req) and (current_image_bytes is not None):
        st.session_state.messages.append(
            {"role": "user", "content": current_image_bytes, "type": "image"}
        )

    # アシスタント側
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        ai_response_content = ""
        should_rerun = True

        if is_gen_img_req and st.session_state.image_count >= MAX_IMAGE_LIMIT:
            error_msg = "⚠️ Image generation limit reached."
            message_placeholder.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )
            ai_response_content = error_msg
            should_rerun = False  

        elif (
            not is_gen_img_req
            and license_type != "admin"
            and st.session_state.get("usage_count", 0) >= MAX_CHAT_LIMIT
        ):
            error_msg = "⚠️ Daily chat limit reached. (本日の制限回数を超えました)"
            message_placeholder.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg}
            )
            ai_response_content = error_msg
            should_rerun = False

        elif api_key and has_openai_lib:
            try:
                client = OpenAI(api_key=api_key)

                
                if is_gen_img_req:
                    clean_prompt = prompt.strip()

                    message_placeholder.markdown(
                        f"Generating visual data for '{clean_prompt}'..."
                    )

                
                    img_response = client.images.generate(
                        model="gpt-image-1",
                        prompt=f"Arknights style, anime art, {clean_prompt}",
                        size="1024x1024",
                        n=1,
                    )

                   
                    image_url = img_response.data[0].url

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
                    ai_response_content = "<Image Generated>"


                # ===== 通常チャットモード =====
                else:
                    if license_type == "admin":
                        system_prompt = """
- 相手は中学校の先生が想定される。専門的な用語を使ってよい。
- Helpful, logical, concise. Use $...$ for math equations.
"""
                    else:
                        system_prompt = """
あなたは中学校の授業で使う学習支援AI「Mr.トマト」です。
- 宿題やテスト問題は、答えだけではなく「考え方のステップ」を重視して説明する。
- 暴力・差別・個人情報など、不適切な内容には丁寧に断る。
- Helpful, logical, concise. Use $...$ for math equations.
"""

                
                    messages_payload = [{"role": "system", "content": system_prompt}]
                    for m in st.session_state.messages:
                        if m.get("type") != "image":
                            messages_payload.append(
                                {"role": m["role"], "content": m["content"]}
                            )

                    if current_image_bytes is not None:
                        b64_img = base64.b64encode(current_image_bytes).decode("utf-8")
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_img}"
                                },
                            },
                        ]
                       
                        if messages_payload and messages_payload[-1]["role"] == "user":
                            messages_payload[-1] = {
                                "role": "user",
                                "content": user_content,
                            }
                        else:
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

                    # ログ
                    if license_type == "student":
                        st.session_state["usage_count"] = (
                            st.session_state.get("usage_count", 0) + 1
                        )
                        if student_id:
                            save_log_to_sheet(student_id, prompt, full_response)

                    ai_response_content = full_response

            except Exception as e:
                # OpenAI エラー時もメッセージとして履歴に残す
                error_msg = f"Error: {str(e)}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
                ai_response_content = error_msg
                should_rerun = False  # エラー時は rerun しない

        # ③ OpenAI が使えないとき
        else:
            dummy_response = "PRTS Offline (API Key Missing)."
            message_placeholder.markdown(dummy_response)
            st.session_state.messages.append(
                {"role": "assistant", "content": dummy_response}
            )
            ai_response_content = dummy_response
            should_rerun = False  # これも rerun しなくてよい

    # 1回ごとに、正常なときだけ rerun する
    if should_rerun:
        time.sleep(0.5)
        st.rerun()
