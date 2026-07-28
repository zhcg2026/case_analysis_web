"""
kb_verify.py —— 灌库后检索层验证（阶段0）
========================================
只验证语义召回（不依赖 LLM）：
  python kb_verify.py
重点验证：
  1) 同义/换说法召回：路灯不亮 / 照明设施坏了 / 灯杆灭了 是否都能命中同一条标准
  2) 法律状态过滤：废止/已修改法规默认不应以"现行有效"身份出现在普通检索
  3) 12345 问答召回
"""
import sys
import logging

from dotenv import load_dotenv
load_dotenv()

import kb_store

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [verify] %(levelname)s %(message)s")
log = logging.getLogger("verify")


def show(title, hits):
    print(f"\n===== {title} =====")
    if not hits:
        print("  (无召回)")
        return
    for i, h in enumerate(hits, 1):
        print(f"  {i}. [{h['doc_type']}] score={h['score']:.3f} "
              f"status={h['law_status'] or '-'} title={h['title']}")
        print(f"     text: {h['text'][:60]}...")


def main():
    # 1) 换说法召回（核心：证明不用同义词也能泛化）
    for q in ["路灯不亮归哪个部门管", "照明设施坏了找谁", "灯杆灭了怎么报修"]:
        show(f"语义召回：{q}", kb_store.search(q, top_k=3))

    # 2) 仅标准类
    show("仅 standard 类：违停怎么处理",
         kb_store.search("机动车违停怎么处理", top_k=3, doc_type="standard"))

    # 3) 法律默认排除废止（include_invalid_laws=False 应为默认）
    show("法律检索(默认排除废止)：施工围挡有什么规定",
         kb_store.search("施工围挡有什么规定", top_k=5))
    show("法律检索(含废止)：施工围挡有什么规定",
         kb_store.search("施工围挡有什么规定", top_k=5, include_invalid_laws=True))

    # 4) 12345 问答
    show("12345 问答召回：暖气不热怎么办",
         kb_store.search("暖气不热怎么办", top_k=3, doc_type="qa"))

    # 5) 职责类
    show("职责召回：市容环卫中心管什么",
         kb_store.search("市容环卫中心负责什么", top_k=3, doc_type="org"))


if __name__ == "__main__":
    main()
