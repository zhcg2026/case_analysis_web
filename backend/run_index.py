"""索引立结案标准知识库"""
import os
import sys

# 设置本地模式环境变量
os.environ['USE_LOCAL_MODE'] = 'true'
os.environ['LOCAL_DB_PATH'] = '../chroma_db'

print('USE_LOCAL_MODE:', os.getenv('USE_LOCAL_MODE'))
print('LOCAL_DB_PATH:', os.getenv('LOCAL_DB_PATH'))

# 导入索引模块
from case_standards import index_all_standards, get_local_embed_model, get_chroma_client

# 加载embedding模型
print('加载embedding模型...')
model = get_local_embed_model()
if model:
    print('模型加载成功')
else:
    print('模型加载失败')
    sys.exit(1)

# 检查ChromaDB连接
client = get_chroma_client()
if client:
    print('ChromaDB连接成功')
else:
    print('ChromaDB连接失败')
    sys.exit(1)

# 执行索引
print('开始索引知识库...')
result = index_all_standards('D:/常用/立案结案标准')
print(f'索引完成: {result["success"]} 成功, {result["failed"]} 失败, {result["total_children"]} 子文档')

# 检查索引结果
collections = client.list_collections()
print('Collections:', [(c.name, c.count()) for c in collections])