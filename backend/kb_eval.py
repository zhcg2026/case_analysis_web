# -*- coding: utf-8 -*-
"""知识库问答评估脚本（在服务器容器内执行，不写业务库）

用法：
    # 1. 上传到容器（宿主机执行）
    docker cp backend/kb_eval.py case-analysis-web:/app/backend/kb_eval.py

    # 2. 容器内执行
    docker exec case-analysis-web python kb_eval.py              # 检索 + 问答全评
    docker exec case-analysis-web python kb_eval.py --search     # 只评检索（不调 LLM，秒回）
    docker exec case-analysis-web python kb_eval.py --ask 6      # 只评前 6 条问答
    docker exec case-analysis-web python kb_eval.py --json       # 机器可读输出（回归对比用）

评估集是人工维护的代表性问题：覆盖 5 类文档，含易错字序（"公交站台"vs库内
"公交站亭"）、别名（"小蓝车"vs"非机动车"）、民生直答（12345 问答）等真实难点。

检索评估：kb_store.search() 的 top_k 内是否出现期望 doc_type / 期望标题关键词。
问答评估：kb_store.ask() 是否输出结构化 JSON、引用标题是否真实存在于召回中、
          是否降级（degraded / LLM 误报暂无被兜底）、耗时。
误拒闸门回归（REFUSAL_SET）：LLM 说"暂无"时，闸门必须能区分"误拒"（库里有，
          放行倒出带框定语的 qa 原文）与"正确拒绝"（库里确实没有，如"银龙水务"，
          必须诚实拒答）。两类都不允许出现无框定的片段原文堆砌。
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import kb_store  # noqa: E402

# (问题, 期望doc_type或None, 期望标题关键词或None, 备注)
EVAL_SET = [
    ("井盖破损多久能处理完", "standard", "井盖", "立结案标准-时限"),
    ("公交站台破损归哪个部门", "standard", "公交站亭", "字序陷阱：用户说站台，库内写站亭"),
    ("小蓝车乱停放归谁管", "standard", "非机动车", "别名：小蓝车=共享单车=非机动车"),
    ("露天烧烤怎么处罚", "standard", "烧烤", "市容环境高频"),
    ("道路积雪积冰多长时间内清理完", "standard", "积雪", "突发事件类"),
    ("违规养犬怎么处理", "standard", "养犬", "市容环境"),
    ("暖气报停怎么办理", "qa", "报停", "12345民生直答"),
    ("在哪里交水费", "qa", None, "民生直答，历史上LLM误报'暂无'的case"),
    ("噪声污染投诉电话是多少", "qa", None, "民生直答"),
    ("市政公用服务中心是干什么的", "org", "市政公用", "职责机构"),
    ("城市精细化管理考核办法内容", "general", "考核", "制度汇编"),
    ("河道违建如何认定处理", "standard", "违建", "市容环境"),
    ("便民服务摊点怎么申请", "standard", "摊点", "街面秩序"),
    ("路灯不亮找谁维修", "standard", "路灯", "公用设施"),
    ("共享单车乱停放占盲道", "law", None, "法规兜底类，检索到法条即可"),
]

# 误拒闸门回归集：(问题, 期望行为, 备注)
#   refuse   —— 知识库确实没有该实体，必须诚实拒答：不得出现任何片段原文直出
#   fallback —— 库里有直答但 LLM 可能误拒：正常作答，或走带框定语的 qa 原文兜底
REFUSAL_SET = [
    ("有银龙水务的电话吗", "refuse", "全库0处银龙——正确拒绝，不得倒出首创水费/供热电话原文"),
    ("解放南路是路灯所管辖范围吗", "refuse", "命中无解放南路——保留拒答"),
    ("在哪里交水费", "fallback", "P0案例：158/159正文含水费——LLM若误拒，闸门应放行倒qa原文"),
    ("首创水务服务电话", "fallback", "命中正文含首创水务——放行"),
]


def _dump_kind(answer: str):
    """识别答案是否片段原文直出：框定兜底(qa_framed/degraded_framed)/
    无框定堆砌(raw)/正常作答(None)。先判降级路径的"原文片段供参考"
    （其前缀同时含 reason 词，避免被误分类成 qa_framed）。"""
    if not answer:
        return None
    looks_dump = ("【12345问答" in answer or "【12345知识问答" in answer
                  or answer.startswith("（已检索到"))
    if not looks_dump:
        return None
    if "原文片段供参考" in answer:
        return "degraded_framed"
    if "大模型未能给出综合回答" in answer:
        return "qa_framed"
    return "raw"


def eval_refusal_gate(queries):
    rows = []
    for q, expect, note in queries:
        t0 = time.perf_counter()
        try:
            r = kb_store.ask(q)
        except Exception as e:
            rows.append({"q": q, "expect": expect, "note": note, "error": str(e)})
            continue
        ms = int((time.perf_counter() - t0) * 1000)
        kind = _dump_kind(r.get("answer") or "")
        if expect == "refuse":
            ok = kind is None
        else:  # fallback：正常作答或带框定语的原文兜底都算通过
            ok = kind in (None, "qa_framed", "degraded_framed")
        rows.append({
            "q": q, "expect": expect, "note": note, "ms": ms,
            "dump_kind": kind, "degraded": bool(r.get("degraded")),
            "pass": ok,
            "answer_preview": (r.get("answer") or "")[:60].replace("\n", " "),
        })
    return rows


def eval_search(queries):
    rows = []
    for q, want_type, want_kw, note in queries:
        t0 = time.perf_counter()
        try:
            hits = kb_store.search(q, top_k=6)
        except Exception as e:
            rows.append({"q": q, "note": note, "error": str(e)})
            continue
        ms = int((time.perf_counter() - t0) * 1000)
        types = [h.get("doc_type") for h in hits]
        titles = [h.get("title") or "" for h in hits]
        type_hit = (want_type in types) if want_type else None
        kw_hit = any(want_kw in t for t in titles) if want_kw else None
        rows.append({
            "q": q, "note": note, "ms": ms, "n": len(hits),
            "type_hit": type_hit, "kw_hit": kw_hit,
            "top3": [f"{h.get('doc_type')}|{(h.get('title') or '')[:24]}" for h in hits[:3]],
            "sim_top1": hits[0].get("similarity") if hits else None,
        })
    return rows


def eval_ask(queries):
    rows = []
    for q, want_type, want_kw, note in queries:
        t0 = time.perf_counter()
        try:
            r = kb_store.ask(q)
        except Exception as e:
            rows.append({"q": q, "note": note, "error": str(e)})
            continue
        ms = int((time.perf_counter() - t0) * 1000)
        retrieved_titles = {h.get("title") for h in (r.get("retrieved") or [])}
        cites = r.get("citations") or []
        bad_cites = [c.get("title") for c in cites
                     if c.get("title") and c.get("title") not in retrieved_titles]
        rows.append({
            "q": q, "note": note, "ms": ms,
            "hits": len(r.get("retrieved") or []),
            "degraded": bool(r.get("degraded")),
            "need_location": bool(r.get("need_location")),
            "answer_len": len(r.get("answer") or ""),
            "n_cites": len(cites),
            "bad_cites": bad_cites,
            "answer_preview": (r.get("answer") or "")[:60].replace("\n", " "),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", action="store_true", help="只评检索")
    ap.add_argument("--ask", type=int, metavar="N", help="只评前 N 条问答（默认全评时取前6）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    out = {"eval_set_size": len(EVAL_SET)}
    only_ask = args.ask is not None

    if not only_ask:
        srows = eval_search(EVAL_SET)
        checked = [r for r in srows if r.get("type_hit") is not None]
        out["search"] = srows
        out["search_type_hit_rate"] = (
            sum(1 for r in checked if r["type_hit"]) / len(checked) if checked else None)

    if not args.search:
        n = args.ask if only_ask else min(6, len(EVAL_SET))
        arows = eval_ask(EVAL_SET[:n])
        ok = [r for r in arows if "error" not in r]
        out["ask"] = arows
        out["ask_n"] = len(arows)
        out["ask_degraded_rate"] = (sum(1 for r in ok if r["degraded"]) / len(ok)) if ok else None
        out["ask_bad_citations"] = sum(len(r.get("bad_cites") or []) for r in ok)

        rrows = eval_refusal_gate(REFUSAL_SET)
        out["refusal_gate"] = rrows
        rok = [r for r in rrows if "error" not in r]
        out["refusal_gate_pass_rate"] = (
            sum(1 for r in rok if r["pass"]) / len(rok)) if rok else None

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return

    print("=" * 72)
    if "search" in out:
        print(f"== 检索评估（top_k=6，期望类型命中率 "
              f"{out['search_type_hit_rate'] * 100:.0f}%）==")
        for r in out["search"]:
            if "error" in r:
                print(f"  [ERR] {r['q']}: {r['error']}")
                continue
            th = "-" if r["type_hit"] is None else ("OK" if r["type_hit"] else "MISS")
            kh = "-" if r["kw_hit"] is None else ("OK" if r["kw_hit"] else "MISS")
            print(f"  类型{th:>4} 关键词{kh:>4} {r['ms']:>5}ms n={r['n']} | {r['q']}")
            print(f"        top3: {' ; '.join(r['top3'])}")
            if r["note"]:
                print(f"        备注: {r['note']}")
    if "ask" in out:
        print(f"== 问答评估（前 {out['ask_n']} 条，降级率 "
              f"{(out['ask_degraded_rate'] or 0) * 100:.0f}%，幻觉引用 "
              f"{out['ask_bad_citations']} 处）==")
        for r in out["ask"]:
            if "error" in r:
                print(f"  [ERR] {r['q']}: {r['error']}")
                continue
            flag = "降级" if r["degraded"] else ("待定位" if r["need_location"] else "正常")
            print(f"  {flag} {r['ms']:>6}ms 命中{r['hits']:>2} 引用{r['n_cites']} | {r['q']}")
            print(f"        答复: {r['answer_preview']}…")
            if r["bad_cites"]:
                print(f"        !! 引用标题不在召回中: {r['bad_cites']}")
    if "refusal_gate" in out:
        print(f"== 误拒闸门回归（通过率 "
              f"{(out['refusal_gate_pass_rate'] or 0) * 100:.0f}%）==")
        for r in out["refusal_gate"]:
            if "error" in r:
                print(f"  [ERR] {r['q']}: {r['error']}")
                continue
            flag = "PASS" if r["pass"] else "FAIL"
            print(f"  [{flag}] 期望{r['expect']:>8} 实出:{str(r['dump_kind']):>14} "
                  f"{r['ms']:>6}ms | {r['q']}")
            print(f"        答复: {r['answer_preview']}…")
            if not r["pass"]:
                print(f"        !! 备注: {r['note']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
