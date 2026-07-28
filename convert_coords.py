"""
百度墨卡托(BD-09MC) → 高德(GCJ-02) 坐标批量转换脚本
使用方法: python convert_coords.py 输入文件.xlsx
输出: 输入文件名_converted.xlsx
"""
import math
import sys
import os

try:
    import pandas as pd
except ImportError:
    print("需要安装 pandas 和 openpyxl: pip install pandas openpyxl")
    sys.exit(1)

# ============================================================
# 百度墨卡托反算系数
# ============================================================
MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
MC2LL = [
    [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331, 200.9824383106796, -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289, 96.32687599759846, -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616, 59.74293618442277, 7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591, 40.31678527705744, 0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062, 23.10934304144901, -0.00023663490511, -0.6321817810242, -0.00663494467042, 0.03430082397953, -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8, 7.47137025468032, -0.00000353937994, -0.02145144861037, -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5]
]
x_pi = 3.14159265358979324 * 3000.0 / 180.0

# 残差修正系数
CORR_LNG = [1.74778933e-03, -3.35808143e-03, -7.64205396e-02]
CORR_LAT = [-1.28829969e-04, -2.66704274e-03, 1.07697590e-01]


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


def convert(x, y):
    """完整转换: BD-09MC → BD-09 → GCJ-02 + 修正"""
    bd_lng, bd_lat = bd_mc_to_bd09(x, y)
    gcj_lng, gcj_lat = bd09_to_gcj02(bd_lng, bd_lat)
    final_lng, final_lat = residual_correction(gcj_lng, gcj_lat)
    return final_lng, final_lat


def main():
    if len(sys.argv) < 2:
        print("用法: python convert_coords.py 输入文件.xlsx [X列名] [Y列名]")
        print("示例: python convert_coords.py data.xlsx X Y")
        sys.exit(1)

    input_file = sys.argv[1]
    x_col = sys.argv[2] if len(sys.argv) > 2 else None
    y_col = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.exists(input_file):
        print(f"文件不存在: {input_file}")
        sys.exit(1)

    print(f"读取文件: {input_file}")
    df = pd.read_excel(input_file)
    print(f"共 {len(df)} 行数据")
    print(f"列名: {list(df.columns)}")

    # 自动检测X/Y列
    if x_col is None or y_col is None:
        cols = [str(c).strip() for c in df.columns]
        x_col = None
        y_col = None
        for c in cols:
            cl = c.lower()
            if cl in ('x', 'x坐标', 'x_coord', 'xcoord', '经度', 'lng', 'longitude'):
                x_col = c
            elif cl in ('y', 'y坐标', 'y_coord', 'ycoord', '纬度', 'lat', 'latitude'):
                y_col = c
        if x_col is None or y_col is None:
            print("无法自动识别X/Y列，请手动指定:")
            print(f"用法: python convert_coords.py {input_file} <X列名> <Y列名>")
            sys.exit(1)
        print(f"自动识别: X列='{x_col}', Y列='{y_col}'")

    # 转换
    lngs = []
    lats = []
    errors = 0
    for idx, row in df.iterrows():
        try:
            x = float(row[x_col])
            y = float(row[y_col])
            lng, lat = convert(x, y)
            # 异常值检查（运城范围: lng 110.5~111.5, lat 34.8~35.3）
            if not (110.0 < lng < 112.0 and 34.5 < lat < 35.5):
                print(f"  警告: 第{idx+2}行坐标异常 lng={lng:.6f}, lat={lat:.6f}")
            lngs.append(round(lng, 6))
            lats.append(round(lat, 6))
        except (ValueError, TypeError):
            lngs.append(None)
            lats.append(None)
            errors += 1

    # 替换原列
    df[x_col] = lngs
    df[y_col] = lats

    # 重命名列（如果列名是X/Y）
    if x_col.upper() == 'X':
        df = df.rename(columns={x_col: '经度'})
    if y_col.upper() == 'Y':
        df = df.rename(columns={y_col: '纬度'})

    # 输出
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_converted.xlsx"
    df.to_excel(output_file, index=False)
    print(f"\n转换完成!")
    print(f"  成功: {len(df) - errors} 条")
    if errors:
        print(f"  失败: {errors} 条")
    print(f"  输出: {output_file}")


if __name__ == "__main__":
    main()
