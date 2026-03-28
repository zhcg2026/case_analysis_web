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
            <textarea v-model="articleForm.content" class="form-textarea content-editor" rows="12" placeholder="请输入文章内容，图片将显示为 ![图片](图片链接)"></textarea>
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
              <input type="checkbox" v-model="editingPermissions.dashboard" />
              <span>数据大屏</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.assessment" />
              <span>考核计分</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.data_analysis" />
              <span>AI应用</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.cases" />
              <span>案件管理</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.huiwentai" />
              <span>汇问台</span>
            </label>
            <label class="permission-item">
              <input type="checkbox" v-model="editingPermissions.map" />
              <span>地图服务</span>
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

    <!-- 数据管理 -->
    <div v-else-if="activeTab === 'data'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">数据管理</h2>
      </div>

      <!-- Excel上传 -->
      <div class="data-section">
        <h3 class="subsection-title">Excel数据上传</h3>
        <div class="upload-options">
          <label class="radio-label">
            <input type="radio" v-model="uploadMode" value="create" />
            <span>新建表（以文件名命名）</span>
          </label>
          <label class="radio-label">
            <input type="radio" v-model="uploadMode" value="append" />
            <span>追加到现有表</span>
          </label>
        </div>

        <div v-if="uploadMode === 'append'" class="append-options">
          <div class="form-group">
            <label class="form-label">目标表</label>
            <select v-model="targetTable" class="form-select">
              <option value="">请选择...</option>
              <option v-for="table in dataTables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">月份（如：202603）</label>
            <input v-model="dataMonth" type="text" class="form-input" placeholder="202603" />
          </div>
        </div>

        <div class="file-upload-row">
          <input type="file" accept=".xlsx" @change="handleFileSelect" ref="excelFileInput" />
          <span class="file-name">{{ excelFile ? excelFile.name : '未选择文件' }}</span>
          <button class="btn btn-primary" @click="uploadExcel" :disabled="uploadLoading || !excelFile || (uploadMode === 'append' && !targetTable)">
            {{ uploadLoading ? '上传中...' : (uploadMode === 'append' ? '追加数据' : '上传导入') }}
          </button>
        </div>
        <div v-if="uploadMessage" class="message success">{{ uploadMessage }}</div>
        <div v-if="uploadError" class="message error">{{ uploadError }}</div>
      </div>

      <!-- 数据表管理 -->
      <div class="data-section">
        <div class="section-header">
          <h3 class="subsection-title">数据表管理</h3>
          <div class="section-actions">
            <button class="btn btn-secondary" @click="fetchDataTables" :disabled="tablesLoading">
              {{ tablesLoading ? '加载中...' : '刷新' }}
            </button>
            <button class="btn btn-primary" @click="saveTableVisibility" :disabled="visibilitySaving">
              {{ visibilitySaving ? '保存中...' : '保存配置' }}
            </button>
          </div>
        </div>
        <p class="section-hint">勾选的数据表将对前端用户可见，未勾选的表用户无法查看。</p>
        <table class="data-table">
          <thead>
            <tr>
              <th>表名</th>
              <th>对用户可见</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="table in dataTables" :key="table">
              <td>{{ table }}</td>
              <td>
                <input type="checkbox" v-model="tableVisibility[table]" />
              </td>
              <td>
                <button class="btn-text danger" @click="deleteDataTable(table)">删除</button>
              </td>
            </tr>
            <tr v-if="dataTables.length === 0">
              <td colspan="3" class="empty-text">暂无数据表</td>
            </tr>
          </tbody>
        </table>
        <div v-if="visibilityMessage" class="message success">{{ visibilityMessage }}</div>
        <div v-if="visibilityError" class="message error">{{ visibilityError }}</div>
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

    <!-- 考核系数配置 -->
    <div v-else-if="activeTab === 'assessment'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">考核计分系数配置</h2>
      </div>

      <div class="info-box">
        <p>计分公式：score = ( (按期率 × 按时系数 + 超期率 × 超时系数) × 结案权重 + (1 - 延期率) × 延期权重 + (1 - 返工率) × 返工权重 ) × 100</p>
      </div>

      <div class="form-group">
        <label class="form-label">选择考核部门</label>
        <select v-model="selectedDept" class="form-select">
          <option v-for="dept in assessmentDepartments" :key="dept" :value="dept">{{ dept }}</option>
        </select>
      </div>

      <div class="coefficients-grid" v-if="currentCoefficients">
        <div class="form-group">
          <label class="form-label">按时结案系数 (on_time)</label>
          <input v-model.number="currentCoefficients.on_time" type="number" step="0.1" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">超时结案系数 (overdue)</label>
          <input v-model.number="currentCoefficients.overdue" type="number" step="0.1" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">结案率权重 (closure_weight)</label>
          <input v-model.number="currentCoefficients.closure_weight" type="number" step="0.1" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">延期率权重 (delay_weight)</label>
          <input v-model.number="currentCoefficients.delay_weight" type="number" step="0.1" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">返工率权重 (rework_weight)</label>
          <input v-model.number="currentCoefficients.rework_weight" type="number" step="0.1" class="form-input" />
        </div>
      </div>

      <div v-if="coefficientsMessage" class="message success">{{ coefficientsMessage }}</div>
      <div v-if="coefficientsError" class="message error">{{ coefficientsError }}</div>

      <div class="form-actions">
        <button class="btn btn-primary" @click="saveCoefficients" :disabled="coefficientsLoading">
          {{ coefficientsLoading ? '保存中...' : '保存系数' }}
        </button>
        <button class="btn btn-secondary" @click="resetCoefficients">重置默认</button>
      </div>
    </div>

    <!-- 小工具 -->
    <div v-else-if="activeTab === 'tools'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">小工具</h2>
      </div>

      <div class="tools-tabs">
        <button class="tool-tab" :class="{ active: activeTool === 'huanwei' }" @click="activeTool = 'huanwei'">市容环卫案件分配</button>
        <button class="tool-tab" :class="{ active: activeTool === 'location' }" @click="activeTool = 'location'">地址信息提取</button>
        <button class="tool-tab" :class="{ active: activeTool === 'cleaning' }" @click="activeTool = 'cleaning'">数据清洗</button>
      </div>

      <!-- 市容环卫案件分配 -->
      <div v-if="activeTool === 'huanwei'" class="tool-section">
        <div class="tool-description">
          <p>该模块允许上传Excel文件，为市容环卫中心的案件分配到各环卫部门（添加"环卫"前缀）。</p>
          <p class="hint">需要包含：处置部门、所属片区 列</p>
        </div>
        <div class="tool-upload">
          <input type="file" accept=".xlsx" @change="handleToolFileSelect('huanwei', $event)" ref="huanweiFileInput" />
          <span>{{ toolFiles.huanwei ? toolFiles.huanwei.name : '未选择文件' }}</span>
          <button class="btn btn-primary" @click="processHuanwei" :disabled="toolLoading.huanwei || !toolFiles.huanwei">
            {{ toolLoading.huanwei ? '处理中...' : '开始处理' }}
          </button>
        </div>
        <div v-if="toolMessages.huanwei" class="message success">{{ toolMessages.huanwei }}</div>
        <div v-if="toolErrors.huanwei" class="message error">{{ toolErrors.huanwei }}</div>
      </div>

      <!-- 地址信息提取 -->
      <div v-if="activeTool === 'location'" class="tool-section">
        <div class="tool-description">
          <p>从问题描述中提取地址信息并替换原文件中的地址描述。</p>
          <p class="hint">需要包含：问题描述、地址描述 列</p>
        </div>
        <div class="tool-upload">
          <input type="file" accept=".xlsx" @change="handleToolFileSelect('location', $event)" ref="locationFileInput" />
          <span>{{ toolFiles.location ? toolFiles.location.name : '未选择文件' }}</span>
          <button class="btn btn-primary" @click="processLocation" :disabled="toolLoading.location || !toolFiles.location">
            {{ toolLoading.location ? '处理中...' : '开始处理' }}
          </button>
        </div>
        <div v-if="toolMessages.location" class="message success">{{ toolMessages.location }}</div>
        <div v-if="toolErrors.location" class="message error">{{ toolErrors.location }}</div>
      </div>

      <!-- 数据清洗 -->
      <div v-if="activeTool === 'cleaning'" class="tool-section">
        <div class="tool-description">
          <p>数据清洗操作，包括去除重复数据、填充缺失值等。</p>
        </div>
        <div class="tool-upload">
          <input type="file" accept=".xlsx" @change="handleToolFileSelect('cleaning', $event)" ref="cleaningFileInput" />
          <span>{{ toolFiles.cleaning ? toolFiles.cleaning.name : '未选择文件' }}</span>
          <button class="btn btn-primary" @click="processCleaning" :disabled="toolLoading.cleaning || !toolFiles.cleaning">
            {{ toolLoading.cleaning ? '处理中...' : '开始处理' }}
          </button>
        </div>
        <div v-if="toolMessages.cleaning" class="message success">{{ toolMessages.cleaning }}</div>
        <div v-if="toolErrors.cleaning" class="message error">{{ toolErrors.cleaning }}</div>
      </div>
    </div>

    <!-- 系统设置 -->
    <div v-else-if="activeTab === 'system'" class="content-card">
      <h2 class="section-title">系统设置</h2>
      <div class="settings-form">
        <div class="form-group">
          <label class="form-label">系统名称</label>
          <input type="text" class="form-input" v-model="systemConfig.name" />
        </div>
        <div class="form-group">
          <label class="form-label">系统Logo</label>
          <input type="text" class="form-input" v-model="systemConfig.logo" />
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'articles', label: '文章管理' },
  { key: 'data', label: '数据管理' },
  { key: 'business', label: '业务平台' },
  { key: 'assessment', label: '考核系数' },
  { key: 'tools', label: '小工具' },
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

// 数据管理
const dataTables = ref([])
const tableVisibility = ref({})
const uploadMode = ref('create')
const targetTable = ref('')
const dataMonth = ref('')
const excelFile = ref(null)
const uploadLoading = ref(false)
const uploadMessage = ref('')
const uploadError = ref('')
const tablesLoading = ref(false)
const visibilitySaving = ref(false)
const visibilityMessage = ref('')
const visibilityError = ref('')

// 考核系数配置
const assessmentDepartments = [
  '城市综合行政执法队',
  '市容环卫中心',
  '园林绿化服务中心（片区）',
  '园林绿化服务中心（公园广场）'
]
const selectedDept = ref(assessmentDepartments[0])
const coefficients = ref({})
const coefficientsLoading = ref(false)
const coefficientsMessage = ref('')
const coefficientsError = ref('')

// 小工具
const activeTool = ref('huanwei')
const toolFiles = ref({ huanwei: null, location: null, cleaning: null })
const toolLoading = ref({ huanwei: false, location: false, cleaning: false })
const toolMessages = ref({ huanwei: '', location: '', cleaning: '' })
const toolErrors = ref({ huanwei: '', location: '', cleaning: '' })

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

// 系统设置
const systemConfig = ref({ name: '', logo: '' })

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
const articleForm = ref({
  title: '',
  category_id: '',
  summary: '',
  content: '',
  file_path: ''
})

// 方法
function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const currentCoefficients = computed({
  get: () => {
    if (!coefficients.value[selectedDept.value]) {
      // 自动初始化该部门的系数
      coefficients.value[selectedDept.value] = {
        on_time: 1.0,
        overdue: 0.4,
        closure_weight: 0.8,
        delay_weight: 0.1,
        rework_weight: 0.1
      }
    }
    return coefficients.value[selectedDept.value]
  },
  set: (val) => {
    coefficients.value[selectedDept.value] = val
  }
})

// ===== 数据管理方法 =====
async function fetchDataTables() {
  tablesLoading.value = true
  try {
    // 管理员获取所有表（用于配置）
    const response = await axios.get('/api/tables/all')
    dataTables.value = response.data.tables || []

    // 获取已保存的可见性配置
    try {
      const visibilityResponse = await axios.get('/api/config/table-visibility')
      const savedVisibility = visibilityResponse.data.config || {}

      // 初始化可见性
      const visibility = {}
      dataTables.value.forEach(table => {
        visibility[table] = savedVisibility[table] !== false // 默认可见
      })
      tableVisibility.value = visibility
    } catch (e) {
      // 如果获取配置失败，默认全部可见
      const visibility = {}
      dataTables.value.forEach(table => {
        visibility[table] = true
      })
      tableVisibility.value = visibility
    }
  } catch (error) {
    console.error('获取数据表失败:', error)
  } finally {
    tablesLoading.value = false
  }
}

function handleFileSelect(e) {
  excelFile.value = e.target.files[0] || null
}

async function uploadExcel() {
  if (!excelFile.value) return
  if (uploadMode.value === 'append' && !targetTable.value) {
    uploadError.value = '请选择目标表'
    return
  }

  uploadLoading.value = true
  uploadMessage.value = ''
  uploadError.value = ''

  const formData = new FormData()
  formData.append('file', excelFile.value)
  if (uploadMode.value === 'append') {
    formData.append('target_table', targetTable.value)
    formData.append('data_month', dataMonth.value)
  }

  try {
    const endpoint = uploadMode.value === 'append' ? '/api/append-data' : '/api/upload'
    const response = await axios.post(endpoint, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    uploadMessage.value = response.data.message || '上传成功'
    fetchDataTables()
  } catch (error) {
    uploadError.value = error.response?.data?.error || '上传失败'
  } finally {
    uploadLoading.value = false
  }
}

async function saveTableVisibility() {
  visibilitySaving.value = true
  visibilityMessage.value = ''
  visibilityError.value = ''

  try {
    await axios.post('/api/config/table-visibility', { config: tableVisibility.value })
    visibilityMessage.value = '保存成功'
  } catch (error) {
    console.error('保存可见性配置失败:', error)
    visibilityError.value = error.response?.data?.error || '保存失败'
  } finally {
    visibilitySaving.value = false
  }
}

async function deleteDataTable(tableName) {
  if (!confirm(`确定删除数据表「${tableName}」？此操作不可恢复！`)) return

  try {
    await axios.delete(`/api/tables/${tableName}`)
    fetchDataTables()
  } catch (error) {
    alert(error.response?.data?.error || '删除失败')
  }
}

// ===== 考核系数方法 =====
async function fetchCoefficients() {
  coefficientsLoading.value = true
  try {
    const response = await axios.get('/api/assessment-coefficients')
    coefficients.value = response.data || {}
  } catch (error) {
    console.error('获取考核系数失败:', error)
  } finally {
    coefficientsLoading.value = false
  }
}

async function saveCoefficients() {
  coefficientsLoading.value = true
  coefficientsMessage.value = ''
  coefficientsError.value = ''

  try {
    const response = await axios.put('/api/assessment-coefficients', {
      department: selectedDept.value,
      ...currentCoefficients.value
    })
    // 更新本地系数数据
    coefficients.value = response.data.coefficients || coefficients.value
    coefficientsMessage.value = '保存成功'
  } catch (error) {
    coefficientsError.value = error.response?.data?.error || '保存失败'
  } finally {
    coefficientsLoading.value = false
  }
}

function resetCoefficients() {
  coefficients.value[selectedDept.value] = {
    on_time: 1.0,
    overdue: 0.4,
    closure_weight: 0.8,
    delay_weight: 0.1,
    rework_weight: 0.1
  }
}

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

function processCleaning() {
  processToolFile('cleaning', '/api/tools/data-cleaning')
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
    dashboard: Boolean(perms.dashboard),
    assessment: Boolean(perms.assessment),
    data_analysis: Boolean(perms.data_analysis),
    cases: Boolean(perms.cases),
    map: Boolean(perms.map),
    huiwentai: Boolean(perms.huiwentai),
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
      dashboard: Boolean(editingPermissions.value.dashboard),
      assessment: Boolean(editingPermissions.value.assessment),
      data_analysis: Boolean(editingPermissions.value.data_analysis),
      cases: Boolean(editingPermissions.value.cases),
      map: Boolean(editingPermissions.value.map),
      huiwentai: Boolean(editingPermissions.value.huiwentai),
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
async function fetchSystemConfig() {
  try {
    const response = await axios.get('/api/system/config')
    systemConfig.value = response.data || {}
  } catch (error) {
    console.error('获取系统配置失败:', error)
  }
}

async function saveSystemConfig() {
  try {
    await axios.post('/api/system/config', systemConfig.value)
    alert('保存成功')
  } catch (error) {
    console.error('保存系统配置失败:', error)
    alert('保存失败')
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
    articleForm.value.content += `\n![${file.name}](${imageUrl})\n`
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

onMounted(() => {
  fetchUsers()
  fetchPlatforms()
  fetchSystemConfig()
  fetchDataTables()
  fetchCoefficients()
  fetchCategories()
  fetchArticles()
})

watch(articlesCurrentPage, fetchArticles)
</script>

<style scoped>
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
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
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
  font-family: var(--font-mono);
  line-height: 1.6;
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

.file-upload-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.file-name {
  color: var(--text-secondary);
  font-size: 14px;
}

/* 考核系数样式 */
.info-box {
  padding: var(--space-4);
  background: var(--fill-light);
  border: 1px solid var(--border-lighter);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-6);
}

.info-box p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.coefficients-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}

.form-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
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

  .coefficients-grid {
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

.article-editor { max-width: 800px; }
.category-manager { max-width: 500px; }
.category-editor { max-width: 400px; }

.content-editor {
  font-family: var(--font-mono);
  line-height: 1.6;
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
</style>