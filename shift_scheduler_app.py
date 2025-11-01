import streamlit as st
import pandas as pd
import numpy as np
from pulp import *

st.set_page_config(page_title="シフト自動作成", layout="wide")

st.title("👩‍💼 シフト自動作成アプリ")
st.write("希望勤務日数・希望休を入力して自動でシフトを作成します。")

# --- 基本設定 ---
num_staff = st.number_input("アルバイト人数", min_value=3, max_value=30, value=18)
num_days = st.number_input("日数", min_value=7, max_value=31, value=28)

# 月初めの曜日入力
first_weekday = st.selectbox("月初めの曜日を選択", ["月", "火", "水", "木", "金", "土", "日"])

staff = [f"バイト{i+1}" for i in range(num_staff)]
days = [f"Day{j+1}" for j in range(num_days)]

# --- 曜日ごとの必要人数入力 ---
st.subheader("曜日ごとの必要人数")
weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
weekday_staff = {}
for i, wd in enumerate(weekday_labels):
    default_val = 9 if wd not in ["土","日"] else (11 if wd=="土" else 12)
    weekday_staff[i] = st.number_input(f"{wd}曜日の必要人数", min_value=1, max_value=num_staff, value=default_val)

# --- 希望勤務日数 ---
st.subheader("各バイトの希望勤務日数")
desired_days_input = {}
for s in staff:
    desired_days_input[s] = st.number_input(f"{s} の希望勤務日数", min_value=1, max_value=num_days, value=15)

# --- 希望休入力 ---
st.subheader("希望休入力（カンマ区切りで日番号を入力）")
holiday_requests_input = {}
for s in staff:
    text = st.text_input(f"{s} の希望休（例: 1,5,12）", value="")
    if text.strip():
        try:
            holiday_requests_input[s] = [int(x.strip()) - 1 for x in text.split(",") if x.strip()]
        except:
            holiday_requests_input[s] = []
    else:
        holiday_requests_input[s] = []

# --- シフト作成ボタン ---
if st.button("🚀 シフトを作成"):
    st.info("最適化中です... 数秒かかる場合があります。")

    # --- データ準備 ---
    P = list(range(num_staff))
    D = list(range(num_days))
    S = {"d"}
    desired_days = {i: desired_days_input[f"バイト{i+1}"] for i in P}
    holiday_requests = {i: holiday_requests_input[f"バイト{i+1}"] for i in P}

    # --- モデル ---
    x = LpVariable.dicts("x", (P, D, S), cat=LpBinary)
    t_plus = LpVariable.dicts("t_plus", P, lowBound=0, cat=LpContinuous)
    t_minus = LpVariable.dicts("t_minus", P, lowBound=0, cat=LpContinuous)

    prob = LpProblem("Shift_Scheduling_WorkloadBalance", LpMinimize)

    workdays = {i: lpSum(x[i][j]["d"] for j in D) for i in P}
    prob += lpSum(t_plus[i] + t_minus[i] for i in P)

    for i in P:
        prob += workdays[i] - desired_days[i] == t_plus[i] - t_minus[i]

    # 各日の必要人数（曜日計算）
    first_wd_index = ["月","火","水","木","金","土","日"].index(first_weekday)
    for j in D:
        weekday_index = (first_wd_index + j) % 7
        prob += lpSum(x[i][j]["d"] for i in P) == weekday_staff[weekday_index]

    # 特定バイト(1,2,3)のうち2人は毎日出勤
    for j in D:
        if num_staff >= 3:
            prob += lpSum(x[i][j]["d"] for i in [0,1,2]) == 2

    # 希望休の反映
    for i in P:
        for j in holiday_requests.get(i, []):
            if j < num_days:
                prob += x[i][j]["d"] == 0

    # 5連勤禁止
    for i in P:
        for j in range(len(D) - 4):
            prob += lpSum(x[i][j+k]["d"] for k in range(5)) <= 4

    # 上限21日
    for i in P:
        prob += workdays[i] <= 21

    # --- 最適化 ---
    prob.solve(PULP_CBC_CMD(msg=False))

    # --- 結果整形 ---
    data = []
    actual_days = {}
    for i in P:
        row = []
        for j in D:
            if value(x[i][j]["d"]) == 1:
                row.append("◎" if i in [0,1,2] else "〇")
            else:
                row.append("休" if j in holiday_requests.get(i,[]) else "×")
        data.append(row)
        actual_days[i] = sum(value(x[i][j]["d"]) for j in D)

    df = pd.DataFrame(data, index=[f"バイト{i+1}" for i in P], columns=days)
    df["出勤日数"] = [int(actual_days[i]) for i in P]

    # 各日の出勤人数
    total_row = [int(sum(value(x[i][j]["d"]) for i in P)) for j in D]
    total_row.append(sum(total_row))
    df.loc["出勤人数"] = total_row

    # 勤務日数まとめ
    summary = pd.DataFrame({
        "希望勤務日数": [desired_days[i] for i in P],
        "実際の勤務日数": [actual_days[i] for i in P],
        "差": [actual_days[i] - desired_days[i] for i in P]
    }, index=[f"バイト{i+1}" for i in P])

    st.success("✅ シフト作成完了！")
    st.dataframe(df)

    # Excel出力
    output_file = "shift_schedule_final.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        df.to_excel(writer, sheet_name="シフト表")
        summary.to_excel(writer, sheet_name="勤務日数まとめ")

    with open(output_file, "rb") as f:
        st.download_button(
            label="📥 Excelをダウンロード",
            data=f,
            file_name=output_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

