"""
coord_transform.py —— 坐标转换模块
====================================
百度墨卡托(BD-09MC) → 高德(GCJ-02) → WGS84 坐标转换
集成自用户提供的 convert_coords.py（百度官方系数版）
"""
import math


# ============================================================
# 百度墨卡托反算系数（来自百度官方）
# ============================================================
MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
MC2LL = [
    [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331, 200.9824383106796,
     -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198,
     -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289, 96.32687599759846,
     -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887,
     2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616, 59.74293618442277,
     7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584,
     0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591, 40.31678527705744,
     0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204,
     -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062, 23.10934304144901,
     -0.00023663490511, -0.6321817810242, -0.00663494467042, 0.03430082397953,
     -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8, 7.47137025468032,
     -0.00000353937994, -0.02145144861037, -0.00001234426596, 0.00010322952773,
     -0.00000323890364, 826088.5]
]
x_pi = 3.14159265358979324 * 3000.0 / 180.0

# 残差修正系数
CORR_LNG = [1.74778933e-03, -3.35808143e-03, -7.64205396e-02]
CORR_LAT = [-1.28829969e-04, -2.66704274e-03, 1.07697590e-01]

# GCJ-02 反算常量
GCJ_A = 6378245.0
GCJ_EE = 0.00669342162296594323


def bd_mc_to_bd09(x, y):
    """百度墨卡托坐标 → BD-09 经纬度"""
    cF = None
    for i, band in enumerate(MCBAND):
        if abs(y) >= band:
            cF = MC2LL[i]
            break
    if cF is None:
        cF = MC2LL[-1]
    T = abs(y)
    lng = cF[0] + cF[1] * abs(x)
    cC = T / cF[9]
    lat = (cF[2] + cF[3] * cC + cF[4] * cC**2 + cF[5] * cC**3 +
           cF[6] * cC**4 + cF[7] * cC**5 + cF[8] * cC**6)
    if x < 0:
        lng = -lng
    if y < 0:
        lat = -lat
    return lng, lat


def bd09_to_gcj02(bd_lng, bd_lat):
    """BD-09 → GCJ-02"""
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    return z * math.cos(theta), z * math.sin(theta)


def residual_correction(gcj_lng, gcj_lat):
    """线性残差修正"""
    dlng = CORR_LNG[0] * gcj_lng + CORR_LNG[1] * gcj_lat + CORR_LNG[2]
    dlat = CORR_LAT[0] * gcj_lng + CORR_LAT[1] * gcj_lat + CORR_LAT[2]
    return gcj_lng + dlng, gcj_lat + dlat


def _transform_lat(lng, lat):
    """GCJ-02 纬度偏移计算"""
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 *
            math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 *
            math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320 *
            math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng, lat):
    """GCJ-02 经度偏移计算"""
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 *
            math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * math.pi) + 40.0 *
            math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 *
            math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(gcj_lng, gcj_lat):
    """GCJ-02 → WGS-84（用于点面匹配，GeoJSON是WGS84）"""
    dlat = _transform_lat(gcj_lng - 105.0, gcj_lat - 35.0)
    dlng = _transform_lng(gcj_lng - 105.0, gcj_lat - 35.0)
    radlat = gcj_lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - GCJ_EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((GCJ_A * (1 - GCJ_EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (GCJ_A / sqrtmagic * math.cos(radlat) * math.pi)
    return gcj_lng - dlng, gcj_lat - dlat


def bd09mc_to_gcj02(x_mc, y_mc):
    """完整转换: BD-09MC → BD-09 → GCJ-02 + 修正"""
    bd_lng, bd_lat = bd_mc_to_bd09(x_mc, y_mc)
    gcj_lng, gcj_lat = bd09_to_gcj02(bd_lng, bd_lat)
    return residual_correction(gcj_lng, gcj_lat)


def bd09mc_to_wgs84(x_mc, y_mc):
    """BD-09MC → WGS84（用于点面匹配）"""
    gcj_lng, gcj_lat = bd09mc_to_gcj02(x_mc, y_mc)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def convert_batch(df, x_col='X坐标', y_col='Y坐标'):
    """批量转换坐标列，返回新的longitude/latitude列"""
    import pandas as pd
    lngs = []
    lats = []
    errors = 0
    for idx, row in df.iterrows():
        try:
            x = float(row[x_col])
            y = float(row[y_col])
            lng, lat = bd09mc_to_gcj02(x, y)
            if not (110.0 < lng < 112.0 and 34.5 < lat < 35.5):
                lngs.append(None)
                lats.append(None)
                errors += 1
            else:
                lngs.append(round(lng, 6))
                lats.append(round(lat, 6))
        except (ValueError, TypeError):
            lngs.append(None)
            lats.append(None)
            errors += 1
    return lngs, lats, errors
