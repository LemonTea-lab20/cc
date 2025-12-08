# auth_gate.py
import streamlit as st
from sheets_utils import (
    find_student_record,
    update_student_pin_and_login,
    update_last_login_only,
    get_initial_usage_count,
)


def _init_session_state():
    defaults = {
        "student_id": None,
        "usage_count": 0,
        "logged_in": False,
        "license_type": "student",  # "student" or "admin"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


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


def security_gate():
    """
    ログイン画面の表示と処理。
    - 管理者：ADMIN_PASSWORD だけでログイン
    - 生徒　：APP_PASSWORD + ID + PIN でログイン
      （初回は PIN 未登録 → サインイン扱い）
    """
    _init_session_state()

    # すでにログイン済みなら何もしない
    if st.session_state.logged_in:
        return

    st.title("🔒 SECURITY GATE")
    st.markdown("Authorized Access Only")

    app_password = st.secrets.get("APP_PASSWORD", None)
    admin_password = st.secrets.get("ADMIN_PASSWORD", None)

    student_id_input = st.text_input(
        "生徒ID（例：1111 → 1年1組11番）",
        value=st.session_state.student_id or "",
    )
    pin_input = st.text_input(
        "PINコード（数字4桁・友だちに教えないで）", type="password"
    )
    access_code = st.text_input("Access Code (合言葉)", type="password")

    st.info(
        "・先生（管理者）は、生徒IDとPINを空のまま、**管理者用の合言葉だけ**で接続できます。\n"
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
            st.rerun()

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
            st.error(
                "生徒IDの形式または範囲が正しくありません。（学年1〜3 / 組1〜3 / 番号1〜40）"
            )
            st.stop()

        row_idx, rec, header = find_student_record(sid)
        if row_idx is None:
            st.error(
                "この生徒IDは先生用シートに登録されていません。先生に確認してください。"
            )
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
            st.success(
                f"サインイン完了: ID {sid} / 本日の利用回数: {st.session_state.usage_count}"
            )
            st.rerun()

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
            st.success(
                f"ログイン成功: ID {sid} / 本日の利用回数: {st.session_state.usage_count}"
            )
            st.rerun()

    # ログイン完了まではメイン処理に進ませない
    st.stop()