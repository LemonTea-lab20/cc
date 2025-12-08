import streamlit as st
import streamlit.components.v1 as components
import base64
import os
import random
import datetime
import re
from dotenv import load_dotenv

# --- Google Sheets 連携用ライブラリ ---
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==============================================================================
# 0. 環境設定 & 定数定義
# ==============================================================================
st.set_page_config(layout="wide", page_title="Tomato AI", initial_sidebar_state="collapsed")
load_dotenv()

ACCENT_COLOR = "#00C8FF"
MAX_CHAT_LIMIT = 15
MAX_IMAGE_LIMIT = 5
LOG_SHEET_NAME = "AI_Chat_Log"            # 利用ログ
STUDENT_SHEET_NAME = "AI_Student_Master"  # アカウントマスタ

# ==============================================================================
# 1. シート連携機能
# ==============================================================================
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    if "gcp_service_account" not in st.secrets:
        return None
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_log_sheet():
    client = get_gspread_client()
    if not client:
        return None
    return client.open(LOG_SHEET_NAME).sheet1

def get_student_sheet():
    client = get_gspread_client()
    if not client:
        return None
    return client.open(STUDENT_SHEET_NAME).sheet1

def get_initial_usage_count(student_id: str) -> int:
    """指定IDの「本日の使用回数」をログシートからカウント"""
    try:
        sheet = get_log_sheet()
        if not sheet:
            return 0
        
        data = sheet.get_all_values()
        if len(data) < 2:
            return 0
            
        count = 0
        target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        for row in data:
            if len(row) > 1:
                # A列：日時文字列 / B列：student_id と想定
                if target_date in row[0] and str(student_id) == str(row[1]):
                    count += 1
        return count
    except Exception as e:
        print(f"Count Check Error: {e}")
        return 0

def save_log_to_sheet(student_id, input_text, output_text):
    """利用ログ保存"""
    try:
        sheet = get_log_sheet()
        if not sheet:
            return
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, student_id, input_text, output_text])
    except Exception as e:
        print(f"Log Error: {e}")

def find_student_record(student_id: str):
    """
    アカウントマスタから student_id に対応するレコードを検索。
    戻り値: (row_index, record_dict, header_list) or (None, None, header_list)
    """
    sheet = get_student_sheet()
    if not sheet:
        return None, None, []

    header = sheet.row_values(1)
    records = sheet.get_all_records()  # 2行目以降

    for idx, rec in enumerate(records, start=2):  # 行番号は2から
        if str(rec.get("student_id")) == str(student_id):
            return idx, rec, header
    return None, None, header

def update_student_pin_and_login(row_index: int, new_pin: str, is_new: bool = False):
    """
    指定行の pin / created_at / last_login を更新
    is_new=True のときは created_at もセット
    """
    sheet = get_student_sheet()
    if not sheet:
        return

    header = sheet.row_values(1)

    def col_idx(col_name):
        return header.index(col_name) + 1 if col_name in header else None

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pin_col = col_idx("pin")
    if pin_col:
        sheet.update_cell(row_index, pin_col, new_pin)

    if is_new:
        created_col = col_idx("created_at")
        if created_col:
            sheet.update_cell(row_index, created_col, now)

    last_login_col = col_idx("last_login")
    if last_login_col:
        sheet.update_cell(row_index, last_login_col, now)

def update_last_login_only(row_index: int):
    """ログイン成功時に last_login だけ更新"""
    sheet = get_student_sheet()
    if not sheet:
        return
    header = sheet.row_values(1)
    if "last_login" in header:
        col = header.index("last_login") + 1
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.update_cell(row_index, col, now)

# ==============================================================================
# 2. ID / PIN フォーマットチェック
# ==============================================================================
def validate_and_parse_id(raw_id: str):
    """
    '1111' 形式で、かつ 学年1〜3 / 組1〜3 / 番号1〜40 の範囲かチェック。
    OKなら (grade, klass, number) を返し、NGなら None を返す。
    """
    s = raw_id.strip()
    if not (len(s) == 4 and s.isdigit()):
        return None
    grade = int(s[0])
    klass = int(s[1])
    number = int(s[2:4])

    if grade not in (1, 2, 3):
        return None
    if klass not in (1, 2, 3):
        return None
    if not (1 <= number <= 40):
        return None

    return grade, klass, number

def validate_pin_format(pin: str):
    """PIN形式チェック（数字4桁）"""
    p = pin.strip()
    return len(p) == 4 and p.isdigit()

# ==============================================================================
# 3. セッション初期化
# ==============================================================================
if "student_id" not in st.session_state:
    st.session_state.student_id = None
if "usage_count" not in st.session_state:
    st.session_state.usage_count = 0
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "license_type" not in st.session_state:
    st.session_state.license_type = "student"  # "student" or "admin"

# ==============================================================================
# 4. SECURITY GATE（ボタン1つで 管理者 or 生徒）
# ==============================================================================
if not st.session_state.logged_in:
    st.title("🔒 SECURITY GATE")
    st.markdown("Authorized Access Only")

    app_password   = st.secrets.get("APP_PASSWORD", None)
    admin_password = st.secrets.get("ADMIN_PASSWORD", None)

    student_id_input = st.text_input(
        "生徒ID（例：1111 → 1年1組11番）",
        value=st.session_state.student_id or ""
    )
    pin_input = st.text_input("PINコード（数字4桁・友だちに教えないで）", type="password")
    access_code = st.text_input("Access Code (合言葉)", type="password")

    st.info(
        "・先生（管理者）は、生徒IDとPINを空のまま、管理者用の合言葉だけで接続できます。\n"
        "・生徒は、学年組番号ID・PIN・合言葉（共通）を入力して接続してください。"
    )

    if st.button("CONNECT / 接続開始"):
        # --- 管理者判定 ---
        if admin_password and access_code == admin_password:
            st.session_state.student_id = "ADMIN"
            st.session_state.logged_in = True
            st.session_state.license_type = "admin"
            st.session_state.usage_count = 0
            st.success("管理者としてログインしました。")
            st.experimental_rerun()

        # --- 生徒ログイン ---
        # 合言葉チェック
        if not app_password:
            st.error("システム設定エラー: APP_PASSWORD が設定されていません。")
            st.stop()
        if access_code != app_password:
            st.error("Access Code（合言葉）が間違っています。")
            st.stop()

        sid = student_id_input.strip()
        if not sid:
            st.error("生徒IDを入力してください。（例：1111）")
            st.stop()
        if validate_and_parse_id(sid) is None:
            st.error("生徒IDの形式または範囲が正しくありません。（学年1〜3 / 組1〜3 / 番号1〜40）")
            st.stop()

        row_idx, rec, header = find_student_record(sid)
        if row_idx is None:
            st.error("この生徒IDは先生用シートに登録されていません。先生に確認してください。")
            st.stop()

        registered_pin = str(rec.get("pin", "")).strip()

        # PIN未設定 → 初回サインイン扱い
        if not registered_pin:
            if not pin_input.strip():
                st.error("初回サインインです。登録したいPINコード（数字4桁）を入力してください。")
                st.stop()
            if not validate_pin_format(pin_input):
                st.error("PINコードは数字4桁で入力してください。")
                st.stop()

            update_student_pin_and_login(row_idx, pin_input.strip(), is_new=True)
            st.session_state.student_id = sid
            st.session_state.logged_in = True
            st.session_state.license_type = "student"
            st.session_state.usage_count = get_initial_usage_count(sid)
            st.success(f"サインイン完了: ID {sid} / 本日の利用回数: {st.session_state.usage_count}")
            st.experimental_rerun()

        # PIN設定済み → 通常ログイン
        else:
            if not pin_input.strip():
                st.error("PINコードを入力してください。")
                st.stop()
            if pin_input.strip() != registered_pin:
                st.error("PINコードが違います。")
                st.stop()

            update_last_login_only(row_idx)
            st.session_state.student_id = sid
            st.session_state.logged_in = True
            st.session_state.license_type = "student"
            st.session_state.usage_count = get_initial_usage_count(sid)
            st.success(f"ログイン成功: ID {sid} / 本日の利用回数: {st.session_state.usage_count}")
            st.experimental_rerun()

    st.stop()

# ==============================================================================
# 5. メインアプリ処理（ここから先はログイン済み）
# ==============================================================================

PARTICLE_IMG_DARK = "assets/ro.png"
PARTICLE_IMG_LIGHT = "assets/ba.png"
WALLPAPER_IMG_DARK = None
WALLPAPER_IMG_LIGHT = None

@st.cache_resource
def get_server_image_key():
    # 旧方式ではここでランダムキーを出していたが、
    # 今回は IMG_PASSWORD を使うので未使用にしてもOK。
    key = f"{random.randint(0, 9999):04d}"
    print(f"KEY: {key}")
    return key

if "chat_count" not in st.session_state:
    st.session_state.chat_count = 0
if "image_count" not in st.session_state:
    st.session_state.image_count = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

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
    st.markdown(f"**ID:** `{st.session_state.student_id}`")

    license_label = "ADMIN" if st.session_state.license_type == "admin" else "STUDENT"
    st.markdown(f"**License:** `{license_label}`")
    
    remaining = MAX_CHAT_LIMIT - st.session_state.usage_count
    if remaining < 0:
        remaining = 0
    if st.session_state.license_type == "admin":
        st.metric("Remaining Chats", "∞")
    else:
        st.metric("Remaining Chats", f"{remaining} / {MAX_CHAT_LIMIT}")
    
    is_dark_mode = st.toggle(
        "Dark Mode",
        value=st.session_state.dark_mode,
        key="mode_toggle",
        on_change=toggle_mode
    )
    st.divider()
    uploaded_file = st.file_uploader("Upload Image", type=['png', 'jpg', 'jpeg'])
    if uploaded_file:
        st.image(uploaded_file, caption="Preview", use_column_width=True)

    if st.button("Logout"):
        st.session_state.messages = []
        st.session_state.logged_in = False
        st.session_state.student_id = None
        st.session_state.license_type = "student"
        st.experimental_rerun()

def get_image_base64(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return ""

if st.session_state.dark_mode:
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

# 背景パーティクル HTML/JS
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
final_html = (
    html_template
    .replace("__PARTICLE_SRC__", particle_src)
    .replace("__BG_STYLE__", bg_style)
    .replace("__P_COLOR_1__", p_color_main)
    .replace("__P_COLOR_2__", p_color_sub)
)
components.html(final_html, height=0)

# CSS
st.markdown(f"""
<style>
    iframe {{ position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; border: none; pointer-events: auto !important; }}
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
# 6. チャットUI
# ==============================================================================
st.markdown('<div class="title-mask"></div>', unsafe_allow_html=True)
st.title("TOMATO LAB NETWORK ")

license_label = "ADMIN" if st.session_state.license_type == "admin" else "STUDENT"
status_text = (
    f"Agent ID: {st.session_state.student_id}\n"
    f"License: {license_label}\n"
    f"Img: {MAX_IMAGE_LIMIT - st.session_state.image_count} | "
    f"Chat: {MAX_CHAT_LIMIT - st.session_state.usage_count}\n"
    f"Ver 20.0.0 // PRTS Online"
)
st.markdown(
    f'<div class="prts-status" style="white-space: pre-line;">{status_text}</div>',
    unsafe_allow_html=True
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
        
        elif (not is_gen_img_req
              and st.session_state.license_type != "admin"
              and st.session_state.usage_count >= MAX_CHAT_LIMIT):
            error_msg = "⚠️ Daily chat limit reached. (本日の制限回数を超えました)"
            message_placeholder.error(error_msg)
            ai_response_content = error_msg
            
        elif api_key and has_openai_lib:
            try:
                client = OpenAI(api_key=api_key)

                # ===== 画像生成モード =====
                if is_gen_img_req:
                    # IMG_PASSWORD チェック
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
                        # プロンプトからキー部分を削除
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
                            n=1
                        )
                        image_url = response.data[0].url
                        message_placeholder.empty()
                        st.image(image_url, caption=f"Generated: {clean_prompt}")
                        st.session_state.messages.append(
                            {"role": "assistant", "content": image_url, "type": "image"}
                        )
                        st.session_state.image_count += 1
                        ai_response_content = f"<Image Generated: {image_url}>"

                # ===== 通常チャットモード =====
                else:
                    system_prompt = (
                        "You are PRTS, the AI of Rhodes Island. "
                        "Helpful, logical, concise. Use $...$ for math equations."
                    )
                    messages_payload = [{"role": "system", "content": system_prompt}]
                    for m in st.session_state.messages:
                        if m.get("type") != "image":
                            messages_payload.append(
                                {"role": m["role"], "content": m["content"]}
                            )

                    if uploaded_file:
                        base64_image = base64.b64encode(
                            uploaded_file.read()
                        ).decode('utf-8')
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
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
                        stream=True
                    )
                    for chunk in stream:
                        if chunk.choices[0].delta.content is not None:
                            full_response += chunk.choices[0].delta.content
                            message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_response}
                    )
                    
                    # 生徒ライセンスのときだけ回数カウント＆ログ保存
                    if st.session_state.license_type == "student":
                        st.session_state.usage_count += 1
                        if st.session_state.student_id:
                            save_log_to_sheet(
                                st.session_state.student_id,
                                prompt,
                                full_response
                            )
                    
                    ai_response_content = full_response
                    
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                message_placeholder.error(error_msg)
                ai_response_content = error_msg
        else:
            dummy_response = "PRTS Offline (API Key Missing)."
            message_placeholder.markdown(dummy_response)
            st.session_state.messages.append(
                {"role": "assistant", "content": dummy_response}
            )
            ai_response_content = dummy_response
