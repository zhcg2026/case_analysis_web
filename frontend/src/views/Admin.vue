<template>
  <div class="page-container">
    <h1 class="page-title">系统管理</h1>

    <!-- 子标签导航 -->
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 用户管理 -->
    <div v-if="activeTab === 'users'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">用户管理</h2>
        <button class="btn btn-primary" @click="openAddUserModal">
          <span>+</span> 添加用户
        </button>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户名</th>
            <th>角色</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in validUsers" :key="user.id">
            <td>{{ user.id }}</td>
            <td>{{ user.username }}</td>
            <td>
              <span :class="['role-badge', user.role]">
                {{ roleMap[user.role] || user.role }}
              </span>
            </td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td>
              <button class="btn-text" @click="editUser(user)">编辑</button>
              <button v-if="user.username !== 'admin'" class="btn-text danger" @click="deleteUser(user)">删除</button>
              <button v-if="user.role !== 'admin'" class="btn-text" @click="openPermissionsEditor(user)">权限</button>
            </td>
          </tr>
          <tr v-if="validUsers.length === 0">
            <td colspan="5" class="empty-text">暂无用户</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 文章管理 -->
    <div v-else-if="activeTab === 'articles'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">文章管理</h2>
        <div class="header-actions">
          <button class="btn btn-secondary" @click="showCategoryManager = true">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
            栏目管理
          </button>
          <button class="btn btn-primary" @click="openArticleEditor()">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            发布文章
          </button>
        </div>
      </div>

      <!-- 分类导航 -->
      <div class="category-nav">
        <button
          v-for="cat in articleCategories"
          :key="cat.id"
          class="category-btn"
          :class="{ active: selectedArticleCategory === cat.id }"
          @click="selectArticleCategory(cat.id)"
        >
          {{ cat.name }}
        </button>
      </div>

      <!-- 文章列表 -->
      <div v-if="articlesLoading" class="loading-state">
        <div class="loading-spinner"></div>
      </div>

      <div v-else class="articles-list">
        <div v-for="article in articles" :key="article.id" class="article-item">
          <div class="article-info">
            <div class="article-header">
              <h3 class="article-title">{{ article.title }}</h3>
              <span v-if="article.file_path" class="attachment-tag">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                </svg>
                附件
              </span>
            </div>
            <div class="article-meta">
              <span class="category-tag">{{ getArticleCategoryName(article.category_id) }}</span>
              <span>{{ formatDate(article.created_at) }}</span>
              <span v-if="article.view_count">阅读 {{ article.view_count }}</span>
            </div>
          </div>
          <div class="article-actions">
            <button class="btn-icon" @click="openArticleEditor(article)" title="编辑">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="btn-icon danger" @click="deleteArticle(article)" title="删除">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>

        <div v-if="articles.length === 0" class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <span>暂无文章</span>
          <button class="btn btn-primary" @click="openArticleEditor()">发布第一篇文章</button>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="articlesTotalPages > 1">
        <button class="pagination-btn" :disabled="articlesCurrentPage === 1" @click="articlesCurrentPage--">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <span class="page-info">{{ articlesCurrentPage }} / {{ articlesTotalPages }}</span>
        <button class="pagination-btn" :disabled="articlesCurrentPage === articlesTotalPages" @click="articlesCurrentPage++">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 文章编辑弹窗 -->
    <div class="modal-overlay" v-if="showArticleEditor" @click.self="closeArticleEditor">
      <div class="modal-content article-editor">
        <div class="modal-header">
          <h2>{{ editingArticle ? '编辑文章' : '发布文章' }}</h2>
          <button class="btn-close" @click="closeArticleEditor">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">文章标题 *</label>
            <input v-model="articleForm.title" type="text" class="form-input" placeholder="请输入文章标题" />
          </div>
          <div class="form-group">
            <label class="form-label">所属栏目 *</label>
            <select v-model="articleForm.category_id" class="form-select">
              <option value="">请选择栏目</option>
              <option v-for="cat in categoryList" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">文章摘要</label>
            <textarea v-model="articleForm.summary" class="form-textarea" rows="2" placeholder="请输入文章摘要（选填）"></textarea>
          </div>

          <!-- 图片上传区域 -->
          <div class="form-group">
            <label class="form-label">插入图片</label>
            <div class="upload-area">
              <input ref="imageInput" type="file" accept="image/*" @change="handleImageUpload" hidden />
              <button class="btn btn-secondary" @click="$refs.imageInput.click()" :disabled="uploadingImage">
                {{ uploadingImage ? '上传中...' : '选择图片' }}
              </button>
              <span class="upload-hint">支持 jpg、png、gif 格式</span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">文章内容 *</label>
            <div class="editor-container">
              <Toolbar
                :editor="editorRef"
                :defaultConfig="toolbarConfig"
                :mode="mode"
                style="border-bottom: 1px solid #ccc"
              />
              <Editor
                v-model="articleForm.content"
                :defaultConfig="editorConfig"
                :mode="mode"
                @onCreated="handleEditorCreated"
                style="height: 320px; overflow-y: hidden"
              />
            </div>
          </div>

          <!-- 附件上传区域 -->
          <div class="form-group">
            <label class="form-label">附件上传</label>
            <div class="upload-area">
              <input ref="fileInput" type="file" @change="handleFileUpload" hidden />
              <button class="btn btn-secondary" @click="$refs.fileInput.click()" :disabled="uploadingFile">
                {{ uploadingFile ? '上传中...' : '选择附件' }}
              </button>
              <span class="upload-hint">支持 doc、docx、pdf、xls、xlsx 等格式</span>
            </div>
            <div v-if="articleForm.file_path" class="attachment-info">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
              </svg>
              <span>已上传附件</span>
              <button class="btn-link" @click="articleForm.file_path = ''">移除</button>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeArticleEditor">取消</button>
          <button class="btn btn-primary" @click="saveArticle" :disabled="articleSaving">
            {{ articleSaving ? '发布中...' : (editingArticle ? '保存' : '发布') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 栏目管理弹窗 -->
    <div class="modal-overlay" v-if="showCategoryManager" @click.self="showCategoryManager = false">
      <div class="modal-content category-manager">
        <div class="modal-header">
          <h2>栏目管理</h2>
          <button class="btn-close" @click="showCategoryManager = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <!-- 添加栏目 -->
          <div class="add-category">
            <input v-model="newCategoryName" type="text" class="form-input" placeholder="输入新栏目名称" @keyup.enter="addCategory" />
            <button class="btn btn-primary" @click="addCategory" :disabled="!newCategoryName.trim()">添加</button>
          </div>
          <!-- 栏目列表 -->
          <div class="category-list">
            <div v-for="cat in categoryList" :key="cat.id" class="category-item">
              <div class="category-info">
                <span class="category-name">{{ cat.name }}</span>
                <span class="category-slug">{{ cat.slug }}</span>
              </div>
              <div class="category-actions">
                <button class="btn-icon" @click="editCategory(cat)" title="编辑">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button class="btn-icon danger" @click="deleteCategory(cat)" title="删除">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 栏目编辑弹窗 -->
    <div class="modal-overlay" v-if="showCategoryEditor" @click.self="showCategoryEditor = false">
      <div class="modal-content category-editor">
        <div class="modal-header">
          <h2>编辑栏目</h2>
          <button class="btn-close" @click="showCategoryEditor = false">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">栏目名称</label>
            <input v-model="editingCategory.name" type="text" class="form-input" />
          </div>
          <div class="form-group">
            <label class="form-label">栏目描述</label>
            <textarea v-model="editingCategory.description" class="form-textarea" rows="2"></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">排序</label>
            <input v-model.number="editingCategory.order" type="number" class="form-input" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showCategoryEditor = false">取消</button>
          <button class="btn btn-primary" @click="updateCategory">保存</button>
        </div>
      </div>
    </div>

    <!-- 用户权限编辑弹窗 -->
    <div class="modal-overlay" v-if="showPermissionsEditor" @click.self="closePermissionsEditor">
      <div class="modal-content permissions-editor">
        <div class="modal-header">
          <h2>编辑用户权限 - {{ editingPermissionsUser?.username }}</h2>
          <button class="btn-close" @click="closePermissionsEditor">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="permissions-grid">
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.data_management" />
              <span>数据管理</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.data_analysis" />
              <span>数据分析</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.map" />
              <span>数图城管</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.business" />
              <span>业务平台</span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closePermissionsEditor">取消</button>
          <button class="btn btn-primary" @click="savePermissions" :disabled="permissionsSaving">
            {{ permissionsSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 添加用户弹窗 -->
    <div class="modal-overlay" v-if="showAddUser" @click.self="showAddUser = false">
      <div class="modal-content add-user-editor">
        <div class="modal-header">
          <h2>{{ editingUser ? '编辑用户' : '添加用户' }}</h2>
          <button class="btn-close" @click="closeUserEditor">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">用户名</label>
            <input v-model="userForm.username" type="text" class="form-input" placeholder="请输入用户名" :disabled="isAdminUser" autocomplete="off" />
          </div>
          <div class="form-group">
            <label class="form-label">密码{{ editingUser ? '（留空不修改）' : '' }}</label>
            <input v-model="userForm.password" type="password" class="form-input" placeholder="请输入密码" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label class="form-label">角色</label>
            <select v-model="userForm.role" class="form-select" :disabled="isAdminUser">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeUserEditor">取消</button>
          <button class="btn btn-primary" @click="saveUser" :disabled="userSaving">
            {{ userSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 业务平台 -->
    <div v-else-if="activeTab === 'business'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">业务平台管理</h2>
        <button class="btn btn-primary" @click="openPlatformEditor()">
          <span>+</span> 添加平台
        </button>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>图片</th>
            <th>名称</th>
            <th>链接</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="platform in platforms" :key="platform.id">
            <td>{{ platform.id }}</td>
            <td>
              <img v-if="platform.image_path" :src="platform.image_path" class="platform-thumb" />
              <span v-else class="no-image">无</span>
            </td>
            <td>{{ platform.name }}</td>
            <td>
              <a :href="platform.url" target="_blank" class="link">{{ platform.url }}</a>
            </td>
            <td>
              <button class="btn-text" @click="openPlatformEditor(platform)">编辑</button>
              <button class="btn-text danger" @click="deletePlatform(platform)">删除</button>
            </td>
          </tr>
          <tr v-if="platforms.length === 0">
            <td colspan="5" class="empty-text">暂无平台</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 知识库管理 -->
    <div v-else-if="activeTab === 'knowledge'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">知识库管理</h2>
      </div>

      <!-- 子标签导航 -->
      <div class="knowledge-sub-tabs">
        <button class="sub-tab" :class="{ active: knowledgeSubTab === 'general' }" @click="knowledgeSubTab = 'general'">
          通用知识库
        </button>
      </div>

      <!-- 通用知识库管理（对齐统一库 unified_kb） -->
      <div v-show="knowledgeSubTab === 'general'">
        <!-- 概览：5 类统计卡 -->
        <div class="kb-stat-grid">
          <div
            v-for="t in kbTypeList"
            :key="t.key"
            class="kb-stat-card"
            :style="{ '--kc': t.color }"
          >
            <span class="kb-stat-icon"><KbIcon :name="t.icon" :size="20" /></span>
            <span class="kb-stat-num">{{ kbOverview.by_type[t.key] || 0 }}</span>
            <span class="kb-stat-label">{{ t.label }}</span>
          </div>
          <div class="kb-stat-card kb-stat-total">
            <span class="kb-stat-icon"><KbIcon name="landmark" :size="20" /></span>
            <span class="kb-stat-num">{{ kbOverview.total || 0 }}</span>
            <span class="kb-stat-label">向量总数</span>
          </div>
        </div>

        <!-- 重建索引 -->
        <div class="kb-rebuild-box">
          <div class="kb-rebuild-head">
            <div>
              <h3 class="subsection-title">重建索引</h3>
              <p class="kb-rebuild-hint">
                <strong>重建步骤：</strong>① 本地打包知识库目录 → ② 上传到服务器 → ③ 配置环境变量 → ④ 点击重建。<br/>
                1. 本地执行 <code>Compress-Archive -Path "D:\常用\知识库" -DestinationPath "D:\kb_source.zip"</code> 打包<br/>
                2. 执行 <code>scp D:\kb_source.zip ubuntu@192.168.101.3:/tmp/kb_source.zip</code> 上传<br/>
                3. 服务器上解压：<code>sudo mkdir -p /home/ubuntu/kb_data && sudo unzip -o /tmp/kb_source.zip -d /home/ubuntu/kb_data</code><br/>
                4. 在 docker-compose 的 environment 中设置 <code>KB_SOURCE_DIR=/home/ubuntu/kb_data/知识库</code>，或挂载 volume 后指向容器内路径<br/>
                5. 重启容器后，点击下方「重建索引（全量）」按钮执行重建
              </p>
            </div>
            <button class="btn btn-primary" @click="rebuildKb" :disabled="kbRebuilding">
              {{ kbRebuilding ? '重建中…' : '重建索引（全量）' }}
            </button>
          </div>
          <div v-if="kbRebuildStatus" class="kb-rebuild-status" :class="kbRebuildStatus.status">
            <div class="kb-rebuild-msg">{{ kbRebuildStatus.message }}</div>
            <div v-if="kbRebuilding && kbRebuildStatus.total" class="kb-progress-bar">
              <div class="kb-progress-fill" :style="{ width: pct(kbRebuildStatus.done, kbRebuildStatus.total) + '%' }"></div>
            </div>
          </div>
        </div>

        <!-- 文档浏览 -->
        <div class="kb-docs-section">
          <div class="section-header">
            <h3 class="subsection-title">已入库文档</h3>
            <div class="section-actions">
              <div class="kb-filter-chips">
                <button class="kb-chip" :class="{ active: kbDocFilter === '' }" @click="kbDocFilter = ''; loadKbDocs()">全部</button>
                <button
                  v-for="t in kbTypeList"
                  :key="t.key"
                  class="kb-chip"
                  :class="{ active: kbDocFilter === t.key }"
                  :style="{ '--kc': t.color }"
                  @click="kbDocFilter = t.key; loadKbDocs()"
                >{{ t.label }}</button>
              </div>
              <input v-model="kbDocKeyword" @keyup.enter="loadKbDocs" placeholder="搜索标题/来源…" class="kb-doc-search" />
              <button class="btn btn-secondary" @click="loadKbDocs" :disabled="kbDocsLoading">刷新</button>
              <button v-if="kbSelectedDocs.length > 0" class="btn btn-danger" @click="batchDeleteKbDocs">
                删除选中 ({{ kbSelectedDocs.length }})
              </button>
            </div>
          </div>

          <div v-if="kbDocsLoading" class="loading-state"><div class="loading-spinner"></div></div>
          <div v-else-if="kbDocs.length" class="docs-list">
            <div class="docs-header">
              <label class="checkbox-label">
                <input type="checkbox" :checked="kbSelectedDocs.length === kbDocs.length && kbDocs.length" @change="toggleKbSelectAll">
                全选
              </label>
              <span class="docs-count">共 {{ kbDocTotal }} 个文档（当前页 {{ kbDocs.length }}）</span>
            </div>
            <div v-for="doc in kbDocs" :key="doc.doc_id" class="doc-row" :style="{ '--c': typeColor(doc.doc_type) }">
              <input type="checkbox" :value="doc.doc_id" v-model="kbSelectedDocs">
              <span class="kb-doc-type-tag" :style="{ color: typeColor(doc.doc_type), background: typeBg(doc.doc_type) }">{{ typeLabel(doc.doc_type) }}</span>
              <span class="doc-id" :title="doc.doc_id">{{ doc.title || doc.doc_id }}</span>
              <span class="doc-chunks">{{ doc.chunks }} 块</span>
              <span class="doc-source">{{ doc.source }}</span>
              <button class="btn-text danger" @click="deleteKbDoc(doc.doc_id)">删除</button>
            </div>
            <!-- 分页 -->
            <div v-if="kbDocTotal > kbDocPageSize" class="kb-pager">
              <button class="btn btn-secondary" :disabled="kbDocPage <= 1" @click="kbDocPage--; loadKbDocs()">上一页</button>
              <span class="kb-pager-info">第 {{ kbDocPage }} 页 / 共 {{ Math.ceil(kbDocTotal / kbDocPageSize) }} 页</span>
              <button class="btn btn-secondary" :disabled="kbDocPage >= Math.ceil(kbDocTotal / kbDocPageSize)" @click="kbDocPage++; loadKbDocs()">下一页</button>
            </div>
          </div>
          <div v-else class="empty-state">暂无文档</div>
        </div>
      </div>

    </div>

    <!-- 报告模板管理 -->
    <div v-else-if="activeTab === 'reports'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">报告模板管理</h2>
        <div class="card-header-actions">
          <button class="btn btn-primary" @click="showTemplateUploader = true">
            <span class="btn-icon">📁</span> 上传Word模板
          </button>
        </div>
      </div>

      <div v-if="reportTemplatesLoading" class="loading-state">
        <div class="loading-spinner"></div>
      </div>

      <div v-else-if="reportTemplates.length === 0" class="empty-state">
        <p>暂无报告模板，点击上方"上传Word模板"按钮导入</p>
      </div>

      <div v-else class="report-grid">
        <div v-for="tpl in reportTemplates" :key="tpl.id" class="report-card">
          <div class="report-card-header">
            <h3 class="report-card-title">{{ tpl.name }}</h3>
            <span class="report-type-badge" :class="tpl.report_type">
              {{ tpl.report_type === 'compare' ? '对比报告' : '单月报告' }}
            </span>
          </div>
          <p class="report-card-desc">{{ tpl.description || '暂无描述' }}</p>
          <div class="report-card-meta">
            <span>{{ tpl.section_count }} 个章节</span>
            <span>{{ tpl.updated_at?.slice(0, 10) }}</span>
          </div>
          <div class="report-card-actions">
            <button class="btn btn-sm btn-secondary" @click="openReportEditor(tpl)">编辑</button>
            <button class="btn btn-sm btn-primary" @click="executeReport(tpl)">执行</button>
            <button class="btn btn-sm btn-danger" @click="deleteReport(tpl)">删除</button>
          </div>
        </div>
      </div>

      <!-- 模板编辑模态框 -->
      <div class="modal-overlay" v-if="showReportEditor" @click.self="closeReportEditor">
        <div class="modal-content report-editor-modal">
          <div class="modal-header">
            <h2>编辑报告模板</h2>
            <button class="close-btn" @click="closeReportEditor">&times;</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label">模板名称 *</label>
              <input v-model="reportForm.name" type="text" class="form-input" placeholder="如：6月案件数据分析报告" />
            </div>
            <div class="form-group">
              <label class="form-label">模板描述</label>
              <textarea v-model="reportForm.description" class="form-textarea" rows="2" placeholder="简要说明报告内容"></textarea>
            </div>
            <div class="form-group">
              <label class="form-label">报告类型</label>
              <select v-model="reportForm.report_type" class="form-select">
                <option value="single">单月报告</option>
                <option value="compare">对比报告</option>
              </select>
            </div>

            <div class="sections-editor">
              <div class="sections-header">
                <label class="form-label">报告章节</label>
                <button class="btn btn-sm btn-secondary" @click="addReportSection">+ 添加章节</button>
              </div>

              <div v-if="reportForm.sections.length === 0" class="empty-sections">
                暂无章节，点击上方按钮添加
              </div>

              <div v-for="(sec, idx) in reportForm.sections" :key="idx" class="section-item">
                <div class="section-item-header">
                  <span class="section-num">{{ idx + 1 }}</span>
                  <input v-model="sec.title" class="form-input section-title-input" placeholder="章节标题，如：一、案件总览" />
                  <div class="section-controls">
                    <button class="btn-icon-sm" @click="moveReportSection(idx, -1)" :disabled="idx === 0">↑</button>
                    <button class="btn-icon-sm" @click="moveReportSection(idx, 1)" :disabled="idx === reportForm.sections.length - 1">↓</button>
                    <button class="btn-icon-sm danger" @click="removeReportSection(idx)">×</button>
                  </div>
                </div>

                <div class="section-charts">
                  <div class="charts-header">
                    <span class="charts-label">图表配置</span>
                  </div>
                  <div v-for="(chart, cidx) in sec.charts || []" :key="cidx" class="chart-item">
                    <input v-model="chart.name" class="form-input chart-name-input" placeholder="图表名称，如：每日上报趋势" />
                    <select v-model="chart.chart_type" class="form-select form-select-sm">
                      <option value="bar">柱状图</option>
                      <option value="horizontal_bar">横向柱状图</option>
                      <option value="pie">饼图</option>
                      <option value="line">折线图</option>
                    </select>
                    <input v-model="chart.query" class="form-input chart-query-input" placeholder="自定义SQL（留空自动匹配，支持 {month_filter} 占位符）" />
                    <button class="btn-icon-sm danger" @click="removeChart(idx, cidx)" title="删除图表">×</button>
                  </div>
                  <button class="btn btn-xs btn-secondary" @click="addChart(idx)">+ 添加图表</button>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeReportEditor">取消</button>
            <button class="btn btn-primary" @click="saveReport" :disabled="reportSaving">
              {{ reportSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Word模板上传模态框 -->
      <div class="modal-overlay" v-if="showTemplateUploader" @click.self="closeTemplateUploader">
        <div class="modal-content report-editor-modal">
          <div class="modal-header">
            <h2>上传Word模板</h2>
            <button class="close-btn" @click="closeTemplateUploader">&times;</button>
          </div>
          <div class="modal-body">
            <div class="upload-area" 
                 @dragover.prevent 
                 @drop.prevent="handleTemplateDrop"
                 :class="{ 'drag-over': isDragging }">
              <input type="file" 
                     ref="templateFileInput" 
                     accept=".docx" 
                     @change="handleTemplateFileSelect"
                     style="display: none" />
              <div class="upload-content" @click="$refs.templateFileInput.click()">
                <div class="upload-icon">📄</div>
                <p class="upload-text">点击或拖拽 Word 文件到这里</p>
                <p class="upload-hint">支持 .docx 格式</p>
              </div>
            </div>
            
            <div v-if="templateUploading" class="upload-progress">
              <div class="loading-spinner"></div>
              <span>正在上传和解析模板...</span>
            </div>
            
            <div v-if="templateUploadResult" class="upload-result">
              <div class="result-success">
                <span class="success-icon">✓</span>
                <span>模板解析成功！</span>
              </div>
              <div class="result-info">
                <p><strong>文件名：</strong>{{ templateUploadResult.original_filename }}</p>
                <p><strong>识别章节：</strong>{{ templateUploadResult.structure?.sections?.length || 0 }} 个</p>
              </div>
              <div class="result-sections">
                <h4>识别到的章节：</h4>
                <ul>
                  <li v-for="(sec, idx) in templateUploadResult.structure?.sections || []" :key="idx">
                    {{ sec.title }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="closeTemplateUploader">取消</button>
            <button class="btn btn-primary" 
                    @click="createFromTemplate" 
                    :disabled="!templateUploadResult || templateSaving">
              {{ templateSaving ? '创建中...' : '使用此模板创建' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 系统设置 -->
    <div v-else-if="activeTab === 'data'" class="content-card" style="padding:0;border:none;background:transparent">
      <DataManagementTab />
    </div>
    <div v-else-if="activeTab === 'system'" class="content-card">
      <h2 class="section-title">系统设置</h2>
      <div class="settings-form">
        <div class="form-group">
          <label class="form-label">系统名称</label>
          <input type="text" class="form-input" v-model="systemConfig.name" />
        </div>
        <div class="form-group">
          <label class="form-label">系统Logo</label>
          <div class="logo-upload">
            <div class="logo-preview" v-if="systemConfig.logo">
              <img :src="systemConfig.logo" alt="Logo 预览" />
            </div>
            <div class="logo-preview logo-preview--empty" v-else>
              <span>暂无 Logo</span>
            </div>
            <div class="logo-upload__actions">
              <input ref="logoInput" type="file" accept="image/*" hidden @change="handleLogoUpload" />
              <button type="button" class="btn btn-secondary" :disabled="uploadingLogo" @click="$refs.logoInput.click()">
                {{ uploadingLogo ? '上传中…' : '选择图片上传' }}
              </button>
              <button type="button" class="btn btn-link" v-if="systemConfig.logo" @click="systemConfig.logo = ''">移除</button>
            </div>
          </div>
          <input type="text" class="form-input" v-model="systemConfig.logo" placeholder="或粘贴图片链接（如 https://…/logo.png）" />
        </div>
        <button class="btn btn-primary" @click="saveSystemConfig">保存设置</button>
      </div>
    </div>

    <!-- 平台编辑弹窗 -->
    <div class="modal-overlay" v-if="showPlatformEditor" @click.self="closePlatformEditor">
      <div class="modal-content platform-editor">
        <div class="modal-header">
          <h2>{{ editingPlatform?.id ? '编辑平台' : '添加平台' }}</h2>
          <button class="btn-close" @click="closePlatformEditor">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">平台名称 *</label>
            <input v-model="platformForm.name" type="text" class="form-input" placeholder="请输入平台名称" />
          </div>
          <div class="form-group">
            <label class="form-label">链接地址 *</label>
            <input v-model="platformForm.url" type="url" class="form-input" placeholder="https://example.com" />
          </div>
          <div class="form-group">
            <label class="form-label">平台图片</label>
            <div class="upload-area" @click="$refs.platformImage.click()">
              <input ref="platformImage" type="file" accept="image/*" @change="handlePlatformImage" hidden />
              <div v-if="platformForm.image_path" class="upload-preview">
                <img :src="platformForm.image_path" @error="onImageError" />
                <button class="remove-image" @click.stop="removePlatformImage" type="button">×</button>
              </div>
              <div v-else class="upload-placeholder">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </svg>
                <span>点击上传图片</span>
              </div>
            </div>
            <div class="form-hint">建议尺寸：200x200px，支持 JPG/PNG/GIF/WebP</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closePlatformEditor">取消</button>
          <button class="btn btn-primary" @click="savePlatform" :disabled="platformSaving">
            {{ platformSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑记录弹窗 -->
    <div class="modal-overlay" v-if="showRecordModal" @click.self="closeRecordModal">
      <div class="modal-content modal-record">
        <div class="modal-header">
          <h3>{{ isAddRecord ? '新增记录' : '编辑记录' }}</h3>
          <button class="close-btn" @click="closeRecordModal">&times;</button>
        </div>
        <div class="modal-body modal-body-scroll">
          <div class="form-group" v-for="col in formFields" :key="col">
            <label class="form-label">{{ col }}</label>
            <template v-if="col === '任务号'">
              <input v-model="recordForm[col]" type="text" class="form-input" :disabled="!isAddRecord" :placeholder="isAddRecord ? '请输入任务号' : '不可编辑'" />
            </template>
            <template v-else-if="col === '是否超时'">
              <select v-model="recordForm[col]" class="form-select">
                <option value="">请选择</option>
                <option value="是">是</option>
                <option value="否">否</option>
              </select>
            </template>
            <template v-else-if="col.includes('次数')">
              <input v-model.number="recordForm[col]" type="number" class="form-input" min="0" />
            </template>
            <template v-else>
              <input v-model="recordForm[col]" type="text" class="form-input" />
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeRecordModal">取消</button>
          <button class="btn btn-primary" @click="saveRecord" :disabled="recordSaving">{{ recordSaving ? '保存中...' : '确认' }}</button>
        </div>
      </div>
    </div>

    <!-- 批量修改弹窗 -->
    <div class="modal-overlay" v-if="showBatchEditModal" @click.self="showBatchEditModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>批量修改</h3>
          <button class="close-btn" @click="showBatchEditModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <p class="batch-info">将修改 {{ selectedRecords.length }} 条记录</p>
          <div class="form-group">
            <label class="form-label">选择修改字段</label>
            <select v-model="batchEditField" class="form-select">
              <option value="">请选择</option>
              <option v-for="col in formFields.filter(c => c !== '任务号')" :key="col" :value="col">{{ col }}</option>
            </select>
          </div>
          <div class="form-group" v-if="batchEditField">
            <label class="form-label">新值</label>
            <template v-if="batchEditField === '是否超时'">
              <select v-model="batchEditValue" class="form-select">
                <option value="">请选择</option>
                <option value="是">是</option>
                <option value="否">否</option>
              </select>
            </template>
            <template v-else-if="batchEditField.includes('次数')">
              <input v-model.number="batchEditValue" type="number" class="form-input" min="0" />
            </template>
            <template v-else>
              <input v-model="batchEditValue" type="text" class="form-input" />
            </template>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showBatchEditModal = false">取消</button>
          <button class="btn btn-primary" @click="batchUpdateRecords" :disabled="batchEditSaving">{{ batchEditSaving ? '保存中...' : '确认修改' }}</button>
        </div>
      </div>
    </div>

    <!-- 日志详情弹窗 -->
    <div class="modal-overlay" v-if="showLogDetailModal" @click.self="showLogDetailModal = false">
      <div class="modal-content modal-large">
        <div class="modal-header">
          <h3>操作详情</h3>
          <button class="close-btn" @click="showLogDetailModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="log-detail">
            <p><strong>操作人：</strong>{{ logDetail?.username }}</p>
            <p><strong>操作类型：</strong>{{ logDetail?.operation_type === 'create' ? '新增' : logDetail?.operation_type === 'update' ? '修改' : '删除' }}</p>
            <p><strong>数据表：</strong>{{ logDetail?.table_name }}</p>
            <p><strong>记录ID：</strong>{{ logDetail?.record_id }}</p>
            <p><strong>操作时间：</strong>{{ logDetail?.created_at }}</p>
            <div v-if="logDetail?.operation_type === 'update'">
              <p><strong>修改前：</strong></p>
              <pre class="json-display">{{ formatJson(logDetail?.old_value) }}</pre>
              <p><strong>修改后：</strong></p>
              <pre class="json-display">{{ formatJson(logDetail?.new_value) }}</pre>
            </div>
            <div v-else-if="logDetail?.operation_type === 'delete'">
              <p><strong>删除的数据：</strong></p>
              <pre class="json-display">{{ formatJson(logDetail?.old_value) }}</pre>
            </div>
            <div v-else>
              <p><strong>新增的数据：</strong></p>
              <pre class="json-display">{{ formatJson(logDetail?.new_value) }}</pre>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showLogDetailModal = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div class="modal-overlay" v-if="showDeleteConfirm" @click.self="showDeleteConfirm = false">
      <div class="modal-content modal-small">
        <div class="modal-header">
          <h3>确认删除</h3>
          <button class="close-btn" @click="showDeleteConfirm = false">&times;</button>
        </div>
        <div class="modal-body">
          <p>{{ deleteConfirmMessage }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="executeDelete" :disabled="deleteSaving">{{ deleteSaving ? '删除中...' : '确认删除' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import '@wangeditor/editor/dist/css/style.css'
import KbIcon from '../components/common/KbIcon.vue'
import DataManagementTab from '../components/admin/DataManagementTab.vue'
import { useSystemConfig } from '../composables/useSystemConfig'

const router = useRouter()

const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'articles', label: '文章管理' },
  { key: 'data', label: '数据管理' },
  { key: 'reports', label: '报告模板' },
  { key: 'knowledge', label: '知识库管理' },
  { key: 'business', label: '业务平台' },
  { key: 'system', label: '系统设置' }
]

const activeTab = ref('users')

// 用户管理
const users = ref([])
const validUsers = computed(() => (users.value || []).filter(u => u.username))
const isAdminUser = computed(() => editingUser.value?.username === 'admin')
const showAddUser = ref(false)
const editingUser = ref(null)
const userForm = ref({ username: '', password: '', role: 'user' })
const userSaving = ref(false)
const showPermissionsEditor = ref(false)
const editingPermissionsUser = ref(null)
const editingPermissions = ref({})
const permissionsSaving = ref(false)
const roleMap = {
  admin: '管理员',
  user: '普通用户'
}

// 知识库管理
const knowledgeSubTab = ref('general')

// 通用知识库管理（对齐统一库 unified_kb）
const kbTypeMeta = {
  standard: { label: '立结案标准', icon: 'standard', color: 'var(--primary-500)', bg: 'var(--primary-50)' },
  org:      { label: '职责机构',   icon: 'org',      color: 'var(--warning)',    bg: 'var(--warning-light)' },
  qa:       { label: '知识问答',   icon: 'qa',       color: 'var(--success)',    bg: 'var(--success-light)' },
  general:  { label: '通用制度',   icon: 'general',  color: 'var(--info)',       bg: 'var(--info-light)' },
  law:      { label: '法律法规',   icon: 'law',      color: 'var(--danger)',     bg: 'var(--danger-light)' },
}
const kbTypeList = Object.keys(kbTypeMeta).map(k => ({ key: k, ...kbTypeMeta[k] }))
function typeLabel(k) { return (kbTypeMeta[k] || {}).label || k }
function typeColor(k) { return (kbTypeMeta[k] || { color: 'var(--info)' }).color }
function typeBg(k) { return (kbTypeMeta[k] || { bg: 'var(--info-light)' }).bg }
function typeIcon(k) { return (kbTypeMeta[k] || { icon: 'file-text' }).icon }

const kbOverview = ref({ exists: false, total: 0, by_type: {}, source: null })
const kbRebuilding = ref(false)
const kbRebuildStatus = ref(null)
const kbRebuildTimer = ref(null)

const kbDocs = ref([])
const kbDocTotal = ref(0)
const kbDocsLoading = ref(false)
const kbSelectedDocs = ref([])
const kbDocFilter = ref('')
const kbDocKeyword = ref('')
const kbDocPage = ref(1)
const kbDocPageSize = 50

function pct(done, total) {
  if (!total) return 0
  return Math.min(100, Math.round((done / total) * 100))
}

async function loadKbOverview() {
  try {
    const res = await axios.get('/api/kb/admin/overview')
    kbOverview.value = res.data || { exists: false, total: 0, by_type: {}, source: null }
  } catch (e) {
    console.error('加载知识库概览失败:', e)
  }
}

async function rebuildKb() {
  if (kbRebuilding.value) return
  if (!confirm('确认重建索引？将删除并重新灌入统一库（约 6000+ 条），耗时约 1-2 分钟。')) return
  kbRebuilding.value = true
  kbRebuildStatus.value = { status: 'running', stage: 'pending', done: 0, total: 0, message: '正在启动重建任务…' }
  try {
    const res = await axios.post('/api/kb/admin/rebuild', {})
    const taskId = res.data.task_id
    if (kbRebuildTimer.value) clearInterval(kbRebuildTimer.value)
    kbRebuildTimer.value = setInterval(async () => {
      try {
        const p = await axios.get(`/api/kb/admin/rebuild/${taskId}`)
        kbRebuildStatus.value = p.data
        if (p.data.status === 'success' || p.data.status === 'error') {
          clearInterval(kbRebuildTimer.value)
          kbRebuildTimer.value = null
          kbRebuilding.value = false
          loadKbOverview()
          loadKbDocs()
        }
      } catch (e) {
        clearInterval(kbRebuildTimer.value)
        kbRebuildTimer.value = null
        kbRebuilding.value = false
      }
    }, 1500)
  } catch (e) {
    kbRebuilding.value = false
    kbRebuildStatus.value = { status: 'error', message: '重建请求失败: ' + (e.response?.data?.error || e.message) }
  }
}

async function loadKbDocs() {
  kbDocsLoading.value = true
  try {
    const params = { page: kbDocPage.value, page_size: kbDocPageSize, doc_type: kbDocFilter.value || undefined, keyword: kbDocKeyword.value || undefined }
    const res = await axios.get('/api/kb/admin/documents', { params })
    kbDocs.value = res.data.items || []
    kbDocTotal.value = res.data.total || 0
    kbSelectedDocs.value = []
  } catch (e) {
    console.error('加载文档列表失败:', e)
    kbDocs.value = []
  } finally {
    kbDocsLoading.value = false
  }
}

function toggleKbSelectAll(e) {
  if (e.target.checked) kbSelectedDocs.value = kbDocs.value.map(d => d.doc_id)
  else kbSelectedDocs.value = []
}

async function deleteKbDoc(docId) {
  if (!confirm(`确认删除文档「${docId}」及其全部片段？`)) return
  try {
    await axios.delete(`/api/kb/admin/documents/${encodeURIComponent(docId)}`)
    loadKbDocs()
    loadKbOverview()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

async function batchDeleteKbDocs() {
  if (kbSelectedDocs.value.length === 0) return
  if (!confirm(`确认删除选中的 ${kbSelectedDocs.value.length} 个文档？`)) return
  try {
    await axios.post('/api/kb/admin/documents/batch-delete',
      { doc_ids: kbSelectedDocs.value })
    kbSelectedDocs.value = []
    loadKbDocs()
    loadKbOverview()
  } catch (e) {
    alert('批量删除失败: ' + (e.response?.data?.error || e.message))
  }
}


// 数据管理

// 报告模板管理
const reportTemplates = ref([])
const reportTemplatesLoading = ref(false)
const showReportEditor = ref(false)
const editingReport = ref(null)
const reportForm = ref({ name: '', description: '', report_type: 'single', sections: [] })
const reportSaving = ref(false)

// Word模板上传
const showTemplateUploader = ref(false)
const templateUploading = ref(false)
const templateUploadResult = ref(null)
const templateSaving = ref(false)
const isDragging = ref(false)

// 业务管理
const platforms = ref([])
const showPlatformEditor = ref(false)
const editingPlatform = ref(null)
const platformForm = ref({
  name: '',
  url: '',
  image_path: ''
})
const platformSaving = ref(false)

// 系统设置：直接使用全局共享配置（与侧边栏/登录页同一份，保存后全站实时生效）
const { config: systemConfig, loadSystemConfig, saveSystemConfig: _saveSystemConfig } = useSystemConfig()

// 文章管理
const articles = ref([])
const articlesLoading = ref(false)
const articlesCurrentPage = ref(1)
const articlesTotalPages = ref(1)
const selectedArticleCategory = ref('all')
const articleCategories = ref([{ id: 'all', name: '全部' }])
const categoryList = ref([])
const showArticleEditor = ref(false)
const showCategoryManager = ref(false)
const showCategoryEditor = ref(false)
const editingArticle = ref(null)
const editingCategory = ref({})
const newCategoryName = ref('')
const articleSaving = ref(false)
const uploadingImage = ref(false)
const uploadingFile = ref(false)
const uploadingLogo = ref(false)
const articleForm = ref({
  title: '',
  category_id: '',
  summary: '',
  content: '',
  file_path: ''
})

// wangEditor配置
const editorRef = shallowRef(null)
const mode = ref('default')
const toolbarConfig = {}
const editorConfig = {
  placeholder: '请输入文章内容...',
  MENU_CONF: {
    uploadImage: {
      server: '/api/upload/image',
      fieldName: 'file',
      maxFileSize: 10 * 1024 * 1024,
      allowedFileTypes: ['image/*'],
      meta: {},
      onBeforeUpload: (file) => {
        return file
      },
      customInsert: (res, insertFn) => {
        insertFn(res.location, '', '')
      }
    }
  }
}

function handleEditorCreated(editor) {
  editorRef.value = editor
}

// 方法
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}


// ===== 报告模板管理 =====
async function loadReportTemplates() {
  reportTemplatesLoading.value = true
  try {
    const res = await axios.get('/api/report-templates')
    reportTemplates.value = res.data.templates || []
  } catch (e) {
    console.error('加载报告模板失败:', e)
  } finally {
    reportTemplatesLoading.value = false
  }
}

function openReportEditor(template) {
  editingReport.value = template
  reportForm.value = {
    name: template.name,
    description: template.description || '',
    report_type: template.report_type || 'single',
    sections: JSON.parse(JSON.stringify(template.sections || [])),
  }
  showReportEditor.value = true
}

function closeReportEditor() {
  showReportEditor.value = false
  editingReport.value = null
}

function addReportSection() {
  reportForm.value.sections.push({
    title: '',
    query: '',
    chart_type: 'bar',
    charts: [{ name: '', chart_type: 'bar', query: '' }]
  })
}

function addChart(sectionIdx) {
  const sec = reportForm.value.sections[sectionIdx]
  if (!sec.charts) sec.charts = []
  sec.charts.push({ name: '', chart_type: 'bar', query: '' })
}

function removeChart(sectionIdx, chartIdx) {
  const sec = reportForm.value.sections[sectionIdx]
  if (!sec.charts) return
  sec.charts.splice(chartIdx, 1)
  // 至少保留一个图表
  if (sec.charts.length === 0) {
    sec.charts.push({ name: '', chart_type: 'bar', query: '' })
  }
}

function removeReportSection(index) {
  reportForm.value.sections.splice(index, 1)
}

function moveReportSection(index, dir) {
  const sections = reportForm.value.sections
  const target = index + dir
  if (target < 0 || target >= sections.length) return
  const temp = sections[index]
  sections[index] = sections[target]
  sections[target] = temp
}

async function saveReport() {
  if (!reportForm.value.name.trim()) return alert('请输入模板名称')
  if (!reportForm.value.sections.length) return alert('请至少添加一个章节')
  if (!editingReport.value) return

  reportSaving.value = true
  try {
    const payload = { ...reportForm.value }
    await axios.put(`/api/report-templates/${editingReport.value.id}`, payload)
    closeReportEditor()
    await loadReportTemplates()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.error || e.message))
  } finally {
    reportSaving.value = false
  }
}

async function deleteReport(template) {
  if (!confirm(`确定删除模板"${template.name}"？`)) return
  try {
    await axios.delete(`/api/report-templates/${template.id}`)
    await loadReportTemplates()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.error || e.message))
  }
}

function executeReport(template) {
  router.push(`/report/${template.id}`)
}

// Word模板上传相关函数
function closeTemplateUploader() {
  showTemplateUploader.value = false
  templateUploadResult.value = null
  templateUploading.value = false
}

function handleTemplateFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    uploadTemplate(file)
  }
}

function handleTemplateDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer.files[0]
  if (file && file.name.endsWith('.docx')) {
    uploadTemplate(file)
  } else {
    alert('请上传 .docx 格式的文件')
  }
}

async function uploadTemplate(file) {
  if (!file.name.endsWith('.docx')) {
    alert('只支持 .docx 格式文件')
    return
  }

  templateUploading.value = true
  templateUploadResult.value = null

  try {
    const formData = new FormData()
    formData.append('file', file)

    const res = await axios.post('/api/report-templates/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (res.data.success) {
      templateUploadResult.value = res.data
    } else {
      alert('上传失败: ' + (res.data.error || '未知错误'))
    }
  } catch (e) {
    alert('上传失败: ' + (e.response?.data?.error || e.message))
  } finally {
    templateUploading.value = false
  }
}

async function createFromTemplate() {
  if (!templateUploadResult.value) return

  templateSaving.value = true
  try {
    const result = templateUploadResult.value
    const structure = result.structure || {}

    // 从解析的结构创建模板（保留 Word 中识别出的多图表层级）
    const sections = (structure.sections || []).map(sec => ({
      title: sec.title || '',
      query: sec.query || '',
      chart_type: sec.chart_type || 'bar',
      charts: (sec.charts || []).map(c => ({
        name: c.name || '',
        chart_type: c.chart_type || 'bar',
        query: c.query || '',
        description: c.description || '',
        image_paragraph_index: c.image_paragraph_index,
      })),
      image_paragraph_index: sec.image_paragraph_index,
      caption_paragraph_index: sec.caption_paragraph_index,
      table_index: sec.table_index,
    }))

    const payload = {
      name: result.original_filename.replace('.docx', ''),
      description: `从Word模板导入 - ${result.original_filename}`,
      report_type: ((result.original_filename || '').includes('对比') || (result.original_filename || '').toLowerCase().includes('compare')) ? 'compare' : 'single',
      sections: sections,
      template_file: result.file_path,
      template_structure: structure,
    }

    const res = await axios.post('/api/report-templates', payload)

    if (res.data.success) {
      closeTemplateUploader()
      await loadReportTemplates()
    } else {
      alert('创建失败: ' + (res.data.error || '未知错误'))
    }
  } catch (e) {
    console.error('Create template error:', e)
    alert('创建失败: ' + (e.response?.data?.error || e.message))
  } finally {
    templateSaving.value = false
  }
}

// ===== 数据管理方法 =====












// ===== 小工具方法 =====
function handleToolFileSelect(tool, e) {
  toolFiles.value[tool] = e.target.files[0] || null
  toolMessages.value[tool] = ''
  toolErrors.value[tool] = ''
}

async function processToolFile(tool, endpoint) {
  if (!toolFiles.value[tool]) return

  toolLoading.value[tool] = true
  toolMessages.value[tool] = ''
  toolErrors.value[tool] = ''

  const formData = new FormData()
  formData.append('file', toolFiles.value[tool])

  try {
    const response = await axios.post(endpoint, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob'
    })
    // 下载处理后的文件
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `processed_${toolFiles.value[tool].name}`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    toolMessages.value[tool] = '处理完成，文件已下载'
  } catch (error) {
    toolErrors.value[tool] = error.response?.data?.error || '处理失败'
  } finally {
    toolLoading.value[tool] = false
  }
}

function processHuanwei() {
  processToolFile('huanwei', '/api/tools/huanwei-assignment')
}

function processLocation() {
  processToolFile('location', '/api/tools/extract-location')
}

// 数据脱敏处理
async function handleDesensitizationFileSelect(e) {
  const file = e.target.files[0]
  if (!file) return

  desensitizationFileName.value = file.name
  toolFiles.value.desensitization = file
  toolMessages.value.desensitization = ''
  toolErrors.value.desensitization = ''
  desensitizationFields.value = []
  desensitizationConfig.value = {}

  toolLoading.value.desensitization = true
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/tools/data-desensitization/fields', formData)
    desensitizationFields.value = response.data.fields || []
    desensitizationFields.value.forEach(f => {
      desensitizationConfig.value[f] = ''
    })
  } catch (error) {
    toolErrors.value.desensitization = error.response?.data?.error || '读取字段失败'
  } finally {
    toolLoading.value.desensitization = false
  }
}

async function processDesensitization() {
  if (!toolFiles.value.desensitization) {
    toolErrors.value.desensitization = '请先上传文件'
    return
  }

  const selectedFields = {}
  Object.keys(desensitizationConfig.value).forEach(field => {
    if (desensitizationConfig.value[field]) {
      selectedFields[field] = desensitizationConfig.value[field]
    }
  })

  if (Object.keys(selectedFields).length === 0) {
    toolErrors.value.desensitization = '请至少选择一个字段进行脱敏'
    return
  }

  toolLoading.value.desensitization = true
  toolMessages.value.desensitization = ''
  toolErrors.value.desensitization = ''

  const formData = new FormData()
  formData.append('file', toolFiles.value.desensitization)
  formData.append('fields', JSON.stringify(selectedFields))

  try {
    const response = await axios.post('/api/tools/data-desensitization', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'desensitized_data.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
    toolMessages.value.desensitization = '脱敏完成，文件已下载'
  } catch (error) {
    toolErrors.value.desensitization = error.response?.data?.error || '处理失败'
  } finally {
    toolLoading.value.desensitization = false
  }
}

function resetDesensitization() {
  desensitizationFileName.value = ''
  toolFiles.value.desensitization = null
  desensitizationFields.value = []
  desensitizationConfig.value = {}
  toolMessages.value.desensitization = ''
  toolErrors.value.desensitization = ''
  if (desensitizationFileInput.value) {
    desensitizationFileInput.value.value = ''
  }
}

// ===== 用户管理方法 =====
async function fetchUsers() {
  try {
    const response = await axios.get('/api/users')
    users.value = response.data.users || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

function editUser(user) {
  editingUser.value = user
  userForm.value = {
    username: user.username,
    password: '',
    role: user.role
  }
  showAddUser.value = true
}

function openAddUserModal() {
  editingUser.value = null
  userForm.value = { username: '', password: '', role: 'user' }
  showAddUser.value = true
}

function closeUserEditor() {
  showAddUser.value = false
  editingUser.value = null
  userForm.value = { username: '', password: '', role: 'user' }
}

async function saveUser() {
  if (!userForm.value.username.trim()) {
    alert('请输入用户名')
    return
  }
  if (!editingUser.value && !userForm.value.password) {
    alert('请输入密码')
    return
  }

  userSaving.value = true
  try {
    const data = {
      username: userForm.value.username,
      role: userForm.value.role
    }
    if (userForm.value.password) {
      data.password = userForm.value.password
    }

    if (editingUser.value) {
      await axios.put(`/api/users/${editingUser.value.id}`, data)
    } else {
      await axios.post('/api/users', data)
    }
    closeUserEditor()
    fetchUsers()
  } catch (error) {
    alert(error.response?.data?.error || '保存失败')
  } finally {
    userSaving.value = false
  }
}

async function deleteUser(user) {
  if (user.id === 1) {
    alert('不能删除管理员账户')
    return
  }
  if (!confirm(`确定删除用户 ${user.username}？`)) return

  try {
    await axios.delete(`/api/users/${user.id}`)
    fetchUsers()
  } catch (error) {
    alert(error.response?.data?.error || '删除失败')
  }
}

function openPermissionsEditor(user) {
  editingPermissionsUser.value = user
  // 确保所有权限字段都有值，并将整数转换为布尔值
  const perms = user.permissions || {}
  editingPermissions.value = {
    data_management: Boolean(perms.data_management),
    data_analysis: Boolean(perms.data_analysis),
    map: Boolean(perms.map),
    business: Boolean(perms.business)
  }
  showPermissionsEditor.value = true
}

function closePermissionsEditor() {
  showPermissionsEditor.value = false
  editingPermissionsUser.value = null
  editingPermissions.value = {}
}

async function savePermissions() {
  permissionsSaving.value = true
  try {
    // 确保发送布尔值
    const dataToSend = {
      data_management: Boolean(editingPermissions.value.data_management),
      data_analysis: Boolean(editingPermissions.value.data_analysis),
      map: Boolean(editingPermissions.value.map),
      business: Boolean(editingPermissions.value.business)
    }
    await axios.put(`/api/users/${editingPermissionsUser.value.id}/permissions`, dataToSend)
    closePermissionsEditor()
    fetchUsers()
  } catch (error) {
    alert(error.response?.data?.error || '保存失败')
  } finally {
    permissionsSaving.value = false
  }
}

// ===== 业务管理方法 =====
async function fetchPlatforms() {
  try {
    const response = await axios.get('/api/business-platforms')
    platforms.value = response.data.platforms || []
  } catch (error) {
    console.error('获取平台列表失败:', error)
  }
}

function openPlatformEditor(platform = null) {
  editingPlatform.value = platform
  if (platform) {
    platformForm.value = {
      name: platform.name,
      url: platform.url,
      image_path: platform.image_path || ''
    }
  } else {
    platformForm.value = {
      name: '',
      url: '',
      image_path: ''
    }
  }
  showPlatformEditor.value = true
}

function closePlatformEditor() {
  showPlatformEditor.value = false
  editingPlatform.value = null
}

async function savePlatform() {
  if (!platformForm.value.name.trim()) {
    alert('请输入平台名称')
    return
  }
  if (!platformForm.value.url.trim()) {
    alert('请输入链接地址')
    return
  }

  platformSaving.value = true
  try {
    if (editingPlatform.value) {
      await axios.put(`/api/business-platforms/${editingPlatform.value.id}`, platformForm.value)
    } else {
      await axios.post('/api/business-platforms', platformForm.value)
    }
    closePlatformEditor()
    fetchPlatforms()
  } catch (error) {
    console.error('保存平台失败:', error)
    alert(error.response?.data?.error || '保存失败')
  } finally {
    platformSaving.value = false
  }
}

async function deletePlatform(platform) {
  if (!confirm(`确定删除平台「${platform.name}」？`)) return

  try {
    await axios.delete(`/api/business-platforms/${platform.id}`)
    fetchPlatforms()
  } catch (error) {
    console.error('删除平台失败:', error)
    alert(error.response?.data?.error || '删除失败')
  }
}

function onImageError(e) {
  e.target.style.display = 'none'
}

async function handlePlatformImage(e) {
  const file = e.target.files[0]
  if (!file) return

  // 检查文件类型
  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    alert('只支持 JPG、PNG、GIF、WebP 格式的图片')
    return
  }

  // 检查文件大小（最大 2MB）
  if (file.size > 2 * 1024 * 1024) {
    alert('图片大小不能超过 2MB')
    return
  }

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post('/api/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    platformForm.value.image_path = response.data.location
  } catch (error) {
    console.error('上传图片失败:', error)
    alert(error.response?.data?.error || '上传失败')
  }

  // 清空input，允许重复选择同一文件
  e.target.value = ''
}

function removePlatformImage() {
  platformForm.value.image_path = ''
}

// ===== 系统设置方法 =====
// 配置已由 App.vue 启动时统一加载（全局共享），此处打开设置页时再拉取一次确保为最新落库值
async function fetchSystemConfig() {
  try {
    await loadSystemConfig()
  } catch (error) {
    console.error('获取系统配置失败:', error)
  }
}

async function saveSystemConfig() {
  try {
    await _saveSystemConfig({ name: systemConfig.name, logo: systemConfig.logo })
    alert('保存成功，全站名称与图标已更新')
  } catch (error) {
    console.error('保存系统配置失败:', error)
    alert('保存失败')
  }
}

// 系统 Logo 上传：选本地图片 → 调 /api/upload/image → 回填 URL
async function handleLogoUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  uploadingLogo.value = true
  const formData = new FormData()
  formData.append('file', file)
  try {
    const response = await axios.post('/api/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    systemConfig.logo = response.data.location || response.data.url
    alert('Logo 已上传，点击"保存设置"即可全站生效')
  } catch (error) {
    console.error('上传 Logo 失败:', error)
    alert('上传 Logo 失败：' + (error.response?.data?.error || error.message))
  } finally {
    uploadingLogo.value = false
    e.target.value = ''
  }
}

// ===== 文章管理方法 =====
async function fetchCategories() {
  try {
    const response = await axios.get('/api/categories')
    categoryList.value = response.data.categories || []
    articleCategories.value = [
      { id: 'all', name: '全部' },
      ...categoryList.value.map(c => ({ id: c.id, name: c.name }))
    ]
  } catch (error) {
    console.error('获取栏目失败:', error)
  }
}

async function fetchArticles() {
  articlesLoading.value = true
  try {
    const params = {
      page: articlesCurrentPage.value,
      per_page: 10,
      include_drafts: 'true'
    }
    if (selectedArticleCategory.value !== 'all') {
      params.category_id = selectedArticleCategory.value
    }
    const response = await axios.get('/api/articles', { params })
    articles.value = response.data.articles || []
    const total = response.data.total || 0
    articlesTotalPages.value = Math.ceil(total / 10) || 1
  } catch (error) {
    console.error('获取文章列表失败:', error)
  } finally {
    articlesLoading.value = false
  }
}

function selectArticleCategory(categoryId) {
  selectedArticleCategory.value = categoryId
  articlesCurrentPage.value = 1
  fetchArticles()
}

function getArticleCategoryName(categoryId) {
  const cat = categoryList.value.find(c => c.id === categoryId)
  return cat ? cat.name : '未分类'
}

async function openArticleEditor(article = null) {
  if (article) {
    try {
      articlesLoading.value = true
      const response = await axios.get(`/api/articles/${article.id}`)
      const fullArticle = response.data
      editingArticle.value = fullArticle
      articleForm.value = {
        title: fullArticle.title,
        category_id: fullArticle.category_id,
        summary: fullArticle.summary || '',
        content: fullArticle.content || '',
        file_path: fullArticle.file_path || ''
      }
    } catch (error) {
      console.error('获取文章详情失败:', error)
      alert('获取文章详情失败')
      return
    } finally {
      articlesLoading.value = false
    }
  } else {
    editingArticle.value = null
    articleForm.value = { title: '', category_id: '', summary: '', content: '', file_path: '' }
  }
  showArticleEditor.value = true
}

function closeArticleEditor() {
  showArticleEditor.value = false
  editingArticle.value = null
  // 销毁编辑器实例
  if (editorRef.value) {
    editorRef.value.destroy()
    editorRef.value = null
  }
}

async function handleImageUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  uploadingImage.value = true
  const formData = new FormData()
  formData.append('file', file)
  try {
    const response = await axios.post('/api/upload/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    const imageUrl = response.data.location
    // 插入到编辑器
    if (editorRef.value) {
      editorRef.value.insertNode({
        type: 'image',
        src: imageUrl,
        alt: file.name,
        style: { width: '100%' }
      })
    }
  } catch (error) {
    console.error('上传图片失败:', error)
    alert('上传图片失败')
  } finally {
    uploadingImage.value = false
    e.target.value = ''
  }
}

async function handleFileUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  uploadingFile.value = true
  const formData = new FormData()
  formData.append('file', file)
  try {
    const response = await axios.post('/api/upload/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    articleForm.value.file_path = response.data.file_path
  } catch (error) {
    console.error('上传附件失败:', error)
    alert('上传附件失败')
  } finally {
    uploadingFile.value = false
    e.target.value = ''
  }
}

async function saveArticle() {
  if (!articleForm.value.title.trim()) { alert('请输入文章标题'); return }
  if (!articleForm.value.category_id) { alert('请选择所属栏目'); return }
  if (!articleForm.value.content.trim()) { alert('请输入文章内容'); return }

  articleSaving.value = true
  try {
    const dataToSave = { ...articleForm.value, status: 'published' }
    if (editingArticle.value) {
      await axios.put(`/api/articles/${editingArticle.value.id}`, dataToSave)
    } else {
      await axios.post('/api/articles', dataToSave)
    }
    closeArticleEditor()
    fetchArticles()
  } catch (error) {
    console.error('保存文章失败:', error)
    alert(error.response?.data?.error || '保存失败')
  } finally {
    articleSaving.value = false
  }
}

async function deleteArticle(article) {
  if (!confirm(`确定删除文章「${article.title}」？`)) return
  try {
    await axios.delete(`/api/articles/${article.id}`)
    fetchArticles()
  } catch (error) {
    console.error('删除文章失败:', error)
    alert(error.response?.data?.error || '删除失败')
  }
}

async function addCategory() {
  if (!newCategoryName.value.trim()) return
  try {
    await axios.post('/api/categories', { name: newCategoryName.value.trim() })
    newCategoryName.value = ''
    fetchCategories()
  } catch (error) {
    console.error('添加栏目失败:', error)
    alert(error.response?.data?.error || '添加失败')
  }
}

function editCategory(category) {
  editingCategory.value = { ...category }
  showCategoryEditor.value = true
}

async function updateCategory() {
  try {
    await axios.put(`/api/categories/${editingCategory.value.id}`, {
      name: editingCategory.value.name,
      description: editingCategory.value.description,
      order: editingCategory.value.order
    })
    showCategoryEditor.value = false
    fetchCategories()
  } catch (error) {
    console.error('更新栏目失败:', error)
    alert(error.response?.data?.error || '更新失败')
  }
}

async function deleteCategory(category) {
  if (!confirm(`确定删除栏目「${category.name}」？\n注意：该栏目下有文章时无法删除。`)) return
  try {
    await axios.delete(`/api/categories/${category.id}`)
    fetchCategories()
  } catch (error) {
    console.error('删除栏目失败:', error)
    alert(error.response?.data?.error || '删除失败')
  }
}

// ===== 数据编辑 =====
const editColumns = ref([])

// 记录弹窗
const isAddRecord = ref(true)

// 批量修改弹窗

// 删除确认
const deleteTarget = ref(null)  // { type: 'single' | 'batch', taskNumber? }

// 操作日志



























// ===== 操作日志 =====
async function fetchLogs() {
  logsLoading.value = true
  try {
    const params = new URLSearchParams({
      page: logPage.value,
      page_size: 20
    })
    if (logTable.value) params.append('table_name', logTable.value)
    if (logType.value) params.append('operation_type', logType.value)
    const response = await axios.get(`/api/operation-logs?${params}`)
    logs.value = response.data.logs || []
    logTotal.value = response.data.total || 0
    logTotalPages.value = Math.ceil(logTotal.value / 20)
  } catch (error) {
    console.error('获取日志失败:', error)
  } finally {
    logsLoading.value = false
  }
}

function viewLogDetail(log) {
  logDetail.value = log
  showLogDetailModal.value = true
}

function formatJson(str) {
  if (!str) return ''
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch {
    return str
  }
}

function formatMonth(month) {
  if (!month || month.length < 6) return month || ''
  const year = month.substring(0, 4)
  const m = month.substring(4, 6)
  return `${year}年${m}月`
}

onMounted(() => {
  fetchUsers()
  fetchPlatforms()
  fetchSystemConfig()
  fetchCategories()
  fetchArticles()
})

// 切换到知识库管理tab时自动加载列表
watch(activeTab, (newTab) => {
  if (newTab === 'knowledge') {
    loadKbOverview()
    loadKbDocs()
  } else if (newTab === 'reports') {
    loadReportTemplates()
  }
})

// 切换知识库子标签时加载对应数据
watch(knowledgeSubTab, (newSubTab) => {
  if (activeTab.value === 'knowledge' && newSubTab === 'general') {
    loadKbOverview()
    loadKbDocs()
  }
})

watch(articlesCurrentPage, fetchArticles)
</script>

<style scoped>
/* ===== 系统 Logo 上传 ===== */
.logo-upload {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 10px;
}
.logo-preview {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e3e8ef);
  background: #f7f9fc;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}
.logo-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.logo-preview--empty {
  color: #9aa5b5;
  font-size: 12px;
}
.logo-upload__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-container {
  padding: var(--space-6);
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-6);
}

.tabs {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.tab {
  padding: var(--space-3) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab:hover { color: var(--primary-500); }
.tab.active { color: var(--primary-500); border-bottom-color: var(--primary-500); }

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
  padding: var(--space-6);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.header-actions {
  display: flex;
  gap: var(--space-3);
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* 按钮样式 */
.btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-primary {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.btn-primary:hover { background: var(--primary-600); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  background: var(--bg-card);
  color: var(--text-primary);
  border-color: var(--border-lighter);
}

.btn-secondary:hover { border-color: var(--primary-300); }

.btn-danger {
  background: var(--danger);
  color: white;
  border-color: var(--danger);
}

.btn-danger:hover:not(:disabled) { background: var(--danger-dark); }

.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-icon:hover {
  border-color: var(--primary-300);
  color: var(--primary-500);
  background: var(--primary-50);
}

.btn-icon.danger:hover {
  border-color: var(--danger-light);
  color: var(--danger);
  background: rgba(245, 108, 108, 0.1);
}

.btn-text {
  background: none;
  border: none;
  color: var(--primary-500);
  cursor: pointer;
  padding: var(--space-1) var(--space-2);
}

.btn-text:hover { text-decoration: underline; }
.btn-text.danger { color: var(--danger); }

/* 表格样式 */
.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  border-bottom: 1px solid var(--border-lighter);
}

.data-table th {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-secondary);
}

.data-table td {
  color: var(--text-primary);
}

.role-badge {
  padding: 2px 8px;
  font-size: 12px;
  border-radius: var(--radius-full);
}

.role-badge.admin { background: var(--primary-100); color: var(--primary-700); }
.role-badge.user { background: var(--neutral-100); color: var(--neutral-700); }

.link {
  color: var(--primary-500);
  text-decoration: none;
}

.link:hover { text-decoration: underline; }

.empty-text {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--space-4);
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-8);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--text-tertiary);
}

.empty-state svg { opacity: 0.3; }

/* 弹窗样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
}

.modal-record {
  max-width: 500px;
}

.modal-body-scroll {
  overflow-y: auto;
  max-height: 60vh;
}

.platform-editor { max-width: 500px; }

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--border-lighter);
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.btn-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.btn-close:hover {
  background: var(--fill-light);
  color: var(--text-primary);
}

.modal-body {
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-lighter);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.form-input,
.form-select,
.form-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: 14px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-100);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.content-editor {
  min-height: 400px;
}

.settings-form {
  max-width: 500px;
}

/* 平台管理样式 */
.platform-thumb {
  width: 48px;
  height: 48px;
  object-fit: contain;
  border-radius: var(--radius-sm);
  background: var(--fill-light);
}

.no-image {
  color: var(--text-tertiary);
  font-size: 12px;
}

.platform-editor {
  max-width: 500px;
}

.form-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.upload-area:hover {
  border-color: var(--primary-400);
  background: var(--fill-light);
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
}

.upload-preview {
  position: relative;
  display: inline-block;
}

.upload-preview img {
  max-width: 150px;
  max-height: 150px;
  border-radius: var(--radius-md);
}

.remove-image {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--danger);
  color: white;
  border: none;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-image:hover {
  background: var(--danger-dark);
}

.image-preview {
  max-width: 200px;
  max-height: 200px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-lighter);
}

/* 数据管理样式 */
.data-section {
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--border-lighter);
}

.data-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.subsection-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-4);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.section-actions {
  display: flex;
  gap: var(--space-3);
}

.upload-options {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-4);
}

.radio-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  color: var(--text-primary);
}

.append-options {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.append-options .form-group {
  margin-bottom: 0;
}

.append-hint {
  width: 100%;
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.append-hint p {
  margin: 0 0 var(--space-2) 0;
}

.append-hint p:last-child {
  margin-bottom: 0;
}

.append-hint strong {
  color: var(--color-primary);
}

.append-hint .field-list {
  font-family: monospace;
  padding: var(--space-2);
  background: rgba(0, 0, 0, 0.05);
  border-radius: var(--radius-sm);
}

.file-upload-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.file-name {
  color: var(--text-secondary);
  font-size: 14px;
}


/* 小工具样式 */
.tools-tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--border-lighter);
}

.tool-tab {
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-tab:hover { color: var(--primary-500); }
.tool-tab.active { color: var(--primary-500); border-bottom-color: var(--primary-500); }

.tool-section {
  max-width: 600px;
}

.tool-description {
  margin-bottom: var(--space-4);
}

.tool-description p {
  margin: 0 0 var(--space-2);
  color: var(--text-secondary);
}

.tool-description .hint {
  font-size: 13px;
  color: var(--text-tertiary);
}

.tool-upload {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

/* 数据脱敏样式 */
.desensitization-fields {
  margin-top: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.desensitization-fields h4 {
  margin: 0 0 var(--space-4);
  color: var(--text-primary);
}

.field-list {
  max-height: 300px;
  overflow-y: auto;
}

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-lighter);
}

.field-row:last-child {
  border-bottom: none;
}

.field-name {
  font-size: 14px;
  color: var(--text-primary);
}

.field-select {
  padding: var(--space-1) var(--space-3);
  font-size: 13px;
  min-width: 140px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
}

.btn-group {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

/* 权限编辑样式 */
.permissions-editor {
  max-width: 400px;
}

.permissions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}

.permission-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.permission-item:hover {
  background: var(--fill-light);
}

/* 消息样式 */
.message {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  margin-top: var(--space-4);
  font-size: 14px;
}

.message.success {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.message.error {
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
  border: 1px solid rgba(245, 108, 108, 0.3);
}

/* 弹窗样式补充 */
.add-user-editor,
.permissions-editor {
  max-width: 400px;
}

@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: var(--space-4);
    align-items: flex-start;
  }

  .form-row {
    grid-template-columns: 1fr;
  }


  .permissions-grid {
    grid-template-columns: 1fr;
  }

  .upload-options {
    flex-direction: column;
    gap: var(--space-2);
  }

  .append-options {
    flex-direction: column;
  }

  .file-upload-row {
    flex-wrap: wrap;
  }

  .tool-upload {
    flex-wrap: wrap;
  }
}

/* 文章管理样式 */
.category-nav {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.category-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.category-btn:hover { border-color: var(--primary-300); }
.category-btn.active {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.articles-list {
  display: flex;
  flex-direction: column;
}

.article-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
  transition: background var(--transition-fast);
}

.article-item:last-child { border-bottom: none; }
.article-item:hover { background: var(--fill-light); }

.article-info { flex: 1; }
.article-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.article-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.article-meta {
  display: flex;
  gap: var(--space-3);
  font-size: 13px;
  color: var(--text-tertiary);
}

.category-tag { color: var(--primary-500); }

.attachment-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  font-size: 11px;
  background: var(--primary-50);
  color: var(--primary-600);
  border-radius: var(--radius-sm);
}

.article-actions {
  display: flex;
  gap: var(--space-2);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-lighter);
}

.pagination-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.pagination-btn:hover:not(:disabled) { border-color: var(--primary-500); color: var(--primary-500); }
.pagination-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { color: var(--text-secondary); font-size: 14px; }

.article-editor { max-width: 900px; }
.category-manager { max-width: 500px; }
.category-editor { max-width: 400px; }

.editor-container {
  border: 1px solid #ccc;
  border-radius: 4px;
  z-index: 100;
}

.content-editor {
  min-height: 400px;
}

.add-category {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.add-category .form-input { flex: 1; }

.category-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.category-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.category-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-name {
  font-weight: 500;
  color: var(--text-primary);
}

.category-slug {
  font-size: 12px;
  color: var(--text-tertiary);
}

.category-actions {
  display: flex;
  gap: var(--space-1);
}

.upload-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.attachment-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
}

.attachment-info svg { color: var(--primary-500); }

.btn-link {
  background: none;
  border: none;
  color: var(--danger);
  cursor: pointer;
  font-size: 12px;
  text-decoration: underline;
}

.btn-link:hover { color: var(--danger-dark); }

/* 数据编辑样式 */
.filter-section {
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-lighter);
}

.filter-row {
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
  margin-bottom: var(--space-3);
}

.filter-row:last-child {
  margin-bottom: 0;
}

.filter-group {
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
  padding: var(--space-3);
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-lighter);
}

.filter-row .form-group {
  margin-bottom: 0;
  min-width: 150px;
}

.action-bar {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  margin-bottom: var(--space-4);
}

.selection-info {
  margin-left: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--primary-100);
  color: var(--primary-600);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding: var(--space-4);
}

.pagination button {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--border);
  background: white;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination button:hover:not(:disabled) {
  background: var(--fill-light);
}

.empty-state {
  text-align: center;
  padding: var(--space-8);
  color: var(--text-secondary);
}

/* 操作日志样式 */
.op-type {
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.op-type.create {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
}

.op-type.update {
  background: rgba(230, 162, 60, 0.1);
  color: #e6a23c;
}

.op-type.delete {
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
}

.log-detail p {
  margin: var(--space-2) 0;
}

.json-display {
  background: var(--fill-dark);
  color: #e6e6e6;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-size: 12px;
  max-height: 300px;
  white-space: pre-wrap;
  word-break: break-all;
}

.modal-large {
  max-width: 700px;
}

.modal-small {
  max-width: 400px;
}

.batch-info {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}

/* 标准库管理样式 */
.stats-card {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  background: var(--fill-light);
  border-radius: var(--radius-md);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-3) var(--space-5);
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--primary-500);
}

.stat-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: var(--space-1);
}

/* ===== 通用知识库管理（统一库 unified_kb）样式 ===== */
.kb-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.kb-stat-card {
  --kc: var(--info);
  display: grid;
  grid-template-columns: 38px 1fr;
  grid-template-rows: auto auto;
  align-items: center;
  gap: 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
}
.kb-stat-icon {
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--kc);
  background: color-mix(in srgb, var(--kc) 14%, transparent);
  grid-row: 1 / 3;
  align-self: center;
}
.kb-stat-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--kc);
  line-height: 1.1;
  align-self: end;
}
.kb-stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  align-self: start;
  white-space: nowrap;
}
.kb-stat-total .kb-stat-icon { color: var(--primary-500); background: var(--primary-50); }
.kb-stat-total .kb-stat-num { color: var(--text-primary); }

.kb-rebuild-box {
  padding: var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}
.kb-rebuild-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.kb-rebuild-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 6px 0 0;
  line-height: 1.6;
  max-width: 560px;
}
.kb-rebuild-hint code {
  padding: 1px 6px;
  background: var(--fill-light);
  border-radius: 4px;
  font-size: 11px;
  word-break: break-all;
}
.kb-rebuild-status {
  margin-top: var(--space-3);
}
.kb-rebuild-status.success .kb-rebuild-msg { color: var(--success); }
.kb-rebuild-status.error .kb-rebuild-msg { color: var(--danger); }
.kb-rebuild-msg {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.kb-progress-bar {
  height: 8px;
  background: var(--fill-light);
  border-radius: 999px;
  overflow: hidden;
}
.kb-progress-fill {
  height: 100%;
  background: var(--primary-500);
  transition: width 0.4s ease;
}

.kb-source-box {
  padding: var(--space-4);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}
.kb-source-dir {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}
.kb-source-exists { color: var(--success); font-size: 12px; }
.kb-source-missing { color: var(--danger); }
.kb-source-subdirs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-2);
}
.kb-source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--fill-light);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.kb-source-name { color: var(--text-secondary); }
.kb-source-meta { color: var(--text-tertiary); }

.kb-docs-section .section-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.kb-filter-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.kb-chip {
  --kc: var(--info);
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-base);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kb-chip:hover { border-color: var(--kc); color: var(--kc); }
.kb-chip.active { color: #fff; background: var(--kc); border-color: var(--kc); }
.kb-doc-search {
  flex: 1;
  min-width: 160px;
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-base);
  color: var(--text-primary);
  outline: none;
}
.kb-doc-search:focus { border-color: var(--primary-500); }
.doc-row {
  --c: var(--info);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 8px 12px;
  font-size: 13px;
}
.kb-doc-type-tag {
  flex-shrink: 0;
  padding: 2px 8px;
  font-size: 11px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}
.doc-row .doc-id { flex: 1; min-width: 0; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-row .doc-chunks { color: var(--text-tertiary); flex-shrink: 0; }
.doc-row .doc-source { color: var(--text-tertiary); flex-shrink: 0; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
  font-size: 13px;
  color: var(--text-secondary);
}
.kb-pager-info { color: var(--text-tertiary); }

/* 知识库子标签样式 */
.knowledge-sub-tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-lighter);
}

.sub-tab {
  padding: var(--space-2) var(--space-4);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-tertiary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sub-tab:hover { color: var(--primary-500); }
.sub-tab.active { color: var(--primary-500); border-bottom-color: var(--primary-500); }

/* 通用知识库上传区域样式 */
.knowledge-upload-section {
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}

.upload-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.upload-row:last-child {
  margin-bottom: 0;
}

.upload-row .form-textarea {
  flex: 1;
}

.upload-row .form-input {
  width: 200px;
}

/* 已上传文档列表样式 */
.knowledge-docs-section {
  margin-top: var(--space-4);
}

.docs-list {
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.docs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-lighter);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary);
}

.docs-count {
  font-size: 12px;
  color: var(--text-tertiary);
}

.doc-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-lighter);
}

.doc-row:last-child {
  border-bottom: none;
}

.doc-row:hover {
  background: var(--fill-light);
}

.doc-row input[type="checkbox"] {
  width: 16px;
  height: 16px;
}

.doc-id {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  min-width: 100px;
}

.doc-chunks {
  font-size: 12px;
  color: var(--primary-500);
  background: var(--primary-50);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.doc-source {
  font-size: 13px;
  color: var(--text-tertiary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-row .btn-text {
  margin-left: auto;
}

/* 报告模板管理 */
.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.report-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  transition: box-shadow 0.2s;
}
.report-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.report-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}
.report-card-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.report-type-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}
.report-type-badge.single {
  background: var(--primary-50);
  color: var(--primary-600);
}
.report-type-badge.compare {
  background: #fef3c7;
  color: #92400e;
}

.report-card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 var(--space-3);
}

.report-card-meta {
  display: flex;
  gap: var(--space-4);
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
}

.report-card-actions {
  display: flex;
  gap: var(--space-2);
}
.report-card-actions .btn-sm {
  flex: 1;
}

/* 报告编辑模态框 */
.report-editor-modal {
  max-width: 900px;
}

.sections-editor {
  margin-top: var(--space-4);
}
.sections-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}
.empty-sections {
  text-align: center;
  padding: var(--space-6);
  color: var(--text-tertiary);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
}

.section-item {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-bottom: var(--space-3);
}
.section-item-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.section-title-input {
  flex: 1;
  margin-bottom: 0 !important;
}
.section-num {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary-500);
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-50);
  border-radius: 50%;
}
.section-controls {
  display: flex;
  gap: var(--space-1);
}

.btn-icon-sm {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s;
}
.btn-icon-sm:hover:not(:disabled) {
  background: var(--bg-tertiary);
  border-color: var(--primary-300);
}
.btn-icon-sm:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.btn-icon-sm.danger:hover {
  color: var(--danger-500);
  border-color: var(--danger-300);
}

.section-item .form-input,
.section-item .form-select {
  width: 100%;
  margin-bottom: var(--space-2);
}
.section-item .form-select-sm {
  margin-bottom: 0;
}

.section-charts {
  background: var(--bg-primary);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin-top: var(--space-2);
}
.charts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}
.charts-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.chart-item {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.chart-item .form-input,
.chart-item .form-select {
  margin-bottom: 0;
  width: auto;
  min-width: 0;
}
.chart-name-input {
  flex: 1.2;
  min-width: 120px;
}
.chart-query-input {
  flex: 2;
  min-width: 200px;
}
.chart-item .btn-icon-sm {
  flex-shrink: 0;
}
.btn-xs {
  padding: 4px 10px;
  font-size: 12px;
}

/* Word模板上传样式 */
.card-header-actions {
  display: flex;
  gap: var(--space-2);
}

.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-8);
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-area:hover,
.upload-area.drag-over {
  border-color: var(--primary-400);
  background: var(--primary-50);
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}

.upload-icon {
  font-size: 48px;
}

.upload-text {
  font-size: 16px;
  color: var(--text-primary);
  margin: 0;
}

.upload-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}

.upload-progress {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-4);
  color: var(--text-secondary);
}

.upload-result {
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.result-success {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--success-500);
  font-weight: 500;
  margin-bottom: var(--space-3);
}

.success-icon {
  width: 24px;
  height: 24px;
  background: var(--success-500);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.result-info {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}

.result-info p {
  margin: var(--space-1) 0;
}

.result-sections h4 {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.result-sections ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.result-sections li {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-1);
  font-size: 14px;
  color: var(--text-secondary);
}
</style>