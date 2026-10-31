# APAR-UC: Web GIS Pencarian APAR Terdekat (Main Building UC)

Aplikasi Web GIS interaktif berbasis Streamlit dan Shapely untuk memetakan denah ruangan, titik APAR (Alat Pemadam Api Ringan), dan Hydrant di Main Building Universitas Ciputra (Lantai 1 - 7).

## Fitur Utama
1. **Pemetaan Interaktif:** Visualisasi denah tiap lantai beserta batas luar (*footprint*), poligon ruangan, titik APAR, dan Hydrant.
2. **Spatial Query:**
   - Pencarian APAR terdekat dari ruangan tertentu menggunakan `centroid` dan `distance`.
   - Analisis jangkauan APAR radius 15 meter menggunakan `buffer(15)` dan uji jangkauan ruangan dengan `intersects`.

## Struktur Direktori
```text
├── app.py                  # Aplikasi utama Streamlit
├── requirements.txt        # Daftar dependency project
├── README.md               # Dokumentasi project
├── data/
│   ├── LT_1.geojson ...    # GeoJSON per lantai (footprint, rooms, APAR, hydrant)
│   ├── build_geojson.py    # Generator / digitasi GeoJSON dari denah
│   └── sumber/             # File denah asli arsitektur (.jpeg)
└── notebooks/              # Jupyter Notebook eksperimen & analisis spasial
```

## Menjalankan Aplikasi
1. Aktifkan virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
2. Jalankan aplikasi Streamlit:
   ```powershell
   streamlit run app.py
   ```