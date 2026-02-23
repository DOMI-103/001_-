import datetime
import os.path
import pickle
from dateutil.relativedelta import relativedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# ===== 早稲アカ コマ定義 =====
WASEDA_KOMA = [
    ("Y", "10:40", "12:10"),
    ("Z", "12:20", "13:50"),
    ("A", "15:00", "16:30"),
    ("B", "16:40", "18:10"),
    ("C", "18:20", "19:50"),
    ("D", "20:00", "21:30"),
]

# ===== バイトごとの給料計算関数 =====

def calc_waseaka(hours, wage, work_days, koma_count):
    # 1コマ＝1.5時間分とする
    # （コマ数）×時給×1.5＋日当×出勤日数＋コマ数×コマ手当
    koma_wage = wage * 1.5
    salary = koma_count * koma_wage + 425 * work_days+koma_count*215
    return salary


def calc_toraya(hours, wage, work_days):
    # (労働時間-0.5×出勤日数)×時給＋交通費×出勤日数
    salary = (hours - 0.5 * work_days) * wage + 292 * work_days
    return salary


def calc_haluene(hours, wage, work_days):
    # 労働時間×時給＋交通費×出勤日数
    salary = hours * wage + 376 * work_days
    return salary


PARTTIME_JOBS = {
    "早稲アカ": {
        "wage": 1410,
        "calc_func": calc_waseaka
    },
    "とらや": {
        "wage": 1250,
        "calc_func": calc_toraya
    },
    "ハルエネ": {
        "wage": 1500,
        "calc_func": calc_haluene
    }
}


def get_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)


def get_month_range(year, month):
    start = datetime.datetime(year, month, 1)
    end = start + relativedelta(months=1)
    return start.isoformat() + 'Z', end.isoformat() + 'Z'


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
    job_koma = {job: 0 for job in PARTTIME_JOBS.keys()}  # ★早稲アカ用

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

                # ===== 早稲アカだけコマ計算 =====
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

    # ===== 給料計算 =====
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

    return job_hours, job_salary,job_koma, total_hours, total_salary


if __name__ == "__main__":
    year = int(input("年を入力してください（例：2026）: "))
    month = int(input("月を入力してください（例：2）: "))

    job_hours, job_salary, job_koma,total_hours, total_salary = calculate_salary(year, month)

    print("\n===== バイト別結果 =====")

    for job in PARTTIME_JOBS.keys():
        print(f"\n【{job}】")
        print(f"勤務時間: {job_hours[job]:.2f} 時間")
        if job == "早稲アカ":
            print(f"コマ数: {job_koma[job]}")
        print(f"給料: {job_salary[job]:,.0f} 円")

    print("\n===== 総計 =====")
    print(f"総勤務時間: {total_hours:.2f} 時間")
    print(f"総給料: {total_salary:,.0f} 円")