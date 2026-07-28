"""
统一 embedding 封装（知识库重构核心）
------------------------------------------------
- 本地模式（USE_LOCAL_MODE=true）：用 sentence-transformers 的 MiniLM 本地模型。
  关键修复：把 max_seq_length 从默认的 256 放大到 512，否则立结案标准/法律条文
  这种超过 256 token 的文本只会被截断到开头，embedding 丢失后半段（责任主体/法条内容），
  召回质量骤降。512 能覆盖绝大多数单条标准与单条法规。
- 非本地模式：回退到 kb_common.get_embedding（原 Ollama jina 路径）。

kb_index（灌库）与 kb_store（查询）必须都 import 本模块的 embed()，
才能保证两端向量空间完全一致。
"""
import logging

from kb_common import USE_LOCAL_MODE, get_local_embed_model, get_embedding

logger = logging.getLogger("kb_embed")


def embed(text: str, max_seq_length: int = 512):
    """返回文本的向量（list[float]）；失败返回 None。"""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None

    if USE_LOCAL_MODE:
        model = get_local_embed_model()
        if model is None:
            logger.error("[kb_embed] 本地 embedding 模型未加载（sentence-transformers 未安装或模型下载失败）")
            return None
        # 幂等放大上下文长度（默认 256 太短，会截断长标准/长法条）
        try:
            if getattr(model, "max_seq_length", 0) != max_seq_length:
                model.max_seq_length = max_seq_length
        except Exception:
            pass
        try:
            vec = model.encode(text, convert_to_numpy=True)
            return vec.tolist()
        except Exception as e:
            logger.error(f"[kb_embed] 本地 embedding 失败: {e}")
            return None

    # 非本地模式：沿用原 Ollama / 云端 embedding 路径
    return get_embedding(text)
