# -*- coding: utf-8 -*-
"""立结案标准库路由模块"""

def register_case_standards_routes(app, Session, engine, protected, admin_required):
    """注册立结案标准库相关路由"""

    # 导入核心函数
    try:
        from backend.case_standards import (
            index_all_standards,
            index_standard_file,
            search_case_standards,
            ask_case_standard,
            get_case_standards_stats,
            clear_case_standards,
            list_indexed_standards,
            delete_single_standard,
            incremental_index,
            index_single_file_upload
        )
    except ImportError:
        from case_standards import (
            index_all_standards,
            index_standard_file,
            search_case_standards,
            ask_case_standard,
            get_case_standards_stats,
            clear_case_standards,
            list_indexed_standards,
            delete_single_standard,
            incremental_index,
            index_single_file_upload
        )

    from flask import request, jsonify

    @app.route('/api/case-standards/stats', methods=['GET'])
    @admin_required
    def case_standards_stats():
        """获取立结案标准库统计信息"""
        try:
            stats = get_case_standards_stats()
            return jsonify(stats), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards/index', methods=['POST'])
    @admin_required
    def case_standards_index():
        """索引立结案标准文件目录"""
        try:
            data = request.get_json() or {}
            directory = data.get('directory', 'D:/常用/立案结案标准')
            result = index_all_standards(directory)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards/clear', methods=['POST'])
    @admin_required
    def case_standards_clear():
        """清空立结案标准库"""
        try:
            result = clear_case_standards()
            return jsonify(result), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards/search', methods=['POST'])
    @protected
    def case_standards_search():
        """搜索立结案标准"""
        try:
            data = request.get_json()
            query = data.get('query', '')
            top_k = data.get('top_k', 5)

            if not query:
                return jsonify({'error': '请提供查询内容'}), 400

            results = search_case_standards(query, top_k)
            return jsonify({'results': results, 'total': len(results)}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards-debug/search', methods=['POST'])
    def case_standards_debug_search():
        """调试端点：搜索立结案标准（无需认证）"""
        try:
            data = request.get_json()
            query = data.get('query', '')
            top_k = data.get('top_k', 5)

            if not query:
                return jsonify({'error': '请提供查询内容'}), 400

            results = search_case_standards(query, top_k)
            return jsonify({
                'results': results,
                'total': len(results)
            }), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

    @app.route('/api/case-standards-debug/ask', methods=['POST'])
    def case_standards_debug_ask():
        """调试端点：立结案标准问答（无需认证）"""
        try:
            data = request.get_json(silent=True) or {}
            question = data.get('question', '')
            top_k = data.get('top_k', 5)
            location = data.get('location')

            if not question:
                return jsonify({'error': '请提供问题'}), 400

            result = ask_case_standard(question, top_k, location)
            if isinstance(result, dict) and 'matches' in result:
                result.pop('matches', None)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

    @app.route('/api/case-standards/ask', methods=['POST'])
    @protected
    def case_standards_ask():
        """立结案标准问答"""
        try:
            data = request.get_json(silent=True) or {}
            question = data.get('question', '')
            top_k = data.get('top_k', 5)
            location = data.get('location')
            history = data.get('history', None)

            if not question:
                return jsonify({'error': '请提供问题'}), 400

            result = ask_case_standard(question, top_k, location, history)
            if isinstance(result, dict) and 'matches' in result:
                result.pop('matches', None)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

    @app.route('/api/case-standards/list', methods=['GET'])
    @admin_required
    def case_standards_list():
        """获取已索引的标准列表"""
        try:
            standards = list_indexed_standards()
            return jsonify({
                'standards': standards,
                'total': len(standards)
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards/delete/<parent_id>', methods=['DELETE'])
    @admin_required
    def case_standards_delete_single(parent_id):
        """删除单个已索引的标准"""
        try:
            result = delete_single_standard(parent_id)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards/incremental', methods=['POST'])
    @admin_required
    def case_standards_incremental_index():
        """增量索引立结案标准"""
        try:
            data = request.get_json() or {}
            directory = data.get('directory', 'D:/常用/立案结案标准')
            result = incremental_index(directory)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/case-standards/index-single', methods=['POST'])
    @admin_required
    def case_standards_index_single():
        """上传并索引单个标准文件"""
        try:
            # 检查是否有文件上传
            if 'file' not in request.files:
                # 也支持通过JSON内容上传
                data = request.get_json()
                if data and 'content' in data and 'filename' in data:
                    result = index_single_file_upload(data['content'], data['filename'])
                    return jsonify(result), 200
                return jsonify({'error': '请上传文件或提供文件内容'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': '未选择文件'}), 400

            if not file.filename.endswith('.txt'):
                return jsonify({'error': '只支持.txt文件'}), 400

            # 读取文件内容
            content = file.read().decode('utf-8')
            filename = file.filename

            result = index_single_file_upload(content, filename)
            return jsonify(result), 200
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
