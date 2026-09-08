# -*- coding: utf-8 -*-
"""LLM 润色模块：将规则引擎的结构化发现转化为公文风格的第7、8章文字
依赖：requests（已在 requirements.txt）
"""
import logging
import os
import re
import requests

logger = logging.getLogger(__name__)

API_KEY = os.getenv('DOUBAO_API_KEY', '')
API_URL = os.getenv('DOUBAO_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
MODEL = os.getenv('DOUBAO_MODEL', 'deepseek-v4-flash-ga-260731')


def build_prompt(findings, key_metrics, month='2026年8月'):
    """构建 LLM prompt"""
    findings_text = '\n'.join(
        f"- [{f['category']}] {f['detail']}" for f in findings
    )
    metrics_text = ', '.join(f'{k}={v}' for k, v in key_metrics.items() if v is not None)

    return f"""你是城市管理案件分析报告的撰写助手。请根据以下数据发现，撰写月度分析报告的两个章节。

## 数据发现（由规则引擎从{month}案件数据中提取）
{findings_text}

## 关键指标
{metrics_text}

## 输出要求

### 第七章 数据特征归纳
总结本月数据的3-5个核心特征，每个特征用"一是""二是"等序数词引导，每段2-3句。
- 数字必须与上方数据完全一致，不要自行计算任何百分比或倍数
- 分析数据之间的关联（如超时集中在某部门→可能的原因）
- 指出值得关注的趋势或异常

### 第八章 工作建议
针对每个数据发现提出一条具体建议，用"一是""二是"等序数词引导，每段2-3句。
- 每条建议必须对应一个具体的数据发现，不要遗漏
- 建议要具体可操作，不要泛泛而谈
- 使用政务公文风格

### 格式要求
- 第七章和第八章之间用空行分隔
- 每段之间空一行
- 不要加章节标题（标题由系统生成）
- 不要输出markdown格式"""


def call_llm(prompt):
    """调用豆包 API，返回生成文本"""
    if not API_KEY:
        raise RuntimeError('DOUBAO_API_KEY 未配置')

    resp = requests.post(
        API_URL,
        headers={
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'model': MODEL,
            'messages': [
                {'role': 'system', 'content': '你是城市管理案件分析报告的撰写助手，擅长政务公文写作。'
                                              '严格使用提供的数据数字，不要自行计算百分比或倍数。'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 2000
        },
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content']


def split_chapters(text):
    """将 LLM 输出拆分为第7章和第8章
    按"针对...""一是...建议"等建议段落起始标记拆分
    """
    # 策略1：按"第八章""工作建议"等明确标题拆分
    for marker in ['第八章', '八、工作建议', '九、工作建议', '工作建议']:
        idx = text.find(marker)
        if idx > 50:  # 至少50字符才算有效拆分
            ch7 = text[:idx].strip()
            ch8 = text[idx + len(marker):].lstrip('：: \n').strip()
            return _clean_ch7(ch7), _clean_ch8(ch8)

    # 策略2：按"针对上述""提出以下"等过渡句拆分
    for marker in ['针对上述数据特征', '针对上述分析', '提出以下']:
        idx = text.find(marker)
        if idx > 50:
            ch7 = text[:idx].strip()
            ch8 = text[idx:].strip()
            return _clean_ch7(ch7), _clean_ch8(ch8)

    # 策略3：找第一个"一是针对"——建议段落的起始（不限长度）
    m = re.search(r'一是针对', text)
    if m and m.start() > 50:
        ch7 = text[:m.start()].strip()
        ch8 = text[m.start():].strip()
        return _clean_ch7(ch7), _clean_ch8(ch8)

    # 兜底：整段作为第7章
    return _clean_ch7(text.strip()), ''


def _clean_ch7(ch7):
    """清理第7章开头可能残留的标题文字（含markdown格式）"""
    ch7 = re.sub(r'^#+\s*', '', ch7)
    for prefix in ['第七章 数据特征归纳', '七、数据特征归纳', '第七章', '数据特征归纳']:
        if ch7.startswith(prefix):
            ch7 = ch7[len(prefix):].lstrip('：: \n')
    return ch7.strip()


def _clean_ch8(ch8):
    """清理第8章开头可能残留的标题文字（含markdown格式）"""
    ch8 = re.sub(r'^#+\s*', '', ch8)
    for prefix in ['第八章 工作建议', '八、工作建议', '第九章 工作建议', '九、工作建议', '第八章', '工作建议']:
        if ch8.startswith(prefix):
            ch8 = ch8[len(prefix):].lstrip('：: \n')
    return ch8.strip()


def generate_ai_chapters(analysis_json_path, month='2026年8月'):
    """主入口：提取发现 → 调 LLM → 返回 {chapter7, chapter8}
    LLM 不可用时 fallback 到规则引擎 bullets
    """
    from backend.monthly_report.findings_extractor import extract_findings, extract_key_metrics
    import json

    with open(analysis_json_path, encoding='utf-8') as f:
        d = json.load(f)

    findings = extract_findings(analysis_json_path)
    key_metrics = extract_key_metrics(d)

    prompt = build_prompt(findings, key_metrics, month)

    try:
        raw = call_llm(prompt)
        logger.info('LLM 输出长度: %d 字符', len(raw))
    except Exception as e:
        logger.warning('LLM 调用失败，fallback 到 bullets: %s', e)
        ch7 = '\n\n'.join(f['detail'] for f in findings)
        return {'chapter7': ch7, 'chapter8': '', 'source': 'fallback'}

    ch7, ch8 = split_chapters(raw)
    return {'chapter7': ch7, 'chapter8': ch8, 'source': 'llm'}
