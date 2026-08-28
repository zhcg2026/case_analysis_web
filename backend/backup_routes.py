# -*- coding: utf-8 -*-
"""数据备份/恢复路由模块 - MySQL + Milvus 全量备份，支持手动和定时自动备份"""
import os
import json
import gzip
import shutil
import subprocess
import threading
import time
import logging
import datetime
from flask import request, jsonify, send_file
from sqlalchemy import text

logger = logging.getLogger(__name__)

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')

# 定时备份线程引用，防止重复启动
_scheduled_thread = None
_stop_event = threading.Event()


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _timestamp():
    return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')


def _file_info(filepath):
    """返回备份文件的元信息"""
    stat = os.stat(filepath)
    return {
        'filename': os.path.basename(filepath),
        'size': stat.st_size,
        'size_human': _human_size(stat.st_size),
        'created_at': datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
    }


def _human_size(size_bytes):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ===================== MySQL 备份 =====================

def _find_mysqldump():
    """查找 mysqldump 可执行文件路径，找不到则尝试自动安装"""
    import shutil
    path = shutil.which('mysqldump')
    if path:
        return path

    # 尝试自动安装 mariadb-client（提供 mysqldump）
    logger.info("mysqldump 未找到，尝试安装 mariadb-client...")
    try:
        proc = subprocess.run(
            ['bash', '-c', 'apt-get update -qq && apt-get install -y --no-install-recommends mariadb-client'],
            capture_output=True, timeout=120
        )
        if proc.returncode == 0:
            path = shutil.which('mysqldump')
            if path:
                logger.info("mariadb-client 安装成功")
                return path
    except Exception as e:
        logger.warning(f"自动安装 mariadb-client 失败: {e}")

    raise RuntimeError(
        'mysqldump 未找到，请在容器中安装 mariadb-client：\n'
        '  apt-get update && apt-get install -y mariadb-client\n'
        '或在 Dockerfile 中确保已安装该包。'
    )


def _backup_mysql():
    """执行 mysqldump，返回备份文件路径"""
    _ensure_backup_dir()
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_NAME', 'case_analysis')

    if not all([db_user, db_password, db_host]):
        raise RuntimeError('数据库配置不完整（DB_USER/DB_PASSWORD/DB_HOST）')

    mysqldump_path = _find_mysqldump()

    filename = f"mysql_backup_{_timestamp()}.sql.gz"
    filepath = os.path.join(BACKUP_DIR, filename)

    cmd = [
        mysqldump_path,
        f'-h{db_host}',
        f'-P{db_port}',
        f'-u{db_user}',
        f'-p{db_password}',
        '--skip-ssl',
        '--single-transaction',
        '--routines',
        '--triggers',
        '--default-character-set=utf8mb4',
        db_name,
    ]

    logger.info(f"开始 MySQL 备份: {db_name}@{db_host}:{db_port}")
    proc = subprocess.run(cmd, capture_output=True, timeout=300)

    if proc.returncode != 0:
        error_msg = proc.stderr.decode('utf-8', errors='replace')
        raise RuntimeError(f"mysqldump 失败: {error_msg}")

    with gzip.open(filepath, 'wb') as f:
        f.write(proc.stdout)

    logger.info(f"MySQL 备份完成: {filepath} ({_human_size(os.path.getsize(filepath))})")
    return filepath


# ===================== Milvus 备份 =====================

def _backup_milvus():
    """导出 Milvus unified_kb 集合为 JSONL.gz 文件"""
    _ensure_backup_dir()

    try:
        from pymilvus import MilvusClient
    except ImportError:
        raise RuntimeError('pymilvus 未安装，无法备份 Milvus')

    from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT

    if USE_LOCAL_MODE:
        if os.path.isabs(LOCAL_MILVUS_FILE):
            db_path = LOCAL_MILVUS_FILE
        else:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOCAL_MILVUS_FILE)
        if not os.path.exists(db_path):
            raise RuntimeError(f'Milvus 本地文件不存在: {db_path}')
        client = MilvusClient(db_path)
    else:
        client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

    collection = "unified_kb"

    logger.info("开始 Milvus 备份: unified_kb 集合")

    filename = f"milvus_backup_{_timestamp()}.jsonl.gz"
    filepath = os.path.join(BACKUP_DIR, filename)

    output_fields = ["doc_id", "chunk_id", "doc_type", "source", "title",
                     "text", "law_status", "case_type", "metadata", "text_tokens",
                     "embedding"]
    batch_size = 16000
    total = 0

    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        offset = 0
        while True:
            rows = client.query(
                collection,
                filter="",
                output_fields=output_fields,
                limit=batch_size,
                offset=offset,
            )
            if not rows:
                break
            for row in rows:
                if "embedding" in row and not isinstance(row["embedding"], str):
                    row["embedding"] = list(row["embedding"])
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            total += len(rows)
            if len(rows) < batch_size:
                break
            offset += batch_size

    logger.info(f"Milvus 备份完成: {total} 条记录 -> {filepath}")
    return filepath


# ===================== MySQL 恢复 =====================

def _find_mysql_client():
    """查找 mysql 客户端可执行文件路径，找不到则尝试自动安装"""
    import shutil
    path = shutil.which('mysql')
    if path:
        return path

    # 尝试自动安装 mariadb-client（提供 mysql 客户端）
    logger.info("mysql 客户端未找到，尝试安装 mariadb-client...")
    try:
        proc = subprocess.run(
            ['bash', '-c', 'apt-get update -qq && apt-get install -y --no-install-recommends mariadb-client'],
            capture_output=True, timeout=120
        )
        if proc.returncode == 0:
            path = shutil.which('mysql')
            if path:
                logger.info("mariadb-client 安装成功")
                return path
    except Exception as e:
        logger.warning(f"自动安装 mariadb-client 失败: {e}")

    raise RuntimeError(
        'mysql 客户端未找到，请在容器中安装 mariadb-client：\n'
        '  apt-get update && apt-get install -y mariadb-client'
    )


def _restore_mysql(filepath):
    """从 .sql.gz 文件恢复 MySQL 数据库"""
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_NAME', 'case_analysis')

    if not all([db_user, db_password, db_host]):
        raise RuntimeError('数据库配置不完整')

    mysql_path = _find_mysql_client()

    # 解压 SQL
    with gzip.open(filepath, 'rb') as f:
        sql_data = f.read()

    cmd = [
        mysql_path,
        f'-h{db_host}',
        f'-P{db_port}',
        f'-u{db_user}',
        f'-p{db_password}',
        '--skip-ssl',
        db_name,
    ]

    logger.info(f"开始 MySQL 恢复: {os.path.basename(filepath)}")
    proc = subprocess.run(cmd, input=sql_data, capture_output=True, timeout=300)

    if proc.returncode != 0:
        error_msg = proc.stderr.decode('utf-8', errors='replace')
        raise RuntimeError(f"mysql 恢复失败: {error_msg}")

    logger.info("MySQL 恢复完成")


# ===================== Milvus 恢复 =====================

def _restore_milvus(filepath):
    """从 .jsonl.gz 文件恢复 Milvus unified_kb 集合"""
    try:
        from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
        from pymilvus.milvus_client.index import IndexParams
    except ImportError:
        raise RuntimeError('pymilvus 未安装')

    from kb_common import USE_LOCAL_MODE, LOCAL_MILVUS_FILE, MILVUS_HOST, MILVUS_PORT

    if USE_LOCAL_MODE:
        db_path = LOCAL_MILVUS_FILE
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        client = MilvusClient(db_path)
    else:
        client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

    collection = "unified_kb"
    dim = 384

    # 删除旧集合
    if client.has_collection(collection):
        client.drop_collection(collection)

    # 重建集合
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=48000),
        FieldSchema(name="law_status", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="case_type", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=24000),
        FieldSchema(name="text_tokens", dtype=DataType.VARCHAR, max_length=24000),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields, description="统一知识库")
    client.create_collection(collection, schema=schema)

    idx = IndexParams()
    idx.add_index("embedding", index_type="FLAT", metric_type="COSINE")
    client.create_index(collection, idx)

    # 导入数据
    field_limits = {"id": 128, "doc_id": 512, "chunk_id": 64, "doc_type": 32,
                    "source": 1024, "title": 1024, "text": 48000, "law_status": 64,
                    "case_type": 256, "metadata": 24000, "text_tokens": 24000}

    rows = []
    total = 0
    batch_size = 500

    with gzip.open(filepath, 'rt', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line.strip())
            if "embedding" in row and not isinstance(row["embedding"], list):
                row["embedding"] = list(row["embedding"])
            # 截断超长字段
            for key, max_len in field_limits.items():
                val = row.get(key, "")
                if isinstance(val, str) and len(val.encode("utf-8")) > max_len:
                    while len(val.encode("utf-8")) > max_len:
                        val = val[:max(1, len(val) * max_len // len(val.encode("utf-8")))]
                    row[key] = val
            rows.append(row)
            if len(rows) >= batch_size:
                client.insert(collection, rows)
                total += len(rows)
                rows = []

    if rows:
        client.insert(collection, rows)
        total += len(rows)

    try:
        client.flush(collection)
    except Exception:
        pass

    logger.info(f"Milvus 恢复完成: 共 {total} 条记录")
    return total


# ===================== 定时备份 =====================

def _get_backup_config(engine):
    """从 system_config 表读取备份配置"""
    default = {
        'backup_enabled': 'false',
        'backup_interval_hours': '24',
        'backup_max_count': '10',
    }
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT config_key, config_value FROM system_config WHERE config_key LIKE 'backup_%'")
            ).fetchall()
            for row in rows:
                default[row[0]] = row[1]
    except Exception:
        pass
    return default


def _save_backup_config(engine, config):
    """保存备份配置到 system_config 表"""
    with engine.connect() as conn:
        for key, val in config.items():
            existing = conn.execute(
                text("SELECT id FROM system_config WHERE config_key = :k"), {'k': key}
            ).fetchone()
            if existing:
                conn.execute(
                    text("UPDATE system_config SET config_value = :v WHERE config_key = :k"),
                    {'v': str(val), 'k': key}
                )
            else:
                conn.execute(
                    text("INSERT INTO system_config (config_key, config_value) VALUES (:k, :v)"),
                    {'k': key, 'v': str(val)}
                )
        conn.commit()


def _cleanup_old_backups(max_count):
    """清理超过保留份数的旧备份文件"""
    try:
        files = []
        for f in os.listdir(BACKUP_DIR):
            if f.startswith('mysql_backup_') or f.startswith('milvus_backup_'):
                filepath = os.path.join(BACKUP_DIR, f)
                files.append((os.path.getmtime(filepath), filepath))
        files.sort(reverse=True)

        # 按类型分别清理
        mysql_files = [fp for _, fp in files if os.path.basename(fp).startswith('mysql_backup_')]
        milvus_files = [fp for _, fp in files if os.path.basename(fp).startswith('milvus_backup_')]

        for file_list in (mysql_files, milvus_files):
            if len(file_list) > max_count:
                for old_file in file_list[max_count:]:
                    try:
                        os.remove(old_file)
                        logger.info(f"清理旧备份: {os.path.basename(old_file)}")
                    except Exception as e:
                        logger.warning(f"清理旧备份失败: {e}")
    except Exception as e:
        logger.warning(f"清理旧备份异常: {e}")


def _scheduled_backup_loop(engine):
    """定时备份守护线程"""
    global _stop_event
    logger.info("定时备份线程已启动")
    while not _stop_event.is_set():
        try:
            config = _get_backup_config(engine)
            if config.get('backup_enabled', 'false').lower() == 'true':
                interval = int(config.get('backup_interval_hours', '24'))
                max_count = int(config.get('backup_max_count', '10'))

                logger.info(f"执行定时全量备份（间隔 {interval}h，保留 {max_count} 份）")
                try:
                    _backup_mysql()
                except Exception as e:
                    logger.error(f"定时 MySQL 备份失败: {e}")
                try:
                    _backup_milvus()
                except Exception as e:
                    logger.error(f"定时 Milvus 备份失败: {e}")

                _cleanup_old_backups(max_count)

                # 等待下一次备份
                wait_seconds = interval * 3600
            else:
                # 未启用，60 秒后再检查
                wait_seconds = 60

            _stop_event.wait(wait_seconds)
        except Exception as e:
            logger.error(f"定时备份线程异常: {e}")
            _stop_event.wait(60)

    logger.info("定时备份线程已退出")


def _start_scheduled_backup(engine):
    """启动定时备份线程（如果尚未启动）"""
    global _scheduled_thread, _stop_event
    if _scheduled_thread and _scheduled_thread.is_alive():
        return
    _stop_event.clear()
    _scheduled_thread = threading.Thread(
        target=_scheduled_backup_loop, args=(engine,), daemon=True
    )
    _scheduled_thread.start()


# ===================== 路由注册 =====================

def register_backup_routes(app, engine=None, protected=None, admin_required=None):
    """注册数据备份/恢复相关路由"""

    # 若未传入装饰器，使用默认导入
    if admin_required is None:
        try:
            from common import admin_required
        except ImportError:
            from helpers import admin_required

    # 启动定时备份
    if engine:
        try:
            _start_scheduled_backup(engine)
        except Exception as e:
            logger.warning(f"启动定时备份失败: {e}")

    # ---------- 全量备份 ----------
    @app.route('/api/backup/full', methods=['POST'])
    @admin_required
    def backup_full():
        results = {}
        errors = []

        try:
            mysql_file = _backup_mysql()
            results['mysql'] = _file_info(mysql_file)
        except Exception as e:
            errors.append(f"MySQL 备份失败: {e}")
            logger.error(f"MySQL 备份失败: {e}")

        try:
            milvus_file = _backup_milvus()
            results['milvus'] = _file_info(milvus_file)
        except Exception as e:
            errors.append(f"Milvus 备份失败: {e}")
            logger.error(f"Milvus 备份失败: {e}")

        if errors and not results:
            return jsonify({'error': '；'.join(errors)}), 500

        return jsonify({
            'message': '全量备份完成' if not errors else '部分备份完成',
            'results': results,
            'warnings': errors if errors else None,
        })

    # ---------- MySQL 备份 ----------
    @app.route('/api/backup/mysql', methods=['POST'])
    @admin_required
    def backup_mysql():
        try:
            filepath = _backup_mysql()
            return jsonify({'message': 'MySQL 备份成功', 'file': _file_info(filepath)})
        except Exception as e:
            logger.error(f"MySQL 备份失败: {e}")
            return jsonify({'error': str(e)}), 500

    # ---------- Milvus 备份 ----------
    @app.route('/api/backup/milvus', methods=['POST'])
    @admin_required
    def backup_milvus():
        try:
            filepath = _backup_milvus()
            return jsonify({'message': 'Milvus 备份成功', 'file': _file_info(filepath)})
        except Exception as e:
            logger.error(f"Milvus 备份失败: {e}")
            return jsonify({'error': str(e)}), 500

    # ---------- 备份列表 ----------
    @app.route('/api/backup/list', methods=['GET'])
    @admin_required
    def backup_list():
        _ensure_backup_dir()
        files = []
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.startswith('mysql_backup_') or f.startswith('milvus_backup_'):
                filepath = os.path.join(BACKUP_DIR, f)
                info = _file_info(filepath)
                info['type'] = 'mysql' if f.startswith('mysql_') else 'milvus'
                files.append(info)
        return jsonify({'files': files})

    # ---------- 下载备份 ----------
    @app.route('/api/backup/download/<filename>', methods=['GET'])
    @admin_required
    def backup_download(filename):
        # 安全校验：只允许下载备份目录下的文件，防止路径穿越
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '非法文件名'}), 400
        filepath = os.path.join(BACKUP_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        return send_file(filepath, as_attachment=True, download_name=filename)

    # ---------- 删除备份 ----------
    @app.route('/api/backup/<filename>', methods=['DELETE'])
    @admin_required
    def backup_delete(filename):
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '非法文件名'}), 400
        filepath = os.path.join(BACKUP_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        try:
            os.remove(filepath)
            return jsonify({'message': f'已删除 {filename}'})
        except Exception as e:
            return jsonify({'error': f'删除失败: {e}'}), 500

    # ---------- MySQL 恢复 ----------
    @app.route('/api/backup/restore/mysql', methods=['POST'])
    @admin_required
    def restore_mysql():
        if 'file' not in request.files:
            return jsonify({'error': '请上传 .sql.gz 备份文件'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '请选择文件'}), 400

        # 保存到临时文件
        _ensure_backup_dir()
        tmp_path = os.path.join(BACKUP_DIR, '_restore_tmp.sql.gz')
        try:
            file.save(tmp_path)
            _restore_mysql(tmp_path)
            return jsonify({'message': 'MySQL 恢复成功'})
        except Exception as e:
            logger.error(f"MySQL 恢复失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ---------- Milvus 恢复 ----------
    @app.route('/api/backup/restore/milvus', methods=['POST'])
    @admin_required
    def restore_milvus():
        if 'file' not in request.files:
            return jsonify({'error': '请上传 .jsonl.gz 备份文件'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': '请选择文件'}), 400

        _ensure_backup_dir()
        tmp_path = os.path.join(BACKUP_DIR, '_restore_tmp.jsonl.gz')
        try:
            file.save(tmp_path)
            count = _restore_milvus(tmp_path)
            return jsonify({'message': f'Milvus 恢复成功，共导入 {count} 条记录'})
        except Exception as e:
            logger.error(f"Milvus 恢复失败: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ---------- 获取自动备份配置 ----------
    @app.route('/api/backup/config', methods=['GET'])
    @admin_required
    def get_backup_config():
        if not engine:
            return jsonify({'error': '数据库未连接'}), 503
        config = _get_backup_config(engine)
        return jsonify({
            'enabled': config.get('backup_enabled', 'false').lower() == 'true',
            'interval_hours': int(config.get('backup_interval_hours', '24')),
            'max_count': int(config.get('backup_max_count', '10')),
        })

    # ---------- 更新自动备份配置 ----------
    @app.route('/api/backup/config', methods=['POST'])
    @admin_required
    def update_backup_config():
        if not engine:
            return jsonify({'error': '数据库未连接'}), 503
        data = request.get_json(force=True, silent=True) or {}

        enabled = str(data.get('enabled', False)).lower()
        interval = str(int(data.get('interval_hours', 24)))
        max_count = str(int(data.get('max_count', 10)))

        if int(interval) < 1:
            return jsonify({'error': '备份间隔不能小于 1 小时'}), 400
        if int(max_count) < 1:
            return jsonify({'error': '保留份数不能小于 1'}), 400

        _save_backup_config(engine, {
            'backup_enabled': enabled,
            'backup_interval_hours': interval,
            'backup_max_count': max_count,
        })

        # 如果启用了定时备份，确保线程在运行
        if enabled == 'true':
            _start_scheduled_backup(engine)

        return jsonify({
            'message': '自动备份配置已保存',
            'enabled': enabled == 'true',
            'interval_hours': int(interval),
            'max_count': int(max_count),
        })

    logger.info("备份路由注册成功")
