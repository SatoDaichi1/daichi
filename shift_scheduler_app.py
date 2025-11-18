import streamlit as st
import pandas as pd
import numpy as np
from pulp import *

st.set_page_config(page_title="シフト自動作成", layout="wide")

st.title("👩‍💼 清掃さんシフト自動作成")
st.write("希望勤務日数・希望休・勤務不可曜日を入力して自動でシフトを作成します。")

# --- 基本設定 ---
num_staff = st.number_input("アルバイト人数", min_value=3, max_value=30, value=18)
num_days = st.number_input("日数", min_value=7, max_value=31, value=30)

# 月初めの曜日入力
weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
first_weekday = st.selectbox("月初めの曜日を選択", weekday_labels)

staff = [f"バイト{i+1}" for i in range(num_staff)]
days = [f"Day{j+1}" for j in range(num_days)]

# --- 曜日ごとの必要人数入力 ---
st.subheader("曜日ごとの必要人数")
weekday_staff = {}
for wd in weekday_labels:
    default_val = 9 if wd not in ["土", "日"] else (11 if wd == "土" else 12)
    weekday_staff[weekday_labels.index(wd)] = st.number_input(
        f"{wd}曜日の必要人数",
        min_value=1, max_value=num_staff, value=default_val
    )

# --- 毎日2人出勤が必要な特定バイト選択 ---
st.subheader("チェッカーさんを指定")
special_workers = st.multiselect(
    options=staff,
    default=staff[:3] if num_staff >= 2 else []
)

special_worker_indices = [staff.index(s) for s in special_workers]

# --- 希望勤務日数 ---
st.subheader("希望勤務日数（各バイト）")
desired_days_input = {
    s: st.number_input(f"{s} の希望勤務日数", min_value=1, max_value=num_days, value=15)
    for s in staff
}

# --- 希望休 ＆ 勤務不可曜日 ---
st.subheader("希望休（日付）と勤務不可曜日（毎週）")

holiday_requests_input = {}
week_off_requests_input = {}

for s in staff:
    c1, c2 = st.columns(2)
    with c1:
        holiday_requests_input[s] = st.multiselect(
            f"{s} の希望休（日付）",
            options=list(range(1, num_days + 1)),
            default=[]
        )
    with c2:
        week_off_requests_input[s] = st.multiselect(
            f"{s} の勤務不可曜日（毎週固定で休み）",
            options=weekday_labels,
            default=[]
        )

# ======================================================================
#                           シフト作成開始
# ======================================================================

if st.button("🚀 シフトを作成"):
    st.info("最適化中です... 数秒かかる場合があります。")

    # --- データ準備 ---
    P = list(range(num_staff))
    D = list(range(num_days))
    S = {"d"}

    desired_days = {i: desired_days_input[f"バイト{i+1}"] for i in P}
    holiday_requests = {
        i: [d-1 for d in holiday_requests_input[f"バイト{i+1}"]]
        for i in P
    }

    weekday_map = {wd: i for i, wd in enumerate(weekday_labels)}
    first_wd_index = weekday_map[first_weekday]

    # --- モデル ---
    x = LpVariable.dicts("x", (P, D, S), cat=LpBinary)
    t_plus = LpVariable.dicts("t_plus", P, lowBound=0, cat=LpContinuous)
    t_minus = LpVariable.dicts("t_minus", P, lowBound=0, cat=LpContinuous)

    prob = LpProblem("Shift_Scheduling_WorkloadBalance", LpMinimize)

    workdays = {i: lpSum(x[i][j]["d"] for j in D) for i in P}

    # 目的関数：希望との差を最小化
    prob += lpSum(t_plus[i] + t_minus[i] for i in P)

    # 希望勤務日数との誤差
    for i in P:
        prob += workdays[i] - desired_days[i] == t_plus[i] - t_minus[i]

    # --- 各日の必要人数（曜日計算）
    for j in D:
        weekday_index = (first_wd_index + j) % 7
        prob += lpSum(x[i][j]["d"] for i in P) == weekday_staff[weekday_index]

    # --- 毎日2人出勤が必要な特定バイト ---
    if len(special_worker_indices) > 0:
        for j in D:
            prob += lpSum(x[i][j]["d"] for i in special_worker_indices) >= min(2, len(special_worker_indices))

    # --- 希望休（日付）の反映 ---
    for i in P:
        for j in holiday_requests[i]:
            if j < num_days:
                prob += x[i][j]["d"] == 0

    # --- 勤務不可曜日（毎週固定） ---
    for i in P:
        for j in D:
            weekday_index = (first_wd_index + j) % 7
            wd_name = weekday_labels[weekday_index]

            if wd_name in week_off_requests_input[f"バイト{i+1}"]:
                prob += x[i][j]["d"] == 0

    # --- 5連勤禁止 ---
    for i in P:
        for j in range(num_days - 4):
            prob += lpSum(x[i][j+k]["d"] for k in range(5)) <= 4

    # --- 上限21日 ---
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
                row.append("◎" if i in special_worker_indices else "〇")
            else:
                row.append("休" if j in holiday_requests[i] else "×")
        data.append(row)
        actual_days[i] = sum(value(x[i][j]["d"]) for j in D)

    df = pd.DataFrame(data, index=staff, columns=days)
    df["出勤日数"] = [int(actual_days[i]) for i in P]

    # 各日の出勤人数
    total_row = [int(sum(value(x[i][j]["d"]) for i in P)) for j in D]
    total_row.append(sum(total_row))
    df.loc["出勤人数"] = total_row

    # 勤務日数サマリー
    summary = pd.DataFrame({
        "希望勤務日数": [desired_days[i] for i in P],
        "実際": [actual_days[i] for i in P],
        "差": [actual_days[i] - desired_days[i] for i in P]
    }, index=staff)

    # --- 出力 ---
    st.success("✨ シフト作成完了！")
    st.dataframe(df)

    # Excel出力
    output_file = "shift_schedule.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        df.to_excel(writer, sheet_name="シフト表")
        summary.to_excel(writer, sheet_name="勤務日数まとめ")

    with open(output_file, "rb") as f:
        st.download_button(
            label="📥 Excelダウンロード",
            data=f,
            file_name=output_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )





