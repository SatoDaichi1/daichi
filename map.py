import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
import math

st.set_page_config(layout="wide")
st.title("距離・真方位・VOR情報 Webアプリ")

# km → 海里
def km_to_nm(km):
    return km * 0.539957

# 真方位
def calculate_bearing(pointA, pointB):
    lat1, lon1 = math.radians(pointA[0]), math.radians(pointA[1])
    lat2, lon2 = math.radians(pointB[0]), math.radians(pointB[1])
    dLon = lon2 - lon1
    x = math.sin(dLon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dLon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

VORS = [
    {"name": "MZE", "lat": 31.87873, "lon": 131.43747},  # 宮崎
    {"name": "HKC", "lat": 31.69722, "lon": 130.58294},  # 鹿児島
    {"name": "KUE", "lat": 32.83480, "lon": 130.84151},  # 熊本
]
VOR_NAMES = [v["name"] for v in VORS]

# セッションステート
if "points" not in st.session_state:
    st.session_state.points = []
if "vor_selection" not in st.session_state:
    st.session_state.vor_selection = []

# 地図初期化
center_point = st.session_state.points[-1] if st.session_state.points else (35.681236, 139.767125)
m = folium.Map(location=center_point, zoom_start=6)

# VORマーカー
for vor in VORS:
    folium.Marker(
        location=(vor["lat"], vor["lon"]),
        icon=folium.Icon(color="blue", icon="plane", prefix="fa"),
        popup=vor["name"]
    ).add_to(m)

# ユーザークリック点マーカー
for idx, pt in enumerate(st.session_state.points):
    folium.Marker(
        location=pt,
        draggable=True,
        icon=folium.DivIcon(
            html=f"<div style='font-weight:bold; color:red; font-size:16px'>{idx+1}</div>"
        )
    ).add_to(m)

# 線
if len(st.session_state.points) > 1:
    folium.PolyLine(st.session_state.points, color="blue").add_to(m)

# 地図表示
map_data = st_folium(m, width=900, height=500)

# クリックで新規点追加
if map_data and map_data.get("last_clicked"):
    latlng = map_data["last_clicked"]
    point = (latlng["lat"], latlng["lng"])
    if point not in st.session_state.points:
        st.session_state.points.append(point)
        st.session_state.vor_selection.append(VOR_NAMES[0])  # デフォルトVORを選択

# ドラッグ後座標反映
if st.button("マーカー座標を反映"):
    if map_data and "all_marker_data" in map_data:
        for idx, marker in enumerate(map_data["all_marker_data"]):
            lat = marker["lat"]
            lng = marker["lng"]
            if idx < len(st.session_state.points):
                st.session_state.points[idx] = (lat, lng)

# 距離・方位表示
if len(st.session_state.points) > 1:
    st.subheader("距離と真方位（nm・°）")
    for i in range(len(st.session_state.points)-1):
        dist_nm = km_to_nm(geodesic(st.session_state.points[i], st.session_state.points[i+1]).km)
        bearing = calculate_bearing(st.session_state.points[i], st.session_state.points[i+1])
        st.write(f"点 {i+1} → {i+2} : 距離 {dist_nm:.2f} nm, 真方位 {bearing:.2f}°")

# 各点ごとにVOR選択・距離・RAD
if st.session_state.points:
    st.subheader("各点から選択VORまでの距離・RAD方位")
    for idx, pt in enumerate(st.session_state.points):
        col1, col2 = st.columns([2,3])
        with col1:
            st.session_state.vor_selection[idx] = st.selectbox(
                f"点{idx+1} VOR選択",
                VOR_NAMES,
                index=VOR_NAMES.index(st.session_state.vor_selection[idx]),
                key=f"vor_select_{idx}"
            )
        with col2:
            selected_vor = next(v for v in VORS if v["name"] == st.session_state.vor_selection[idx])
            dist_nm = km_to_nm(geodesic(pt, (selected_vor["lat"], selected_vor["lon"])).km)
            rad = calculate_bearing((selected_vor["lat"], selected_vor["lon"]), pt)
            st.write(f"距離 {dist_nm:.1f} nm, RAD {rad:.0f}°")

# 最後の点削除・リセット
col1, col2 = st.columns(2)
with col1:
    if st.button("最後の点を削除"):
        if st.session_state.points:
            st.session_state.points.pop()
            st.session_state.vor_selection.pop()
with col2:
    if st.button("リセット"):
        st.session_state.points = []
        st.session_state.vor_selection = []
