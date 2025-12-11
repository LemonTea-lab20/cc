# sheets_utils.py
import datetime
import time
import random
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import APIError

LOG_SHEET_NAME = "AI_Chat_Log"            # 利用ログ
STUDENT_SHEET_NAME = "AI_Student_Master"  # アカウントマスタ

# 日本時間（JST）の設定
JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

# ★キャッシュ設定
@st.cache_resource(ttl=600)
def get_cached_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" not in st.secrets:
        return None
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_gspread_client_with_retry():
    max_retries = 3
    for i in range(max_retries):
        try:
            return get_cached_gspread_client()
        except Exception as e:
            if i == max_retries - 1:
                print(f"Auth Error: {e}")
                return None
            time.sleep(1 + random.random())
    return None

def open_sheet_with_retry(sheet_name):
    client = get_gspread_client_with_retry()
    if not client:
        return None
    
    max_retries = 5
    for i in range(max_retries):
        try:
            return client.open(sheet_name).sheet1
        except APIError as e:
            if i == max_retries - 1:
                print(f"Open Sheet Error ({sheet_name}): {e}")
                return None
            wait_time = (2 ** i) + random.random()
            print(f"Rate limit hit. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
        except Exception as e:
            print(f"Unexpected Error ({sheet_name}): {e}")
            return None
    return None

def get_log_sheet():
    return open_sheet_with_retry(LOG_SHEET_NAME)

def get_student_sheet():
    return open_sheet_with_retry(STUDENT_SHEET_NAME)


def get_initial_usage_count(student_id: str) -> int:
    try:
        sheet = get_log_sheet()
        if not sheet:
            return 0
        
        # 読み込みリトライ
        try:
            data = sheet.get_all_values()
        except APIError:
            time.sleep(1)
            data = sheet.get_all_values()

        if len(data) < 2:
            return 0

        count = 0
        target_date = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        
        for row in data:
            if len(row) > 1:
                if target_date in row[0] and str(student_id) == str(row[1]):
                    count += 1
        return count
    except Exception as e:
        print(f"Count Check Error: {e}")
        return 0


def save_log_to_sheet(student_id, input_text, output_text):
    try:
        sheet = get_log_sheet()
        if not sheet:
            return
        
        now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        
        # 書き込みリトライ
        try:
            sheet.append_row([now, student_id, input_text, output_text])
        except APIError:
            time.sleep(2)
            sheet.append_row([now, student_id, input_text, output_text])
            
    except Exception as e:
        print(f"Log Error: {e}")


def find_student_record(student_id: str):
    sheet = get_student_sheet()
    if not sheet:
        return None, None, []

    try:
        header = sheet.row_values(1)
        records = sheet.get_all_records()
    except APIError:
        time.sleep(1)
        header = sheet.row_values(1)
        records = sheet.get_all_records()

    for idx, rec in enumerate(records, start=2):
        # ID照合
        if str(rec.get("student_id")) == str(student_id):
            
            if "pin" in rec:
                val = rec["pin"]
                s_val = str(val)
                if "." in s_val:
                    s_val = s_val.split(".")[0]
                rec["pin"] = s_val.zfill(4)
            
            return idx, rec, header

    return None, None, header


def update_student_pin_and_login(row_index: int, new_pin: str, is_new: bool = False):
    sheet = get_student_sheet()
    if not sheet:
        return

    try:
        header = sheet.row_values(1)
    except:
        return

    def col_idx(col_name):
        return header.index(col_name) + 1 if col_name in header else None

    now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

    try:
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
    except APIError:
        pass


def update_last_login_only(row_index: int):
    sheet = get_student_sheet()
    if not sheet:
        return
    
    try:
        header = sheet.row_values(1)
        if "last_login" in header:
            col = header.index("last_login") + 1
            now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            try:
                sheet.update_cell(row_index, col, now)
            except APIError:
                time.sleep(1)
                sheet.update_cell(row_index, col, now)
    except Exception as e:
        print(f"Login Update Error: {e}")
