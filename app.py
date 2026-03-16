import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Polygon, Point
import numpy as np
import folium
from streamlit_folium import folium_static
from pyproj import Transformer
import json

# --- 1. SISTEM LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""

def check_login(username, password):
    users_db = {
        "1": ["FARAHANI", "admin123"],
        "2": ["PALANI", "admin123"],
        "3": ["FARAH", "admin123"]
    }
    
    if username in users_db:
        correct_password = users_db[username][1]
        display_name = users_db[username][0]
        if password == correct_password:
            st.session_state.logged_in = True
            st.session_state.user_name = display_name
            return True
    return False

if not st.session_state.logged_in:
    st.set_page_config(page_title="GateLogin - Analisis Ukur", page_icon="🔒")
    
    # --- TAMBAHAN LOGO DI SINI ---
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        st.image("Poli_Logo (1).png", use_container_width=True)
    # ----------------------------

    st.markdown("""
        <style>
        .stButton>button { width: 100%; border-radius: 5px; background-color: #007bff; color: white; }
        .login-header { text-align: center; color: #007bff; margin-top: -10px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 class='login-header'>🔒 Log Masuk Sistem Ukur</h1>", unsafe_allow_html=True)
    with st.form("login_form"):
        u = st.text_input("Username (Masukkan ID: 1, 2, atau 3)")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk"):
            if check_login(u, p): 
                st.rerun()
            else: 
                st.error("Username atau Password salah!")
    st.stop()

# --- 2. KONFIGURASI APLIKASI UTAMA ---
st.set_page_config(page_title="Analisis Ukur Pro", layout="wide", page_icon="📐")

def dd_to_dms(dd):
    dd = abs(dd)
    minutes, seconds = divmod(dd * 3600, 60)
    degrees, minutes = divmod(minutes, 60)
    return f"{int(degrees)}° {int(minutes):02d}' {int(seconds):02d}\""

st.title("📐 Pelan Poligon Ukur (EPSG:4390)")
uploaded_file = st.file_uploader("Upload fail CSV anda (Pastikan ada kolum: STN, E, N)", type=['csv'])

# --- SIDEBAR PENGURUSAN ---
with st.sidebar:
    st.markdown(f"""
        <div style="background-color: #007bff; padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">
            <h3 style="margin:0; font-size: 18px;">👤 Pengguna Aktif</h3>
            <p style="margin:0; opacity: 0.9; font-weight: bold;">{st.session_state.user_name}</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.subheader("⚙️ Konfigurasi Paparan")
    no_lot = st.text_input("Masukkan Nombor Lot", "11487")
    font_size = st.slider("Saiz Tulisan (Label)", 6, 20, 10)
    
    st.markdown("---")
    st.subheader("🎨 Tema Poligon")
    col1, col2 = st.columns(2)
    with col1:
        poly_color = st.color_picker("Garisan", "#FFFF00") 
    with col2:
        fill_color = st.color_picker("Isian", "#FFFF00")
    fill_opac = st.slider("Kelegapan (Opacity)", 0.0, 1.0, 0.2)

    st.markdown("<br>"*5, unsafe_allow_html=True)
    if st.button("🚪 Log Keluar"):
        st.session_state.logged_in = False
        st.rerun()

# --- 3. PROSES DATA & VISUALISASI ---
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    if 'E' in df.columns and 'N' in df.columns and 'STN' in df.columns:
        coords = list(zip(df['E'], df['N']))
        poly_geom = Polygon(coords)
        luas = poly_geom.area
        centroid = poly_geom.centroid
        
        # --- PERSEDIAAN DATA ATRIBUT ---
        bearing_list = []
        jarak_list = []
        stn_list = []
        ke_stn_list = []
        
        for i in range(len(df)):
            p1 = df.iloc[i]
            p2 = df.iloc[(i + 1) % len(df)]
            dist = np.sqrt((p2['E'] - p1['E'])**2 + (p2['N'] - p1['N'])**2)
            angle_deg = np.degrees(np.arctan2(p2['E'] - p1['E'], p2['N'] - p1['N'])) % 360
            
            stn_list.append(str(int(p1['STN'])))
            ke_stn_list.append(str(int(p2['STN'])))
            bearing_list.append(dd_to_dms(angle_deg))
            jarak_list.append(round(dist, 3))

        # Dataframe Poligon dengan atribut lengkap
        gdf_poly = gpd.GeoDataFrame({
            'Nombor_Lot': [no_lot], 
            'Luas_m2': [round(luas, 3)],
            'Perimeter': [round(sum(jarak_list), 3)],
            'Senarai_STN': [", ".join(stn_list)]
        }, geometry=[poly_geom], crs="EPSG:4390")

        # Dataframe Point dengan atribut Bearing & Jarak (ke stesen seterusnya)
        gdf_points = gpd.GeoDataFrame({
            'STN': df['STN'].astype(int),
            'E': df['E'],
            'N': df['N'],
            'Ke_STN': ke_stn_list,
            'Bearing': bearing_list,
            'Jarak_m': jarak_list,
            'Lot': no_lot
        }, geometry=[Point(x, y) for x, y in coords], crs="EPSG:4390")
        
        transformer = Transformer.from_crs("epsg:4390", "epsg:4326", always_xy=True)

        tab_pelan, tab_satelit, tab_jadual, tab_export = st.tabs([
            "📊 Pelan Teknikal", "🌍 Google Satellite", "📋 Jadual Data", "📤 Export QGIS"
        ])

        # --- TAB 1: PELAN TEKNIKAL ---
        with tab_pelan:
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.grid(True, linestyle='--', alpha=0.6, color='gray')
            gdf_poly.plot(ax=ax, facecolor=fill_color, edgecolor=poly_color, alpha=fill_opac, linewidth=2)
            ax.text(centroid.x, centroid.y, f"LOT {no_lot}\nLUAS: {luas:.2f} m²", 
                    fontsize=font_size+2, fontweight='bold', ha='center', color='darkblue',
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none'))
            
            for i in range(len(df)):
                p1, p2 = df.iloc[i], df.iloc[(i + 1) % len(df)]
                mid_e, mid_n = (p1['E'] + p2['E']) / 2, (p1['N'] + p2['N']) / 2
                ax.text(mid_e, mid_n + 0.3, f"{bearing_list[i]}", fontsize=font_size-2, color='darkred', ha='center')
                ax.text(mid_e, mid_n - 0.3, f"{jarak_list[i]}m", fontsize=font_size-2, color='darkblue', ha='center')
                ax.text(p1['E'], p1['N']+0.5, f"{int(p1['STN'])}", fontsize=font_size, fontweight='bold')
            ax.set_aspect('equal')
            st.pyplot(fig)

        # --- TAB 2: GOOGLE SATELLITE ---
        with tab_satelit:
            c_lon, c_lat = transformer.transform(centroid.x, centroid.y)
            m = folium.Map(location=[c_lat, c_lon], zoom_start=19, max_zoom=22)
            
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                attr='Google', name='Google Satellite', overlay=False, control=True, max_zoom=22, max_native_zoom=20
            ).add_to(m)

            wgs_poly = [transformer.transform(x, y) for x, y in coords]
            poly_latlon = [[p[1], p[0]] for p in wgs_poly]
            folium.Polygon(
                locations=poly_latlon, color=poly_color, fill=True, fill_color=fill_color, 
                fill_opacity=fill_opac, popup=f"<b>LOT {no_lot}</b><br>Luas: {luas:.2f} m²"
            ).add_to(m)

            for i in range(len(df)):
                lon1, lat1 = transformer.transform(df.iloc[i]['E'], df.iloc[i]['N'])
                lon2, lat2 = transformer.transform(df.iloc[(i+1)%len(df)]['E'], df.iloc[(i+1)%len(df)]['N'])
                folium.PolyLine(locations=[[lat1, lon1], [lat2, lon2]], color=poly_color, weight=3, opacity=1).add_to(m)
                
                mid_lat, mid_lon = (lat1 + lat2) / 2, (lon1 + lon2) / 2
                label_html = f"""<div style="font-size: {font_size-2}px; color: white; text-shadow: 2px 2px 4px black; font-weight: bold; white-space: nowrap;">
                                 {bearing_list[i]}<br>{jarak_list[i]}m</div>"""
                folium.Marker([mid_lat, mid_lon], icon=folium.DivIcon(html=label_html)).add_to(m)

            # --- BAHAGIAN YANG DIKEMASKINI: POPUP TANDA SEMPADAN ---
            for i, row in df.iterrows():
                lon, lat = transformer.transform(row['E'], row['N'])
                
                # Bina kandungan popup dengan maklumat lengkap
                info_popup = f"""
                <div style="font-family: Arial; font-size: 12px; width: 180px;">
                    <h4 style="margin:0; color: #007bff;">STESEN {int(row['STN'])}</h4>
                    <hr style="margin: 5px 0;">
                    <b>Easting:</b> {row['E']:.3f} m<br>
                    <b>Northing:</b> {row['N']:.3f} m<br>
                    <b>Latitude:</b> {lat:.7f}°<br>
                    <b>Longitude:</b> {lon:.7f}°
                </div>
                """
                
                folium.CircleMarker(
                    location=[lat, lon], 
                    radius=6, 
                    color="red", 
                    fill=True, 
                    fill_color="yellow", 
                    fill_opacity=1, 
                    popup=folium.Popup(info_popup, max_width=300)
                ).add_to(m)

            folium_static(m, width=1000)

        # --- TAB 3: JADUAL ---
        with tab_jadual:
            st.subheader("📋 Jadual Koordinat, Ukuran & Geografi")
            combined_data = []
            for i in range(len(df)):
                p1 = df.iloc[i]
                lon, lat = transformer.transform(p1['E'], p1['N'])
                combined_data.append({
                    "STN": int(p1['STN']),
                    "E (m)": f"{p1['E']:.3f}",
                    "N (m)": f"{p1['N']:.3f}",
                    "Latitude": f"{lat:.8f}",
                    "Longitude": f"{lon:.8f}",
                    "Ke STN": ke_stn_list[i],
                    "Bearing": bearing_list[i],
                    "Jarak (m)": f"{jarak_list[i]:.3f}"
                })
            df_combined = pd.DataFrame(combined_data)
            st.dataframe(df_combined, use_container_width=True, hide_index=True)
            st.download_button(label="📥 Muat Turun Jadual Lengkap (CSV)", data=df_combined.to_csv(index=False).encode('utf-8'), file_name=f"Data_Lengkap_Lot_{no_lot}.csv", mime='text/csv')

        # --- TAB 4: EXPORT ---
        with tab_export:
            st.subheader("📤 Eksport Data untuk QGIS")
            st.write("Semua data **Bearing** dan **Jarak** telah dimasukkan ke dalam Attribute Table fail di bawah.")
            
            col_exp1, col_exp2 = st.columns(2)
            gdf_poly_exp = gdf_poly.to_crs(epsg=4326)
            gdf_points_exp = gdf_points.to_crs(epsg=4326)

            with col_exp1:
                st.info("📦 **Layer Poligon**")
                st.download_button(label="💾 Muat Turun Poligon.geojson", data=gdf_poly_exp.to_json(), file_name=f"Lot_{no_lot}_Sempadan.geojson", mime="application/json")
            with col_exp2:
                st.info("📍 **Layer Stesen**")
                st.download_button(label="📍 Muat Turun Points.geojson", data=gdf_points_exp.to_json(), file_name=f"Lot_{no_lot}_Titik.geojson", mime="application/json")
            
            st.success("✅ **Nota QGIS:** Sila semak 'Attribute Table' pada layer di QGIS untuk melihat Bearing dan Jarak.")

    else:
        st.error("Ralat: Pastikan fail CSV mempunyai kolum STN, E, dan N!")
else:
    st.info("👋 Sila upload fail CSV untuk memulakan analisis ukur.")
