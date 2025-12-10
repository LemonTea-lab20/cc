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
        pointer-events: none !important; /* 背景への操作を無効化してスクロールを阻害しない */
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
        z-index: 1001 !important; /* 最前面に */
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

    /* ★ヘッダー部分のマスク（修正：z-indexを上げてメッセージを隠す） */
    .title-mask {{
        position: fixed; top: 0; left: 0;
        width: 100%; height: 80px; /* 少し高さを確保 */
        background: {css_mask_color};
        background: linear-gradient(to bottom, {css_mask_color} 60%, transparent);
        z-index: 999; /* メッセージ(997)より上にする */
        pointer-events: none;
    }}

    /* タイトル文字 */
    h1 {{
        position: fixed !important;
        top: 15px; left: 60px; /* ハンバーガーメニューと被らない位置に */
        margin: 0 !important;
        font-family: 'Arial', sans-serif;
        font-weight: 900; font-size: 1.8rem !important;
        letter-spacing: 2px;
        color: {css_text_color} !important;
        text-shadow: 0 0 10px rgba(128,128,128,0.3);
        z-index: 1000; pointer-events: none;
    }}

    /* チャット入力欄エリア（背景追加） */
    div[data-testid="stBottom"] {{
        background: linear-gradient(
            to top,
            {css_mask_color} 40%, 
            transparent 100%
        ) !important;
        z-index: 998;
        padding-bottom: 20px;
    }}
    
    /* 入力欄そのものの幅 */
    div[data-testid="stChatInput"] {{
        width: 70% !important; /* 少し広げる */
        margin: 0 auto !important;
        position: relative; z-index: 1000;
    }}
    
    /* 入力ボックスのデザイン */
    .stTextInput input, .stTextInput textarea {{
        background-color: {css_input_bg} !important;
        color: {css_text_color} !important;
        border: 1px solid {css_border_color} !important;
        border-radius: 12px !important;
    }}

    /* ★メインコンテナ（修正箇所：ここがレイアウトの肝です） */
    .block-container {{
        padding-top: 120px !important;    /* ヘッダーとかぶらないように確保 */
        padding-bottom: 120px !important; /* ★ここを320pxから減らすことでチャットエリアが広がる */
        max-width: 900px !important;      /* 横に広がりすぎないように制限 */
    }}

    /* チャットメッセージの吹き出し */
    div[data-testid="stChatMessage"] {{
        background-color: {css_bg_rgba} !important;
        border: 1px solid {css_border_color};
        border-left: 3px solid {ACCENT_COLOR} !important;
        border-radius: 4px;
        backdrop-filter: blur(5px);
        width: 80%; /* 幅を少し広げる */
        margin: 0 auto;
        position: relative; 
        z-index: 997; /* マスク(999)より下にする */
    }}
    
    /* 文字色など */
    div[data-testid="stChatMessage"] div,
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] code {{
        color: {css_text_color} !important;
    }}
    .katex {{ color: {css_text_color} !important; }}

    /* 右下のステータス表示 */
    .prts-status {{
        position: fixed !important;
        bottom: 10px; right: 20px;
        font-family: 'Courier New', monospace;
        color: {css_text_color} !important;
        z-index: 1000;
        pointer-events: none;
        text-align: right; font-size: 0.7em;
        opacity: 0.6;
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

