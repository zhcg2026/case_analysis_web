# 案件分析系统（整理版说明）

当前仓库采用前后端同仓：

- `backend/`: Flask 后端（接口 + 静态文件服务）
- `frontend/`: Vue 3 + Vite 前端
- `docker-compose.yml`: 生产/服务器常用启动方式（MySQL + Flask）

## 当前可用启动方式

### 1) 本地开发（推荐调试）

后端：

```bash
cd backend
python app.py
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:5173`

> 前端开发代理默认转发到 `http://localhost:5000`，可通过 `VITE_API_TARGET` 覆盖。

### 2) Docker 部署（服务器常用）

```bash
docker-compose up -d --build
```

访问：`http://<server-ip>:5000`

## 配置说明（已做兼容改造）

后端配置优先读取环境变量，没有配置时沿用原默认值，不影响现有运行：

- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `DB_HOST`
- `DB_PORT`
- `JWT_SECRET_KEY`
- `TOKEN_EXPIRATION_SECONDS`
- `FLASK_HOST`
- `FLASK_PORT`
- `FLASK_DEBUG`

前端开发代理支持：

- `VITE_API_TARGET`

可参考根目录 `.env.example`。

## 本轮整改内容

- 后端数据库/JWT/启动参数改为环境变量优先（保持默认值兼容）
- 前端 Vite 代理改为支持 `VITE_API_TARGET`
- 增加项目级 `README.md` 与 `.env.example` 便于统一维护

## 下一步建议（可选）

1. 将 `backend/app.py` 按模块拆分（auth / users / cases / tools）
2. 将 `frontend/src/App.vue` 拆为页面和组件
3. 将临时修复脚本归档到 `scripts/legacy/`
