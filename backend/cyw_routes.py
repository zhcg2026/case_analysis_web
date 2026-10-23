# -*- coding: utf-8 -*-
"""创文问题处置模块（一期）——监控盯守问题的登记/反馈全流程台账。

安全约定（与考核人工录入模块一致）：
- 仅 CREATE TABLE IF NOT EXISTS 新建 cyw_ 前缀表，不改 case_data 等既有业务表
- 不 DROP 任何业务数据表
- 照片/详单落 backend/uploads/cyw/ 子目录，经 app.py 既有 /uploads/ 静态路由访问

状态机（2026-10-16 简化）：登记即视为已派发，直接进入「处置中」；部门反馈即办结，
转「已办结」。不标记派发、不核销、不退回，也不计算超时——只剩两个状态。
历史四态数据由 ensure_cyw_tables 里的 _normalize_status 一次性归并（幂等）。
权限：字典（点位/部门/类型）admin 维护；案件登记凭 cyw_input、反馈凭 cyw_ledger
（admin 直通，普通用户需 permissions 对应列=1；照片上传/详单/照片识别为录入与台账共用，两列取「或」）。
AI 识别：POST /api/cyw/parse-photo 调本机 ollama 私有化 Qwen2.5-VL 解析照片，失败/超时一律
success:false 由前端静默降级为手动填写，不阻断登记（云端 API 不合规，不走）。
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import uuid
from collections import Counter
from datetime import datetime, date, time, timedelta
from urllib.parse import quote

import pandas as pd
import requests
from flask import request, jsonify, Response
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import bindparam, text
from functools import wraps

logger = logging.getLogger(__name__)

try:
    from common import protected as _protected, admin_required as _admin_required
    from common import verify_token as _verify_token
except ImportError:
    from helpers import protected as _protected, admin_required as _admin_required
    from helpers import verify_token as _verify_token

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
CYW_PHOTO_DIR = os.path.join(UPLOAD_DIR, 'cyw', 'photos')
CYW_SLIP_DIR = os.path.join(UPLOAD_DIR, 'cyw', 'slips')
for _d in (CYW_PHOTO_DIR, CYW_SLIP_DIR):
    os.makedirs(_d, exist_ok=True)

ALLOWED_IMG_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# AI 照片识别（私有化 Qwen2.5-VL，走本机 ollama 容器；云端 API 不合规故不用）
CYW_VL_MODEL = os.getenv('CYW_VL_MODEL', 'qwen2.5vl:7b')
CYW_VL_TIMEOUT = int(os.getenv('CYW_VL_TIMEOUT', '90'))
OLLAMA_HOST_CYW = os.getenv('OLLAMA_HOST', 'http://ollama:11434')

# VL 类型知识卡：每类的视觉判定要点 + 台账真实案例（案例取自 2026.1-5 台账 1000 行的描述风格）。
# 7B 小模型只给类型名时没有判定依据、准确率低；给"封闭类型集+判定要点+同风格案例"后
# 实测类型选择明显更稳。字典里新增的类型没有知识卡，退化为只给类型名。
CYW_TYPE_HINTS = {
    '垃圾不洁': ('地面/路面/绿化带/树坑里有零散或成片垃圾、纸屑、烟头、塑料袋、油污、尘土、落叶、粪便、污水。车辆、坐凳、配电箱等设施不算垃圾',
              ['人行道上有垃圾', '绿化带内有白色垃圾', '路面油污脏洁']),
    '机动车乱停放': ('汽车/货车/SUV/微型四轮电动车/老年代步车等四轮或有牌照的车辆（含警车）违停、占道、压线、双排停放、占用消防通道/人行道/绿化带；停在划线车位/停放区内按规定停的不算',
                ['机动车乱停放', '机动车占用人行道', '微型电动车停在人行道']),
    '非机动车乱停放': ('电动车/自行车/共享单车/三轮车（两个轮、车身小）乱停、占用盲道或通道；停在划线停放区/车位内的不算',
                  ['非机动车乱停放', '电动车占用盲道', '共享单车占道']),
    '占道经营': ('流动摊贩占道、商户店外经营、摆摊售卖、出店堆放货品',
             ['流动摊贩占道经营', '商户出店经营', '摊贩占道售卖']),
    '乱堆物料': ('商铺/住户门前、人行道上成堆堆放的商品、物品、物料（店外经营外摆、门前堆物）',
             ['店外物料乱堆放', '商铺门前乱堆物品', '乱堆物料']),
    '遛狗不牵绳': ('画面中有人遛狗且未牵绳', ['市民遛狗未牵绳', '遛狗不牵绳']),
    '园林绿化': ('树木/绿植本身的问题：干枝、死株、草坪裸露秃斑、枝叶过长遮挡监控或信号灯、绿化破损',
             ['树枝干枯', '绿化带草坪裸露', '枝叶遮挡监控探头']),
    '户外广告': ('违规广告牌、横幅、标语、乱张贴的海报小广告、破损脱落的招牌灯箱',
             ['墙面乱贴小广告', '违规设置横幅', '招牌破损脱落']),
    '市政设施': ('设施破损：井盖破损缺失、路面坑槽塌陷、路灯不亮或倾斜、线缆垂落、配电箱破损、护栏损坏',
             ['路面坑槽', '井盖破损', '电线垂落']),
    '施工围挡': ('工地围挡倒伏破损、施工占道、路面开挖、渣土车抛洒、脚手架',
             ['施工围挡破损', '工地围挡倒伏', '路面开挖']),
    '其他': ('以上类型都明显不符合时才选', []),
}

CYW_VL_PROMPT = """你是城市管理问题的图像识别助手。照片来自城市监控摄像头（多为手机对屏幕翻拍，反光、网格纹是翻拍造成，不是问题）。请找出监控员标注的问题。

【识别步骤】
1. 先在画面中找红/绿色的手绘圆圈、椭圆或弧线——这是监控员圈出的问题位置；圈注可能只在画面边缘露出一段弧线，同样是圈注。逐个说出每个圈里是什么物体、在什么位置
2. 判定类型以圈内物体为准，不要选圈外的物体，哪怕圈外的车辆/物体更大更显眼；画面没有任何圈注时，才选最显眼的一处市容问题
3. 多个圈都有问题时：警车、消防车、救护车等正在执行公务的车辆不算问题，选其余圈里普通的车或物；其余都有问题就选面积最大或最居中的圈。圈里既有警车又有两轮车时，问题按两轮车算
4. 判断主体是车还是物：汽车、货车、SUV、微型四轮电动车、老年代步车、警车、摩托车 → 机动车；两轮的电动车、自行车、共享单车（小蓝车）、三轮车 → 非机动车。注意：微型四轮车、老年代步车虽然常被叫作"电动车"，但它们有四个轮、能上牌照，一律按机动车算

【类型清单】只能从以下类型中选一个最贴切的，严格沿用类型原文：
{type_cards}

【判定规则】
- 只要圈内或问题主体是车辆，就按第4步选"机动车乱停放"或"非机动车乱停放"，禁止选"垃圾不洁"和"园林绿化"；垃圾不洁只用于纸屑、塑料袋、油污、烟头等真正的垃圾，园林绿化只用于树木绿植本身的问题（干枝、死株、草坪裸露、枝叶遮挡）
- 车辆乱停放指：停在线外、占道、压线、双排、开上绿化带/人行道/盲道/消防通道，或机动车占用非机动车停放区；按划线车位/停放区正常停放的不算
- 两轮车停在地面能看清画有自行车图案或白方框的停放区内不算问题
- 圈内的汽车只露出车头或车尾、车身不完整时，仍按汽车/机动车判断（看轮子数量和车身宽度），不要判成两轮电动车
- 圈注明确圈住的乱停车辆直接算问题，不再纠结地面划线；画面里未被圈注的其他车辆再显眼也不选
- 道路名称不是类型依据：汽车停在"非机动车道"上仍选"机动车乱停放"
- 圈内只有很小的白点或散落物（看不清具体是什么）时按垃圾不洁处理
- 画面四角的摄像头编号、点位名（如"YHQ1066_东方国旅南侧"）、"固-枪-外-怡-东"、日期时间是设备叠加的水印，不是垃圾、不是小广告、不是横幅
- 店外/门前堆放的商品、物品、物料 → 乱堆物料；建筑垃圾、渣土 → 垃圾不洁
- 清单里的"案例"只用于说明该类型长什么样；description 必须写这张照片里实际看到的现象，禁止照抄案例原句
- 只写看清的内容，不猜路名；照片模糊到完全看不出问题时 description 填 ""

【输出格式】只输出 JSON，不要输出其他任何内容：
{"observation": "写你实际看到的：圈在哪、圈内是什么（几个轮子/车型、在什么位置）", "description": "问题简句，20字以内", "type": "类型名"}
observation 必须写具体看到的物体和位置，禁止照抄格式说明或提示里的示例句子，不写分类结论
observation 与 type 必须一致：观察里写的是两轮车（电动车/自行车/单车/三轮）时 type 只能是"非机动车乱停放"；写的是四轮车（汽车/轿车/SUV/货车/微型四轮车/警车）时 type 只能是"机动车乱停放"
type 只能是类型清单中"："左边的类型名（如 垃圾不洁、机动车乱停放），原样照抄，禁止把描述句子填进 type
type 是"机动车乱停放"或"非机动车乱停放"时，description 原样写该类型名，不写车型、颜色和停放位置"""

# 状态机（中文状态值，与前端一致）
# 2026-10-16 流程简化（用户要求）：登记即视为已派发，部门反馈即办结。
# 去掉「标记已派发 / 核销 / 退回」三个手工环节，也不再计算超时——只剩两个状态。
ST_DOING = '处置中'
ST_DONE = '已办结'
CYW_STATUSES = [ST_DOING, ST_DONE]
# 旧状态值：仅用于把历史数据一次性归并到新两态，以及留痕表里旧记录的兼容展示
LEGACY_STATUS_MAP = {'待派发': ST_DOING, '已反馈': ST_DONE, '已核销': ST_DONE}

# 部门底色（详单标题条/单位标签取色）。种子单位取 2026.1-5 台账实际派发的 7 个责任单位
# （台账 1000 条只涉及这 7 个，用户确认"处置单位表里也是准确的"，故按台账原名入库不做折叠）
DEFAULT_DEPTS = [
    ('环卫中心', '#2E7D32'),
    ('执法队', '#C62828'),
    ('交警队', '#EF6C00'),
    ('市容秩序科', '#6A1B9A'),
    ('夜市', '#00838F'),
    ('经开区', '#1565C0'),
    ('盬街', '#8D6E63'),
]
# 问题类型默认映射：名称 → (默认主办部门, 默认处置时限小时)
# 类型按 2026.1-5 台账 1000 条真实案件描述聚类梳理（2026-10-14 更新）；
# 默认主办对齐台账实际派发口径（如机动车乱停放 325 条中 256 条派交警队）
DEFAULT_TYPES = [
    ('垃圾不洁', '环卫中心', 4),
    ('机动车乱停放', '交警队', 4),
    ('非机动车乱停放', '执法队', 4),
    ('占道经营', '执法队', 2),
    ('乱堆物料', '执法队', 4),
    ('遛狗不牵绳', '执法队', 8),
    ('园林绿化', '环卫中心', 8),
    ('户外广告', '执法队', 8),
    ('市政设施', '执法队', 8),
    ('施工围挡', '执法队', 8),
    ('其他', '执法队', 8),
]

# 历史台账一键导入：台账单位别名 → 字典规范单位名（字典没有的按原名自动创建，不丢原始单位）
CYW_IMPORT_DEPT_ALIASES = {
    '环卫处': '环卫中心', '环卫队': '环卫中心', '环卫所': '环卫中心', '环卫局': '环卫中心',
    '执法中队': '执法队', '城管执法': '执法队', '综合执法队': '执法队',
    '交警大队': '交警队', '交警': '交警队',
    '市容秩序股': '市容秩序科', '市容科': '市容秩序科',
    '开发区': '经开区', '经济开发区': '经开区',
}

# 历史台账一键导入：问题描述 → 类型关键词，按优先级从前到后（先专有后通用，都不中标"未识别"由导入方选回退类型）
# 顺序要点：① 遛狗/广告/围挡/市政/占道等专有名词优先；② 垃圾不洁先于园林和停放——
#    "绿化带内垃圾"按垃圾算（对齐台账派环卫中心），"非机动车道上有垃圾"这类把车名词当位置写的也不会误判成停放；
#    ③ 非机动车先于机动车——"非机动车"含子串"机动车"。
# 该表对 2026.1-5 台账 1000 条实测命中 999 条，仅"环卫工人长时间停留"需人工选回退类型。
CYW_TYPE_KEYWORDS = [
    ('遛狗不牵绳', ('遛狗', '牵绳', '无绳')),
    ('户外广告', ('广告', '招牌', '横幅', '标语', '灯箱', '标牌', '海报', '张贴', '条幅')),
    ('施工围挡', ('围挡', '施工', '工地', '开挖', '渣土', '脚手架')),
    ('市政设施', ('井盖', '线体', '垂落', '破损', '损坏', '坑槽', '塌陷', '路灯', '配电箱', '设施')),
    ('占道经营', ('占道经营', '店外', '流动摊', '流动商贩', '摊贩', '商贩', '售卖', '促销', '出店')),
    ('垃圾不洁', ('垃圾', '不洁', '污渍', '油污', '脏', '泥', '尘土', '积灰', '灰尘', '落叶', '粪便',
                '渣', '遗落', '拖布', '桶', '瓶', '清扫工具', '车轮印', '污水', '痰', '烟头')),
    ('园林绿化', ('树枝', '修剪', '枝叶', '干枝', '弃料', '树木', '草坪', '绿植', '绿化', '树坑',
                '树池', '树穴', '绿地', '彩灯', '花草')),
    ('乱堆物料', ('乱堆放', '乱堆', '堆放', '物料', '杂物')),
    ('非机动车乱停放', ('非机动车', '电动车', '电瓶车', '单车', '自行车', '小蓝', '哈啰', '大唐',
                    '小彬', '共享', '三轮')),
    ('机动车乱停放', ('机动车', '汽车', '货车', '摩托', '车辆', '机动', '环卫车', '清扫车')),
]

CYW_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS cyw_dept (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL COMMENT '单位名称',
        contact VARCHAR(50) COMMENT '创文联络员',
        phone VARCHAR(30) COMMENT '联系电话',
        color VARCHAR(20) DEFAULT '#1565C0' COMMENT '部门底色(详单标题条取派发部门色)',
        sort_order INT DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uk_name (name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创文责任单位'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_spot (
        id INT AUTO_INCREMENT PRIMARY KEY,
        spot_no VARCHAR(50) COMMENT '点位编号(管理用,可空)',
        monitor_no VARCHAR(50) NOT NULL COMMENT '监控序号(快速录入检索键)',
        name VARCHAR(200) NOT NULL COMMENT '点位名称',
        road VARCHAR(200) COMMENT '所在路段',
        manage_unit VARCHAR(50) DEFAULT '城市管理局' COMMENT '点位管理单位(大部分属城市管理局,个别归开发区)',
        is_key TINYINT(1) DEFAULT 0 COMMENT '是否重点点位',
        lng DECIMAL(10,6) NULL COMMENT '经度(高德GCJ-02,预留地图展示)',
        lat DECIMAL(10,6) NULL COMMENT '纬度(高德GCJ-02,预留地图展示)',
        note VARCHAR(500) COMMENT '备注',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_monitor_no (monitor_no)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创文监控点位档案'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_spot_contact (
        id INT AUTO_INCREMENT PRIMARY KEY,
        spot_id INT NOT NULL COMMENT '点位cyw_spot.id',
        dept_label VARCHAR(100) COMMENT '部门/角色(环卫中心/点位主管/执法队·东城分队三中队/建投等)',
        person VARCHAR(50) COMMENT '联系人',
        phone VARCHAR(50) COMMENT '电话',
        sort_order INT DEFAULT 0,
        KEY idx_spot (spot_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创文点位联系人(按部门/人员/电话逐条)'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_type (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL COMMENT '问题类型名称',
        default_dept_id INT NULL COMMENT '默认派发部门cyw_dept.id',
        deadline_hours INT DEFAULT 4 COMMENT '默认处置时限(小时)(历史遗留,新流程不再使用)',
        icon VARCHAR(100) COMMENT '图标标识(预留)',
        sort_order INT DEFAULT 0,
        UNIQUE KEY uk_name (name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创文问题类型'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_issue (
        id INT AUTO_INCREMENT PRIMARY KEY,
        case_no VARCHAR(30) NOT NULL COMMENT '案件编号 CWyyyymmdd-xxx',
        found_at DATETIME NOT NULL COMMENT '发现时间',
        spot_id INT NOT NULL COMMENT '点位cyw_spot.id',
        type_id INT NOT NULL COMMENT '问题类型cyw_type.id',
        dept_id INT NOT NULL COMMENT '派发部门cyw_dept.id(单部门派发)',
        description TEXT COMMENT '问题描述',
        photos TEXT COMMENT '现场照片JSON:[{name,path}]',
        status VARCHAR(20) NOT NULL DEFAULT '处置中' COMMENT '处置中/已办结(登记即视为已派发,反馈即办结)',
        deadline_at DATETIME COMMENT '处置时限截止=发现时间+类型时限(历史遗留,新流程不再使用)',
        is_fed TINYINT(1) DEFAULT 0 COMMENT '派发部门是否已反馈',
        fed_at DATETIME COMMENT '反馈时间',
        feedback_note TEXT COMMENT '反馈说明',
        feedback_photos TEXT COMMENT '反馈照片JSON:[{name,path}]',
        closed_by VARCHAR(50) COMMENT '办结人',
        closed_at DATETIME COMMENT '办结时间(反馈即办结,故=首次反馈时间)',
        return_count INT DEFAULT 0 COMMENT '历史退回次数(新流程无退回环节,仅存量)',
        remark VARCHAR(500) COMMENT '反馈/办结备注',
        created_by VARCHAR(50) COMMENT '登记人',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '登记时间(中国时间,由Python显式写入)',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '勿依赖此默认值:MySQL跑在UTC,会比中国时间晚8小时',
        UNIQUE KEY uk_case_no (case_no),
        KEY idx_status (status),
        KEY idx_found_at (found_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创文问题台账(核心表)'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_issue_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        issue_id INT NOT NULL,
        action VARCHAR(50) NOT NULL COMMENT '登记/编辑/反馈/办结',
        from_status VARCHAR(20) COMMENT '变更前状态',
        to_status VARCHAR(20) COMMENT '变更后状态',
        note VARCHAR(500) COMMENT '备注',
        operator VARCHAR(50) COMMENT '操作人',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间(中国时间,由Python显式写入)',
        KEY idx_issue (issue_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问题状态留痕(全程留痕,不删除)'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_check_batch (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch_no VARCHAR(30) NOT NULL COMMENT '抽查批次号 CCyyyymmdd-xxx',
        spot_count INT DEFAULT 5 COMMENT '本批抽几个点位',
        status VARCHAR(20) NOT NULL DEFAULT '进行中' COMMENT '进行中/已结束',
        created_by VARCHAR(50) COMMENT '发起人',
        created_at DATETIME COMMENT '发起时间(中国时间,由Python显式写入)',
        finished_at DATETIME COMMENT '结束时间',
        UNIQUE KEY uk_batch_no (batch_no),
        KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='在岗抽查批次'
    """,
    """
    CREATE TABLE IF NOT EXISTS cyw_check_item (
        id INT AUTO_INCREMENT PRIMARY KEY,
        batch_id INT NOT NULL COMMENT '批次cyw_check_batch.id',
        spot_id INT NOT NULL COMMENT '点位cyw_spot.id',
        spot_no VARCHAR(50) COMMENT '点位监控序号(冗余,点位改名不影响历史报告)',
        spot_name VARCHAR(100) COMMENT '点位名称(冗余,同上)',
        dept_label VARCHAR(100) COMMENT '联系人部门/角色',
        person VARCHAR(50) COMMENT '联系人姓名',
        phone VARCHAR(50) COMMENT '联系人电话',
        pick_rule VARCHAR(50) COMMENT '命中规则:环卫点位主管/执法首位/点位兜底/无联系人',
        status VARCHAR(20) NOT NULL DEFAULT '待抽查' COMMENT '待抽查/在岗/不在岗',
        called_at DATETIME COMMENT '点击电话时间',
        deadline_at DATETIME COMMENT '倒计时截止=called_at+5分钟,到点未点在岗即自动判不在岗',
        result_at DATETIME COMMENT '结果落定时间',
        result_by VARCHAR(50) COMMENT '结果确认人',
        corrected TINYINT(1) DEFAULT 0 COMMENT '是否被管理员事后修正',
        corrected_by VARCHAR(50) COMMENT '修正人',
        corrected_at DATETIME COMMENT '修正时间',
        corrected_reason VARCHAR(500) COMMENT '修正原因',
        KEY idx_batch (batch_id),
        KEY idx_pending (status, deadline_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='在岗抽查明细(每个被抽查联系人一行)'
    """,
]

# 中文字体探测顺序：容器内文泉驿 → 本地 Windows 微软雅黑/黑体
FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simhei.ttf',
    'C:/Windows/Fonts/simsun.ttc',
]


def _now_user():
    return getattr(request, 'username', None) or 'admin'


def _now():
    """取中国时间（容器 TZ=Asia/Shanghai，与前端发现时间同口径）。

    不能用 SQL 的 NOW()/CURRENT_TIMESTAMP：MySQL 跑在 UTC（system_time_zone=UTC），
    落库比中国时间晚 8 小时，而 found_at 是前端传的中国时间——两种口径混在一行里，
    按日统计会把凌晨 0-8 点的记录算到前一天。所有时间戳一律由 Python 显式写入。
    """
    return datetime.now()


def _parse_json_list(raw):
    """附件/照片 JSON 字段解析，异常或非 list 兜底 []（照抄 notice_routes 模式）"""
    try:
        val = json.loads(raw or '[]')
        return val if isinstance(val, list) else []
    except Exception:
        return []


def _dump_json_list(items):
    if not isinstance(items, list):
        items = []
    return json.dumps(items, ensure_ascii=False)[:100000]


def _parse_dt(value, default=None):
    """解析前端 datetime-local / ISO 字符串，失败回落默认值"""
    if not value:
        return default
    s = str(value).strip().replace('T', ' ')
    if s.endswith('Z'):
        s = s[:-1]
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return default


def _resolve_stat_range(args):
    """解析统计时间范围，返回 (起, 止, 是否单日, 展示用日期串)。

    时间段模式：date_from + date_to 都必填，取首日 00:00:00 至末日 23:59:59。
    单日模式：沿用 date 参数，行为与改造前完全一致。
    非法区间抛 ValueError，由调用方转 400（文案即中文提示）。
    """
    date_from = (args.get('date_from') or '').strip()
    date_to = (args.get('date_to') or '').strip()
    if bool(date_from) != bool(date_to):
        raise ValueError('请同时选择开始日期和结束日期')
    if date_from:
        d0 = _parse_dt(date_from)
        d1 = _parse_dt(date_to)
        if not d0 or not d1:
            raise ValueError('日期格式不正确，请选择起止日期')
        day_from = d0.date()
        day_to = d1.date()
    else:
        day_from = _parse_dt(args.get('date'), datetime.now()).date()
        day_to = day_from
    start = datetime(day_from.year, day_from.month, day_from.day, 0, 0, 0)
    end = datetime(day_to.year, day_to.month, day_to.day, 23, 59, 59)
    if start > end:
        raise ValueError('开始日期不能晚于结束日期')
    if (end - start).days > 365:
        raise ValueError('统计区间最长一年，请缩小起止日期范围')
    return start, end, start.date() == end.date(), day_from.strftime('%Y-%m-%d')


# ==================== 在岗抽查 ====================
# 抽查时长（分钟）：点击「电话」后开始倒计时，到点未点「在岗」即自动判不在岗
CHECK_WINDOW_MINUTES = 5

# 抽查池排除的点位监控序号：摄像头不在线，抽中也没法核岗，白占一个名额（2026-11 用户确认）
CHECK_POOL_EXCLUDE_NOS = (
    'GJ01', 'GJ02', 'YM01', 'YM02', 'JCDD055', 'SSJ046', 'HXL005', 'PAJ008',
)


def _pick_contacts_for_check(contacts, spot_contact=None):
    """给一个点位挑出「要打电话的那些人」：环卫一个 + 执法一个。

    规则按用户原话：环卫显示点位主管姓名电话、执法显示第一个人姓名电话。
    contacts 是该点位全部联系人 [{dept_label, person, phone}]，已按 sort_order 排好；
    spot_contact 是点位档案上的负责人 (name, phone)，只在两侧都没人时兜底。
    返回 [{dept_label, person, phone, pick_rule}, ...]；某一侧没人时该项 person 为 None、
    pick_rule='无联系人'，页面与报告如实记一笔，不悄悄跳过——否则抽查覆盖率是假的。
    """
    def first_match(pred):
        for c in contacts:
            if pred(c.get('dept_label') or ''):
                return c
        return None

    def row(label, person, phone, rule):
        return {'dept_label': label, 'person': person, 'phone': phone, 'pick_rule': rule}

    # ① 环卫：优先「点位主管」，退回该点位任一环卫联系人
    c = first_match(lambda d: '点位主管' in d)
    hw = row(c['dept_label'], c['person'], c['phone'], '环卫点位主管') if c else None
    if not hw:
        c = first_match(lambda d: d.startswith('环卫'))
        hw = row(c['dept_label'], c['person'], c['phone'], '环卫联系人') if c else None

    # ② 执法：取排序第一人（label 形如「执法队·东城分队二中队」，盬街点位用「盬街」前缀）
    c = first_match(lambda d: d.startswith('执法') or d.startswith('盬街'))
    zf = row(c['dept_label'], c['person'], c['phone'], '执法首位') if c else None

    if hw or zf:
        # 有一侧就得把两侧都列出来：缺的那侧记「未登记」，让缺口看得见
        return [hw or row('环卫', None, None, '无联系人'),
                zf or row('执法', None, None, '无联系人')]

    # ③ 两侧都空（夜市 YM01/YM02 只有点位总负责人/点位责任人）：兜底出一条，
    #    别把同一个人拆成环卫/执法两行各打一遍
    c = first_match(lambda d: '负责人' in d or '责任人' in d)
    if c:
        return [row(c['dept_label'], c['person'], c['phone'], '点位兜底')]
    if spot_contact and spot_contact[0]:
        return [row('点位负责人', spot_contact[0], spot_contact[1], '点位兜底')]
    return [row('点位', None, None, '无联系人')]


def _sweep_expired_items(conn, batch_id=None):
    """把「倒计时已过、还没人在岗」的明细自动判为不在岗。

    不在请求外起守护线程：容器是 gunicorn --workers 4，后台线程每 worker 各起一个，
    既不可靠也没必要。改为读时兜底扫（lazy sweep）——任何一次读/点/结束都会先把过期的结掉，
    刷新页面、换电脑、关浏览器都不丢状态，报告导出前也会全量扫一遍。
    """
    conn.execute(text(
        "UPDATE cyw_check_item SET status='不在岗', result_at=:ts, result_by='系统自动判定' "
        "WHERE status='待抽查' AND deadline_at IS NOT NULL AND deadline_at < :ts"
        + (" AND batch_id=:b" if batch_id else "")
    ), {'ts': _now(), **({'b': batch_id} if batch_id else {})})


def _check_item_to_dict(r):
    return {
        'id': r[0], 'batch_id': r[1], 'spot_id': r[2], 'spot_no': r[3],
        'spot_name': r[4], 'dept_label': r[5], 'person': r[6], 'phone': r[7],
        'pick_rule': r[8], 'status': r[9],
        'called_at': r[10].strftime('%Y-%m-%d %H:%M:%S') if r[10] else None,
        'deadline_at': r[11].strftime('%Y-%m-%d %H:%M:%S') if r[11] else None,
        'result_at': r[12].strftime('%Y-%m-%d %H:%M:%S') if r[12] else None,
        'result_by': r[13],
        'corrected': bool(r[14]),
        'corrected_by': r[15],
        'corrected_at': r[16].strftime('%Y-%m-%d %H:%M:%S') if r[16] else None,
        'corrected_reason': r[17],
    }


def _spot_full_name(name, road):
    """完整点位名称（含道路）：点名自带道路语义时不重复拼。

    点名分两类：一类压根不含路（「毕家索东」→ 拼成「学苑路毕家索东」），一类自带
    路名（「槐东路东槐东文化苑西门北侧」）。运城路名爱带东南西北变体——圣惠路/
    圣惠北路、河东街/河东东街同源，直接拼会出「圣惠路圣惠北路环岛西北侧」这种叠字
    名；黄河夜市的点名又以「夜市东出入口」开头，拼出来「黄河夜市夜市东出入口」同样
    叠。满足下面任一条就认为点名已含道路、原样返回：

    1. 点名以 road 开头（槐东路西陈氏大虾前）；
    2. 点名以「road 去末字 + 方位 + 路街巷道」开头（圣惠北路←圣惠路、河东东街←
       河东街、人民北路←人民路）——运城同一条路的东南西北段；
    3. 点名整段包含 road（步青街魏风街西南侧、运城盬街方言桥东南）；
    4. road 四字以上且点名以去掉前两字的后半开头（黄河夜市→夜市东出入口南侧向西）。

    注意不能退化成「与 road 同头两字就不拼」：冒烟测试点位「冒烟抽查点位」与道路
    「冒烟抽查路」同头两字却毫不相干，那样会把该拼的点位也放过。
    """
    name = (name or '').strip()
    road = (road or '').strip()
    if not road or not name:
        return name
    core = road[:-1]
    if (name.startswith(road)
            or (len(name) >= len(core) + 2 and name.startswith(core)
                and name[len(core)] in '东南西北中' and name[len(core) + 1] in '路街巷道')
            or road in name
            or (len(road) > 3 and name.startswith(road[2:]))):
        return name
    return f'{road}{name}'


def _load_batch_items(conn, batch_id):
    rows = conn.execute(text(
        "SELECT id, batch_id, spot_id, spot_no, spot_name, dept_label, person, phone, pick_rule, "
        "status, called_at, deadline_at, result_at, result_by, corrected, corrected_by, "
        "corrected_at, corrected_reason FROM cyw_check_item WHERE batch_id=:b ORDER BY id"
    ), {'b': batch_id}).fetchall()
    items = [_check_item_to_dict(r) for r in rows]
    if not items:
        return items
    # 报告要打「完整点位名称（含道路）+（监控序号）」：点位名是建批次时的快照，
    # 道路/监控序号现查 cyw_spot 补（点位行被删过就退快照值，不能把明细变空白）。
    extra = {r[0]: (r[1], r[2]) for r in conn.execute(text(
        "SELECT i.id, s.road, s.monitor_no FROM cyw_check_item i "
        "LEFT JOIN cyw_spot s ON s.id = i.spot_id WHERE i.batch_id = :b"
    ), {'b': batch_id}).fetchall()}
    for i in items:
        road, monitor = extra.get(i['id'], (None, None))
        i['spot_road'] = road
        i['spot_full'] = _spot_full_name(i['spot_name'], road)
        i['monitor_no'] = i['spot_no'] or monitor
    return items


def _check_short_label(item):
    """报告明细里的部门简称：环卫侧一律打「环卫」、执法侧一律打「执法」。

    完整 dept_label（如「环卫中心·点位主管」「执法队·中城分队十二中队」）是给现场
    打电话看的，报告只记在岗情况，用不上；兜底行没有环卫/执法之分，原样打它的标签。
    """
    rule = item.get('pick_rule') or ''
    label = item.get('dept_label') or ''
    if rule.startswith('环卫') or label.startswith('环卫'):
        return '环卫'
    if rule.startswith('执法') or label.startswith('执法'):
        return '执法'
    return label or '点位'


def _check_export_text(batch, items):
    """抽查报告 txt：标题 + 批次信息 + 汇总 + 按点位的在岗情况。BOM + RFC5987 与数据统计导出一致。"""
    L = []
    A = L.append
    A('创文点位在岗抽查报告')
    A(f'抽查批次：{batch["batch_no"]}')
    A(f'发起时间：{batch["created_at"]}')
    A(f'发起人：{batch["created_by"]}')
    if batch.get('finished_at'):
        A(f'结束时间：{batch["finished_at"]}')
    A('')

    on = sum(1 for i in items if i['status'] == '在岗')
    off = sum(1 for i in items if i['status'] == '不在岗')
    wait = sum(1 for i in items if i['status'] == '待抽查')
    no_person = sum(1 for i in items if not i['person'])
    spot_cnt = len({i['spot_id'] for i in items})
    # 一行 = 「一个点位某一侧的那个联系人」；点位没登记该侧联系人时这项是空的。
    # 汇总按「项」计总数、按「人」计到岗——写成「共10人」会把没联系人的项也算成一个人。
    A(f'【抽查汇总】抽查 {spot_cnt} 个点位、共{len(items)}项（{len(items) - no_person}人）：'
      f'在岗 {on} 人，不在岗 {off} 人'
      + (f'，待抽查 {wait} 人' if wait else '')
      + (f'，未登记联系人 {no_person} 人' if no_person else ''))
    if items:
        judged = on + off
        A(f'  到岗率：{on}/{judged}（{round(on / judged * 100) if judged else 0}%）')
    A('')

    A('【抽查明细】')
    # 一个点位出两行（环卫一行、执法一行），明细按点位归组：只打点位名称 + 两侧在岗情况。
    # 人名、电话、去电时间、修正过程一律不进报告——现场打电话看页面就够了，
    # 报告是留给台账留档的，越短越好核。没登记联系人的那一侧打「未登记」，
    # 不能打成「不在岗」：一个是没人可打，一个是打了没见人，两回事。
    # 点位格式 = 完整点位名称（含道路）+（监控序号），例：学苑路毕家索东（XY01）——
    # 光打名称对不上台账里的编号，光打编号又说不出在哪，两个都要才好核。
    groups = {}
    for i in items:
        groups.setdefault(i['spot_id'], []).append(i)
    for idx, grp in enumerate(groups.values(), 1):
        first = grp[0]
        label = first.get('spot_full') or first['spot_name']
        no = first.get('monitor_no') or first['spot_no']
        A(f'  {idx}. {label}（{no}）' if no else f'  {idx}. {label}')
        for i in grp:
            A(f'     {_check_short_label(i)}：{i["status"] if i["person"] else "未登记"}')
    return '\n'.join(L) + '\n'


def ensure_cyw_tables(engine):
    """建表 + 种子默认字典（仅首次，INSERT IGNORE 防重复）"""
    with engine.begin() as conn:
        for sql in CYW_TABLES:
            conn.execute(text(sql))
        # 种子：责任单位（含底色）
        for name, color in DEFAULT_DEPTS:
            conn.execute(text(
                "INSERT IGNORE INTO cyw_dept (name, color) VALUES (:n, :c)"
            ), {'n': name, 'c': color})
        # 种子：问题类型（默认派发部门按名称回查 id）
        dept_rows = conn.execute(text("SELECT id, name FROM cyw_dept")).fetchall()
        dept_map = {r[1]: r[0] for r in dept_rows}
        for name, host, hours in DEFAULT_TYPES:
            conn.execute(text(
                "INSERT IGNORE INTO cyw_type (name, default_dept_id, deadline_hours) "
                "VALUES (:n, :d, :h)"
            ), {'n': name, 'd': dept_map.get(host), 'h': hours})
        _ensure_columns(conn, 'cyw_spot', [
            ('lng', "DECIMAL(10,6) NULL COMMENT '经度(高德GCJ-02,预留地图展示)'"),
            ('lat', "DECIMAL(10,6) NULL COMMENT '纬度(高德GCJ-02,预留地图展示)'"),
            ('manage_unit', "VARCHAR(50) DEFAULT '城市管理局' COMMENT '点位管理单位(大部分属城市管理局,个别归开发区)'"),
            ('camera_source', "VARCHAR(50) NULL COMMENT '摄像头归属(雪亮/盬街/黄河夜市等)'"),
            ('spot_type', "VARCHAR(50) NULL COMMENT '点位类型(主干道/次干道/商业大街/夜市)'"),
            ('contact_name', "VARCHAR(50) NULL COMMENT '点位负责人'"),
            ('contact_phone', "VARCHAR(50) NULL COMMENT '负责人电话'"),
            ('contact_extra', "TEXT NULL COMMENT '其他联系人(环卫/主管/执法等,原文保留)'"),
        ])
        _normalize_status(conn)
    logger.info('cyw tables ensured')


def _normalize_status(conn):
    """把旧四态一次性归并到新两态（登记即已派发、反馈即办结）。
    归并到「已办结」时顺手补齐办结人/办结时间，避免出现"已办结但没有办结时间"的脏行
    （日报按 closed_at 统计，缺了时间这些历史案件会从两类统计里同时消失）。
    幂等：已归并的行不再匹配 WHERE，重复执行无副作用；留痕表的历史状态值不动。"""
    moved = 0
    ts = _now()
    for old, new in LEGACY_STATUS_MAP.items():
        if new == ST_DONE:
            r = conn.execute(text(
                "UPDATE cyw_issue SET status = :n, is_fed = 1, "
                "fed_at = COALESCE(fed_at, closed_at, updated_at), "
                "closed_at = COALESCE(closed_at, fed_at, updated_at), "
                "closed_by = COALESCE(closed_by, '历史归并'), updated_at = :ts "
                "WHERE status = :o"), {'n': new, 'o': old, 'ts': ts})
        else:
            r = conn.execute(text("UPDATE cyw_issue SET status = :n WHERE status = :o"),
                             {'n': new, 'o': old})
        moved += r.rowcount or 0
    if moved:
        logger.info(f'[CYW] 状态归并：{moved} 条历史案件由旧四态并入「处置中/已办结」')


def _ensure_columns(conn, table, columns):
    """旧库补列：columns 为 (列名, 列定义) 列表（照抄 assessment_manual 模式）"""
    cols = {r[0] for r in conn.execute(text(f"SHOW COLUMNS FROM {table}"))}
    for name, ddl in columns:
        if name not in cols:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            logger.info(f'{table} 表新增列: {name}')


def _parse_coord(value, kind):
    """坐标解析：空→None；非数字或超出全球范围→(None, 错误信息)。
    中国范围外的导入值由调用方给警告（不阻断）。"""
    if value is None or value == '':
        return None, None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None, f'{kind}格式不正确: {value}'
    lo, hi = (-180.0, 180.0) if kind == '经度' else (-90.0, 90.0)
    if not (lo <= v <= hi):
        return None, f'{kind}超出范围: {value}'
    return round(v, 6), None


def _load_spot_contacts(conn, spot_ids):
    """按点位批量取联系人 → {spot_id: [{dept_label, person, phone}, ...]}（按 sort_order/id）"""
    if not spot_ids:
        return {}
    params, ph = {}, []
    for idx, sid in enumerate(spot_ids):
        params[f's{idx}'] = sid
        ph.append(f':s{idx}')
    rows = conn.execute(text(
        f"SELECT spot_id, dept_label, person, phone FROM cyw_spot_contact "
        f"WHERE spot_id IN ({','.join(ph)}) ORDER BY spot_id, sort_order, id"
    ), params).mappings().fetchall()
    out = {}
    for r in rows:
        out.setdefault(r['spot_id'], []).append(
            {'dept_label': r['dept_label'] or '', 'person': r['person'] or '', 'phone': r['phone'] or ''})
    return out


def _replace_spot_contacts(conn, spot_id, contacts):
    """整表替换某点位的联系人：随点位保存/导入一并维护，无独立增删接口"""
    conn.execute(text("DELETE FROM cyw_spot_contact WHERE spot_id = :i"), {'i': spot_id})
    for idx, c in enumerate(contacts or []):
        person = (c.get('person') or '').strip()
        if not person:
            continue
        conn.execute(text(
            "INSERT INTO cyw_spot_contact (spot_id, dept_label, person, phone, sort_order) "
            "VALUES (:i, :d, :p, :ph, :o)"
        ), {'i': spot_id, 'd': (c.get('dept_label') or '').strip() or None,
            'p': person, 'ph': (c.get('phone') or '').strip() or None, 'o': idx})


def _parse_vl_json(content):
    """从 VL 模型输出提取 JSON 字典：容忍 ```json 包裹、前后杂文本、单引号。"""
    if not content:
        return None
    m = re.search(r'\{.*\}', content, re.S)
    if not m:
        return None
    raw = m.group(0)
    try:
        obj = json.loads(raw)
    except Exception:
        try:
            obj = json.loads(raw.replace("'", '"'))
        except Exception:
            return None
    return obj if isinstance(obj, dict) else None


# VL 类型纠偏：7B 模型偶发"观察写车辆违停、type 却给垃圾/绿化类"
# （2026-10-15 真图评测 4 个错例之一：观察"白色汽车停在绿化带内"→ type=垃圾不洁）。
# 观察/描述里主体明显是车+违停位置时按车型强制改判停放类；占道经营等有专有锚点的类型不纠。
_VEH_TYPE_REPAIR = re.compile(
    r'(汽车|轿车|SUV|货车|面包车|卡车|警车|越野车|四轮|机动车|车辆)')
_NONMOTOR_REPAIR = re.compile(
    r'(电动车|电瓶车|自行车|单车|共享单车|三轮车|两轮车)')
_VIOLATION_POS_REPAIR = re.compile(
    r'(乱停|违停|占道|压线|双排|绿化带|绿篱|人行道|便道|盲道|消防|通道|路口|'
    r'机动车道|快车道|辅路|台阶|平台上)')
# 观察词 → 车型强信号：四轮/汽车类（不含"摩托车"——台账口径里两轮摩托按非机动车归类存疑，不碰）
_MOTOR_STRONG_REPAIR = re.compile(
    r'(汽车|轿车|SUV|货车|面包车|卡车|警车|越野|四轮)')
_TWO_WHEEL_REPAIR = re.compile(
    r'(两轮|电动车|电瓶车|自行车|单车|小蓝|哈啰|三轮)')


def _repair_parking_type(type_name, observation, description):
    """观察/描述与 type 冲突时的确定性纠偏。
    ① 观察里明确写了"四轮"却判成非机动车：微型四轮车/老年代步车俗名"电动车"，实为机动车
       （2026-10-15 真图评测错例：观察"灰色的微型四轮电动车，停在绿化带内"→ type=非机动车）；
    ② 观察/描述主体明显是车+违停位置、type 却落在垃圾/绿化类时，按车型改判停放类。
    关键词只在 observation+description 上匹配，且四轮规则要求观察里另有违停位置词：
    停放类的 description 被本模块强制写成类型名（"非机动车乱停放"），自带"机动车"
    "乱停"子串，拼进匹配会自我触发误纠偏（2026-10-15 评测实测踩过）。
    """
    if type_name in ('占道经营', '户外广告', '施工围挡', '市政设施', '遛狗不牵绳'):
        return type_name
    obs = observation or ''
    text = f'{obs} {description or ""}'
    if (type_name == '非机动车乱停放' and '四轮' in obs
            and _VIOLATION_POS_REPAIR.search(obs)):
        return '机动车乱停放'
    # 观察词与停放类型一致性兜底：观察只有四轮强信号（无两轮词）却判非机动车 → 改机动车，反之亦然
    # （模型偶尔违反提示词的一致性约束，如观察"白色轿车停在非机动车道上"→ type=非机动车）
    motor_hit = bool(_MOTOR_STRONG_REPAIR.search(obs))
    two_hit = bool(_TWO_WHEEL_REPAIR.search(obs))
    if type_name == '非机动车乱停放' and motor_hit and not two_hit:
        return '机动车乱停放'
    if type_name == '机动车乱停放' and two_hit and not motor_hit:
        return '非机动车乱停放'
    if type_name in ('机动车乱停放', '非机动车乱停放'):
        return type_name
    if _VEH_TYPE_REPAIR.search(text) and _VIOLATION_POS_REPAIR.search(text):
        if _NONMOTOR_REPAIR.search(text):
            return '非机动车乱停放'
        return '机动车乱停放'
    return type_name


# ---------------------------------------------------------------- 历史台账 Excel 一键导入的单元格解析

def _split_spot_text(text):
    """「1506铺安街韩信路往东南420米路东北侧」→ ('1506', '铺安街韩信路往东南420米路东北侧')
    无数字前缀（如「夜市东出入口南侧向西」）→ ('', 原文)，靠名称匹配点位"""
    s = (text or '').strip()
    m = re.match(r'^(\d{1,6})\s*[-—]?\s*(.+)$', s)
    if m:
        return m.group(1), m.group(2).strip()
    return '', s


def _parse_import_date(value, fallback_year=None):
    """解析台账日期单元格：'2026.1.6' / '2026.2.1早高峰' / '3.2日晚高峰'（缺年份用 fallback_year）"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s or s.lower() == 'nan':
        return None
    m = re.search(r'(20\d{2})\D+(\d{1,2})\D+(\d{1,2})', s)
    if not m:
        m2 = re.search(r'(?<!\d)(\d{1,2})\D+(\d{1,2})', s)
        if m2 and fallback_year:
            try:
                return date(fallback_year, int(m2.group(1)), int(m2.group(2)))
            except ValueError:
                return None
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _parse_import_time(value):
    """解析台账时间单元格：datetime.time / '17:35:00' / '07;39'（手误分号）→ time，失败 None"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    m = re.match(r'^\s*(\d{1,2})\s*[:：；;]\s*(\d{1,2})', str(value))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return time(h, mi) if 0 <= h < 24 and 0 <= mi < 60 else None


def _parse_import_result(value):
    """处置结果原文 → (是否已办结, 结果中的处理时间或 None)。空结果 = 未办结"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False, None
    s = str(value).strip()
    if not s or s.lower() == 'nan':
        return False, None
    return True, _parse_import_time(s)


def _match_type_name(desc):
    """问题描述 → 类型名（关键词优先级），都不中返回 None"""
    for tname, kws in CYW_TYPE_KEYWORDS:
        if any(k in desc for k in kws):
            return tname
    return None


def register_cyw_routes(app, Session=None, engine=None, protected=None, admin_required=None):
    """注册创文问题处置路由"""
    protected = protected or _protected
    admin_required = admin_required or _admin_required

    def perm_access(permission_key):
        """细粒度权限鉴权：admin 直接放行；普通用户需 permissions 表任一对应列=1
        （permission_key 为单键或键元组，元组是「或」语义，供录入/台账两页共用的接口）
        （与 assessment_manual_routes 的 exempt 维护同一套口径）"""
        keys = (permission_key,) if isinstance(permission_key, str) else tuple(permission_key)
        cols = ', '.join(keys)

        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                token = request.headers.get("Authorization")
                if not token:
                    return jsonify({"error": "Missing token"}), 401
                if token.startswith("Bearer "):
                    token = token[7:]
                payload = _verify_token(token)
                if not payload:
                    return jsonify({"error": "Invalid or expired token"}), 401
                request.user_id = payload["user_id"]
                request.username = payload["username"]
                request.role = payload["role"]
                if payload.get("role") == "admin":
                    return f(*args, **kwargs)
                if engine is None:
                    return jsonify({"error": "数据库未连接，无法校验权限"}), 503
                try:
                    with engine.connect() as conn:
                        row = conn.execute(
                            text(f"SELECT {cols} FROM permissions WHERE user_id = :uid"),
                            {"uid": payload["user_id"]}
                        ).fetchone()
                    if not row or not any(row):
                        return jsonify({"error": "Permission denied"}), 403
                except Exception as e:
                    logger.error(f"创文模块权限校验失败: {e}")
                    return jsonify({"error": "Permission check failed"}), 500
                return f(*args, **kwargs)
            return decorated
        return decorator

    if engine:
        try:
            ensure_cyw_tables(engine)
        except Exception as e:
            logger.warning(f'cyw 表创建/种子失败: {e}')

    # 权限键与二级菜单子栏目一一对应；录入/台账共用的接口（照片上传、详单）取「或」
    cyw_input_access = perm_access('cyw_input')
    cyw_ledger_access = perm_access('cyw_ledger')
    cyw_biz_access = perm_access(('cyw_input', 'cyw_ledger'))

    # ---------------------------------------------------------------- 工具函数

    def _gen_case_no(conn, day=None):
        """案件编号：CW + yyyymmdd + 当日 3 位序号（唯一键兜底重试两次）。day 可指定发现日期（历史导入用）"""
        day = day or datetime.now()
        prefix = f"CW{day.strftime('%Y%m%d')}-"
        cnt = conn.execute(
            text("SELECT COUNT(*) FROM cyw_issue WHERE case_no LIKE :p"),
            {'p': prefix + '%'}
        ).scalar()
        for i in range(3):
            case_no = f"{prefix}{cnt + 1 + i:03d}"
            exists = conn.execute(
                text("SELECT id FROM cyw_issue WHERE case_no = :c"), {'c': case_no}
            ).first()
            if not exists:
                return case_no
        return f"{prefix}{uuid.uuid4().hex[:6]}"

    def _write_log(conn, issue_id, action, from_status, to_status, note=None):
        conn.execute(text(
            "INSERT INTO cyw_issue_log (issue_id, action, from_status, to_status, note, operator, created_at) "
            "VALUES (:i, :a, :f, :t, :n, :o, :ts)"
        ), {'i': issue_id, 'a': action, 'f': from_status, 't': to_status,
            'n': note, 'o': _now_user(), 'ts': _now()})

    def _issue_row(conn, issue_id):
        return conn.execute(text(
            "SELECT i.*, s.name AS spot_name, s.monitor_no, s.road, s.is_key, "
            "t.name AS type_name, d.name AS dept_name, d.color AS dept_color "
            "FROM cyw_issue i "
            "JOIN cyw_spot s ON s.id = i.spot_id "
            "JOIN cyw_type t ON t.id = i.type_id "
            "JOIN cyw_dept d ON d.id = i.dept_id "
            "WHERE i.id = :id"
        ), {'id': issue_id}).mappings().first()

    def _serialize_issue(row, now=None):
        """行字典 + 单部门反馈摘要（超时机制已下线，不再计算 is_overdue）"""
        item = dict(row)
        item['photos'] = _parse_json_list(item.get('photos'))
        item['feedback_photos'] = _parse_json_list(item.get('feedback_photos'))
        item['is_fed'] = bool(item.get('is_fed'))
        if item.get('fed_at'):
            item['fed_at'] = item['fed_at'].strftime('%Y-%m-%d %H:%M')
        # 时限字段已从界面和统计中全部下线，从响应里摘掉，避免前端误用
        item.pop('deadline_at', None)
        item.pop('deadline_hours', None)
        for k in ('found_at', 'closed_at', 'created_at', 'updated_at'):
            if item.get(k):
                item[k] = item[k].strftime('%Y-%m-%d %H:%M:%S')
        return item

    # ---------------------------------------------------------------- 字典：部门

    @app.route('/api/cyw/depts', methods=['GET'])
    @protected
    def cyw_dept_list():
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM cyw_dept ORDER BY sort_order, id"
            )).mappings().fetchall()
        return jsonify({'success': True, 'depts': [dict(r) for r in rows]})

    @app.route('/api/cyw/depts', methods=['POST'])
    @admin_required
    def cyw_dept_create():
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '单位名称不能为空'}), 400
        with engine.begin() as conn:
            dup = conn.execute(text("SELECT id FROM cyw_dept WHERE name = :n"), {'n': name}).first()
            if dup:
                return jsonify({'error': '单位名称已存在'}), 400
            cur = conn.execute(text(
                "INSERT INTO cyw_dept (name, contact, phone, color, sort_order) "
                "VALUES (:n, :c, :p, :col, :s)"
            ), {'n': name, 'c': data.get('contact'), 'p': data.get('phone'),
                'col': data.get('color') or '#1565C0', 's': data.get('sort_order') or 0})
            return jsonify({'success': True, 'id': cur.lastrowid})

    @app.route('/api/cyw/depts/<int:dept_id>', methods=['PUT'])
    @admin_required
    def cyw_dept_update(dept_id):
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '单位名称不能为空'}), 400
        with engine.begin() as conn:
            dup = conn.execute(text(
                "SELECT id FROM cyw_dept WHERE name = :n AND id <> :i"), {'n': name, 'i': dept_id}
            ).first()
            if dup:
                return jsonify({'error': '单位名称已存在'}), 400
            conn.execute(text(
                "UPDATE cyw_dept SET name=:n, contact=:c, phone=:p, color=:col, sort_order=:s "
                "WHERE id=:i"
            ), {'n': name, 'c': data.get('contact'), 'p': data.get('phone'),
                'col': data.get('color') or '#1565C0', 's': data.get('sort_order') or 0, 'i': dept_id})
        return jsonify({'success': True})

    @app.route('/api/cyw/depts/<int:dept_id>', methods=['DELETE'])
    @admin_required
    def cyw_dept_delete(dept_id):
        with engine.begin() as conn:
            ref = conn.execute(text(
                "SELECT "
                "(SELECT COUNT(*) FROM cyw_type WHERE default_dept_id=:i) + "
                "(SELECT COUNT(*) FROM cyw_issue WHERE dept_id=:i) AS cnt"
            ), {'i': dept_id}).scalar()
            if ref:
                return jsonify({'error': '该单位已被问题类型/问题台账引用，不能删除'}), 400
            conn.execute(text("DELETE FROM cyw_dept WHERE id=:i"), {'i': dept_id})
        return jsonify({'success': True})

    # ---------------------------------------------------------------- 字典：问题类型

    @app.route('/api/cyw/types', methods=['GET'])
    @protected
    def cyw_type_list():
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT t.*, d.name AS default_dept_name, d.color AS default_dept_color "
                "FROM cyw_type t LEFT JOIN cyw_dept d ON d.id = t.default_dept_id "
                "ORDER BY t.sort_order, t.id"
            )).mappings().fetchall()
        return jsonify({'success': True, 'types': [dict(r) for r in rows]})

    @app.route('/api/cyw/types', methods=['POST'])
    @admin_required
    def cyw_type_create():
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '类型名称不能为空'}), 400
        with engine.begin() as conn:
            dup = conn.execute(text("SELECT id FROM cyw_type WHERE name = :n"), {'n': name}).first()
            if dup:
                return jsonify({'error': '类型名称已存在'}), 400
            cur = conn.execute(text(
                "INSERT INTO cyw_type (name, default_dept_id, deadline_hours, icon, sort_order) "
                "VALUES (:n, :d, :h, :ic, :s)"
            ), {'n': name, 'd': data.get('default_dept_id'),
                'h': int(data.get('deadline_hours') or 4),
                'ic': data.get('icon'), 's': data.get('sort_order') or 0})
            return jsonify({'success': True, 'id': cur.lastrowid})

    @app.route('/api/cyw/types/<int:type_id>', methods=['PUT'])
    @admin_required
    def cyw_type_update(type_id):
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '类型名称不能为空'}), 400
        with engine.begin() as conn:
            dup = conn.execute(text(
                "SELECT id FROM cyw_type WHERE name = :n AND id <> :i"), {'n': name, 'i': type_id}
            ).first()
            if dup:
                return jsonify({'error': '类型名称已存在'}), 400
            conn.execute(text(
                "UPDATE cyw_type SET name=:n, default_dept_id=:d, deadline_hours=:h, icon=:ic, sort_order=:s "
                "WHERE id=:i"
            ), {'n': name, 'd': data.get('default_dept_id'),
                'h': int(data.get('deadline_hours') or 4),
                'ic': data.get('icon'), 's': data.get('sort_order') or 0, 'i': type_id})
        return jsonify({'success': True})

    @app.route('/api/cyw/types/<int:type_id>', methods=['DELETE'])
    @admin_required
    def cyw_type_delete(type_id):
        with engine.begin() as conn:
            ref = conn.execute(text(
                "SELECT COUNT(*) FROM cyw_issue WHERE type_id=:i"), {'i': type_id}).scalar()
            if ref:
                return jsonify({'error': '该类型已被问题台账引用，不能删除'}), 400
            conn.execute(text("DELETE FROM cyw_type WHERE id=:i"), {'i': type_id})
        return jsonify({'success': True})

    # ---------------------------------------------------------------- 字典：点位档案

    @app.route('/api/cyw/spots', methods=['GET'])
    @protected
    def cyw_spot_list():
        keyword = (request.args.get('keyword') or '').strip()
        page = max(int(request.args.get('page') or 1), 1)
        page_size = min(max(int(request.args.get('page_size') or 20), 1), 200)
        where, params = '', {}
        if keyword:
            where = "WHERE s.monitor_no LIKE :k OR s.name LIKE :k OR s.road LIKE :k OR s.spot_no LIKE :k"
            params['k'] = f'%{keyword}%'
        with engine.connect() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM cyw_spot s {where}"), params).scalar()
            rows = conn.execute(text(
                f"SELECT s.* FROM cyw_spot s {where} ORDER BY s.id LIMIT :lim OFFSET :off"
            ), {**params, 'lim': page_size, 'off': (page - 1) * page_size}).mappings().fetchall()
            items = [dict(r) for r in rows]
            contacts = _load_spot_contacts(conn, [it['id'] for it in items])
            for it in items:
                it['contacts'] = contacts.get(it['id'], [])
        return jsonify({'success': True, 'total': total, 'page': page, 'page_size': page_size, 'spots': items})

    @app.route('/api/cyw/spots', methods=['POST'])
    @admin_required
    def cyw_spot_create():
        data = request.get_json(silent=True) or {}
        monitor_no = (data.get('monitor_no') or '').strip()
        name = (data.get('name') or '').strip()
        if not monitor_no or not name:
            return jsonify({'error': '监控序号和点位名称不能为空'}), 400
        lng, err = _parse_coord(data.get('lng'), '经度')
        if err:
            return jsonify({'error': err}), 400
        lat, err = _parse_coord(data.get('lat'), '纬度')
        if err:
            return jsonify({'error': err}), 400
        with engine.begin() as conn:
            dup = conn.execute(text(
                "SELECT id FROM cyw_spot WHERE monitor_no = :m"), {'m': monitor_no}).first()
            if dup:
                return jsonify({'error': f'监控序号 {monitor_no} 已存在'}), 400
            cur = conn.execute(text(
                "INSERT INTO cyw_spot (spot_no, monitor_no, name, road, manage_unit, camera_source, spot_type, "
                "contact_name, contact_phone, contact_extra, is_key, lng, lat, note) "
                "VALUES (:sn, :m, :n, :r, :mu, :cs, :st, :cn, :cp, :ce, :k, :lng, :lat, :note)"
            ), {'sn': data.get('spot_no'), 'm': monitor_no, 'n': name, 'r': data.get('road'),
                'mu': (data.get('manage_unit') or '').strip() or '城市管理局',
                'cs': (data.get('camera_source') or '').strip() or None,
                'st': (data.get('spot_type') or '').strip() or None,
                'cn': (data.get('contact_name') or '').strip() or None,
                'cp': (data.get('contact_phone') or '').strip() or None,
                'ce': (data.get('contact_extra') or '').strip() or None,
                'k': 1 if data.get('is_key') else 0, 'lng': lng, 'lat': lat,
                'note': data.get('note')})
            spot_id = cur.lastrowid
            # 联系人（按部门/人员/电话逐条）随点位整表替换；老单联系人列已废弃，不再写入。
            # 仅当请求显式带 contacts 键才替换，避免不带该键的调用误清空
            if 'contacts' in data:
                _replace_spot_contacts(conn, spot_id, data.get('contacts'))
        return jsonify({'success': True, 'id': spot_id})

    @app.route('/api/cyw/spots/<int:spot_id>', methods=['PUT'])
    @admin_required
    def cyw_spot_update(spot_id):
        data = request.get_json(silent=True) or {}
        monitor_no = (data.get('monitor_no') or '').strip()
        name = (data.get('name') or '').strip()
        if not monitor_no or not name:
            return jsonify({'error': '监控序号和点位名称不能为空'}), 400
        lng, err = _parse_coord(data.get('lng'), '经度')
        if err:
            return jsonify({'error': err}), 400
        lat, err = _parse_coord(data.get('lat'), '纬度')
        if err:
            return jsonify({'error': err}), 400
        with engine.begin() as conn:
            dup = conn.execute(text(
                "SELECT id FROM cyw_spot WHERE monitor_no = :m AND id <> :i"),
                {'m': monitor_no, 'i': spot_id}).first()
            if dup:
                return jsonify({'error': f'监控序号 {monitor_no} 已被其他点位占用'}), 400
            conn.execute(text(
                "UPDATE cyw_spot SET spot_no=:sn, monitor_no=:m, name=:n, road=:r, manage_unit=:mu, "
                "camera_source=:cs, spot_type=:st, contact_name=:cn, contact_phone=:cp, contact_extra=:ce, "
                "is_key=:k, lng=:lng, lat=:lat, note=:note WHERE id=:i"
            ), {'sn': data.get('spot_no'), 'm': monitor_no, 'n': name, 'r': data.get('road'),
                'mu': (data.get('manage_unit') or '').strip() or '城市管理局',
                'cs': (data.get('camera_source') or '').strip() or None,
                'st': (data.get('spot_type') or '').strip() or None,
                'cn': (data.get('contact_name') or '').strip() or None,
                'cp': (data.get('contact_phone') or '').strip() or None,
                'ce': (data.get('contact_extra') or '').strip() or None,
                'k': 1 if data.get('is_key') else 0, 'lng': lng, 'lat': lat,
                'note': data.get('note'), 'i': spot_id})
            # 联系人整表替换（随点位保存）；老单联系人列已废弃，不再写入。
            # 仅当请求显式带 contacts 键才替换，避免不带该键的调用误清空
            if 'contacts' in data:
                _replace_spot_contacts(conn, spot_id, data.get('contacts'))
        return jsonify({'success': True})

    @app.route('/api/cyw/spots/<int:spot_id>', methods=['DELETE'])
    @admin_required
    def cyw_spot_delete(spot_id):
        with engine.begin() as conn:
            ref = conn.execute(text(
                "SELECT COUNT(*) FROM cyw_issue WHERE spot_id=:i"), {'i': spot_id}).scalar()
            if ref:
                return jsonify({'error': '该点位已被问题台账引用，不能删除'}), 400
            conn.execute(text("DELETE FROM cyw_spot_contact WHERE spot_id=:i"), {'i': spot_id})
            conn.execute(text("DELETE FROM cyw_spot WHERE id=:i"), {'i': spot_id})
        return jsonify({'success': True})

    # 点位 Excel 导入列名别名（44 点位清单批量建档）
    SPOT_COL_ALIASES = {
        'spot_no': ['点位编号', '编号'],
        'monitor_no': ['监控序号', '序号'],
        'name': ['点位名称', '名称'],
        'road': ['所在路段', '路段'],
        'manage_unit': ['管理单位', '管辖单位', '所属单位'],
        'camera_source': ['摄像头归属', '归属', '摄像头来源'],
        'spot_type': ['点位类型', '类型'],
        'contact_name': ['点位负责人', '负责人', '联系人'],
        'contact_phone': ['负责人电话', '联系电话', '联系方式'],
        'contact_extra': ['其他联系人', '补充联系人'],
        'is_key': ['是否重点', '重点', '是否重点点位'],
        'lng': ['经度', '高德经度', 'longitude', 'lng'],
        'lat': ['纬度', '高德纬度', 'latitude', 'lat'],
    }

    def _norm_spot_df(df):
        """列名归一化 + 逐行校验，返回 (rows, invalid)"""
        col_map = {}
        for col in df.columns:
            c = str(col).strip()
            for key, aliases in SPOT_COL_ALIASES.items():
                if c in aliases and key not in col_map:
                    col_map[key] = col
                    break
        rows, invalid, warnings = [], [], []
        for idx, raw in df.iterrows():
            row_no = idx + 2  # Excel 行号（含表头）
            def g(key):
                col = col_map.get(key)
                if col is None:
                    return ''
                v = raw.get(col)
                if v is None or pd.isna(v):
                    return ''
                # Excel 纯数字列（电话/序号）会被 pandas 推成 float，整数浮点去掉 .0 尾巴
                if isinstance(v, float) and v == int(v):
                    return str(int(v))
                return str(v).strip()
            monitor_no = g('monitor_no')
            name = g('name')
            if not monitor_no or not name:
                invalid.append({'row': row_no, 'reason': f'监控序号/点位名称不能为空（序号:{monitor_no or "空"}）'})
                continue
            lng, lng_err = _parse_coord(g('lng'), '经度')
            lat, lat_err = _parse_coord(g('lat'), '纬度')
            coord_err = lng_err or lat_err
            if coord_err:
                invalid.append({'row': row_no, 'reason': coord_err})
                continue
            if (lng is not None or lat is not None) and not (73 <= (lng or 0) <= 135 and 3 <= (lat or 0) <= 53):
                warnings.append({'row': row_no, 'monitor_no': monitor_no,
                                 'reason': f'坐标({lng},{lat})不在中国范围内，请确认是否填反或录错'})
            is_key_raw = g('is_key').lower()
            rows.append({
                'spot_no': g('spot_no'), 'monitor_no': monitor_no, 'name': name,
                'road': g('road'), 'manage_unit': g('manage_unit'),
                'camera_source': g('camera_source'), 'spot_type': g('spot_type'),
                'contact_name': g('contact_name'), 'contact_phone': g('contact_phone'),
                'contact_extra': g('contact_extra'),
                'is_key': 1 if is_key_raw in ('1', '是', 'true', 'y', 'yes', '重点') else 0,
                'lng': lng, 'lat': lat,
            })
        return rows, invalid, warnings, bool(col_map.get('monitor_no') and col_map.get('name'))

    # 联系人 sheet 列名别名（一个点位可有多行：环卫中心/点位主管/执法队…按部门逐条）
    CONTACT_COL_ALIASES = {
        'monitor_no': ['监控序号', '序号'],
        'dept_label': ['部门', '部门/角色', '所属部门', '角色'],
        'person': ['人员', '姓名', '联系人', '负责人'],
        'phone': ['电话', '联系电话', '联系方式'],
    }

    def _norm_contact_df(df):
        """联系人 sheet → {监控序号: [{dept_label, person, phone}, ...]}；缺序号/人员列则返回空"""
        col_map = {}
        for col in df.columns:
            c = str(col).strip()
            for key, aliases in CONTACT_COL_ALIASES.items():
                if c in aliases and key not in col_map:
                    col_map[key] = col
                    break
        out = {}
        if not (col_map.get('monitor_no') and col_map.get('person')):
            return out
        for idx, raw in df.iterrows():
            def g(key):
                col = col_map.get(key)
                if col is None:
                    return ''
                v = raw.get(col)
                if v is None or pd.isna(v):
                    return ''
                # 电话列同样是纯数字，会被 pandas 推成 float
                if isinstance(v, float) and v == int(v):
                    return str(int(v))
                return str(v).strip()
            monitor_no, person = g('monitor_no'), g('person')
            if not monitor_no or not person:
                continue
            out.setdefault(monitor_no, []).append(
                {'dept_label': g('dept_label'), 'person': person, 'phone': g('phone')})
        return out

    def _sheet_has_spot_cols(df):
        """sheet 是否含点位主表必需列（监控序号+点位名称），用于多 sheet 工作簿里定位主表"""
        cols = set()
        for col in df.columns:
            c = str(col).strip()
            for key, aliases in SPOT_COL_ALIASES.items():
                if c in aliases:
                    cols.add(key)
        return {'monitor_no', 'name'} <= cols

    @app.route('/api/cyw/spots/import', methods=['POST'])
    @admin_required
    def cyw_spot_import_preview():
        """上传点位 Excel → 预览校验（两段式第一步，照抄 cleaning/upload）
        工作簿可含两个 sheet：主表（点位）+「联系人」表（按部门/人员/电话逐条，按监控序号归组）"""
        if 'file' not in request.files:
            return jsonify({'error': '请选择文件'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '文件名为空'}), 400
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.xlsx', '.xls'):
            return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400
        try:
            sheets = pd.read_excel(io.BytesIO(file.read()), sheet_name=None)
        except Exception as e:
            logger.error(f'创文点位导入解析失败: {e}')
            return jsonify({'error': f'文件解析失败: {str(e)}'}), 400
        if not sheets:
            return jsonify({'error': '文件无数据'}), 400
        df, contact_df = None, None
        for sheet_name, sdf in sheets.items():
            if sdf is None or sdf.empty:
                continue
            if df is None and _sheet_has_spot_cols(sdf):
                df = sdf
                continue
            if contact_df is None and ('联系人' in str(sheet_name) or '联络' in str(sheet_name)
                                       or 'contact' in str(sheet_name).lower()):
                contact_df = sdf
        if df is None:
            # 没有合法主表：取第一个非空 sheet，让后面的缺列校验给出列名清单
            df = next((s for s in sheets.values() if s is not None and not s.empty), pd.DataFrame())
        if df.empty:
            return jsonify({'error': '文件无数据行'}), 400
        rows, invalid, warnings, has_required = _norm_spot_df(df)
        if not has_required:
            return jsonify({'error': '缺少必要列：监控序号（或序号）、点位名称（或名称）',
                            'actual_columns': [str(c) for c in df.columns]}), 400
        # 联系人 sheet：按监控序号归组挂到主表行上；主表没有的序号只警告不阻断
        contact_count = 0
        if contact_df is not None:
            contacts_by_no = _norm_contact_df(contact_df)
            contact_count = sum(len(v) for v in contacts_by_no.values())
            valid_nos = {r['monitor_no'] for r in rows}
            for mno, items in contacts_by_no.items():
                if mno not in valid_nos:
                    warnings.append({'row': '-', 'monitor_no': mno,
                                     'reason': f'联系人表中序号 {mno} 在主表不存在，该点位联系人不会导入'})
            for r in rows:
                r['contacts'] = contacts_by_no.get(r['monitor_no'], [])
        # 文件内监控序号重复检查
        seen, dup = set(), []
        for r in rows:
            if r['monitor_no'] in seen:
                dup.append(r['monitor_no'])
            seen.add(r['monitor_no'])
        return jsonify({
            'success': True, 'total': len(rows), 'valid_count': len(rows),
            'invalid': invalid, 'warnings': warnings, 'dup_in_file': dup,
            'contact_count': contact_count,
            'preview': rows[:10], 'rows': rows,
        })

    @app.route('/api/cyw/spots/import/confirm', methods=['POST'])
    @admin_required
    def cyw_spot_import_confirm():
        """确认导入（两段式第二步）：按监控序号 upsert"""
        data = request.get_json(silent=True) or {}
        rows = data.get('rows') or []
        if not rows:
            return jsonify({'error': '没有可导入的数据'}), 400
        inserted, updated = 0, 0
        with engine.begin() as conn:
            for r in rows:
                monitor_no = str(r.get('monitor_no') or '').strip()
                name = str(r.get('name') or '').strip()
                if not monitor_no or not name:
                    continue
                exist = conn.execute(text(
                    "SELECT id FROM cyw_spot WHERE monitor_no = :m"), {'m': monitor_no}).first()
                if exist:
                    conn.execute(text(
                        "UPDATE cyw_spot SET spot_no=:sn, name=:n, road=:r, manage_unit=:mu, camera_source=:cs, "
                        "spot_type=:st, contact_name=:cn, contact_phone=:cp, contact_extra=:ce, "
                        "is_key=:k, lng=:lng, lat=:lat WHERE id=:i"
                    ), {'sn': r.get('spot_no'), 'n': name, 'r': r.get('road'),
                        'mu': (r.get('manage_unit') or '').strip() or '城市管理局',
                        'cs': (r.get('camera_source') or '').strip() or None,
                        'st': (r.get('spot_type') or '').strip() or None,
                        'cn': (r.get('contact_name') or '').strip() or None,
                        'cp': (r.get('contact_phone') or '').strip() or None,
                        'ce': (r.get('contact_extra') or '').strip() or None,
                        'k': 1 if r.get('is_key') else 0, 'lng': r.get('lng'), 'lat': r.get('lat'),
                        'i': exist[0]})
                    spot_id = exist[0]
                    updated += 1
                else:
                    cur = conn.execute(text(
                        "INSERT INTO cyw_spot (spot_no, monitor_no, name, road, manage_unit, camera_source, spot_type, "
                        "contact_name, contact_phone, contact_extra, is_key, lng, lat) "
                        "VALUES (:sn, :m, :n, :r, :mu, :cs, :st, :cn, :cp, :ce, :k, :lng, :lat)"
                    ), {'sn': r.get('spot_no'), 'm': monitor_no, 'n': name,
                        'r': r.get('road'),
                        'mu': (r.get('manage_unit') or '').strip() or '城市管理局',
                        'cs': (r.get('camera_source') or '').strip() or None,
                        'st': (r.get('spot_type') or '').strip() or None,
                        'cn': (r.get('contact_name') or '').strip() or None,
                        'cp': (r.get('contact_phone') or '').strip() or None,
                        'ce': (r.get('contact_extra') or '').strip() or None,
                        'k': 1 if r.get('is_key') else 0,
                        'lng': r.get('lng'), 'lat': r.get('lat')})
                    spot_id = cur.lastrowid
                    inserted += 1
                # 联系人（按部门/人员/电话逐条）随导入整表替换：行上带 contacts 键才动，
                # 即文件含「联系人」sheet 时以该表为准（没列到的点位联系人会被清空）
                if 'contacts' in r:
                    _replace_spot_contacts(conn, spot_id, r.get('contacts') or [])
        return jsonify({'success': True, 'inserted': inserted, 'updated': updated})

    # ---------------------------------------------------------------- 案件台账一键导入（历史 Excel 两段式）

    @app.route('/api/cyw/issues/import', methods=['POST'])
    @admin_required
    def cyw_issue_import_preview():
        """历史台账 Excel 导入（第一步预览）：多月份 sheet 合并解析，点位/单位/类型匹配情况一目了然
        兼容实际台账格式：标题行下表头、日期列仅每天首行有值（向下填充）、点位列=监控序号+名称连写、
        处置单位用俗称（别名映射）、处置结果非空即视为已办结（含处理时间）"""
        if 'file' not in request.files:
            return jsonify({'error': '请选择文件'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '文件名为空'}), 400
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.xlsx', '.xls'):
            return jsonify({'error': '仅支持 .xlsx / .xls 格式'}), 400
        try:
            sheets = pd.read_excel(io.BytesIO(file.read()), sheet_name=None, header=None)
        except Exception as e:
            logger.error(f'创文台账导入解析失败: {e}')
            return jsonify({'error': f'文件解析失败: {str(e)}'}), 400
        month_sheets = {sn: df for sn, df in sheets.items()
                        if re.fullmatch(r'\d+\s*月', str(sn).strip())}
        skipped = [{'sheet': str(sn), 'reason': '非月份工作表（仅导入"N月"表）'}
                   for sn in sheets if sn not in month_sheets]
        if not month_sheets:
            return jsonify({'error': '未找到按月份命名的工作表（如"1月""2月"），请核对文件格式',
                            'actual_columns': [str(s) for s in sheets.keys()]}), 400

        # 第一遍：按 sheet 找表头行、收集原始单元格（日期先不填充，缺年份的要用全文件年份众数兜底）
        raw_rows = []
        for sn, df in month_sheets.items():
            hdr = None
            for i in range(min(10, len(df))):
                cells = [str(x) for x in df.iloc[i].tolist()]
                if any('点位' in c for c in cells) and any('描述' in c for c in cells):
                    hdr = i
                    break
            if hdr is None:
                skipped.append({'sheet': str(sn), 'reason': '未找到表头行（需含「点位/问题描述」列）'})
                continue
            for _, r in df.iloc[hdr + 1:, :7].iterrows():
                cells = list(r) + [None] * max(0, 7 - len(r))
                desc = '' if pd.isna(cells[4]) else str(cells[4]).strip()
                if not desc:
                    continue  # 空行/表尾统计行
                raw_rows.append({
                    'sheet': str(sn),
                    'date_raw': cells[0],
                    'time_raw': cells[2],
                    'spot_text': '' if pd.isna(cells[3]) else str(cells[3]).strip(),
                    'description': desc,
                    'dept_raw': cells[5],
                    'result_raw': cells[6],
                })
        if not raw_rows:
            return jsonify({'error': '月份工作表中没有数据行（需含「点位/问题描述」列）'}), 400

        years = [int(y) for rr in raw_rows for y in re.findall(r'(20\d{2})', str(rr['date_raw']) or '')]
        fallback_year = Counter(years).most_common(1)[0][0] if years else datetime.now().year

        # 第二遍：日期向下填充 + 字典匹配
        with engine.connect() as conn:
            spot_by_no = {r[1]: r[0] for r in conn.execute(text("SELECT id, monitor_no FROM cyw_spot"))}
            spot_by_name = {r[1]: r[0] for r in conn.execute(text("SELECT id, name FROM cyw_spot"))}
            dept_by_name = {r[1]: r[0] for r in conn.execute(text("SELECT id, name FROM cyw_dept"))}
            type_by_name = {r[1]: r[0] for r in conn.execute(text("SELECT id, name FROM cyw_type"))}

        rows, invalid = [], []
        seen_keys, cur_date = set(), None
        for rr in raw_rows:
            d = _parse_import_date(rr['date_raw'], fallback_year)
            if d:
                cur_date = d
            if not cur_date:
                invalid.append({'sheet': rr['sheet'], 'reason': '无法解析日期（首行即无日期）'})
                continue
            monitor_no, spot_name = _split_spot_text(rr['spot_text'])
            spot_id = spot_by_no.get(monitor_no) if monitor_no else None
            if spot_id is None and spot_name:
                spot_id = spot_by_name.get(spot_name)
            dept_raw = '' if pd.isna(rr['dept_raw']) else str(rr['dept_raw']).strip()
            dept_alias = CYW_IMPORT_DEPT_ALIASES.get(dept_raw, dept_raw)
            dept_id = dept_by_name.get(dept_alias) if dept_alias else None
            type_name = _match_type_name(rr['description'])
            type_id = type_by_name.get(type_name) if type_name else None
            closed, closed_t = _parse_import_result(rr['result_raw'])
            found_at = datetime.combine(cur_date, _parse_import_time(rr['time_raw']) or time(0, 0))
            closed_at = None
            if closed:
                closed_at = datetime.combine(cur_date, closed_t) if closed_t else found_at
                if closed_at < found_at:
                    closed_at += timedelta(days=1)  # 跨零点的处理时间归到次日
            key = (spot_id or spot_name, found_at, rr['description'])
            dup = key in seen_keys
            seen_keys.add(key)
            result_raw = '' if pd.isna(rr['result_raw']) else str(rr['result_raw']).strip()
            rows.append({
                'sheet': rr['sheet'], 'found_at': found_at.strftime('%Y-%m-%d %H:%M:%S'),
                'spot_text': rr['spot_text'], 'spot_monitor_no': monitor_no, 'spot_name': spot_name,
                'spot_id': spot_id, 'spot_new': spot_id is None,
                'dept_name': dept_alias, 'dept_id': dept_id, 'dept_new': dept_id is None and bool(dept_alias),
                'type_name': type_name or '未识别', 'type_id': type_id,
                'description': rr['description'], 'result_raw': result_raw,
                # 台账口径：进库的都是已派发的——结果非空=已办结，空=处置中（单位未反馈）
                'status': ST_DONE if closed else ST_DOING,
                'closed_at': closed_at.strftime('%Y-%m-%d %H:%M:%S') if closed_at else None,
                'dup_in_file': dup,
            })

        new_spots = sorted({r['spot_name'] or r['spot_monitor_no'] for r in rows if r['spot_new']})
        new_depts = sorted({r['dept_name'] for r in rows if r['dept_new']})
        unmatched_type = sum(1 for r in rows if r['type_id'] is None)
        no_result = sum(1 for r in rows if not r['result_raw'])
        dup_in_file = sum(1 for r in rows if r['dup_in_file'])
        logger.info(f'[CYW] 台账导入预览：{len(rows)} 行 / {len(month_sheets)} 个月份sheet，'
                    f'新点位 {len(new_spots)} / 新单位 {len(new_depts)} / 未识别类型 {unmatched_type}')
        return jsonify({
            'success': True, 'sheets': [str(s) for s in month_sheets], 'skipped_sheets': skipped,
            'total': len(rows), 'invalid': invalid,
            'stats': {
                'new_spot_count': len(new_spots), 'new_dept_count': len(new_depts),
                'closed_count': sum(1 for r in rows if r['status'] == ST_DONE),
                'unmatched_type': unmatched_type, 'no_result': no_result, 'dup_in_file': dup_in_file,
            },
            'new_spots': new_spots, 'new_depts': new_depts,
            'preview': rows[:10], 'rows': rows,
        })

    @app.route('/api/cyw/issues/import/confirm', methods=['POST'])
    @admin_required
    def cyw_issue_import_confirm():
        """确认导入（第二步）：自动创建缺失点位/单位、未识别类型按回退类型入库、重复行跳过（可重复导入）"""
        data = request.get_json(silent=True) or {}
        rows = data.get('rows') or []
        if not rows:
            return jsonify({'error': '没有可导入的数据'}), 400
        fallback_type_id = data.get('fallback_type_id')
        create_spots = data.get('create_spots', True)
        create_depts = data.get('create_depts', True)
        inserted = skipped_dup = skipped_spot = skipped_nodept = 0
        created_spots = created_depts = 0
        with engine.begin() as conn:
            spot_by_no = {r[1]: r[0] for r in conn.execute(text("SELECT id, monitor_no FROM cyw_spot"))}
            spot_by_name = {r[1]: r[0] for r in conn.execute(text("SELECT id, name FROM cyw_spot"))}
            dept_by_name = {r[1]: r[0] for r in conn.execute(text("SELECT id, name FROM cyw_dept"))}
            type_by_name = {r[1]: r[0] for r in conn.execute(text("SELECT id, name FROM cyw_type"))}
            need_fallback = sum(1 for r in rows if not r.get('type_id'))
            if need_fallback and not fallback_type_id:
                return jsonify({'error': f'有 {need_fallback} 行未识别问题类型，请先选择回退类型'}), 400
            if fallback_type_id and fallback_type_id not in type_by_name.values():
                return jsonify({'error': '回退类型不存在'}), 400
            seen_keys = set()
            for r in rows:
                desc = (r.get('description') or '').strip()
                found_at = _parse_dt(r.get('found_at'))
                if not desc or not found_at:
                    continue
                # ---- 点位：命中 / 自动创建（无数字前缀的用 XC- 合成序号，原文字进备注）
                monitor_no = (r.get('spot_monitor_no') or '').strip()
                spot_name = (r.get('spot_name') or '').strip()
                spot_id = r.get('spot_id')
                if spot_id:
                    spot_id = int(spot_id)
                elif monitor_no and monitor_no in spot_by_no:
                    spot_id = spot_by_no[monitor_no]
                elif spot_name and spot_name in spot_by_name:
                    spot_id = spot_by_name[spot_name]
                elif create_spots and (monitor_no or spot_name):
                    synthetic = not monitor_no
                    if synthetic:
                        monitor_no = f"XC-{uuid.uuid4().hex[:6]}"
                    cur = conn.execute(text(
                        "INSERT INTO cyw_spot (monitor_no, name, note) VALUES (:m, :n, :note)"),
                        {'m': monitor_no, 'n': spot_name or monitor_no,
                         'note': '历史台账导入自动创建（原无监控序号）' if synthetic else '历史台账导入自动创建'})
                    spot_id = cur.lastrowid
                    spot_by_no[monitor_no] = spot_id
                    if spot_name:
                        spot_by_name[spot_name] = spot_id
                    created_spots += 1
                else:
                    skipped_spot += 1
                    continue
                # ---- 单位：命中 / 自动创建；单位空缺的回落到类型默认派发部门
                dept_name = (r.get('dept_name') or '').strip()
                dept_id = r.get('dept_id')
                if dept_id:
                    dept_id = int(dept_id)
                elif dept_name in dept_by_name:
                    dept_id = dept_by_name[dept_name]
                elif create_depts and dept_name:
                    cur = conn.execute(text(
                        "INSERT INTO cyw_dept (name, color) VALUES (:n, '#1565C0')"), {'n': dept_name})
                    dept_id = cur.lastrowid
                    dept_by_name[dept_name] = dept_id
                    created_depts += 1
                # ---- 类型（时限字段已下线，只取默认主办部门）
                type_id = r.get('type_id') or fallback_type_id
                trow = conn.execute(text(
                    "SELECT default_dept_id FROM cyw_type WHERE id = :i"),
                    {'i': type_id}).mappings().first()
                if not trow:
                    continue
                if not dept_id:
                    dept_id = trow['default_dept_id']
                if not dept_id:
                    skipped_nodept += 1
                    continue
                # ---- 去重：库内 (点位+发现时间+描述) 相同即跳过，文件内同理
                key = (spot_id, found_at, desc)
                if key in seen_keys:
                    skipped_dup += 1
                    continue
                seen_keys.add(key)
                if conn.execute(text(
                        "SELECT id FROM cyw_issue WHERE spot_id=:s AND found_at=:f AND description=:d"),
                        {'s': spot_id, 'f': found_at, 'd': desc}).first():
                    skipped_dup += 1
                    continue
                status = r.get('status') if r.get('status') in CYW_STATUSES else ST_DOING
                closed_at = _parse_dt(r.get('closed_at')) if status == ST_DONE else None
                case_no = _gen_case_no(conn, found_at)
                ts = _now()
                cur = conn.execute(text(
                    "INSERT INTO cyw_issue (case_no, found_at, spot_id, type_id, dept_id, "
                    "description, status, is_fed, fed_at, feedback_note, "
                    "closed_by, closed_at, created_by, created_at, updated_at) "
                    "VALUES (:c, :f, :s, :t, :dp, :d, :st, :fed, :fa, :note, :cb, :ca, :user, :ts, :ts)"
                ), {'c': case_no, 'f': found_at, 's': spot_id, 't': type_id, 'dp': dept_id,
                    'd': desc, 'st': status,
                    'fed': 1 if status == ST_DONE else 0, 'fa': closed_at,
                    'note': (r.get('result_raw') or '')[:2000] or None,
                    'cb': '历史导入' if status == ST_DONE else None, 'ca': closed_at,
                    'user': _now_user(), 'ts': ts})
                issue_id = cur.lastrowid
                _write_log(conn, issue_id, '历史导入', None, status,
                           note=f"来源：{r.get('sheet') or 'Excel'}；处置结果：{r.get('result_raw') or '无'}"[:500])
                inserted += 1
        logger.info(f'[CYW] 台账导入完成：新增 {inserted} / 重复跳过 {skipped_dup} / '
                    f'无点位跳过 {skipped_spot} / 无部门跳过 {skipped_nodept} / '
                    f'自动建点位 {created_spots} / 自动建单位 {created_depts}')
        return jsonify({'success': True, 'inserted': inserted, 'skipped_dup': skipped_dup,
                        'skipped_spot': skipped_spot, 'skipped_nodept': skipped_nodept,
                        'created_spots': created_spots, 'created_depts': created_depts})

    # ---------------------------------------------------------------- 快速录入：序号带出

    @app.route('/api/cyw/spot-by-no', methods=['GET'])
    @protected
    def cyw_spot_by_no():
        no = (request.args.get('no') or '').strip()
        if not no:
            return jsonify({'error': '监控序号不能为空'}), 400
        with engine.connect() as conn:
            spot = conn.execute(text(
                "SELECT * FROM cyw_spot WHERE monitor_no = :m"), {'m': no}
            ).mappings().first()
            if not spot:
                return jsonify({'success': False, 'hit': False, 'error': f'未找到监控序号 {no} 对应的点位'}), 404
            types = conn.execute(text(
                "SELECT t.id, t.name, t.default_dept_id, "
                "d.name AS default_dept_name FROM cyw_type t "
                "LEFT JOIN cyw_dept d ON d.id = t.default_dept_id ORDER BY t.sort_order, t.id"
            )).mappings().fetchall()
            contacts = _load_spot_contacts(conn, [spot['id']]).get(spot['id'], [])
        return jsonify({
            'success': True, 'hit': True,
            'spot': {k: spot[k] for k in ('id', 'spot_no', 'monitor_no', 'name', 'road', 'manage_unit',
                                          'camera_source', 'spot_type', 'contact_name', 'contact_phone',
                                          'contact_extra', 'is_key', 'lng', 'lat')},
            'contacts': contacts,
            'types': [dict(t) for t in types],
        })

    # ---------------------------------------------------------------- 照片上传（操作员为普通账号，自建权限上传口）

    @app.route('/api/cyw/upload-image', methods=['POST'])
    @cyw_biz_access
    def cyw_upload_image():
        if 'file' not in request.files:
            return jsonify({'error': '请选择文件'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '文件名为空'}), 400
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_IMG_EXT:
            return jsonify({'error': '仅支持图片格式（jpg/png/gif/webp/bmp）'}), 400
        save_name = uuid.uuid4().hex + ext
        file.save(os.path.join(CYW_PHOTO_DIR, save_name))
        url = f'/uploads/cyw/photos/{save_name}'
        return jsonify({'success': True, 'url': url, 'name': file.filename})

    # ---------------------------------------------------------------- AI 照片识别（私有化 Qwen2.5-VL）
    # 设计红线：识别失败/超时一律 HTTP 200 + success:false，由前端静默降级为手动填写，绝不阻断登记

    @app.route('/api/cyw/parse-photo', methods=['POST'])
    @cyw_biz_access
    def cyw_parse_photo():
        data = request.get_json(silent=True) or {}
        url = (data.get('url') or '').strip()
        if not url.startswith('/uploads/cyw/photos/'):
            return jsonify({'success': False, 'error': '照片地址不合法'}), 400
        fname = url.rsplit('/', 1)[-1]
        if fname != os.path.basename(fname) or not os.path.splitext(fname)[1].lower() in ALLOWED_IMG_EXT:
            return jsonify({'success': False, 'error': '照片地址不合法'}), 400
        path = os.path.join(CYW_PHOTO_DIR, fname)
        if not os.path.isfile(path):
            return jsonify({'success': False, 'error': '照片不存在'}), 400

        with engine.connect() as conn:
            type_rows = conn.execute(text(
                "SELECT id, name FROM cyw_type ORDER BY sort_order, id"
            )).mappings().fetchall()
        if not type_rows:
            type_rows = [{'id': None, 'name': t[0]} for t in DEFAULT_TYPES]

        # 类型知识卡：命中 CYW_TYPE_HINTS 的类型带判定要点+案例，字典新增类型退化为只给名称
        cards = []
        for i, r in enumerate(type_rows, 1):
            hint = CYW_TYPE_HINTS.get(r['name'])
            if hint:
                defn, examples = hint
                ex = '、'.join(f'"{e}"' for e in examples)
                cards.append(f'{i}. {r["name"]}：{defn}。案例：{ex}' if ex
                             else f'{i}. {r["name"]}：{defn}')
            else:
                cards.append(f'{i}. {r["name"]}')
        type_cards = '\n'.join(cards)

        try:
            with open(path, 'rb') as f:
                raw = f.read()
        except Exception as e:
            logger.warning(f"[CYW] 读取照片失败: {e}")
            return jsonify({'success': False, 'error': '照片读取失败，请手动填写'})

        # 送模型前统一预处理：大文件或超大分辨率缩到最大边 1280。
        # 按像素判定而非只看文件大小——高清低质量压缩图文件不大但分辨率很大，
        # 只看大小会漏过，视觉 token 暴涨撑爆上下文会让识别直接失败
        try:
            img = Image.open(io.BytesIO(raw)).convert('RGB')
            if len(raw) > 2 * 1024 * 1024 or max(img.width, img.height) > 2048:
                # 1280 边 ≈ 2100 视觉 token，加提示与输出仍在 6144 上下文内，识别内容不变
                if max(img.width, img.height) > 1280:
                    scale = 1280 / max(img.width, img.height)
                    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=85)
                raw = buf.getvalue()
        except Exception as e:
            logger.warning(f"[CYW] 照片缩放失败，按原图送模型: {e}")
        b64 = base64.b64encode(raw).decode('ascii')

        t0 = datetime.now()
        try:
            resp = requests.post(
                f"{OLLAMA_HOST_CYW}/api/generate",
                json={
                    'model': CYW_VL_MODEL,
                    'prompt': CYW_VL_PROMPT.replace('{type_cards}', type_cards),
                    'images': [b64],
                    'stream': False,
                    'format': 'json',
                    'options': {'temperature': 0.1, 'num_predict': 400, 'num_ctx': 6144},
                },
                timeout=CYW_VL_TIMEOUT,
            )
        except requests.Timeout:
            # 超时绝大多数是模型掉到 CPU 上跑（ollama 容器 GPU 句柄失效后 offloaded 0/N），
            # 日志直接带排查命令，省一次「翻 ollama 日志猜原因」
            logger.warning(
                "[CYW] VL 识别超时（>%ss）。先查 GPU：docker exec ollama nvidia-smi -L "
                "报 Failed to initialize NVML 即容器掉了显卡，docker restart ollama 即可恢复",
                CYW_VL_TIMEOUT,
            )
            return jsonify({'success': False, 'error': '识别超时，请手动填写'})
        except Exception as e:
            logger.warning(f"[CYW] VL 识别服务异常: {e}")
            return jsonify({'success': False, 'error': '识别服务暂不可用，请手动填写'})

        if resp.status_code != 200:
            logger.warning(f"[CYW] VL 识别失败: HTTP {resp.status_code} {resp.text[:200]}")
            return jsonify({'success': False, 'error': '识别服务暂不可用，请手动填写'})

        elapsed_ms = int((datetime.now() - t0).total_seconds() * 1000)
        parsed = _parse_vl_json(resp.json().get('response') or '')
        description = (parsed.get('description') or '').strip() if parsed else ''
        type_name = (parsed.get('type') or '').strip() if parsed else ''
        observation = (parsed.get('observation') or '').strip() if parsed else ''
        repaired = _repair_parking_type(type_name, observation, description)
        if repaired != type_name:
            logger.info(f"[CYW] VL 类型纠偏: {type_name or '(空)'} -> {repaired} 观察={observation[:40]}")
            type_name = repaired
        if not description:
            return jsonify({'success': False, 'error': '未能识别出问题，请手动填写', 'elapsed_ms': elapsed_ms})
        type_id = next((r['id'] for r in type_rows if r['name'] == type_name), None)
        if type_id is None and type_name:
            # 模型偶尔返回清单变体（如"垃圾"代替"垃圾不洁"），做一次包含匹配兜底
            for r in type_rows:
                if type_name and (type_name in r['name'] or r['name'] in type_name):
                    type_id, type_name = r['id'], r['name']
                    break
        if type_id is None:
            # 仍不命中（模型把描述句填进了 type 或自造词）：按关键词表兜底，
            # 与历史台账导入共用同一套口径，保证 AI 判定和导入归类一致
            for name, kws in CYW_TYPE_KEYWORDS:
                if any(k in (type_name or description) for k in kws):
                    hit = next((r for r in type_rows if r['name'] == name), None)
                    if hit and hit['id'] is not None:
                        logger.info(f"[CYW] VL 类型关键词兜底: {type_name or '(空)'} -> {name}")
                        type_id, type_name = hit['id'], hit['name']
                        break
        if type_id and type_name in ('机动车乱停放', '非机动车乱停放'):
            # 停放类描述直接写问题名（用户口径：只说问题，不写车型/颜色/停放位置）。
            # 提示词里已有同规则，此处再兜一层确定性，避免模型时听时不听
            description = type_name
        logger.info(f"[CYW] VL 识别成功: {description[:30]}... 类型={type_name} 耗时={elapsed_ms}ms"
                    + (f" 观察={observation[:40]}" if observation else ""))
        return jsonify({
            'success': True,
            'description': description[:200],
            'type_id': type_id,
            'type_name': type_name if type_id else '',
            'elapsed_ms': elapsed_ms,
        })

    # ---------------------------------------------------------------- 案件：登记/查询/编辑

    @app.route('/api/cyw/issues', methods=['GET'])
    @protected
    def cyw_issue_list():
        status = (request.args.get('status') or '').strip()
        spot_id = request.args.get('spot_id')
        type_id = request.args.get('type_id')
        dept_id = request.args.get('dept_id')
        date_from = (request.args.get('date_from') or '').strip()
        date_to = (request.args.get('date_to') or '').strip()
        keyword = (request.args.get('keyword') or '').strip()
        page = max(int(request.args.get('page') or 1), 1)
        page_size = min(max(int(request.args.get('page_size') or 20), 1), 100)

        where, params = [], {}
        if status:
            where.append("i.status = :status")
            params['status'] = status
        if spot_id:
            where.append("i.spot_id = :spot_id")
            params['spot_id'] = spot_id
        if type_id:
            where.append("i.type_id = :type_id")
            params['type_id'] = type_id
        if dept_id:
            where.append("i.dept_id = :dept_id")
            params['dept_id'] = dept_id
        if date_from:
            where.append("i.found_at >= :df")
            params['df'] = f'{date_from} 00:00:00'
        if date_to:
            where.append("i.found_at <= :dt")
            params['dt'] = f'{date_to} 23:59:59'
        if keyword:
            where.append("(i.case_no LIKE :k OR i.description LIKE :k OR s.name LIKE :k OR s.monitor_no LIKE :k)")
            params['k'] = f'%{keyword}%'
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        base_from = ("FROM cyw_issue i JOIN cyw_spot s ON s.id = i.spot_id "
                     "JOIN cyw_type t ON t.id = i.type_id "
                     "JOIN cyw_dept d ON d.id = i.dept_id")
        with engine.connect() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) {base_from} {where_sql}"), params).scalar()
            rows = conn.execute(text(
                f"SELECT i.*, s.name AS spot_name, s.monitor_no, s.road, s.is_key, "
                f"t.name AS type_name, d.name AS dept_name, d.color AS dept_color "
                f"{base_from} {where_sql} ORDER BY i.found_at DESC, i.id DESC "
                f"LIMIT :lim OFFSET :off"
            ), {**params, 'lim': page_size, 'off': (page - 1) * page_size}).mappings().fetchall()
            items = [_serialize_issue(r) for r in rows]
        return jsonify({'success': True, 'total': total, 'page': page,
                        'page_size': page_size, 'issues': items})

    @app.route('/api/cyw/issues', methods=['POST'])
    @cyw_input_access
    def cyw_issue_create():
        """登记：序号带出点位后提交（部门默认带出、可改单部门）。
        2026-10-16 起登记即视为已派发，直接落「处置中」，无后续派发动作。"""
        data = request.get_json(silent=True) or {}
        spot_id = data.get('spot_id')
        type_id = data.get('type_id')
        if not spot_id or not type_id:
            return jsonify({'error': '点位和问题类型不能为空'}), 400
        found_at = _parse_dt(data.get('found_at'), datetime.now())
        description = (data.get('description') or '').strip()
        if not description:
            return jsonify({'error': '问题描述不能为空'}), 400
        photos = data.get('photos') or []
        with engine.begin() as conn:
            trow = conn.execute(text(
                "SELECT default_dept_id FROM cyw_type WHERE id = :i"), {'i': type_id}
            ).mappings().first()
            if not trow:
                return jsonify({'error': '问题类型不存在'}), 400
            spot = conn.execute(text("SELECT id FROM cyw_spot WHERE id = :i"), {'i': spot_id}).first()
            if not spot:
                return jsonify({'error': '点位不存在'}), 400
            dept_id = data.get('dept_id') or trow['default_dept_id']
            if not dept_id:
                return jsonify({'error': '请选择派发部门（该类型未配置默认派发部门）'}), 400
            if not conn.execute(text("SELECT id FROM cyw_dept WHERE id = :i"), {'i': dept_id}).first():
                return jsonify({'error': '派发部门不存在'}), 400
            case_no = _gen_case_no(conn)
            ts = _now()
            cur = conn.execute(text(
                "INSERT INTO cyw_issue (case_no, found_at, spot_id, type_id, dept_id, "
                "description, photos, status, created_by, created_at, updated_at) "
                "VALUES (:c, :f, :s, :t, :dp, :d, :p, :st, :cb, :ts, :ts)"
            ), {'c': case_no, 'f': found_at, 's': spot_id, 't': type_id, 'dp': dept_id,
                'd': description, 'p': _dump_json_list(photos), 'st': ST_DOING,
                'cb': _now_user(), 'ts': ts})
            issue_id = cur.lastrowid
            _write_log(conn, issue_id, '登记', None, ST_DOING)
            row = _issue_row(conn, issue_id)
        return jsonify({'success': True, 'id': issue_id, 'case_no': case_no,
                        'issue': _serialize_issue(row)})

    @app.route('/api/cyw/issues/<int:issue_id>', methods=['GET'])
    @protected
    def cyw_issue_detail(issue_id):
        with engine.connect() as conn:
            row = _issue_row(conn, issue_id)
            if not row:
                return jsonify({'error': '问题不存在'}), 404
            logs = [dict(r) for r in conn.execute(text(
                "SELECT * FROM cyw_issue_log WHERE issue_id = :i ORDER BY id"
            ), {'i': issue_id}).mappings().fetchall()]
        item = _serialize_issue(row)
        for lg in logs:
            if lg.get('created_at'):
                lg['created_at'] = lg['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        item['logs'] = logs
        return jsonify({'success': True, 'issue': item})

    @app.route('/api/cyw/issues/<int:issue_id>', methods=['PUT'])
    @cyw_input_access
    def cyw_issue_update(issue_id):
        """仅「处置中」可编辑；已办结的问题一律留痕不改（如需更正请删除后重新登记）"""
        data = request.get_json(silent=True) or {}
        with engine.begin() as conn:
            row = conn.execute(text("SELECT * FROM cyw_issue WHERE id = :i"), {'i': issue_id}).mappings().first()
            if not row:
                return jsonify({'error': '问题不存在'}), 404
            if row['status'] != ST_DOING:
                return jsonify({'error': f'当前状态为{row["status"]}，已办结的问题不能编辑'}), 400
            spot_id = data.get('spot_id') or row['spot_id']
            type_id = data.get('type_id') or row['type_id']
            found_at = _parse_dt(data.get('found_at'), row['found_at'])
            dept_id = data.get('dept_id') or row['dept_id']
            if not dept_id:
                return jsonify({'error': '请选择派发部门'}), 400
            if not conn.execute(text("SELECT id FROM cyw_dept WHERE id = :i"), {'i': dept_id}).first():
                return jsonify({'error': '派发部门不存在'}), 400
            description = (data.get('description') or '').strip() or row['description']
            photos = data.get('photos')
            conn.execute(text(
                "UPDATE cyw_issue SET spot_id=:s, type_id=:t, dept_id=:dp, found_at=:f, "
                "description=:d, photos=:p, updated_at=:ts WHERE id=:i"
            ), {'s': spot_id, 't': type_id, 'dp': dept_id,
                'f': found_at, 'd': description,
                'p': _dump_json_list(photos) if photos is not None else row['photos'],
                'i': issue_id, 'ts': _now()})
            _write_log(conn, issue_id, '编辑', row['status'], row['status'])
        return jsonify({'success': True})

    @app.route('/api/cyw/issues/<int:issue_id>', methods=['DELETE'])
    @cyw_input_access
    def cyw_issue_delete(issue_id):
        """仅「处置中」可删除——登记错误纠正；已办结一律留痕不删"""
        with engine.begin() as conn:
            row = conn.execute(text("SELECT status FROM cyw_issue WHERE id = :i"), {'i': issue_id}).first()
            if not row:
                return jsonify({'error': '问题不存在'}), 404
            if row[0] != ST_DOING:
                return jsonify({'error': '已办结的问题不能删除（全程留痕）'}), 400
            conn.execute(text("DELETE FROM cyw_issue_log WHERE issue_id = :i"), {'i': issue_id})
            conn.execute(text("DELETE FROM cyw_issue WHERE id=:i"), {'i': issue_id})
        return jsonify({'success': True})

    # ---------------------------------------------------------------- 流程：反馈即办结

    @app.route('/api/cyw/issues/<int:issue_id>/feedback', methods=['POST'])
    @cyw_ledger_access
    def cyw_issue_feedback(issue_id):
        """派发部门回填反馈，反馈即办结（2026-10-16 起无核销/退回环节）。
        已办结的案件允许再反馈一次作为更正通道，首次办结时间保留，避免日报办结数被更正动作虚增。"""
        data = request.get_json(silent=True) or {}
        note = (data.get('feedback_note') or '').strip()
        photos = data.get('feedback_photos') or []
        # 反馈即办结，空反馈等于"什么都没说就结案"，前后端都拦一道
        if not note and not photos:
            return jsonify({'error': '请填写反馈说明或上传反馈照片'}), 400
        with engine.begin() as conn:
            row = conn.execute(text(
                "SELECT i.status, i.is_fed, d.name FROM cyw_issue i JOIN cyw_dept d ON d.id = i.dept_id "
                "WHERE i.id = :i"), {'i': issue_id}).first()
            if not row:
                return jsonify({'error': '问题不存在'}), 404
            old_status = row[0]
            first_feedback = not row[1]
            ts = _now()
            # 首次反馈同时落办结人与办结时间；再次反馈只更新反馈内容（首次办结时间保留）
            if first_feedback:
                conn.execute(text(
                    "UPDATE cyw_issue SET is_fed = 1, fed_at = :ts, feedback_note = :n, "
                    "feedback_photos = :p, status = :s, closed_by = :cb, closed_at = :ts, "
                    "updated_at = :ts WHERE id = :i"
                ), {'n': note, 'p': _dump_json_list(photos), 's': ST_DONE,
                    'cb': _now_user(), 'i': issue_id, 'ts': ts})
            else:
                conn.execute(text(
                    "UPDATE cyw_issue SET is_fed = 1, feedback_note = :n, "
                    "feedback_photos = :p, updated_at = :ts WHERE id = :i"
                ), {'n': note, 'p': _dump_json_list(photos), 'i': issue_id, 'ts': ts})
            _write_log(conn, issue_id, '反馈' if first_feedback else '补充反馈',
                       old_status, ST_DONE, note[:200] if note else None)
        return jsonify({'success': True, 'status': ST_DONE})

    # ---------------------------------------------------------------- 一键生成案件详单（PIL 绘图）

    def _load_font(size):
        for path in FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception as e:
                    logger.warning(f'字体加载失败 {path}: {e}')
        return ImageFont.load_default()

    def _wrap_text(draw, text_str, font, max_width):
        """按像素宽度逐字换行（中文无空格，按字宽累计）"""
        lines, cur = [], ''
        for ch in str(text_str or ''):
            if ch == '\n':
                lines.append(cur)
                cur = ''
                continue
            if draw.textlength(cur + ch, font=font) > max_width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines or ['']

    @app.route('/api/cyw/issues/<int:issue_id>/slip', methods=['POST'])
    @cyw_biz_access
    def cyw_issue_slip(issue_id):
        """生成处置详单 JPG：白底工单式，顶部标题条取派发部门底色（方案 6.2）"""
        with engine.connect() as conn:
            row = _issue_row(conn, issue_id)
            if not row:
                return jsonify({'error': '问题不存在'}), 404

        host_color = row.get('dept_color') or '#1565C0'
        try:
            rgb = tuple(int(host_color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
        except Exception:
            rgb = (21, 101, 192)

        W, PAD = 960, 44
        f_title = _load_font(36)
        f_label = _load_font(22)
        f_value = _load_font(22)
        f_small = _load_font(18)

        # 预排版：计算画布高度
        probe = Image.new('RGB', (W, 100))
        pdraw = ImageDraw.Draw(probe)
        desc_lines = _wrap_text(pdraw, row.get('description') or '', f_value, W - PAD * 2 - 90)

        # 现场照片：全部排入（原来只放第一张，且取的是 path 键——上传接口返回的是 url 键，
        # 取出来一直是空串，os.path.join 落到 uploads 目录本身，Image.open 必炸被 except 吞掉，
        # 结果详单从来没带上过照片）。这里 url/path 两个键都认。
        loaded = []
        for p in _parse_json_list(row.get('photos')):
            rel = p.get('url') or p.get('path') or ''
            if not rel:
                continue
            fs_path = os.path.join(UPLOAD_DIR, rel.lstrip('/uploads/'))
            if not os.path.isfile(fs_path):
                continue
            try:
                loaded.append(Image.open(fs_path).convert('RGB'))
            except Exception as e:
                logger.warning(f'详单照片加载失败 {rel}: {e}')

        def _fit(im, box_w, box_h):
            r = min(box_w / im.width, box_h / im.height, 1)
            return im.resize((max(int(im.width * r), 1), max(int(im.height * r), 1)),
                             Image.LANCZOS)

        # 1 张通栏、按实际高度收；2 张起两列等宽网格、行高统一，避免详单被照片撑得过长
        PHOTO_GAP, PHOTO_CELL_H = 16, 420
        photo_cells, photo_cols = [], 1
        if loaded:
            photo_cols = 1 if len(loaded) == 1 else 2
            if photo_cols == 1:
                im = _fit(loaded[0], W - PAD * 2, 560)
                photo_cells = [im]
                photo_h = im.height + 24
            else:
                cell_w = (W - PAD * 2 - PHOTO_GAP) // photo_cols
                photo_cells = [_fit(im, cell_w, PHOTO_CELL_H) for im in loaded]
                rows = (len(photo_cells) + photo_cols - 1) // photo_cols
                photo_h = rows * PHOTO_CELL_H + (rows - 1) * PHOTO_GAP + 24
        else:
            photo_h = 0

        title_h = 96
        info_h = 6 * 44 + 16          # 6 行信息（已去掉处置时限）
        desc_h = 34 + len(desc_lines) * 32 + 16
        photo_title_h = 34 if photo_cells else 0
        footer_h = 56
        H = title_h + info_h + desc_h + photo_title_h + photo_h + footer_h + PAD

        img = Image.new('RGB', (W, H), 'white')
        draw = ImageDraw.Draw(img)
        # 标题条（派发部门底色）
        draw.rectangle([0, 0, W, title_h], fill=rgb)
        draw.text((PAD, 26), '创文问题处置单', font=f_title, fill='white')
        draw.text((W - PAD - draw.textlength(row['case_no'], font=f_small), 62),
                  row['case_no'], font=f_small, fill='white')

        y = title_h + 18

        def info_line(label, value, x=PAD):
            nonlocal y
            draw.text((x, y), label, font=f_label, fill='#888888')
            draw.text((x + 92, y), str(value or '—'), font=f_value, fill='#222222')
            y += 44

        found_str = row['found_at'].strftime('%Y-%m-%d %H:%M') if row.get('found_at') else '—'
        info_line('案件编号', row['case_no'])
        info_line('监控序号', f"{row.get('monitor_no') or '—'}（{row.get('spot_name') or ''}）")
        info_line('所在路段', row.get('road'))
        info_line('问题类型', row.get('type_name'))
        info_line('发现时间', found_str)
        info_line('派发单位', row.get('dept_name'))

        # 问题描述
        draw.text((PAD, y), '问题描述', font=f_label, fill='#888888')
        y += 34
        for ln in desc_lines:
            draw.text((PAD, y), ln, font=f_value, fill='#222222')
            y += 32
        y += 16

        # 现场照片（全部）
        if photo_cells:
            draw.text((PAD, y), f'现场照片（{len(photo_cells)} 张）', font=f_label, fill='#888888')
            y += 34
            if photo_cols == 1:
                img.paste(photo_cells[0], (PAD, y))
                y += photo_cells[0].height + 24
            else:
                cell_w = (W - PAD * 2 - PHOTO_GAP) // photo_cols
                for idx, cell in enumerate(photo_cells):
                    img.paste(cell, (PAD + (idx % photo_cols) * (cell_w + PHOTO_GAP),
                                     y + (idx // photo_cols) * (PHOTO_CELL_H + PHOTO_GAP)))
                y += photo_h

        # 页脚
        draw.line([PAD, H - footer_h, W - PAD, H - footer_h], fill='#DDDDDD', width=1)
        draw.text((PAD, H - footer_h + 14),
                  f"本单由一站通·创文问题处置模块生成 | 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                  font=f_small, fill='#999999')

        save_name = f"slip_{row['case_no']}.jpg"
        img.save(os.path.join(CYW_SLIP_DIR, save_name), quality=92)
        url = f'/uploads/cyw/slips/{save_name}'
        return jsonify({'success': True, 'url': url, 'case_no': row['case_no']})

    # ---------------------------------------------------------------- 在岗抽查

    def _check_batch_dict(b, items):
        on = sum(1 for i in items if i['status'] == '在岗')
        off = sum(1 for i in items if i['status'] == '不在岗')
        return {
            'id': b[0], 'batch_no': b[1], 'spot_count': b[2], 'status': b[3],
            'created_by': b[4],
            'created_at': b[5].strftime('%Y-%m-%d %H:%M:%S') if b[5] else None,
            'finished_at': b[6].strftime('%Y-%m-%d %H:%M:%S') if b[6] else None,
            'on_count': on, 'off_count': off,
            'wait_count': sum(1 for i in items if i['status'] == '待抽查'),
            'items': items,
        }

    @app.route('/api/cyw/check/start', methods=['POST'])
    @perm_access('cyw_check')
    def cyw_check_start():
        """发起一轮抽查：从全部点位随机抽 5 个，每个点位按规则挑一个联系人。

        只抽管理单位为「城市管理局」的点位：开发区的点位不归本系统考核口径。
        CHECK_POOL_EXCLUDE_NOS 里的监控序号（摄像头不在线）一并排除，不进抽查池。
        未登记联系人的点位照样会抽中，报告里如实记「未登记联系人」而不是悄悄跳过——
        否则抽查覆盖率是假的。
        同一时刻只允许一个进行中的批次：重复点击「抽查」不会叠批次，而是把旧批次里
        还没出结果的明细判掉后重开，避免两份未结批次互相干扰。
        """
        try:
            n = int((request.get_json(silent=True) or {}).get('spot_count') or 5)
        except (TypeError, ValueError):
            n = 5
        n = max(1, min(n, 48))
        with engine.begin() as conn:
            # 先把上一个没结束的批次结掉：其中待抽查且有倒计时的按规则自动判，无倒计时的直接判不在岗
            prev = conn.execute(text(
                "SELECT id FROM cyw_check_batch WHERE status='进行中' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            if prev:
                _sweep_expired_items(conn, prev[0])
                conn.execute(text(
                    "UPDATE cyw_check_item SET status='不在岗', result_at=:ts, result_by='系统自动判定' "
                    "WHERE batch_id=:b AND status='待抽查'"
                ), {'ts': _now(), 'b': prev[0]})
                conn.execute(text(
                    "UPDATE cyw_check_batch SET status='已结束', finished_at=:ts WHERE id=:b"
                ), {'ts': _now(), 'b': prev[0]})

            # 随机抽点位：只抽管理单位为「城市管理局」的——开发区的点位不归本系统考核口径，
            # 且开发区那 6 个未登记联系人的点位正好都在其内，一并排除。
            # 摄像头不在线的 8 个点位（CHECK_POOL_EXCLUDE_NOS）也排除：抽中了核不了岗。
            # RAND() 在几十行的小表上无所谓性能。
            spots = conn.execute(
                text(
                    "SELECT id, monitor_no, name FROM cyw_spot "
                    "WHERE manage_unit = '城市管理局' AND monitor_no NOT IN :nos "
                    "ORDER BY RAND() LIMIT :n"
                ).bindparams(bindparam('nos', expanding=True)),
                {'n': n, 'nos': list(CHECK_POOL_EXCLUDE_NOS)},
            ).fetchall()
            if not spots:
                return jsonify({'error': '没有管理单位为「城市管理局」的点位，无法抽查'}), 400

            # 批次号：当天第几轮
            today = _now().strftime('%Y%m%d')
            seq = conn.execute(text(
                "SELECT COUNT(*) FROM cyw_check_batch WHERE batch_no LIKE :p"
            ), {'p': f'CC{today}-%'}).scalar() or 0
            batch_no = f'CC{today}-{seq + 1:03d}'
            conn.execute(text(
                "INSERT INTO cyw_check_batch (batch_no, spot_count, status, created_by, created_at) "
                "VALUES (:no, :n, '进行中', :u, :ts)"
            ), {'no': batch_no, 'n': len(spots), 'u': _now_user(), 'ts': _now()})
            batch_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            items = []
            for sid, sno, sname in spots:
                rows = conn.execute(text(
                    "SELECT dept_label, person, phone FROM cyw_spot_contact "
                    "WHERE spot_id=:s ORDER BY sort_order, id"
                ), {'s': sid}).fetchall()
                contacts = [{'dept_label': r[0], 'person': r[1], 'phone': r[2]} for r in rows]
                srow = conn.execute(text(
                    "SELECT contact_name, contact_phone FROM cyw_spot WHERE id=:s"
                ), {'s': sid}).fetchone()
                # 一个点位出两条：环卫一条、执法一条（缺人的那侧记「未登记」）
                picks = _pick_contacts_for_check(
                    contacts, (srow[0], srow[1]) if srow else None)
                for p in picks:
                    conn.execute(text(
                        "INSERT INTO cyw_check_item "
                        "(batch_id, spot_id, spot_no, spot_name, dept_label, person, phone, pick_rule, status) "
                        "VALUES (:b, :s, :no, :nm, :dl, :p, :ph, :rule, '待抽查')"
                    ), {'b': batch_id, 's': sid, 'no': sno, 'nm': sname,
                        'dl': p['dept_label'], 'p': p['person'], 'ph': p['phone'],
                        'rule': p['pick_rule']})
            items = _load_batch_items(conn, batch_id)
            b = conn.execute(text(
                "SELECT id, batch_no, spot_count, status, created_by, created_at, finished_at "
                "FROM cyw_check_batch WHERE id=:b"
            ), {'b': batch_id}).fetchone()
        return jsonify({'batch': _check_batch_dict(b, items)})

    @app.route('/api/cyw/check/current', methods=['GET'])
    @perm_access('cyw_check')
    def cyw_check_current():
        """当前进行中的批次。刷新页面/换电脑都靠它恢复现场——权威状态只在数据库里。"""
        with engine.begin() as conn:
            b = conn.execute(text(
                "SELECT id, batch_no, spot_count, status, created_by, created_at, finished_at "
                "FROM cyw_check_batch WHERE status='进行中' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            if not b:
                return jsonify({'batch': None})
            _sweep_expired_items(conn, b[0])
            items = _load_batch_items(conn, b[0])
        return jsonify({'batch': _check_batch_dict(b, items)})

    @app.route('/api/cyw/check/item/<int:item_id>/call', methods=['POST'])
    @perm_access('cyw_check')
    def cyw_check_call(item_id):
        """工作人员打了电话 → 点「电话」：记去电时间，倒计时 5 分钟。

        倒计时截止时间由服务端写死，不是前端算的：前端只拿它显示剩余秒数（纯 UX），
        判定永远以服务端时间为准，避免改本机时钟/跨时区把判定搅乱。
        """
        with engine.begin() as conn:
            _sweep_expired_items(conn)
            # 列序：id, status, called_at, person —— it[2] 必须是 called_at，
            # 少了它会让「是否已在倒计时中」的判断错取到 person
            it = conn.execute(text(
                "SELECT id, status, called_at, person FROM cyw_check_item WHERE id=:i"
            ), {'i': item_id}).fetchone()
            if not it:
                return jsonify({'error': '抽查明细不存在'}), 404
            if not it[3]:
                return jsonify({'error': '该点位未登记联系人，无法电话抽查'}), 400
            if it[1] != '待抽查':
                return jsonify({'error': f'该人员已判定为「{it[1]}」，不能重复去电'}), 400
            if it[2]:
                # called_at 已有值说明倒计时已在走。重复点「去电」会把 5 分钟窗口整个重置，
                # 窗口就能被无限续期，「到点自动判不在岗」永远不触发——必须拦住。
                # 确实需要改判的走「修正」通道（会留痕）。
                return jsonify({'error': '该人员已在倒计时中，不能重复去电；如需改判请用「修正」'}), 400
            now = _now()
            deadline = now + timedelta(minutes=CHECK_WINDOW_MINUTES)
            conn.execute(text(
                "UPDATE cyw_check_item SET called_at=:c, deadline_at=:d WHERE id=:i"
            ), {'c': now, 'd': deadline, 'i': item_id})
        return jsonify({
            'success': True, 'called_at': now.strftime('%Y-%m-%d %H:%M:%S'),
            'deadline_at': deadline.strftime('%Y-%m-%d %H:%M:%S'),
            'window_minutes': CHECK_WINDOW_MINUTES,
        })

    @app.route('/api/cyw/check/item/<int:item_id>/on-duty', methods=['POST'])
    @perm_access('cyw_check')
    def cyw_check_on_duty(item_id):
        """工作人员在监控里看到人 → 点「在岗」。

        倒计时内点击 = 正常判定在岗。
        倒计时已过 = 该行早被兜底扫判成「不在岗」，此时再点按用户说的「管理员有权限
        可以对到岗情况进行修改」处理：允许覆盖，但要求二次确认并写修正留痕。
        """
        with engine.begin() as conn:
            _sweep_expired_items(conn)
            it = conn.execute(text(
                "SELECT id, status, called_at, deadline_at, person FROM cyw_check_item WHERE id=:i"
            ), {'i': item_id}).fetchone()
            if not it:
                return jsonify({'error': '抽查明细不存在'}), 404
            if not it[4]:
                return jsonify({'error': '该点位未登记联系人，无法判定在岗'}), 400
            if it[1] == '在岗':
                return jsonify({'error': '该人员已判定为在岗'}), 400
            now = _now()
            expired = bool(it[3]) and it[3] < now
            if expired:
                return jsonify({
                    'error': '倒计时已结束，该人员已被系统自动判定为「不在岗」。'
                             '如实际情况是在岗，请使用「修正」通道并注明原因。',
                    'need_correct': True,
                }), 409
            conn.execute(text(
                "UPDATE cyw_check_item SET status='在岗', result_at=:t, result_by=:u "
                "WHERE id=:i"
            ), {'t': now, 'u': _now_user(), 'i': item_id})
        return jsonify({'success': True, 'status': '在岗'})

    @app.route('/api/cyw/check/batch/<int:batch_id>/finish', methods=['POST'])
    @perm_access('cyw_check')
    def cyw_check_finish(batch_id):
        """结束抽查：全量兜底扫一遍（没点过电话的也算不在岗），批次置已结束。"""
        with engine.begin() as conn:
            b = conn.execute(text(
                "SELECT id, batch_no, status FROM cyw_check_batch WHERE id=:b"
            ), {'b': batch_id}).fetchone()
            if not b:
                return jsonify({'error': '抽查批次不存在'}), 404
            _sweep_expired_items(conn, batch_id)
            now = _now()
            # 没点过电话（无 called_at）的也算不在岗：抽查是「打了电话才算数」
            conn.execute(text(
                "UPDATE cyw_check_item SET status='不在岗', result_at=:ts, result_by='系统自动判定' "
                "WHERE batch_id=:b AND status='待抽查'"
            ), {'ts': now, 'b': batch_id})
            conn.execute(text(
                "UPDATE cyw_check_batch SET status='已结束', finished_at=:ts WHERE id=:b"
            ), {'ts': now, 'b': batch_id})
            items = _load_batch_items(conn, batch_id)
            b = conn.execute(text(
                "SELECT id, batch_no, spot_count, status, created_by, created_at, finished_at "
                "FROM cyw_check_batch WHERE id=:b"
            ), {'b': batch_id}).fetchone()
        return jsonify({'batch': _check_batch_dict(b, items)})

    @app.route('/api/cyw/check/batch/<int:batch_id>', methods=['GET'])
    @perm_access('cyw_check')
    def cyw_check_batch_detail(batch_id):
        with engine.begin() as conn:
            b = conn.execute(text(
                "SELECT id, batch_no, spot_count, status, created_by, created_at, finished_at "
                "FROM cyw_check_batch WHERE id=:b"
            ), {'b': batch_id}).fetchone()
            if not b:
                return jsonify({'error': '抽查批次不存在'}), 404
            _sweep_expired_items(conn, batch_id)
            items = _load_batch_items(conn, batch_id)
        return jsonify({'batch': _check_batch_dict(b, items)})

    @app.route('/api/cyw/check/item/<int:item_id>/correct', methods=['PUT'])
    @admin_required
    def cyw_check_correct(item_id):
        """管理员修正到岗情况（用户明确要求的权限）。改判定必须留痕：谁、何时、改成什么、为什么。"""
        data = request.get_json(silent=True) or {}
        new_status = (data.get('status') or '').strip()
        if new_status not in ('在岗', '不在岗'):
            return jsonify({'error': '修正结果只能是「在岗」或「不在岗」'}), 400
        with engine.begin() as conn:
            it = conn.execute(text(
                "SELECT id, status, person FROM cyw_check_item WHERE id=:i"
            ), {'i': item_id}).fetchone()
            if not it:
                return jsonify({'error': '抽查明细不存在'}), 404
            if not it[2]:
                return jsonify({'error': '该点位未登记联系人，无需修正'}), 400
            if it[1] == new_status:
                return jsonify({'error': f'该人员当前已是「{new_status}」'}), 400
            now = _now()
            # result_at/result_by 保留「原判定」不覆盖：审计要能看出「系统 15:18 判不在岗，
            # 管理员 15:20 改成在岗」这条链。只有从未判定过的行（无 result_at）才就地补上。
            conn.execute(text(
                "UPDATE cyw_check_item SET status=:s, "
                "result_at = COALESCE(result_at, :t), result_by = COALESCE(result_by, :u), "
                "corrected=1, corrected_by=:u, corrected_at=:t, corrected_reason=:r WHERE id=:i"
            ), {'s': new_status, 't': now, 'u': _now_user(),
                'r': (data.get('reason') or '').strip() or None, 'i': item_id})
        return jsonify({'success': True, 'status': new_status})

    @app.route('/api/cyw/check/batch/<int:batch_id>/export', methods=['GET'])
    @perm_access('cyw_check')
    def cyw_check_export(batch_id):
        """下载抽查报告 txt。格式与数据统计导出一致：BOM + RFC5987 中文文件名。"""
        with engine.begin() as conn:
            b = conn.execute(text(
                "SELECT id, batch_no, spot_count, status, created_by, created_at, finished_at "
                "FROM cyw_check_batch WHERE id=:b"
            ), {'b': batch_id}).fetchone()
            if not b:
                return jsonify({'error': '抽查批次不存在'}), 404
            _sweep_expired_items(conn, batch_id)
            items = _load_batch_items(conn, batch_id)
            batch = _check_batch_dict(b, items)
        content = _check_export_text(batch, items)
        span = batch['created_at'][:10].replace('-', '')
        fname = f'创文在岗抽查报告_{span}.txt'
        ascii_name = f'cyw_check_{span}.txt'
        resp = Response('\ufeff'.encode('utf-8') + content.encode('utf-8'), mimetype='text/plain')
        resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
        resp.headers['Content-Disposition'] = (
            f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(fname)}')
        return resp

    @app.route('/api/cyw/check/history', methods=['GET'])
    @perm_access('cyw_check')
    def cyw_check_history():
        """历史抽查批次列表（分页），供回溯与重新下载报告。"""
        page = max(1, int(request.args.get('page') or 1))
        size = min(100, max(1, int(request.args.get('size') or 20)))
        with engine.begin() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM cyw_check_batch")).scalar() or 0
            rows = conn.execute(text(
                "SELECT b.id, b.batch_no, b.spot_count, b.status, b.created_by, b.created_at, b.finished_at, "
                "(SELECT COUNT(*) FROM cyw_check_item i WHERE i.batch_id=b.id) AS item_cnt, "
                "(SELECT COUNT(*) FROM cyw_check_item i WHERE i.batch_id=b.id AND i.status='在岗') AS on_cnt, "
                "(SELECT COUNT(*) FROM cyw_check_item i WHERE i.batch_id=b.id AND i.status='不在岗') AS off_cnt "
                "FROM cyw_check_batch b ORDER BY b.id DESC LIMIT :l OFFSET :o"
            ), {'l': size, 'o': (page - 1) * size}).fetchall()
            lst = [{
                'id': r[0], 'batch_no': r[1], 'spot_count': r[2], 'status': r[3],
                'created_by': r[4],
                'created_at': r[5].strftime('%Y-%m-%d %H:%M:%S') if r[5] else None,
                'finished_at': r[6].strftime('%Y-%m-%d %H:%M:%S') if r[6] else None,
                'item_cnt': r[7], 'on_cnt': r[8], 'off_cnt': r[9],
            } for r in rows]
        return jsonify({'total': total, 'page': page, 'size': size, 'list': lst})

    # ---------------------------------------------------------------- 日报（按需生成，无定时任务）

    @app.route('/api/cyw/report/daily', methods=['GET'])
    @protected
    def cyw_report_daily():
        """日报/周期统计：新增/已办结/处置中三类数量+明细（方案 6.4）。
        2026-10-16 流程简化后不再有超时口径，「超时未反馈」一栏已下线。
        支持 date_from + date_to 选时间段（连续几天/一周/一月），
        历史区间按末日 24:00 快照口径，不传区间则退化为单日 date 行为。
        """
        try:
            range_start, range_end, is_single, day_text = _resolve_stat_range(request.args)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        with engine.connect() as conn:
            def q(extra_where, params):
                return [dict(r) for r in conn.execute(text(
                    "SELECT i.id, i.case_no, i.found_at, i.status, "
                    "s.name AS spot_name, s.monitor_no, t.name AS type_name "
                    f"FROM cyw_issue i JOIN cyw_spot s ON s.id = i.spot_id "
                    f"JOIN cyw_type t ON t.id = i.type_id WHERE {extra_where} "
                    "ORDER BY i.found_at DESC, i.id DESC"
                ), params).mappings().fetchall()]

            new_issues = q("i.found_at BETWEEN :ds AND :de",
                           {'ds': range_start, 'de': range_end})
            closed_issues = q("i.closed_at BETWEEN :ds AND :de",
                              {'ds': range_start, 'de': range_end})
            doing_issues = q("i.status = '处置中' AND i.found_at <= :de "
                             "AND (i.closed_at IS NULL OR i.closed_at > :de)",
                             {'de': range_end})
            total_open = conn.execute(text(
                "SELECT COUNT(*) FROM cyw_issue WHERE status = '处置中'")).scalar()

        def fmt(rows):
            out = []
            for r in rows:
                r = dict(r)
                r['found_at'] = (r['found_at'].strftime('%H:%M' if is_single else '%m-%d %H:%M')
                                 if r.get('found_at') else None)
                out.append(r)
            return out

        return jsonify({
            'success': True,
            'date': day_text,
            'date_from': range_start.strftime('%Y-%m-%d'),
            'date_to': range_end.strftime('%Y-%m-%d'),
            'is_single': is_single,
            'counts': {
                'new': len(new_issues), 'closed': len(closed_issues),
                'doing': len(doing_issues), 'open_total': total_open,
            },
            'details': {
                'new': fmt(new_issues), 'closed': fmt(closed_issues),
                'doing': fmt(doing_issues),
            },
        })

    # ---------------------------------------------------------------- 数据统计：一键导出 txt

    @app.route('/api/cyw/report/daily/export', methods=['GET'])
    @protected
    def cyw_report_daily_export():
        """把指定日期/时间段的派发处置汇总导成 txt（交接班对账用）。

        格式按用户要求极简：标题 + 统计日期 + 当日概况（共几件/办结几件）
        + 按派发部门汇总。不出案件明细、不出导出时间、不加分隔线和落款。
        单日模式文案与改造前逐字一致（用户已确认终版）；
        时间段模式只把「统计日期/当日概况/当日无派发案件」换成周期口径。
        与 /api/cyw/report/daily 同数据源、同口径。
        文件带 UTF-8 BOM——Windows 记事本靠 BOM 识别中文，否则一片乱码。
        """
        try:
            range_start, range_end, is_single, day_text = _resolve_stat_range(request.args)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        with engine.connect() as conn:
            def cnt(extra_where, params):
                return conn.execute(text(
                    "SELECT COUNT(*) FROM cyw_issue i "
                    f"WHERE {extra_where}"), params).scalar()

            new_cnt = cnt("i.found_at BETWEEN :ds AND :de",
                          {'ds': range_start, 'de': range_end})
            # 按派发部门汇总：只统计本区间新增（派发）的案件
            by_dept = {}
            for dept_name, st in conn.execute(text(
                    "SELECT d.name, i.status FROM cyw_issue i "
                    "JOIN cyw_dept d ON d.id = i.dept_id "
                    "WHERE i.found_at BETWEEN :ds AND :de"),
                    {'ds': range_start, 'de': range_end}):
                d = by_dept.setdefault(dept_name or '未分配',
                                       {'dispatched': 0, 'closed': 0})
                d['dispatched'] += 1
                if st == ST_DONE:
                    d['closed'] += 1
            # 办结数取"本区间派发案件里当前已办结的"，与第二节各部门数字相加一致；
            # 不能用 closed_at 落在区间内的口径——区间内派、区间后结的案子会被漏算
            closed_cnt = sum(d['closed'] for d in by_dept.values())

        L = []
        A = L.append
        A('创文问题处理 · 数据统计')
        if is_single:
            A(f'统计日期：{range_start.strftime("%Y年%m月%d日")}')
            A('【一、当日概况】')
        else:
            A(f'统计周期：{range_start.strftime("%Y年%m月%d日")}'
              f' 至 {range_end.strftime("%Y年%m月%d日")}'
              f'（共{(range_end - range_start).days + 1}天）')
            A('【一、周期概况】')
        A(f'  共{new_cnt}件，办结{closed_cnt}件')
        A('')
        A('【二、按派发部门汇总】')
        if by_dept:
            for name, d in sorted(by_dept.items(), key=lambda kv: -kv[1]['dispatched']):
                A(f'  {name}：派发 {d["dispatched"]} 件，办结 {d["closed"]} 件。')
        elif is_single:
            A('  （当日无派发案件）')
        else:
            A('  （本周期无派发案件）')

        content = '\n'.join(L) + '\n'
        if is_single:
            fname = f'创文数据统计_{day_text.replace("-", "")}.txt'
            ascii_name = f'cyw_stats_{day_text.replace("-", "")}.txt'
        else:
            span = f'{range_start.strftime("%Y%m%d")}-{range_end.strftime("%Y%m%d")}'
            fname = f'创文数据统计_{span}.txt'
            ascii_name = f'cyw_stats_{span}.txt'
        # 显式写 Content-Type：Flask 看到 text/ 会自动再补一个 charset，不覆盖会变成两份
        resp = Response('\ufeff'.encode('utf-8') + content.encode('utf-8'), mimetype='text/plain')
        resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
        resp.headers['Content-Disposition'] = (
            f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(fname)}')
        return resp

    # ---------------------------------------------------------------- 数据分析（只读聚合）

    @app.route('/api/cyw/report/analysis', methods=['GET'])
    @perm_access('cyw_analysis')
    def cyw_report_analysis():
        """数据分析：高发点位/高发问题/点位×问题交叉榜 + 按天趋势（方案 2026-10-23）。

        与 /api/cyw/report/daily 同口径——「高发」按 found_at 落在统计区间内计数，
        不发明新口径；办结数取该区间新增案件里当前已办结的（与数据统计第二节相加一致）。
        纯 SELECT 只读，不写库不建表；数据量在万件级以内实时聚合足够快。
        支持 dimension 参数换维度（spot/road/dept）看同一张榜，交叉榜固定点位×类型。
        """
        try:
            range_start, range_end, is_single, day_text = _resolve_stat_range(request.args)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        dimension = (request.args.get('dimension') or 'spot').strip()
        if dimension not in ('spot', 'road', 'dept'):
            return jsonify({'success': False, 'error': 'dimension 仅支持 spot/road/dept'}), 400

        # 每个维度一套 label 表达式与关联表：label 为展示名，join 为取 label 的 SQL 片段。
        # road 维度：道路为空时打「未填路段」——库里 road 列确实有空值，不能让它从榜上消失。
        # dept 维度：案件必然带 dept_id（建表 NOT NULL），「未分配部门」只为字典行被删后的兜底。
        DIM = {
            'spot': ("COALESCE(NULLIF(s.name, ''), '未命名点位')", "cyw_spot s ON s.id = i.spot_id"),
            'road': ("COALESCE(NULLIF(s.road, ''), '未填路段')", "cyw_spot s ON s.id = i.spot_id"),
            'dept': ("COALESCE(NULLIF(d.name, ''), '未分配部门')", "cyw_dept d ON d.id = i.dept_id"),
        }
        label_expr, join_sql = DIM[dimension]

        # 只读聚合 SQL 模板：label/join 来自上面的白名单字典，时间参数一律走绑定，无外部字符串拼接
        RANK_SQL = (
            f"SELECT {label_expr} AS label, COUNT(*) AS total, "
            f"SUM(CASE WHEN i.status = '{ST_DONE}' THEN 1 ELSE 0 END) AS closed "
            f"FROM cyw_issue i JOIN {join_sql} "
            "WHERE i.found_at BETWEEN :ds AND :de "
            "GROUP BY label ORDER BY total DESC, label LIMIT 10"
        )

        with engine.connect() as conn:
            # 主榜：随 dimension 切换（点位/路段/部门）
            ranking = [dict(r) for r in conn.execute(text(RANK_SQL),
                       {'ds': range_start, 'de': range_end}).mappings().fetchall()]
            # 高发问题榜：固定按问题类型，不随 dimension 变——它是独立的一张榜
            by_type = [dict(r) for r in conn.execute(text(
                "SELECT COALESCE(NULLIF(t.name, ''), '未分类') AS label, COUNT(*) AS total, "
                f"SUM(CASE WHEN i.status = '{ST_DONE}' THEN 1 ELSE 0 END) AS closed "
                "FROM cyw_issue i JOIN cyw_type t ON t.id = i.type_id "
                "WHERE i.found_at BETWEEN :ds AND :de "
                "GROUP BY label ORDER BY total DESC, label LIMIT 10"
            ), {'ds': range_start, 'de': range_end}).mappings().fetchall()]
            # 交叉榜：点位 × 问题类型，最 actionable——直接说明「该去哪个点位重点管哪类问题」
            cross = [dict(r) for r in conn.execute(text(
                "SELECT s.name AS spot_name, s.monitor_no, s.road AS spot_road, "
                "t.name AS type_name, COUNT(*) AS total, "
                f"SUM(CASE WHEN i.status = '{ST_DONE}' THEN 1 ELSE 0 END) AS closed "
                "FROM cyw_issue i JOIN cyw_spot s ON s.id = i.spot_id "
                "JOIN cyw_type t ON t.id = i.type_id "
                "WHERE i.found_at BETWEEN :ds AND :de "
                "GROUP BY s.id, t.id ORDER BY total DESC, s.name, t.name LIMIT 10"
            ), {'ds': range_start, 'de': range_end}).mappings().fetchall()]
            # 按天趋势：区间内逐日新增/办结。存量曲线由前端按累计差自行算，不在这里拼
            trend = [dict(r) for r in conn.execute(text(
                "SELECT DATE(i.found_at) AS day, COUNT(*) AS total, "
                f"SUM(CASE WHEN i.status = '{ST_DONE}' THEN 1 ELSE 0 END) AS closed "
                "FROM cyw_issue i WHERE i.found_at BETWEEN :ds AND :de "
                "GROUP BY day ORDER BY day"
            ), {'ds': range_start, 'de': range_end}).mappings().fetchall()]
            # 占比分母一律取区间案件总数：road/dept 维度下按行汇总会与总数不一致
            # （spot 维度每案只归一格所以恰好相等），用总数口径三个维度才可比
            grand_total = conn.execute(text(
                "SELECT COUNT(*) FROM cyw_issue WHERE found_at BETWEEN :ds AND :de"),
                {'ds': range_start, 'de': range_end}).scalar() or 0

        def decorate(rows):
            out = []
            for r in rows:
                total = int(r['total'] or 0)
                closed = int(r['closed'] or 0)
                out.append({
                    'label': r.get('label'),
                    'spot_name': r.get('spot_name'),
                    'monitor_no': r.get('monitor_no'),
                    'spot_road': r.get('spot_road'),
                    'type_name': r.get('type_name'),
                    'total': total,
                    'closed': closed,
                    'doing': total - closed,
                    'ratio': round(total / grand_total * 100, 1) if grand_total else 0.0,
                })
            return out

        return jsonify({
            'success': True,
            'date': day_text,
            'date_from': range_start.strftime('%Y-%m-%d'),
            'date_to': range_end.strftime('%Y-%m-%d'),
            'is_single': is_single,
            'dimension': dimension,
            'grand_total': grand_total,
            'ranking': decorate(ranking),
            'by_type': decorate(by_type),
            'cross': decorate(cross),
            'trend': [{'day': str(r['day']), 'total': int(r['total'] or 0),
                       'closed': int(r['closed'] or 0)} for r in trend],
        })

    return {
        'ensure_tables': ensure_cyw_tables,
    }
