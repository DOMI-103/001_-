import datetime
import os
import streamlit as st
from dateutil.relativedelta import relativedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# ==============================
# 早稲アカ コマ定義
# ==============================
WASEDA_KOMA = [
    ("Y", "10:40", "12:10"),
    ("Z", "12:20", "13:50"),
    ("A", "15:00", "16:30"),
    ("B", "16:40", "18:10"),
    ("C", "18:20", "19:50"),
    ("D", "20:00", "21:30"),
]

# ==============================
# 給料計算関数
# ==============================

def calc_waseaka(hours, wage, work_days, koma_count):
    koma_wage = wage * 1.5
    salary = koma_count * koma_wage + 425 * work_days + koma_count * 215
    return salary


def calc_toraya(hours, wage, work_days):
    return (hours - 0.5 * work_days) * wage + 292 * work_days


def calc_haluene(hours, wage, work_days):
    return hours * wage + 376 * work_days


PARTTIME_JOBS = {
    "早稲アカ": {"wage": 1410, "calc_func": calc_waseaka},
    "とらや": {"wage": 1250, "calc_func": calc_toraya},
    "ハルエネ": {"wage": 1500, "calc_func": calc_haluene},
}

# ==============================
# Google認証（クラウド用）
# ==============================
def get_service():

    if "credentials" in st.session_state:
        return build("calendar", "v3", credentials=st.session_state["credentials"])

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": st.secrets["google"]["client_id"],
                "client_secret": st.secrets["google"]["client_secret"],
                "auth_uri": st.secrets["google"]["auth_uri"],
                "token_uri": st.secrets["google"]["token_uri"],
            }
        },
        scopes=SCOPES,
        redirect_uri=st.secrets["google"]["redirect_uri"],
    )

    query_params = st.query_params

    if "code" not in query_params:

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent"
        )

        st.markdown(f"[👉 Googleでログインする]({auth_url})")
        st.stop()

    else:
        flow.fetch_token(code=query_params["code"])
        credentials = flow.credentials
        st.session_state["credentials"] = credentials
        return build("calendar", "v3", credentials=credentials)

# ==============================
# 月範囲取得
# ==============================

def get_month_range(year, month):
    start = datetime.datetime(year, month, 1)
    end = start + relativedelta(months=1)
    return start.isoformat() + 'Z', end.isoformat() + 'Z'


# ==============================
# 給料計算
# ==============================

def calculate_salary(year, month):

    service = get_service()
    time_min, time_max = get_month_range(year, month)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    job_hours = {job: 0 for job in PARTTIME_JOBS.keys()}
    job_days = {job: 0 for job in PARTTIME_JOBS.keys()}
    job_koma = {job: 0 for job in PARTTIME_JOBS.keys()}

    for event in events:
        if 'summary' not in event:
            continue

        for job in PARTTIME_JOBS.keys():
            if job in event['summary']:

                start = datetime.datetime.fromisoformat(
                    event['start']['dateTime'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(
                    event['end']['dateTime'].replace('Z', '+00:00'))

                hours = (end - start).total_seconds() / 3600
                job_hours[job] += hours
                job_days[job] += 1

                if job == "早稲アカ":
                    for koma_name, koma_start, koma_end in WASEDA_KOMA:

                        koma_start_dt = start.replace(
                            hour=int(koma_start.split(":")[0]),
                            minute=int(koma_start.split(":")[1])
                        )

                        koma_end_dt = start.replace(
                            hour=int(koma_end.split(":")[0]),
                            minute=int(koma_end.split(":")[1])
                        )

                        if start < koma_end_dt and end > koma_start_dt:
                            job_koma[job] += 1

    job_salary = {}
    total_hours = 0
    total_salary = 0

    for job, hours in job_hours.items():
        wage = PARTTIME_JOBS[job]["wage"]
        calc_func = PARTTIME_JOBS[job]["calc_func"]

        if job == "早稲アカ":
            salary = calc_func(hours, wage, job_days[job], job_koma[job])
        else:
            salary = calc_func(hours, wage, job_days[job])

        job_salary[job] = salary
        total_hours += hours
        total_salary += salary

    return job_hours, job_salary, job_koma, total_hours, total_salary
