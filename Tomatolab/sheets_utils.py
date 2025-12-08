# sheets_utils.py
import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

LOG_SHEET_NAME = "AI_Chat_Log"            # 利用ログ
STUDENT_SHEET_NAME = "AI_Student_Master"  # アカウントマスタ


def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
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