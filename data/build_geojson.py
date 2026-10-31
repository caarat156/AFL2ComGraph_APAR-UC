"""Build GeoJSON denah Main Building UC (LT_1 .. LT_7).

Isi tiap file data/LT_*.geojson:
  - 1 feature  type="footprint" : batas luar gedung (Polygon)
  - N feature  type="room"      : ruangan hasil digitasi manual dari gambar sumber (Polygon)
  - N feature  type="APAR"      : titik merah hasil deteksi warna (Point)
  - N feature  type="Hydrant"   : titik biru hasil deteksi warna (Point)

Sistem koordinat: piksel gambar sumber (1600x1280), x ke kanan, y ke bawah.
Skala: garis dimensi "1000" (cm) = 150 px  ->  PX_PER_M = 15.
Jadi radius 15 m = 15 * PX_PER_M = 225 px.

Jalankan dari root project:
    python data/build_geojson.py            # tulis GeoJSON
    python data/build_geojson.py --preview  # + gambar cek di data/preview/
"""
from pathlib import Path
import json
import sys

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Point, Polygon, LineString, box, mapping

DATA = Path(__file__).resolve().parent
SOURCE = DATA / "sumber"
PREVIEW = DATA / "preview"
PX_PER_M = 15.0

FLOORS = {
    "LT_1": "Denah Lantai 1jpeg.jpeg",
    "LT_2": "Denah Lantai 2.jpeg",
    "LT_2A": "Denah Lantai 2A.jpeg",
    "LT_3": "Denah Lantai 3.jpeg",
    "LT_4": "Denah Lantai 4.jpeg",
    "LT_5": "Denah Lantai 5.jpeg",
    "LT_6": "Denah Lantai 6.jpeg",
    "LT_7": "Denah Lantai 7.jpeg",
}

# Footprint = bagian gedung yang tertutup (plaza terbuka di LT_1/LT_2/LT_2A tidak ikut).
FOOTPRINT = {
    "LT_1": [(60, 158), (1570, 158), (1570, 466), (60, 466)],
    "LT_2": [(75, 172), (1578, 172), (1578, 468), (75, 468)],
    "LT_2A": [(62, 170), (1560, 170), (1560, 473), (62, 473)],
    "LT_3": [(40, 182), (1548, 182), (1548, 500), (975, 500), (975, 1085),
             (640, 1085), (640, 500), (25, 500), (25, 380), (40, 380)],
    "LT_4": [(48, 202), (1568, 202), (1568, 515), (1000, 515), (1000, 1080),
             (650, 1080), (650, 515), (48, 515)],
    "LT_5": [(48, 188), (1568, 188), (1568, 500), (1000, 500), (1000, 1065),
             (650, 1065), (650, 500), (48, 500)],
    "LT_6": [(45, 210), (1565, 210), (1565, 518), (1000, 518), (1000, 1078),
             (650, 1078), (650, 518), (45, 518)],
    "LT_7": [(50, 180), (1565, 180), (1565, 487), (1000, 487), (1000, 1082),
             (648, 1082), (648, 487), (50, 487)],
}

# Koridor utama per lantai (LineString): jalur jalan kaki di lorong.
# Berbentuk huruf T (sayap barat-timur dan sayap tengah vertikal).
CORRIDORS = {
    "LT_1": [
        [(80, 342), (1540, 342)],
        [(960, 342), (960, 450)],
    ],
    "LT_2": [
        [(90, 348), (1550, 348)],
    ],
    "LT_2A": [
        [(80, 350), (1530, 350)],
    ],
    "LT_3": [
        [(60, 362), (1520, 362)],
        [(832, 362), (832, 1050)],
    ],
    "LT_4": [
        [(70, 378), (1540, 378)],
        [(858, 378), (858, 1050)],
    ],
    "LT_5": [
        [(70, 362), (1540, 362)],
        [(858, 362), (858, 1040)],
    ],
    "LT_6": [
        [(70, 385), (1540, 385)],
        [(858, 385), (858, 1050)],
    ],
    "LT_7": [
        [(70, 362), (1540, 362)],
        [(858, 362), (858, 1050)],
    ],
}

# Ruangan: (kode, nama, geometri)
#   geometri = (x1, y1, x2, y2) -> persegi panjang
#   geometri = [(x, y), ...]    -> polygon bebas
# Ruangan kecil yang berada DI DALAM ruangan lain otomatis dilubangi
# dari ruangan induknya (lihat resolve_nested).
ROOMS = {
    "LT_1": [
        ("113", "Lab 113", (148, 160, 580, 318)),
        ("113a", "113a", (110, 245, 148, 318)),
        ("113b", "113b", (110, 200, 148, 245)),
        ("113c", "113c-d", (110, 160, 148, 200)),
        ("102", "Musholla", (665, 160, 740, 220)),
        ("101", "LOT", (665, 220, 765, 318)),
        ("103", "R. Server", (765, 160, 810, 195)),
        ("ENT", "Entrance", (665, 318, 975, 466)),
        ("114", "Kelas (tanpa nomor)", (60, 365, 500, 466)),
        ("115a", "Lab. Penelitian", (500, 365, 615, 466)),
        ("116", "Klinik", (615, 385, 660, 466)),
        ("104", "Workshop & Business Unit", (980, 160, 1110, 318)),
        ("105", "CBZ Hot Kitchen Laboratory", (1110, 160, 1255, 318)),
        ("107", "CBZ Kitchen Studio Laboratory",
         [(1255, 160), (1410, 160), (1410, 466), (1290, 466), (1290, 410), (1255, 410)]),
        ("107A", "Laboratorium Support", (1255, 410, 1290, 466)),
        ("110", "CBZ Beverages Laboratory", (1410, 190, 1515, 310)),
        ("109", "CBZ Kitchen Studio Laboratory", (1410, 310, 1570, 466)),
        ("106", "Restaurant & Bar", (980, 318, 1125, 466)),
        ("108", "CBZ Pastry Kitchen Laboratory", (1125, 360, 1255, 466)),
    ],
    "LT_2": [
        ("222", "Area Koleksi", (125, 172, 465, 330)),
        ("222a", "R. Pengolahan", (465, 190, 520, 225)),
        ("222b", "R. Audio Visual", (465, 230, 520, 300)),
        ("221", "Life Action Laboratory", (520, 172, 670, 330)),
        ("223", "Entrepreneurship Corner", (75, 330, 215, 468)),
        ("224", "224", (215, 330, 275, 420)),
        ("225a", "Collaboration Room", (225, 420, 300, 468)),
        ("225", "Lounge Perpustakaan", [(275, 330), (525, 330), (525, 468), (300, 468), (300, 420), (275, 420)]),
        ("226", "Student Lounge", (525, 330, 630, 468)),
        ("226b", "Rg. Laktasi", (615, 330, 640, 360)),
        ("226a", "Command Centre", (630, 400, 675, 468)),
        ("201C", "Tax Center", (990, 172, 1055, 235)),
        ("201B", "Rg. SRB", (990, 235, 1055, 285)),
        ("201A", "Rg. SC", (990, 285, 1055, 330)),
        ("201", "Rg. Meeting", (995, 330, 1055, 370)),
        ("202", "Student Lounge", (1055, 172, 1315, 330)),
        ("203", "BAA", (1315, 172, 1465, 330)),
        ("203A", "Rg. Produksi", (1420, 180, 1465, 212)),
        ("203B", "Rg. Arsip BAA", (1465, 172, 1525, 330)),
        ("207", "BMA", (1040, 365, 1225, 465)),
        ("206", "Rg. Konseling BMA", (1120, 365, 1215, 398)),
        ("208", "Gudang BMA", (995, 400, 1040, 465)),
        ("205", "MNA", (1225, 365, 1525, 465)),
        ("204", "Gudang MNA", (1525, 365, 1575, 465)),
    ],
    "LT_2A": [
        ("230", "Lab IKM - FK", (112, 172, 215, 327)),
        ("229", "Kelas", (215, 172, 368, 327)),
        ("228", "Kelas", (368, 172, 518, 327)),
        ("227", "Kelas", (518, 172, 660, 327)),
        ("231-232", "UC Online", (62, 372, 368, 473)),
        ("234", "NNP", (368, 372, 520, 473)),
        ("235", "CAD", (560, 405, 660, 473)),
        ("210-211", "Meeting Room", (975, 170, 1250, 327)),
        ("212c", "Rector", (1252, 172, 1325, 220)),
        ("212d", "Vice 3", (1325, 172, 1400, 220)),
        ("214b", "BOD", (1400, 172, 1488, 220)),
        ("212b", "Vice 2", (1252, 220, 1310, 272)),
        ("212a", "Vice 1", (1252, 272, 1310, 327)),
        ("212", "Directors", (1310, 220, 1425, 248)),
        ("213", "Meeting Room", (1343, 248, 1405, 327)),
        ("214a", "EBO", (1425, 220, 1488, 272)),
        ("214", "EBO", (1405, 272, 1488, 327)),
        ("LOBBY", "Lobby", (1205, 327, 1330, 405)),
        ("220", "Multimedia Room", (975, 405, 1050, 473)),
        ("219", "LSP", (1050, 405, 1120, 473)),
        ("218", "QA", (1120, 405, 1325, 473)),
        ("216", "University Office", (1330, 375, 1400, 473)),
        ("215", "HCM", (1400, 375, 1560, 473)),
    ],
    "LT_3": [
        ("324G", "Keterampilan Medik", (95, 182, 145, 265)),
        ("324H", "Keterampilan Medik", (145, 182, 197, 265)),
        ("324I", "Keterampilan Medik", (197, 182, 248, 265)),
        ("324J", "Keterampilan Medik", (248, 182, 298, 265)),
        ("324K", "Keterampilan Medik", (298, 182, 348, 265)),
        ("324L", "Keterampilan Medik", (348, 182, 398, 265)),
        ("324M", "Keterampilan Medik", (398, 182, 462, 265)),
        ("324N", "Keterampilan Medik", (462, 182, 533, 265)),
        ("324O", "Keterampilan Medik", (533, 182, 605, 265)),
        ("323", "Gudang", (605, 182, 640, 265)),
        ("324F", "Keterampilan Medik", (112, 268, 162, 338)),
        ("324E", "Keterampilan Medik", (162, 268, 212, 338)),
        ("324D", "Keterampilan Medik", (212, 268, 258, 338)),
        ("324C", "Keterampilan Medik", (258, 268, 303, 338)),
        ("324B", "Keterampilan Medik", (303, 268, 348, 338)),
        ("324A", "Keterampilan Medik", (348, 268, 398, 338)),
        ("321A", "R. Tutor", (418, 268, 500, 338)),
        ("321B", "R. Tutor", (500, 268, 578, 338)),
        ("322", "R. Penguji & R. Kendali", (578, 268, 640, 338)),
        ("325", "R. Gudang Manekin", (25, 382, 340, 500)),
        ("326", "Gudang Penyimpanan", (340, 382, 435, 500)),
        ("327", "R. Belajar Manekin", (435, 382, 500, 500)),
        ("328", "R. WD1", (500, 385, 548, 450)),
        ("329", "R. WD2", (548, 385, 597, 450)),
        ("330", "R. Dekan", (597, 385, 645, 450)),
        ("330a", "R. WD3", (645, 385, 690, 450)),
        ("331", "Academic Support", (715, 385, 800, 480)),
        ("310", "Rg. Dosen MED", (640, 480, 805, 630)),
        ("309", "Kelas", (640, 630, 805, 780)),
        ("307-308", "Kelas", (640, 780, 805, 1085)),
        ("301", "Academic Support", (862, 385, 955, 470)),
        ("302", "Rg. Dosen MDP", (860, 485, 975, 780)),
        ("304", "Rg. Dosen MED", (860, 780, 975, 930)),
        ("306", "Rg. Meeting", (860, 930, 955, 1040)),
        ("311", "Lab 311", (955, 182, 1100, 350)),
        ("312", "Lab 312", (1100, 182, 1240, 350)),
        ("313", "Lab 313", (1240, 182, 1390, 350)),
        ("314", "Server", (1390, 182, 1490, 340)),
        ("320", "HOD MDP", (955, 385, 1005, 455)),
        ("319", "WD 3", (1005, 385, 1055, 455)),
        ("318", "WD 2", (1055, 385, 1100, 455)),
        ("317", "Metrodata", (1100, 385, 1235, 500)),
        ("316", "Kelas 316", (1235, 385, 1395, 500)),
        ("KPL", "R. Kpl Lab", (1395, 415, 1435, 500)),
        ("315", "Lab Komp", (1435, 385, 1545, 500)),
    ],
    "LT_4": [
        ("421", "Lab. Sensori", (110, 202, 198, 355)),
        ("420", "Lab. Penelitian", (198, 202, 370, 355)),
        ("418", "R. Steril & Autoclave", (370, 215, 422, 245)),
        ("419", "R. Laboran", (370, 255, 422, 305)),
        ("419a", "R. Penyimpanan", (370, 310, 422, 355)),
        ("417", "Lab. Penelitian", (422, 202, 665, 355)),
        ("408", "FA", (980, 202, 1125, 355)),
        ("409", "Pantry & Gudang FA/PM", (1125, 202, 1258, 355)),
        ("410", "PM", (1258, 202, 1410, 355)),
        ("411", "ICT", (1410, 202, 1515, 355)),
        ("422", "Kelas", (48, 400, 220, 515)),
        ("423", "Kelas", (220, 400, 370, 515)),
        ("424", "Storage Alat2 FTP", (370, 400, 435, 495)),
        ("425", "Rg. Dosen FTP", (435, 400, 605, 495)),
        ("425b", "R. Kaprogdi FTP", (605, 402, 665, 435)),
        ("425a", "R. Dekan FTP", (665, 408, 735, 440)),
        ("407", "Academic Support FTO", (735, 408, 822, 490)),
        ("406", "SEH - DLB", (665, 495, 830, 640)),
        ("405B", "Kelas / LCC", (665, 640, 830, 785)),
        ("404", "Lab. HTB", (665, 785, 830, 1080)),
        ("401", "Academic Support CB / HTB", (885, 402, 980, 495)),
        ("402", "R. Dosen HTB", (885, 495, 980, 660)),
        ("403", "SEH", (885, 680, 980, 1040)),
        ("416", "Kaprogdi", (980, 435, 1025, 495)),
        ("415", "Kaprogdi", (1025, 435, 1070, 495)),
        ("414", "Kaprogdi", (1070, 435, 1115, 495)),
        ("CBZ", "R. Dosen CBZ", (1115, 402, 1290, 495)),
        ("413", "413", (1290, 402, 1415, 515)),
        ("412", "ICT", (1415, 402, 1565, 515)),
    ],
    "LT_5": [
        ("516-517", "Lab Histologi & PA", (112, 188, 455, 340)),
        ("515", "Kelas", (455, 188, 665, 340)),
        ("507", "Kelas", (980, 188, 1185, 340)),
        ("508", "Kelas", (1185, 188, 1410, 340)),
        ("509", "Mini Theater", (1410, 188, 1515, 340)),
        ("518", "Lab. Faal & Farmakologi", (48, 385, 370, 500)),
        ("519", "Kelas", (370, 385, 665, 485)),
        ("506", "CoE", (668, 390, 830, 555)),
        ("505b", "Kelas", (668, 555, 830, 700)),
        ("505a", "Kelas", (668, 700, 830, 845)),
        ("504", "Kelas", (668, 845, 830, 1065)),
        ("501", "Academic Support", (885, 385, 980, 470)),
        ("502A", "HOD IMT", (885, 483, 952, 530)),
        ("502B", "Dean FTI", (885, 530, 952, 578)),
        ("502C", "HOD ISB", (885, 578, 952, 628)),
        ("503", "R. Dosen FTI", (885, 628, 980, 1020)),
        ("513", "Lounge", (980, 385, 1105, 485)),
        ("512", "Rg. Meeting", (1105, 385, 1197, 485)),
        ("511", "Rg. Meeting", (1197, 385, 1260, 485)),
        ("510", "Lounge", (1260, 360, 1568, 500)),
    ],
    "LT_6": [
        ("619b", "619b", (110, 210, 192, 272)),
        ("618d", "618d", (192, 210, 270, 272)),
        ("618c", "618c", (270, 210, 348, 272)),
        ("617d", "617d", (348, 210, 426, 272)),
        ("617c", "617c", (426, 210, 505, 272)),
        ("616c", "616c", (505, 210, 583, 272)),
        ("616b", "616b", (583, 210, 665, 272)),
        ("619a", "Ruang Kendali", (150, 308, 213, 372)),
        ("618b", "618b", (213, 308, 290, 372)),
        ("618a", "618a", (290, 308, 370, 372)),
        ("617b", "617b", (370, 308, 448, 372)),
        ("617a", "617a", (448, 308, 526, 372)),
        ("616a", "616a", (526, 308, 605, 372)),
        ("620", "Lab. Bio Oral", (45, 405, 218, 515)),
        ("621", "Kelas", (218, 405, 368, 515)),
        ("622", "Kelas", (368, 405, 518, 505)),
        ("623", "Kelas", (518, 405, 663, 500)),
        ("625", "Ruang Meeting", (663, 412, 733, 500)),
        ("626a", "Lab PSY One Way Mirror", (733, 412, 825, 455)),
        ("626b", "626b", (733, 455, 825, 500)),
        ("607", "LPPM", (665, 500, 828, 785)),
        ("606", "Kelas FKG", (665, 785, 828, 930)),
        ("605", "Lab Skill", (665, 930, 828, 1078)),
        ("601", "Academic Support FKG", (885, 412, 930, 495)),
        ("615a", "Dekan", (930, 412, 972, 470)),
        ("615b", "Wadek 1", (972, 412, 1015, 470)),
        ("615c", "Wadek 2", (1015, 412, 1058, 470)),
        ("615d", "Wadek 3", (1058, 412, 1100, 470)),
        ("614", "Dosen FKG", (1100, 412, 1255, 498)),
        ("601a", "Kaprog", (885, 500, 930, 540)),
        ("615e", "Kaprog", (930, 500, 975, 540)),
        ("602a", "R. Monitor", (885, 540, 940, 568)),
        ("602b", "Gudang Alat Tes", (940, 540, 975, 568)),
        ("602", "Lab PSY", (885, 570, 975, 760)),
        ("603", "Lab PSY", (885, 760, 975, 905)),
        ("604", "Rg. Diskusi FKG", (882, 905, 975, 1032)),
        ("608", "Lab IMTKG", (978, 210, 1120, 358)),
        ("609", "Kelas FKG", (1120, 210, 1255, 358)),
        ("610-611", "TLiC", (1255, 210, 1400, 358)),
        ("613", "Kelas", (1265, 405, 1412, 518)),
        ("612", "Rg. UKM", (1412, 405, 1563, 518)),
    ],
    "LT_7": [
        ("713", "Theater", (120, 180, 530, 340)),
        ("712", "Kelas", (530, 180, 668, 335)),
        ("714A", "R. Tutor 1", (72, 383, 124, 480)),
        ("714B", "R. Tutor 2", (124, 383, 175, 480)),
        ("714C", "R. Tutor 3", (175, 383, 227, 480)),
        ("714D", "R. Tutor 4", (227, 383, 277, 480)),
        ("714E", "R. Tutor 5", (277, 383, 327, 480)),
        ("714F", "R. Tutor 6", (327, 383, 377, 480)),
        ("714G", "R. Tutor 7", (377, 383, 427, 480)),
        ("714H", "R. Tutor 8", (427, 383, 477, 480)),
        ("714i", "R. Tutor 9", (477, 383, 527, 480)),
        ("714J", "R. Tutor 10", (527, 383, 577, 480)),
        ("714K", "R. Tutor 11", (577, 383, 624, 480)),
        ("714L", "R. Tutor 12", (624, 383, 668, 480)),
        ("PREF", "Prefunction", (668, 340, 1085, 480)),
        ("707", "Storage", (982, 180, 1130, 335)),
        ("708", "Storage", (1130, 215, 1215, 290)),
        ("709", "Storage", (1148, 290, 1215, 385)),
        ("710", "Storage Auditorium", (1085, 425, 1215, 485)),
        ("711", "Auditorium (Kapasitas 500)", (1215, 180, 1475, 485)),
        ("701A", "R. Tutor 13", (888, 483, 975, 530)),
        ("701B", "R. Tutor 14", (888, 530, 975, 580)),
        ("701C", "R. Tutor 15", (888, 580, 975, 630)),
        ("702", "Gudang Alat FK", (888, 630, 975, 780)),
        ("705-706", "Ruang VR", (672, 480, 830, 780)),
        ("703-704", "Theater 2 (On Progress)", (672, 780, 980, 1080)),
    ],
}


def to_polygon(geom):
    if isinstance(geom, tuple) and len(geom) == 4:
        return box(*geom)
    return Polygon(geom)


def resolve_nested(rooms):
    """Jika ruangan B berada di dalam ruangan A, lubangi A dengan B (A = A - B)."""
    polys = [to_polygon(g) for _, _, g in rooms]
    for i, a in enumerate(polys):
        for j, b in enumerate(polys):
            if i != j and b.area < a.area and b.within(a.buffer(1)):
                a = a.difference(b)
        polys[i] = a
    return polys


def label_components(mask):
    """Connected-component labeling sederhana (8-tetangga), pengganti cv2."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    comps = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, pix = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        comps.append(np.array(pix))
    return comps


def detect_dots(image, kind):
    hsv = np.array(image.convert("HSV")).astype(int)  # H,S,V dalam 0..255
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if kind == "APAR":
        mask = ((h <= 17) | (h >= 241)) & (s >= 90) & (v >= 90)
    else:
        mask = (h >= 135) & (h <= 191) & (s >= 90) & (v >= 80)
    points = []
    for pix in label_components(mask):
        if len(pix) < 35:
            continue
        cy, cx = pix[:, 0].mean(), pix[:, 1].mean()
        if 45 < cx < 1580 and 110 < cy < 1110:  # buang legenda di pojok kanan bawah
            points.append(Point(round(float(cx), 1), round(float(cy), 1)))
    return sorted(points, key=lambda p: (p.y, p.x))


def build_floor(floor, filename):
    image = Image.open(SOURCE / filename).convert("RGB")
    footprint = Polygon(FOOTPRINT[floor])
    rooms = ROOMS[floor]
    room_polys = resolve_nested(rooms)
    apar = detect_dots(image, "APAR")
    hydrant = detect_dots(image, "Hydrant")
    near_building = footprint.buffer(15)  # titik di garis dinding tetap dianggap di dalam

    features = [{
        "type": "Feature",
        "properties": {"floor": floor, "type": "footprint"},
        "geometry": mapping(footprint),
    }]
    for (code, name, _), poly in zip(rooms, room_polys):
        features.append({
            "type": "Feature",
            "properties": {
                "floor": floor, "type": "room", "id": f"{floor}-{code}",
                "code": code, "name": name,
                "area_m2": round(poly.area / PX_PER_M ** 2, 1),
            },
            "geometry": mapping(poly),
        })
    for i, line_coords in enumerate(CORRIDORS.get(floor, []), 1):
        features.append({
            "type": "Feature",
            "properties": {
                "floor": floor, "type": "corridor", "id": f"{floor}-corridor-{i}",
            },
            "geometry": mapping(LineString(line_coords)),
        })
    for kind, points in (("APAR", apar), ("Hydrant", hydrant)):
        for i, p in enumerate(points, 1):
            features.append({
                "type": "Feature",
                "properties": {
                    "floor": floor, "type": kind, "id": f"{floor}-{kind}-{i:02d}",
                    "inside_building": bool(near_building.contains(p)),
                },
                "geometry": mapping(p),
            })

    collection = {
        "type": "FeatureCollection",
        "name": floor,
        "metadata": {
            "source_image": filename,
            "coordinate_system": "source image pixels (x right, y down)",
            "image_size": list(image.size),
            "px_per_m": PX_PER_M,
        },
        "features": features,
    }
    (DATA / f"{floor}.geojson").write_text(json.dumps(collection, indent=2), encoding="utf-8")
    return image, footprint, list(zip(rooms, room_polys)), apar, hydrant


def draw_preview(floor, image, footprint, rooms, apar, hydrant):
    PREVIEW.mkdir(exist_ok=True)
    img = image.copy().convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.line(list(footprint.exterior.coords), fill=(0, 160, 0, 255), width=3)
    for (code, _, _), poly in rooms:
        for part in getattr(poly, "geoms", [poly]):
            d.polygon(list(part.exterior.coords), fill=(255, 200, 0, 70), outline=(230, 120, 0, 255))
        c = poly.representative_point()
        d.text((c.x - 10, c.y - 5), code, fill=(120, 0, 120, 255))
    for p in apar:
        d.ellipse((p.x - 7, p.y - 7, p.x + 7, p.y + 7), outline=(255, 0, 0, 255), width=3)
    for p in hydrant:
        d.ellipse((p.x - 7, p.y - 7, p.x + 7, p.y + 7), outline=(0, 60, 255, 255), width=3)
    Image.alpha_composite(img, layer).convert("RGB").save(PREVIEW / f"{floor}_preview.png")


def main():
    preview = "--preview" in sys.argv
    for floor, filename in FLOORS.items():
        image, footprint, rooms, apar, hydrant = build_floor(floor, filename)
        if preview:
            draw_preview(floor, image, footprint, rooms, apar, hydrant)
        print(f"{floor}: {len(rooms)} ruangan, {len(apar)} APAR, {len(hydrant)} Hydrant")


if __name__ == "__main__":
    main()
