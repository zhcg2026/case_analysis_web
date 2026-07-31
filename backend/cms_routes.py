# -*- coding: utf-8 -*-
"""CMS路由模块 - 文章管理、分类管理"""
import datetime
from flask import request, jsonify
import logging
from helpers import protected, generate_slug
logger = logging.getLogger(__name__)

def register_cms_routes(app, Session, Category, Article):
    """注册CMS相关路由"""
    
    # ==================== 分类路由 ====================
    
    @app.route('/api/categories', methods=['GET'])
    @protected
    def get_categories():
        # 创建新的session实例
        session = Session()
        try:
            # 获取所有栏目，按排序字段排序
            categories = session.query(Category).order_by(Category.order).all()
            
            # 转换为字典列表
            categories_list = []
            for category in categories:
                categories_list.append({
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'order': category.order,
                    'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S') if category.created_at else None,
                    'updated_at': category.updated_at.strftime('%Y-%m-%d %H:%M:%S') if category.updated_at else None
                })
            
            session.commit()
            return jsonify({'categories': categories_list}), 200
        except Exception as e:
            session.rollback()
            logging.exception('Error in get_categories')
            return jsonify({'error': '操作失败'}), 500
        finally:
            session.close()

    # ==================== 文章路由 ====================
    
    @app.route('/api/articles', methods=['GET'])
    @protected
    def get_articles():
        # 创建新的session实例
        session = Session()
        try:
            # 获取查询参数
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            category_id = request.args.get('category_id', type=int)
            status = request.args.get('status')
            include_drafts = request.args.get('include_drafts', 'false').lower() == 'true'

            # 构建查询
            query = session.query(Article)

            # 应用筛选条件
            if category_id:
                query = query.filter_by(category_id=category_id)
            if status:
                query = query.filter_by(status=status)
            elif not include_drafts:
                # 如果没有指定状态且不包含草稿，只获取已发布的
                query = query.filter_by(status='published')

            # 计算总数
            total = query.count()

            # 分页
            articles = query.order_by(Article.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()

            # 转换为字典列表
            articles_list = []
            for article in articles:
                try:
                    article_dict = {
                        'id': article.id,
                        'title': article.title,
                        'slug': article.slug,
                        'summary': article.summary,
                        'category_id': article.category_id,
                        'author_id': article.author_id,
                        'status': article.status,
                        'view_count': article.view_count,
                        'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None,
                        'updated_at': article.updated_at.strftime('%Y-%m-%d %H:%M:%S') if article.updated_at else None,
                        'published_at': article.published_at.strftime('%Y-%m-%d %H:%M:%S') if article.published_at else None
                    }
                    # 尝试获取file_path字段，如果不存在则跳过
                    try:
                        article_dict['file_path'] = article.file_path
                    except AttributeError:
                        article_dict['file_path'] = None
                    articles_list.append(article_dict)
                except Exception as article_error:
                    logging.warning(f"Error processing article {article.id}: {str(article_error)}")
                    continue

            session.commit()
            return jsonify({
                'articles': articles_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in get_articles")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    # 获取单个文章详情
    @app.route('/api/articles/<int:id>', methods=['GET'])
    @protected
    def get_article_detail(id):
        session = Session()
        try:
            article = session.query(Article).filter_by(id=id).first()
            if not article:
                return jsonify({'error': '文章不存在'}), 404

            # 增加阅读计数
            article.view_count = (article.view_count or 0) + 1
            session.commit()

            article_dict = {
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'content': article.content,
                'summary': article.summary,
                'category_id': article.category_id,
                'author_id': article.author_id,
                'status': article.status,
                'view_count': article.view_count,
                'file_path': article.file_path,
                'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None,
                'updated_at': article.updated_at.strftime('%Y-%m-%d %H:%M:%S') if article.updated_at else None,
                'published_at': article.published_at.strftime('%Y-%m-%d %H:%M:%S') if article.published_at else None
            }

            return jsonify(article_dict), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in get_article_detail")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    # 创建文章
    @app.route('/api/articles', methods=['POST'])
    @protected
    def create_article():
        session = Session()
        try:
            data = request.get_json()
            title = data.get('title', '').strip()
            category_id = data.get('category_id')
            content = data.get('content', '')
            summary = data.get('summary', '')
            status = data.get('status', 'draft')
            file_path = data.get('file_path', '')

            if not title:
                return jsonify({'error': '标题不能为空'}), 400
            if not category_id:
                return jsonify({'error': '请选择栏目'}), 400

            slug = generate_slug(title)
            # 确保slug唯一
            existing = session.query(Article).filter_by(slug=slug).first()
            if existing:
                slug = slug + '-' + str(int(datetime.datetime.now().timestamp()))

            article = Article(
                title=title,
                slug=slug,
                content=content,
                summary=summary,
                category_id=category_id,
                author_id=request.user_id,
                status=status,
                file_path=file_path,
                published_at=datetime.datetime.now() if status == 'published' else None
            )
            session.add(article)
            session.commit()

            return jsonify({
                'id': article.id,
                'title': article.title,
                'message': '创建成功'
            }), 201
        except Exception as e:
            session.rollback()
            logging.exception("Error in create_article")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    # 更新文章
    @app.route('/api/articles/<int:id>', methods=['PUT'])
    @protected
    def update_article(id):
        session = Session()
        try:
            article = session.query(Article).filter_by(id=id).first()
            if not article:
                return jsonify({'error': '文章不存在'}), 404

            data = request.get_json()
            title = data.get('title', '').strip()
            category_id = data.get('category_id')
            content = data.get('content', '')
            summary = data.get('summary', '')
            status = data.get('status', 'draft')
            file_path = data.get('file_path', '')

            if title:
                article.title = title
            if category_id:
                article.category_id = category_id
            if content is not None:
                article.content = content
            if summary is not None:
                article.summary = summary
            if status:
                article.status = status
                if status == 'published' and not article.published_at:
                    article.published_at = datetime.datetime.now()
            if file_path is not None:
                article.file_path = file_path

            session.commit()

            return jsonify({
                'id': article.id,
                'title': article.title,
                'message': '更新成功'
            }), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in update_article")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    # 删除文章
    @app.route('/api/articles/<int:id>', methods=['DELETE'])
    @protected
    def delete_article(id):
        session = Session()
        try:
            article = session.query(Article).filter_by(id=id).first()
            if not article:
                return jsonify({'error': '文章不存在'}), 404

            session.delete(article)
            session.commit()

            return jsonify({'message': '删除成功'}), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in delete_article")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()

    # 首页栏目接口
    @app.route('/api/cms/home-columns', methods=['GET'])
    @protected
    def get_home_columns():
        session = Session()
        try:
            # 获取所有栏目
            categories = session.query(Category).order_by(Category.order).all()

            result = []
            for cat in categories:
                # 获取该栏目下最新的5篇已发布文章
                articles = session.query(Article).filter_by(
                    category_id=cat.id,
                    status='published'
                ).order_by(Article.created_at.desc()).limit(5).all()

                articles_list = []
                for article in articles:
                    articles_list.append({
                        'id': article.id,
                        'title': article.title,
                        'summary': article.summary,
                        'view_count': article.view_count,
                        'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S') if article.created_at else None
                    })

                result.append({
                    'id': cat.id,
                    'name': cat.name,
                    'slug': cat.slug,
                    'description': cat.description,
                    'articles': articles_list
                })

            session.commit()
            return jsonify(result), 200
        except Exception as e:
            session.rollback()
            logging.exception("Error in get_home_columns")
            return jsonify({"error": "操作失败，请稍后重试"}), 500
        finally:
            session.close()
