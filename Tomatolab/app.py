import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx
import base64
import os
import time
import random
import logging
import datetime
import uuid
from dotenv import load_dotenv

# --- Google Sheets 連携用ライブラリ ---
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==============================================================================
# 0. 環境設定
# ==============================================================================
st.set_page_config(layout="wide", page_title="Tomato AI", initial_sidebar_state="collapsed")
load_dotenv()

# --- ログ保存用関数（完成版） ---
def save_log_to_sheet(student_id, input_text, output_text):
    """
    Googleスプレッドシートにログを追記する関数
    """
    try:
        # 1. 認証情報の準備
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Secretsから認証情報を取得
        # 注意: Secretsの設定名は [gcp_service_account] にしてください
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        # 2. シートを開く (※シート名は作成したものに合わせてください！)
        sheet = client.open("AI_Chat_Log").sheet1 

        # 3. 書き込むデータ
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 4. 行を追加
        sheet.append_row([now, student_id, input_text, output_text])
        # print(f"Log saved: {student_id}") # デバッグ用
        
    except Exception as e:
        # エラーが起きてもアプリは止めない（ログ失敗で授業を止めないため）
        print(f"Log Error: {e}")

# ==============================================================================
# 0.5. クッキーによる自動ID管理
# ==============================================================================
def get_cookie_manager():
    return stx.CookieManager()
    
cookie_manager = get_cookie_manager()
cookie_id = cookie_manager.get(cookie="student_uuid")

if not cookie_id:
    new_uuid = str(uuid.uuid4())[:8]
    expires_at = datetime.datetime.now() + datetime.timedelta(days=365)
    cookie_manager.set("student_uuid", new_uuid, expires_at=expires_at)
    cookie_id = new_uuid
    time.sleep(0.5)

st.session_state.student_id = cookie_id

# ==============================================================================
# 0.8. 門番（パスワード認証）
# ==============================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 SECURITY GATE")
    st.markdown(f"Device ID: `{st.session_state.student_id}`")
    st.caption("※端末固有IDにより自動識別中")

    correct_password = st.secrets.get("APP_PASSWORD", None)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        input_pass = st.text_input("Access Code", type="password")
    
    if st.button("CONNECT"):
        if not correct_password:
             st.error("Error: APP_PASSWORD not set in Secrets.")
        elif input_pass == correct_password:
            st.session_state.logged_in = True
            st.success("Access Granted.")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Invalid Code.")
    st.stop()

# ==============================================================================
# 1. メインアプリ設定
# ==============================================================================

current_dir = os.path.dirname(os.path.abspath(__file__))

PARTICLE_IMG_DARK = os.path.join(current_dir, "ro.png")
PARTICLE_IMG_LIGHT = os.path.join(current_dir, "ba.png")
WALLPAPER_IMG_DARK = None
WALLPAPER_IMG_LIGHT = None

# ↓ 修正: ランダム生成をやめて、Secretsの固定パスワードを使うように変更
def get_server_image_key():
    # secretsに設定がなければ "0000" になる
    key = st.secrets.get("IMG_PASSWORD", "9203")
    return key

IMAGE_KEY = get_server_image_key()
ACCENT_COLOR = "#00C8FF"
MAX_CHAT_LIMIT = 15
MAX_IMAGE_LIMIT = 5

if "chat_count" not in st.session_state: st.session_state.chat_count = 0
if "image_count" not in st.session_state: st.session_state.image_count = 0
if "messages" not in st.session_state: st.session_state.messages = []
if "dark_mode" not in st.session_state: st.session_state.dark_mode = True

try:
    from openai import OpenAI
    api_key = st.secrets.get("OPENAI_API_KEY")
    has_openai_lib = True
except ImportError:
    has_openai_lib = False
    api_key = None

def toggle_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

with st.sidebar:
    st.title("TERMINAL CONTROL")
    st.markdown(f"**Device ID:** `{st.session_state.student_id}`")
    is_dark_mode = st.toggle("Dark Mode", value=st.session_state.dark_mode, key="mode_toggle", on_change=toggle_mode)
    st.divider()
    st.header("DATA INPUT")
    uploaded_file = st.file_uploader("Upload Image", type=['png', 'jpg', 'jpeg'])
    if uploaded_file:
        st.image(uploaded_file, caption="Preview", use_column_width=True)

def get_image_base64(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return ""

if is_dark_mode:
    particle_src = get_image_base64(PARTICLE_IMG_DARK)
    wallpaper_src = get_image_base64(WALLPAPER_IMG_DARK)
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
    wallpaper_src = get_image_base64(WALLPAPER_IMG_LIGHT)
    bg_color = "#ffffff"
    p_color_main = "#000000"
    p_color_sub = "#cccccc"
    css_text_color = "#333333"
    css_bg_rgba = "rgba(255, 255, 255, 0.7)"
    css_input_bg = "rgba(245, 245, 245, 0.95)"
    css_border_color = "rgba(0, 0, 0, 0.1)"
    css_mask_color = "#ffffff"

if wallpaper_src:
    bg_style = f"background-image: url('{wallpaper_src}'); background-size: cover; background-position: center;"
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
    <script>
        const CONFIG = { particleSize: 2.2, particleMargin: 1, repulsionRadius: 80, repulsionForce: 3.0, friction: 0.12, returnSpeed: 0.02, samplingStep: 2, maxDisplayRatio: 0.6 };
        let particles = [], mouse = { x: -1000, y: -1000 };
        const canvas = document.getElementById('canvas'), ctx = canvas.getContext('2d');
        const imageSrc = "__PARTICLE_SRC__";
        class Particle {
            constructor(x, y, colorType) {
                this.originalX = x; this.originalY = y; this.x = x; this.y = y; this.vx = 0; this.vy = 0;
                this.baseColor = colorType === 'main' ? '__P_COLOR_1__' : '__P_COLOR_2__';
            }
            update() {
                const dx = this.x - mouse.x, dy = this.y - mouse.y, dist = Math.sqrt(dx*dx + dy*dy);
                if (dist < CONFIG.repulsionRadius) {
                    const angle = Math.atan2(dy, dx), force = (CONFIG.repulsionRadius - dist) / CONFIG.repulsionRadius;
                    const rep = force * force * CONFIG.repulsionForce;
                    this.vx += Math.cos(angle) * rep; this.vy += Math.sin(angle) * rep;
                }
                this.vx += (this.originalX - this.x) * CONFIG.returnSpeed; this.vy += (this.originalY - this.y) * CONFIG.returnSpeed;
                this.vx *= (1 - CONFIG.friction); this.vy *= (1 - CONFIG.friction);
                this.x += this.vx; this.y += this.vy;
            }
            draw() { ctx.fillStyle = this.baseColor; ctx.beginPath(); ctx.arc(this.x, this.y, CONFIG.particleSize/2, 0, Math.PI*2); ctx.fill(); }
        }
        function init() {
            window.addEventListener('resize', resize);
            window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
            window.addEventListener('touchmove', e => { mouse.x = e.touches[0].clientX; mouse.y = e.touches[0].clientY; });
            if (imageSrc) { const img = new Image(); img.src = imageSrc; img.onload = () => { resize(); generateParticles(img); }; }
        }
        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        function generateParticles(img) {
            particles = []; const temp = document.createElement('canvas'), tCtx = temp.getContext('2d');
            const tW = window.innerWidth * CONFIG.maxDisplayRatio, tH = window.innerHeight * CONFIG.maxDisplayRatio;
            const scale = Math.min(tW / img.width, tH / img.height);
            const w = Math.floor(img.width * scale), h = Math.floor(img.height * scale);
            temp.width = w; temp.height = h; tCtx.drawImage(img, 0, 0, w, h);
            const data = tCtx.getImageData(0, 0, w, h).data;
            const offX = (window.innerWidth - w) / 2, offY = (window.innerHeight - h) / 2;
            for (let y = 0; y < h; y += CONFIG.samplingStep) {
                for (let x = 0; x < w; x += CONFIG.samplingStep) {
                    const i = (y * w + x) * 4;
                    if (data[i + 3] > 128) {
                        const b = (data[i]+data[i+1]+data[i+2])/3;
                        particles.push(new Particle(x+offX, y+offY, b > 128 ? 'main':'sub'));
                    }
                }
            }
            animate();
        }
        function animate() { ctx.clearRect(0, 0, canvas.width, canvas.height); particles.forEach(p => { p.update(); p.draw(); }); requestAnimationFrame(animate); }
        init();
    </script>
</body>
</html>
"""
final_html = html_template.replace("__PARTICLE_SRC__", particle_src).replace("__BG_STYLE__", bg_style).replace("__P_COLOR_1__", p_color_main).replace("__P_COLOR_2__", p_color_sub)
components.html(final_html, height=0)

# CSS
st.markdown(f"""
<style>
    iframe {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; border: none; pointer-events: auto !important; }}
    .stApp {{ background: transparent !important; }}
    header, header > div {{ background: transparent !important; }}
    button[data-testid="stSidebarCollapsedControl"] {{ color: {css_text_color} !important; background-color: {css_bg_rgba} !important; border-radius: 5px; margin-top: 10px; margin-left: 10px; }}
    section[data-testid="stSidebar"] {{ background-color: {css_input_bg} !important; border-right: 1px solid {css_border_color}; }}
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] span {{ color: {css_text_color} !important; }}
    .title-mask {{ position: fixed; top: 0; left: 0; width: 100%; height: 120px; background: {css_mask_color}; z-index: 998; pointer-events: none; background: linear-gradient(to bottom, {css_mask_color} 80%, transparent); }}
    h1 {{ position: fixed !important; top: 30px; left: 60px; margin: 0 !important; font-family: 'Arial', sans-serif; font-weight: 900; font-size: 2.5rem !important; letter-spacing: 2px; color: {css_text_color} !important; text-shadow: 0 0 10px rgba(128,128,128,0.3); z-index: 1000; pointer-events: none; }}
    div[data-testid="stBottom"] {{ background: {css_mask_color} !important; border-top: none {css_border_color}; z-index: 998; padding-top: 20px; padding-bottom: 20px; }}
    div[data-testid="stBottom"] > div {{ background: transparent !important; }}
    div[data-testid="stChatInput"] {{ width: 60% !important; margin: 0 auto !important; position: relative; z-index: 1000; }}
    .stTextInput input, .stTextInput textarea {{ background-color: {css_input_bg} !important; color: {css_text_color} !important; border: 1px solid {css_border_color} !important; border-radius: 12px !important; }}
    .block-container {{ padding-top: 140px !important; padding-bottom: 120px !important; pointer-events: none; }}
    div[data-testid="stChatMessage"] {{ background-color: {css_bg_rgba} !important; border: 1px solid {css_border_color}; border-left: 3px solid {ACCENT_COLOR} !important; border-radius: 4px; backdrop-filter: blur(5px); width: 70%; margin: 0 auto; position: relative; z-index: 997; pointer-events: none !important; }}
    div[data-testid="stChatMessage"] div, div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] code {{ color: {css_text_color} !important; pointer-events: auto !important; }}
    .katex {{ color: {css_text_color} !important; pointer-events: auto !important; }}
    .katex-display {{ pointer-events: auto !important; }}
    .prts-status {{ position: fixed !important; bottom: 20px; right: 30px; font-family: 'Courier New', monospace; color: {css_text_color} !important; z-index: 1000; pointer-events: none; text-align: right; font-size: 0.8em; opacity: 0.8; }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. メイン処理
# ==============================================================================
st.markdown('<div class="title-mask"></div>', unsafe_allow_html=True)
st.title("TOMATO LAB NETWORK ")

status_text = f"Device ID: {st.session_state.student_id}\nImg: {MAX_IMAGE_LIMIT - st.session_state.image_count} | Chat: {MAX_CHAT_LIMIT - st.session_state.chat_count}\n Ver 17.3.0 // PRTS Online"
st.markdown(f'<div class="prts-status" style="white-space: pre-line;">{status_text}</div>', unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("type") == "image": st.image(msg["content"])
        else: st.markdown(msg["content"])

if prompt := st.chat_input("Command..."):
    is_gen_img_req = prompt.startswith("/img ")
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_file and not is_gen_img_req: st.image(uploaded_file, caption="Visual Data", width=200)
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        ai_response_content = ""

        if is_gen_img_req and st.session_state.image_count >= MAX_IMAGE_LIMIT:
            error_msg = "⚠️ Image generation limit reached."
            message_placeholder.error(error_msg)
            ai_response_content = error_msg
        elif not is_gen_img_req and st.session_state.chat_count >= MAX_CHAT_LIMIT:
            error_msg = "⚠️ Chat limit reached."
            message_placeholder.error(error_msg)
            ai_response_content = error_msg
        elif api_key and has_openai_lib:
            try:
                client = OpenAI(api_key=api_key)
                if is_gen_img_req:
                    if f"key:{IMAGE_KEY}" in prompt or f"キー:{IMAGE_KEY}" in prompt:
                        clean_prompt = prompt.replace(f"key:{IMAGE_KEY}", "").replace(f"キー:{IMAGE_KEY}", "").replace("/img", "").strip()
                        message_placeholder.markdown(f"Generating visual data for '{clean_prompt}'...")
                        response = client.images.generate(model="dall-e-3", prompt=f"Arknights style, anime art, {clean_prompt}", size="1024x1024", quality="standard", n=1)
                        image_url = response.data[0].url
                        message_placeholder.empty()
                        st.image(image_url, caption=f"Generated: {clean_prompt}")
                        st.session_state.messages.append({"role": "assistant", "content": image_url, "type": "image"})
                        st.session_state.image_count += 1
                        ai_response_content = f"<Image Generated: {image_url}>"
                    else:
                        error_msg = "🔒 Access Denied. Invalid Key."
                        message_placeholder.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                        ai_response_content = error_msg
                else:
                    messages_payload = [{"role": "system", "content": "You are PRTS, the AI of Rhodes Island. Helpful, logical, concise. Use $...$ for math equations."}]
                    for m in st.session_state.messages:
                        if m.get("type") != "image": messages_payload.append({"role": m["role"], "content": m["content"]})
                    if uploaded_file:
                        base64_image = base64.b64encode(uploaded_file.read()).decode('utf-8')
                        user_content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]
                        messages_payload.pop() 
                        messages_payload.append({"role": "user", "content": user_content})
                    stream = client.chat.completions.create(model="gpt-4o-mini", messages=messages_payload, stream=True)
                    for chunk in stream:
                        if chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.session_state.chat_count += 1
                    ai_response_content = full_response
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                message_placeholder.error(error_msg)
                ai_response_content = error_msg
        else:
            dummy_response = "PRTS Offline (API Key Missing)."
            message_placeholder.markdown(dummy_response)
            st.session_state.messages.append({"role": "assistant", "content": dummy_response})
            ai_response_content = dummy_response
        
        # ログ保存（スプレッドシートへ書き込み）
        save_log_to_sheet(st.session_state.student_id, prompt, ai_response_content)

    time.sleep(0.5)
    st.rerun()
