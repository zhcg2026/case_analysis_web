# -*- coding: utf-8 -*-
"""
统一知识库路由（阶段0 重写）
================================
路由路径沿用原 /api/kb/*（app.py 已注册 register_kb_routes），但内部实现换成
真实的统一检索/问答（kb_store）与索引（kb_index）模块：

  POST /api/kb/ask      -> kb_store.ask   （纯语义召回 + LLM 强约束 + citations + 派单）
  POST /api/kb/search   -> kb_store.search （纯语义召回，调试/前端候选）
  GET  /api/kb/stats    -> 集合统计（总数 + 各 doc_type 分布 + 法律状态分布）

建库（灌库）动作由脚本 `python kb_index.py --reset` 执行，不暴露为 Web 接口，
避免 Flask 请求超时与并发写库冲突。
"""
import os
from dotenv import load_dotenv
from flask import request, jsonify

# 确保 kb_common 读取 USE_LOCAL_MODE 等时使用正确的 .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

UNIFIED_COLLECTION = "unified_kb"
DOC_TYPES = ["standard", "org", "qa", "general", "law"]


def register_kb_routes(app, protected=None, admin_required=None):
    """注册统一知识库相关路由（真实实现）。"""
    # protected / admin_required 由 app.py 注入；缺省时退化为无鉴权（便于本地调试）
    def _protected(fn):
        return (protected or (lambda f: f))(fn)

    def _admin(fn):
        # 优先用管理员鉴权；未注入 admin_required 时退化为普通鉴权
        return (admin_required or protected or (lambda f: f))(fn)

    @app.route('/api/kb/ask', methods=['POST'])
    @_protected
    def kb_unified_ask():
        """统一知识库问答：语义召回 + LLM 强约束 + 引用溯源 + 地理派单"""
        try:
            from kb_store import ask as _ask
            data = request.get_json(force=True, silent=True) or {}
            question = (data.get('question') or '').strip()
            location = data.get('location')
            top_k = int(data.get('top_k', 6))

            if not question:
                return jsonify({'error': '请提供问题'}), 400

            result = _ask(question, location=location, top_k=top_k)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/search', methods=['POST'])
    @_protected
    def kb_unified_search():
        """统一知识库语义检索（不含 LLM 生成）"""
        try:
            from kb_store import search as _search
            data = request.get_json(force=True, silent=True) or {}
            query = (data.get('query') or '').strip()
            doc_type = data.get('doc_type') or None
            top_k = int(data.get('top_k', 10))

            if not query:
                return jsonify({'error': '请提供搜索内容'}), 400

            results = _search(query, top_k=top_k, doc_type=doc_type)
            return jsonify({'results': results, 'total': len(results)}), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/stats', methods=['GET'])
    @_protected
    def kb_unified_stats():
        """集合统计：总数 + 各 doc_type 分布 + 法律状态分布"""
        try:
            from pymilvus import MilvusClient
            from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT
            client = MilvusClient(LOCAL_MILVUS_FILE) if USE_LOCAL_MODE \
                else MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

            if not client.has_collection(UNIFIED_COLLECTION):
                return jsonify({"exists": False, "total": 0, "by_type": {}, "by_law_status": {}}), 200

            # Milvus Lite 在独立进程/重启后集合处于 released 状态，查询前必须先 load 到内存
            try:
                client.load_collection(UNIFIED_COLLECTION)
            except Exception:
                pass

            rows = client.query(
                UNIFIED_COLLECTION,
                filter="",
                output_fields=["doc_type", "law_status"],
                limit=20000,
            )
            by_type = {t: 0 for t in DOC_TYPES}
            by_law_status = {}
            for r in rows:
                t = r.get("doc_type") or "unknown"
                by_type[t] = by_type.get(t, 0) + 1
                ls = r.get("law_status") or "(空)"
                by_law_status[ls] = by_law_status.get(ls, 0) + 1

            total = client.get_collection_stats(UNIFIED_COLLECTION).get("row_count", len(rows))
            return jsonify({
                "exists": True,
                "total": total,
                "by_type": by_type,
                "by_law_status": by_law_status,
            }), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # ================= 管理端接口（系统管理 - 知识库管理，对齐统一库 unified_kb） =================
    # 重建索引任务状态保存在进程内存（单进程 Flask，够用）；后台线程执行，前端轮询进度。
    _rebuild_tasks = {}

    @app.route('/api/kb/admin/overview', methods=['GET'])
    @_admin
    def kb_admin_overview():
        """管理概览：复用 /stats 的计数 + 数据源信息"""
        try:
            from pymilvus import MilvusClient
            from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT
            from kb_index import KB_SOURCE_DIR, DIR_DOC_TYPE, UNIFIED_COLLECTION
            import os
            client = MilvusClient(LOCAL_MILVUS_FILE) if USE_LOCAL_MODE \
                else MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

            by_type = {t: 0 for t in DOC_TYPES}
            total = 0
            exists = client.has_collection(UNIFIED_COLLECTION)
            if exists:
                try:
                    client.load_collection(UNIFIED_COLLECTION)
                except Exception:
                    pass
                rows = client.query(UNIFIED_COLLECTION, filter="",
                                    output_fields=["doc_type"], limit=20000)
                for r in rows:
                    t = r.get("doc_type") or "unknown"
                    by_type[t] = by_type.get(t, 0) + 1
                total = client.get_collection_stats(UNIFIED_COLLECTION).get("row_count", len(rows))

            # 数据源：各子目录文件数
            source_dir = KB_SOURCE_DIR
            source_info = {"dir": source_dir, "exists": os.path.isdir(source_dir), "subdirs": {}}
            for sub, dt in DIR_DOC_TYPE.items():
                d = os.path.join(source_dir, sub)
                cnt = 0
                if os.path.isdir(d):
                    for root, _, files in os.walk(d):
                        cnt += len([f for f in files if f not in {"laws_corpus.jsonl", "法规采集清单.csv", "build_jsonl.py"}])
                source_info["subdirs"][sub] = {"doc_type": dt, "files": cnt}

            return jsonify({
                "exists": exists,
                "total": total,
                "by_type": by_type,
                "source": source_info,
            }), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/admin/rebuild', methods=['POST'])
    @_admin
    def kb_admin_rebuild():
        """触发全量重建索引（替代旧 zip 批量上传死代码）。后台线程执行，返回 task_id 供轮询。"""
        import threading, uuid
        try:
            from kb_index import rebuild_index
            task_id = uuid.uuid4().hex[:12]
            _rebuild_tasks[task_id] = {"stage": "pending", "done": 0, "total": 0,
                                       "message": "任务已创建，等待启动…", "status": "running"}

            def _run():
                try:
                    def cb(phase, done, total, msg):
                        _rebuild_tasks[task_id].update(
                            stage=phase, done=done, total=total, message=msg, status="running")
                    res = rebuild_index(reset=True, progress_cb=cb)
                    _rebuild_tasks[task_id].update(
                        stage="done", done=res["added"], total=res["added"],
                        message=f"重建完成，本次新增 {res['added']} 条", status="success")
                except Exception as e:
                    _rebuild_tasks[task_id].update(
                        stage="error", status="error", message=f"重建失败：{e}")

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            return jsonify({"task_id": task_id, "status": "running"}), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/admin/rebuild/<task_id>', methods=['GET'])
    @_admin
    def kb_admin_rebuild_progress(task_id):
        """查询重建进度"""
        task = _rebuild_tasks.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在或已过期"}), 404
        return jsonify(task), 200

    @app.route('/api/kb/admin/documents', methods=['GET'])
    @_admin
    def kb_admin_documents():
        """文档列表：按 doc_type / 关键词过滤，分页。返回 distinct doc_id 列表（含块数、标题、来源）。"""
        try:
            from pymilvus import MilvusClient
            from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT
            client = MilvusClient(LOCAL_MILVUS_FILE) if USE_LOCAL_MODE \
                else MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

            doc_type = request.args.get('doc_type') or None
            keyword = (request.args.get('keyword') or '').strip()
            page = max(1, int(request.args.get('page', 1)))
            page_size = min(200, int(request.args.get('page_size', 50)))

            if not client.has_collection(UNIFIED_COLLECTION):
                return jsonify({"items": [], "total": 0, "page": page, "page_size": page_size}), 200

            try:
                client.load_collection(UNIFIED_COLLECTION)
            except Exception:
                pass

            # 拉全量（库仅 6k+ 条，安全），按 doc_id 聚合
            rows = client.query(UNIFIED_COLLECTION, filter="",
                                output_fields=["doc_id", "title", "doc_type", "source"], limit=20000)
            docs = {}
            for r in rows:
                did = r.get("doc_id") or ""
                if did not in docs:
                    docs[did] = {
                        "doc_id": did,
                        "title": r.get("title") or did,
                        "doc_type": r.get("doc_type") or "",
                        "source": r.get("source") or "",
                        "chunks": 0,
                    }
                docs[did]["chunks"] += 1

            items = list(docs.values())
            if doc_type:
                items = [d for d in items if d["doc_type"] == doc_type]
            if keyword:
                kw = keyword.lower()
                items = [d for d in items
                         if kw in (d["title"] or "").lower() or kw in (d["source"] or "").lower()
                         or kw in (d["doc_id"] or "").lower()]

            total = len(items)
            items.sort(key=lambda d: d["doc_id"])
            start = (page - 1) * page_size
            page_items = items[start:start + page_size]
            return jsonify({
                "items": page_items, "total": total, "page": page, "page_size": page_size
            }), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/admin/documents/<path:doc_id>', methods=['DELETE'])
    @_admin
    def kb_admin_delete_document(doc_id):
        """删除单个文档（按 doc_id 删除其全部块）。"""
        try:
            from pymilvus import MilvusClient
            from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT
            client = MilvusClient(LOCAL_MILVUS_FILE) if USE_LOCAL_MODE \
                else MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

            if not client.has_collection(UNIFIED_COLLECTION):
                return jsonify({"error": "集合不存在"}), 404
            try:
                client.load_collection(UNIFIED_COLLECTION)
            except Exception:
                pass
            # doc_id 可能是 URL 编码，还原
            from urllib.parse import unquote
            real_doc_id = unquote(doc_id)
            res = client.delete(UNIFIED_COLLECTION, filter=f'doc_id == "{real_doc_id}"')
            client.flush(UNIFIED_COLLECTION)
            return jsonify({"deleted": True, "doc_id": real_doc_id, "result": str(res)}), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/kb/admin/documents/batch-delete', methods=['POST'])
    @_admin
    def kb_admin_batch_delete():
        """批量删除文档"""
        try:
            data = request.get_json(force=True, silent=True) or {}
            ids = data.get('doc_ids') or []
            if not ids:
                return jsonify({"error": "请提供 doc_ids"}), 400
            from pymilvus import MilvusClient
            from urllib.parse import unquote
            from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT
            client = MilvusClient(LOCAL_MILVUS_FILE) if USE_LOCAL_MODE \
                else MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")
            if not client.has_collection(UNIFIED_COLLECTION):
                return jsonify({"error": "集合不存在"}), 404
            try:
                client.load_collection(UNIFIED_COLLECTION)
            except Exception:
                pass
            expr = ' or '.join([f'doc_id == "{unquote(i)}"' for i in ids])
            res = client.delete(UNIFIED_COLLECTION, filter=expr)
            client.flush(UNIFIED_COLLECTION)
            return jsonify({"deleted": True, "count": len(ids), "result": str(res)}), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
