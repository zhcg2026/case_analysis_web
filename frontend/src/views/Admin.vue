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

    <!-- 数据编辑 -->
    <div v-else-if="activeTab === 'dataEdit'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">数据编辑</h2>
      </div>

      <!-- 筛选区域 -->
      <div class="filter-section">
        <div class="filter-row">
          <div class="filter-group">
            <div class="form-group">
              <label class="form-label">选择数据表</label>
              <select v-model="editTable" class="form-select" @change="onEditTableChange">
                <option value="">请选择</option>
                <option v-for="table in visibleTables" :key="table" :value="table">{{ table }}</option>
              </select>
            </div>
            <div class="form-group" v-if="editAvailableMonths.length > 0">
              <label class="form-label">选择月份</label>
              <select v-model="editMonth" class="form-select" @change="fetchEditRecords">
                <option value="">全部</option>
                <option v-for="month in editAvailableMonths" :key="month" :value="month">{{ formatMonth(month) }}</option>
              </select>
            </div>
          </div>
          <div class="filter-group">
            <div class="form-group">
              <label class="form-label">查找字段</label>
              <select v-model="searchField" class="form-select">
                <option value="">请选择</option>
                <option value="任务号">任务号（精确匹配）</option>
                <option v-for="col in formFields.filter(c => c !== '任务号')" :key="col" :value="col">{{ col }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">查找值</label>
              <input v-model="searchValue" type="text" class="form-input" placeholder="输入查找值" @keyup.enter="fetchEditRecords" />
            </div>
            <button class="btn btn-primary" @click="fetchEditRecords">查询</button>
            <button class="btn btn-secondary" @click="resetEditFilters">重置</button>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <button class="btn btn-primary" @click="openAddRecordModal">+ 新增</button>
        <button class="btn btn-secondary" :disabled="selectedRecords.length === 0" @click="openBatchEditModal">批量修改</button>
        <button class="btn btn-danger" :disabled="selectedRecords.length === 0" @click="confirmBatchDelete">批量删除</button>
        <span class="selection-info" v-if="selectedRecords.length > 0">已选择 {{ selectedRecords.length }} 条</span>
      </div>

      <!-- 数据列表 -->
      <div v-if="editLoading" class="loading-state">
        <div class="loading-spinner"></div>
      </div>
      <div v-else-if="editRecords.length > 0">
        <table class="data-table">
          <thead>
            <tr>
              <th><input type="checkbox" v-model="selectAll" @change="toggleSelectAll" /></th>
              <th v-for="col in displayColumns" :key="col">{{ col }}</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in editRecords" :key="record['任务号']">
              <td><input type="checkbox" :value="record['任务号']" v-model="selectedRecords" /></td>
              <td v-for="col in displayColumns" :key="col">{{ record[col] || '-' }}</td>
              <td>
                <button class="btn-text" @click="openEditRecordModal(record)">编辑</button>
                <button class="btn-text danger" @click="confirmDeleteRecord(record)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <!-- 分页 -->
        <div class="pagination">
          <button :disabled="editPage <= 1" @click="editPage--; fetchEditRecords()">上一页</button>
          <span>第 {{ editPage }} / {{ editTotalPages }} 页，共 {{ editTotal }} 条</span>
          <button :disabled="editPage >= editTotalPages" @click="editPage++; fetchEditRecords()">下一页</button>
        </div>
      </div>
      <div v-else class="empty-state">
        <p v-if="editTable">暂无数据</p>
        <p v-else>请选择数据表</p>
      </div>
    </div>

    <!-- 操作日志 -->
    <div v-else-if="activeTab === 'logs'" class="content-card">
      <div class="card-header">
        <h2 class="section-title">操作日志</h2>
      </div>

      <!-- 筛选 -->
      <div class="filter-section">
        <div class="filter-row">
          <div class="form-group">
            <label class="form-label">数据表</label>
            <select v-model="logTable" class="form-select">
              <option value="">全部</option>
              <option v-for="table in visibleTables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">操作类型</label>
            <select v-model="logType" class="form-select">
              <option value="">全部</option>
              <option value="create">新增</option>
              <option value="update">修改</option>
              <option value="delete">删除</option>
            </select>
          </div>
          <button class="btn btn-primary" @click="fetchLogs">查询</button>
        </div>
      </div>

      <!-- 日志列表 -->
      <div v-if="logsLoading" class="loading-state">
        <div class="loading-spinner"></div>
      </div>
      <div v-else-if="logs.length > 0">
        <table class="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>操作类型</th>
              <th>数据表</th>
              <th>记录ID</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td>{{ log.created_at }}</td>
              <td>{{ log.username }}</td>
              <td>
                <span :class="['op-type', log.operation_type]">
                  {{ log.operation_type === 'create' ? '新增' : log.operation_type === 'update' ? '修改' : '删除' }}
                </span>
              </td>
              <td>{{ log.table_name }}</td>
              <td>{{ log.record_id }}</td>
              <td><button class="btn-text" @click="viewLogDetail(log)">详情</button></td>
            </tr>
          </tbody>
        </table>
        <div class="pagination">
          <button :disabled="logPage <= 1" @click="logPage--; fetchLogs()">上一页</button>
          <span>第 {{ logPage }} / {{ logTotalPages }} 页，共 {{ logTotal }} 条</span>
          <button :disabled="logPage >= logTotalPages" @click="logPage++; fetchLogs()">下一页</button>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>暂无操作日志</p>
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
        <button class="sub-tab" :class="{ active: knowledgeSubTab === 'standards' }" @click="knowledgeSubTab = 'standards'">
          立结案标准库
        </button>
      </div>

      <!-- 通用知识库管理 -->
      <div v-show="knowledgeSubTab === 'general'">
        <!-- 统计信息 -->
        <div class="stats-card">
          <div class="stat-item">
            <span class="stat-value">{{ generalKnowledgeStats.count || 0 }}</span>
            <span class="stat-label">向量数</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ generalKnowledgeDocs.length || 0 }}</span>
            <span class="stat-label">文档数</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ generalKnowledgeStats.exists ? (generalKnowledgeStats.mode === 'server' ? '服务器' : '本地') : '未初始化' }}</span>
            <span class="stat-label">运行模式</span>
          </div>
        </div>

        <!-- 文档上传 -->
        <div class="knowledge-upload-section">
          <h3 class="subsection-title">上传文档</h3>
          <div class="upload-row">
            <input ref="knowledgeFileInput" type="file" accept=".txt,.md,.docx,.xlsx" @change="onKnowledgeFileSelect" hidden />
            <button class="btn btn-secondary" @click="$refs.knowledgeFileInput.click()">
              选择文件
            </button>
            <span class="file-name">{{ knowledgeSelectedFile?.name || '未选择' }}</span>
          </div>
          <div class="upload-row">
            <input ref="knowledgeZipInput" type="file" accept=".zip" @change="onKnowledgeZipSelect" hidden />
            <button class="btn btn-info" @click="$refs.knowledgeZipInput.click()">
              批量上传(zip)
            </button>
            <span class="file-name">{{ knowledgeSelectedZip?.name || '未选择' }}</span>
          </div>
          <div class="upload-row">
            <textarea v-model="knowledgeTextContent" placeholder="或直接输入文本内容..." rows="4" class="form-textarea"></textarea>
            <input v-model="knowledgeTextSource" placeholder="来源名称（可选）" class="form-input" />
          </div>
          <button class="btn btn-primary" @click="uploadKnowledgeDoc" :disabled="knowledgeUploading">
            {{ knowledgeUploading ? '上传中...' : '提交到知识库' }}
          </button>

          <!-- 上传结果 -->
          <div v-if="knowledgeUploadResult" class="message" :class="knowledgeUploadResult.success ? 'success' : 'error'">
            {{ knowledgeUploadResult.message }}
          </div>

          <!-- 批量上传进度 -->
          <div v-if="knowledgeBatchProgress" class="standards-progress">
            <div class="progress-text">处理中: {{ knowledgeBatchProgress.processed }} / {{ knowledgeBatchProgress.total }}</div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: (knowledgeBatchProgress.processed / knowledgeBatchProgress.total * 100) + '%' }"></div>
            </div>
            <div class="progress-summary">成功: {{ knowledgeBatchProgress.success }}，失败: {{ knowledgeBatchProgress.failed }}</div>
          </div>
        </div>

        <!-- 已上传文档列表 -->
        <div class="knowledge-docs-section">
          <div class="section-header">
            <h3 class="subsection-title">已上传文档</h3>
            <div class="section-actions">
              <button class="btn btn-secondary" @click="loadKnowledgeDocs">刷新</button>
              <button v-if="knowledgeSelectedDocs.length > 0" class="btn btn-danger" @click="batchDeleteKnowledgeDocs">
                删除选中 ({{ knowledgeSelectedDocs.length }})
              </button>
            </div>
          </div>

          <div v-if="generalKnowledgeDocs.length" class="docs-list">
            <div class="docs-header">
              <label class="checkbox-label">
                <input type="checkbox" :checked="knowledgeSelectedDocs.length === generalKnowledgeDocs.length" @change="toggleKnowledgeSelectAll">
                全选
              </label>
              <span class="docs-count">共 {{ generalKnowledgeDocs.length }} 个文档</span>
            </div>
            <div v-for="doc in generalKnowledgeDocs" :key="doc.doc_id" class="doc-row">
              <input type="checkbox" :value="doc.doc_id" v-model="knowledgeSelectedDocs">
              <span class="doc-id">{{ doc.doc_id }}</span>
              <span class="doc-chunks">{{ doc.chunks }} 个片段</span>
              <span class="doc-source">{{ doc.sources?.join(', ') }}</span>
              <button class="btn-text danger" @click="deleteKnowledgeDoc(doc.doc_id)">删除</button>
            </div>
          </div>
          <div v-else class="empty-state">暂无文档</div>
        </div>
      </div>

      <!-- 立结案标准库管理 -->
      <div v-show="knowledgeSubTab === 'standards'">
        <!-- 统计信息 -->
        <div class="stats-card">
          <div class="stat-item">
            <span class="stat-value">{{ standardsStats?.parents || 0 }}</span>
            <span class="stat-label">父文档数</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ standardsStats?.children || 0 }}</span>
            <span class="stat-label">子文档数</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ (standardsStats?.exists) ? (standardsStats?.mode || '本地') : '未初始化' }}</span>
            <span class="stat-label">运行模式</span>
          </div>
        </div>

        <!-- 操作区域 -->
        <div class="standards-actions">
          <button class="btn btn-primary" @click="fetchStandardsList" :disabled="standardsLoading">
            {{ standardsLoading ? '加载中...' : '刷新列表' }}
          </button>
          <button class="btn btn-info" @click="startIncrementalIndex" :disabled="incrementalLoading">
            {{ incrementalLoading ? '索引中...' : '增量索引' }}
          </button>
          <input ref="singleStandardsFileInput" type="file" accept=".txt" @change="onSingleStandardsFileSelect" hidden />
          <button class="btn btn-secondary" @click="$refs.singleStandardsFileInput.click()">
            上传单文件
          </button>
        </div>

        <!-- 增量索引进度 -->
        <div v-if="incrementalProgress.active" class="standards-progress">
          <div class="progress-text">处理中: {{ incrementalProgress.filename }}</div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: (incrementalProgress.current / incrementalProgress.total * 100) + '%' }"></div>
          </div>
          <div class="progress-summary">已处理: {{ incrementalProgress.current }} / {{ incrementalProgress.total }}</div>
        </div>

        <!-- 增量索引结果 -->
        <div v-if="incrementalResult" class="standards-result">
          <p>新增 {{ incrementalResult.success }} 个，跳过 {{ incrementalResult.skipped }} 个，失败 {{ incrementalResult.failed }} 个</p>
        </div>

        <!-- 已索引标准列表 -->
        <div v-if="standardsList.length" class="standards-table">
          <table class="data-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>案件类型</th>
                <th>大类/小类</th>
                <th>子文档数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="std in standardsList" :key="std.parent_id">
                <td>{{ std.filename || '-' }}</td>
                <td>{{ std.case_type || '-' }}</td>
                <td>{{ std.big_category }} / {{ std.small_category }}</td>
                <td>{{ std.child_count }}</td>
                <td>
                  <button class="btn-text danger" @click="deleteStandard(std.parent_id)" :disabled="standardsDeleteLoading">
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!standardsLoading && standardsListFetched" class="empty-state">
          <p>暂无已索引的标准，请执行增量索引或上传单个文件</p>
        </div>

        <!-- 单文件上传结果 -->
        <div v-if="singleStandardsFileResult" class="standards-result">
          <p :class="singleStandardsFileResult.success ? 'success' : 'error'">{{ singleStandardsFileResult.message }}</p>
        </div>
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
        <button class="tool-tab" :class="{ active: activeTool === 'desensitization' }" @click="activeTool = 'desensitization'">数据脱敏</button>
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

      <!-- 数据脱敏 -->
      <div v-if="activeTool === 'desensitization'" class="tool-section">
        <div class="tool-description">
          <p>对Excel文件中的敏感数据进行脱敏处理，支持姓名、电话、地址等字段。</p>
          <p class="hint">上传文件后选择需要脱敏的字段和类型</p>
        </div>
        <div class="tool-upload">
          <input type="file" accept=".xlsx" @change="handleDesensitizationFileSelect($event)" ref="desensitizationFileInput" />
          <span>{{ desensitizationFileName || '未选择文件' }}</span>
        </div>

        <div v-if="desensitizationFields.length > 0" class="desensitization-fields">
          <h4>选择脱敏字段和类型</h4>
          <div class="field-list">
            <div v-for="field in desensitizationFields" :key="field" class="field-row">
              <span class="field-name">{{ field }}</span>
              <select v-model="desensitizationConfig[field]" class="field-select">
                <option value="">不处理</option>
                <option value="name">姓名脱敏</option>
                <option value="phone">手机号脱敏</option>
                <option value="landline">座机号脱敏</option>
                <option value="address">地址脱敏</option>
                <option value="problem_description">问题描述清洗</option>
              </select>
            </div>
          </div>
          <div class="btn-group">
            <button class="btn btn-primary" @click="processDesensitization" :disabled="toolLoading.desensitization">
              {{ toolLoading.desensitization ? '处理中...' : '开始脱敏' }}
            </button>
            <button class="btn btn-secondary" @click="resetDesensitization">重置</button>
          </div>
        </div>

        <div v-if="toolLoading.desensitization && desensitizationFields.length === 0" class="message info">读取文件字段中...</div>
        <div v-if="toolMessages.desensitization" class="message success">{{ toolMessages.desensitization }}</div>
        <div v-if="toolErrors.desensitization" class="message error">{{ toolErrors.desensitization }}</div>
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
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'articles', label: '文章管理' },
  { key: 'data', label: '数据管理' },
  { key: 'dataEdit', label: '数据编辑' },
  { key: 'logs', label: '操作日志' },
  { key: 'business', label: '业务平台' },
  { key: 'assessment', label: '考核系数' },
  { key: 'knowledge', label: '知识库管理' },
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
const visibleTables = computed(() => {
  // 只返回可见的表
  return dataTables.value.filter(t => tableVisibility.value[t] !== false)
})
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

// 知识库管理
const knowledgeSubTab = ref('general')

// 通用知识库管理
const generalKnowledgeStats = ref({ exists: false, count: 0 })
const generalKnowledgeDocs = ref([])
const knowledgeSelectedDocs = ref([])
const knowledgeSelectedFile = ref(null)
const knowledgeSelectedZip = ref(null)
const knowledgeTextContent = ref('')
const knowledgeTextSource = ref('')
const knowledgeUploading = ref(false)
const knowledgeUploadResult = ref(null)
const knowledgeBatchProgress = ref(null)

// 立结案标准库管理
const standardsStats = ref(null)
const standardsList = ref([])
const standardsLoading = ref(false)
const standardsListFetched = ref(false)
const standardsDeleteLoading = ref(false)
const incrementalLoading = ref(false)
const incrementalProgress = ref({ active: false, current: 0, total: 0, filename: '', status: '' })
const incrementalResult = ref(null)
const singleStandardsFileResult = ref(null)

// 小工具
const activeTool = ref('huanwei')
const toolFiles = ref({ huanwei: null, location: null, desensitization: null })
const toolLoading = ref({ huanwei: false, location: false, desensitization: false })
const toolMessages = ref({ huanwei: '', location: '', desensitization: '' })
const toolErrors = ref({ huanwei: '', location: '', desensitization: '' })

// 数据脱敏
const desensitizationFileName = ref('')
const desensitizationFields = ref([])
const desensitizationConfig = ref({})

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

// ===== 通用知识库管理方法 =====
async function loadKnowledgeStats() {
  try {
    const res = await axios.get('/api/knowledge/stats')
    generalKnowledgeStats.value = res.data
  } catch (error) {
    console.error('加载知识库统计失败:', error)
  }
}

async function loadKnowledgeDocs() {
  try {
    const res = await axios.get('/api/knowledge/documents')
    generalKnowledgeDocs.value = res.data.documents || []
  } catch (error) {
    console.error('加载文档列表失败:', error)
  }
}

function onKnowledgeFileSelect(e) {
  knowledgeSelectedFile.value = e.target.files[0] || null
  knowledgeTextContent.value = ''
  knowledgeUploadResult.value = null
}

function onKnowledgeZipSelect(e) {
  knowledgeSelectedZip.value = e.target.files[0] || null
  knowledgeUploadResult.value = null
  if (knowledgeSelectedZip.value) {
    uploadKnowledgeZip()
  }
}

async function uploadKnowledgeZip() {
  if (!knowledgeSelectedZip.value) return
  knowledgeUploading.value = true
  knowledgeUploadResult.value = null
  knowledgeBatchProgress.value = null

  try {
    const formData = new FormData()
    formData.append('file', knowledgeSelectedZip.value)
    const res = await axios.post('/api/knowledge/batch-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    knowledgeUploadResult.value = res.data
    if (res.data.success && res.data.task_id) {
      knowledgeSelectedZip.value = null
      pollKnowledgeProgress(res.data.task_id, res.data.total_files)
    }
  } catch (error) {
    knowledgeUploadResult.value = { success: false, message: '批量上传失败: ' + (error.response?.data?.error || error.message) }
    knowledgeUploading.value = false
  }
}

async function pollKnowledgeProgress(taskId, totalFiles) {
  knowledgeBatchProgress.value = { total: totalFiles, processed: 0, success: 0, failed: 0 }

  const poll = async () => {
    try {
      const res = await axios.get(`/api/knowledge/batch-upload/progress/${taskId}`)
      if (res.data.status === 'completed') {
        knowledgeBatchProgress.value = res.data
        knowledgeUploading.value = false
        knowledgeUploadResult.value = {
          success: true,
          message: `处理完成！成功 ${res.data.success} 个，失败 ${res.data.failed} 个`
        }
        loadKnowledgeStats()
        loadKnowledgeDocs()
      } else {
        knowledgeBatchProgress.value = res.data
        setTimeout(poll, 2000)
      }
    } catch (error) {
      setTimeout(poll, 2000)
    }
  }
  poll()
}

async function uploadKnowledgeDoc() {
  if (!knowledgeSelectedFile.value && !knowledgeTextContent.value.trim()) {
    knowledgeUploadResult.value = { success: false, message: '请选择文件或输入内容' }
    return
  }

  knowledgeUploading.value = true
  knowledgeUploadResult.value = null

  try {
    if (knowledgeSelectedFile.value) {
      const formData = new FormData()
      formData.append('file', knowledgeSelectedFile.value)
      const res = await axios.post('/api/knowledge/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      knowledgeUploadResult.value = res.data
      if (res.data.success) {
        knowledgeSelectedFile.value = null
        loadKnowledgeStats()
        loadKnowledgeDocs()
      }
    } else {
      const res = await axios.post('/api/knowledge/upload', {
        content: knowledgeTextContent.value,
        source: knowledgeTextSource.value || '手动输入'
      })
      knowledgeUploadResult.value = res.data
      if (res.data.success) {
        knowledgeTextContent.value = ''
        knowledgeTextSource.value = ''
        loadKnowledgeStats()
        loadKnowledgeDocs()
      }
    }
  } catch (error) {
    knowledgeUploadResult.value = { success: false, message: '上传失败: ' + (error.response?.data?.error || error.message) }
  } finally {
    knowledgeUploading.value = false
  }
}

function toggleKnowledgeSelectAll() {
  if (knowledgeSelectedDocs.value.length === generalKnowledgeDocs.value.length) {
    knowledgeSelectedDocs.value = []
  } else {
    knowledgeSelectedDocs.value = generalKnowledgeDocs.value.map(d => d.doc_id)
  }
}

async function batchDeleteKnowledgeDocs() {
  if (knowledgeSelectedDocs.value.length === 0) return
  if (!confirm(`确定删除选中的 ${knowledgeSelectedDocs.value.length} 个文档？`)) return

  try {
    const res = await axios.post('/api/knowledge/documents/batch-delete', { doc_ids: knowledgeSelectedDocs.value })
    if (res.data.success) {
      alert(res.data.message)
      knowledgeSelectedDocs.value = []
      loadKnowledgeStats()
      loadKnowledgeDocs()
    } else {
      alert('删除失败: ' + res.data.error)
    }
  } catch (error) {
    alert('删除失败: ' + (error.response?.data?.error || error.message))
  }
}

async function deleteKnowledgeDoc(docId) {
  if (!confirm('确定删除该文档？')) return

  try {
    const res = await axios.delete(`/api/knowledge/documents/${docId}`)
    if (res.data.success) {
      loadKnowledgeStats()
      loadKnowledgeDocs()
    } else {
      alert('删除失败: ' + res.data.message)
    }
  } catch (error) {
    alert('删除失败: ' + (error.response?.data?.error || error.message))
  }
}

// ===== 立结案标准库管理方法 =====
async function fetchStandardsList() {
  standardsLoading.value = true
  standardsListFetched.value = false
  try {
    const statsRes = await axios.get('/api/case-standards/stats')
    standardsStats.value = statsRes.data
    const listRes = await axios.get('/api/case-standards/list')
    standardsList.value = listRes.data.standards || []
    standardsListFetched.value = true
  } catch (error) {
    console.error('获取标准列表失败:', error)
    alert('获取标准列表失败: ' + (error.response?.data?.error || error.message))
  } finally {
    standardsLoading.value = false
  }
}

async function deleteStandard(parentId) {
  if (!confirm('确认删除该标准？此操作不可恢复！')) return
  standardsDeleteLoading.value = true
  try {
    const response = await axios.delete(`/api/case-standards/delete/${parentId}`)
    if (response.data.success) {
      await fetchStandardsList()
      alert('删除成功')
    } else {
      alert('删除失败: ' + response.data.message)
    }
  } catch (error) {
    alert('删除失败: ' + (error.response?.data?.error || error.message))
  } finally {
    standardsDeleteLoading.value = false
  }
}

async function startIncrementalIndex() {
  incrementalLoading.value = true
  incrementalProgress.value = { active: true, current: 0, total: 0, filename: '准备开始...', status: '' }
  incrementalResult.value = null
  try {
    const response = await axios.post('/api/case-standards/incremental', {
      directory: 'D:/常用/立案结案标准'
    })
    incrementalResult.value = response.data
    incrementalProgress.value.active = false
    await fetchStandardsList()
  } catch (error) {
    incrementalProgress.value.active = false
    alert('增量索引失败: ' + (error.response?.data?.error || error.message))
  } finally {
    incrementalLoading.value = false
  }
}

function onSingleStandardsFileSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  if (!file.name.endsWith('.txt')) {
    alert('只支持.txt文件')
    return
  }
  uploadSingleStandardsFile(file)
}

async function uploadSingleStandardsFile(file) {
  standardsLoading.value = true
  singleStandardsFileResult.value = null
  const formData = new FormData()
  formData.append('file', file)
  try {
    const response = await axios.post('/api/case-standards/index-single', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    singleStandardsFileResult.value = response.data
    if (response.data.success) {
      await fetchStandardsList()
    }
  } catch (error) {
    singleStandardsFileResult.value = { success: false, message: error.response?.data?.error || error.message }
  } finally {
    standardsLoading.value = false
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

// ===== 数据编辑 =====
const editTable = ref('')
const editMonth = ref('')
const editAvailableMonths = ref([])
const editColumns = ref([])
const displayColumns = ref([])
const formFields = ref([])
const editRecords = ref([])
const editTotal = ref(0)
const editPage = ref(1)
const editTotalPages = ref(1)
const editLoading = ref(false)
const searchField = ref('')
const searchValue = ref('')
const selectedRecords = ref([])
const selectAll = ref(false)

// 记录弹窗
const showRecordModal = ref(false)
const isAddRecord = ref(true)
const recordForm = ref({})
const recordSaving = ref(false)

// 批量修改弹窗
const showBatchEditModal = ref(false)
const batchEditField = ref('')
const batchEditValue = ref('')
const batchEditSaving = ref(false)

// 删除确认
const showDeleteConfirm = ref(false)
const deleteConfirmMessage = ref('')
const deleteTarget = ref(null)  // { type: 'single' | 'batch', taskNumber? }
const deleteSaving = ref(false)

// 操作日志
const logs = ref([])
const logTotal = ref(0)
const logPage = ref(1)
const logTotalPages = ref(1)
const logsLoading = ref(false)
const logTable = ref('')
const logType = ref('')
const showLogDetailModal = ref(false)
const logDetail = ref(null)

async function onEditTableChange() {
  editMonth.value = ''
  editAvailableMonths.value = []
  editRecords.value = []
  editColumns.value = []
  displayColumns.value = []
  formFields.value = []
  selectedRecords.value = []
  searchField.value = ''
  searchValue.value = ''

  if (editTable.value) {
    // 获取可用月份
    try {
      const response = await axios.get(`/api/available-months?table_name=${editTable.value}`)
      editAvailableMonths.value = response.data.months || []
    } catch (error) {
      console.error('获取月份失败:', error)
    }

    // 自动加载数据
    await fetchEditRecords()
  }
}

async function fetchEditRecords() {
  if (!editTable.value) return
  editLoading.value = true
  try {
    const params = new URLSearchParams({
      table_name: editTable.value,
      page: editPage.value,
      page_size: 20
    })
    if (editMonth.value) params.append('month', editMonth.value)
    if (searchField.value && searchValue.value) {
      params.append('search_field', searchField.value)
      params.append('search_value', searchValue.value)
    }
    const response = await axios.get(`/api/data-edit/records?${params}`)
    editRecords.value = response.data.records || []
    editTotal.value = response.data.total || 0
    editColumns.value = response.data.columns || []
    displayColumns.value = response.data.display_fields || []
    formFields.value = response.data.edit_fields || []
    editTotalPages.value = Math.ceil(editTotal.value / 20)
    selectedRecords.value = []
    selectAll.value = false
  } catch (error) {
    console.error('获取数据失败:', error)
    alert(error.response?.data?.error || '获取数据失败')
  } finally {
    editLoading.value = false
  }
}

function resetEditFilters() {
  editMonth.value = ''
  searchField.value = ''
  searchValue.value = ''
  editPage.value = 1
  fetchEditRecords()
}

function toggleSelectAll() {
  if (selectAll.value) {
    selectedRecords.value = editRecords.value.map(r => r['任务号'])
  } else {
    selectedRecords.value = []
  }
}

async function openAddRecordModal() {
  if (!editTable.value) {
    alert('请先选择数据表')
    return
  }

  // 如果没有列信息，先获取
  if (formFields.value.length === 0) {
    await fetchEditRecords()
  }

  // 如果还是没有列信息，报错
  if (formFields.value.length === 0) {
    alert('无法获取表结构，请检查数据表')
    return
  }

  isAddRecord.value = true
  recordForm.value = {}
  formFields.value.forEach(col => {
    recordForm.value[col] = ''
  })
  showRecordModal.value = true
}

function openEditRecordModal(record) {
  isAddRecord.value = false
  recordForm.value = { ...record }
  showRecordModal.value = true
}

function closeRecordModal() {
  showRecordModal.value = false
  recordForm.value = {}
}

async function saveRecord() {
  if (!recordForm.value['任务号']) {
    alert('任务号不能为空')
    return
  }
  recordSaving.value = true
  try {
    if (isAddRecord.value) {
      await axios.post('/api/data-edit/record', {
        table_name: editTable.value,
        record_data: recordForm.value
      })
      alert('新增成功')
    } else {
      await axios.put(`/api/data-edit/record/${recordForm.value['任务号']}`, {
        table_name: editTable.value,
        record_data: recordForm.value
      })
      alert('修改成功')
    }
    closeRecordModal()
    fetchEditRecords()
  } catch (error) {
    alert(error.response?.data?.error || '保存失败')
  } finally {
    recordSaving.value = false
  }
}

function confirmDeleteRecord(record) {
  deleteTarget.value = { type: 'single', taskNumber: record['任务号'] }
  deleteConfirmMessage.value = `确定删除记录「${record['任务号']}」？此操作不可恢复。`
  showDeleteConfirm.value = true
}

function confirmBatchDelete() {
  if (selectedRecords.value.length === 0) return
  deleteTarget.value = { type: 'batch', taskNumbers: [...selectedRecords.value] }
  deleteConfirmMessage.value = `确定删除选中的 ${selectedRecords.value.length} 条记录？此操作不可恢复。`
  showDeleteConfirm.value = true
}

async function executeDelete() {
  deleteSaving.value = true
  try {
    if (deleteTarget.value.type === 'single') {
      await axios.delete(`/api/data-edit/record/${deleteTarget.value.taskNumber}?table_name=${editTable.value}`)
      alert('删除成功')
    } else {
      await axios.post('/api/data-edit/batch-delete', {
        table_name: editTable.value,
        task_numbers: deleteTarget.value.taskNumbers
      })
      alert('批量删除成功')
    }
    showDeleteConfirm.value = false
    selectedRecords.value = []
    fetchEditRecords()
  } catch (error) {
    alert(error.response?.data?.error || '删除失败')
  } finally {
    deleteSaving.value = false
  }
}

function openBatchEditModal() {
  if (selectedRecords.value.length === 0) {
    alert('请先选择要修改的记录')
    return
  }
  batchEditField.value = ''
  batchEditValue.value = ''
  showBatchEditModal.value = true
}

async function batchUpdateRecords() {
  if (!batchEditField.value) {
    alert('请选择要修改的字段')
    return
  }
  batchEditSaving.value = true
  try {
    await axios.post('/api/data-edit/batch-update', {
      table_name: editTable.value,
      task_numbers: selectedRecords.value,
      update_data: { [batchEditField.value]: batchEditValue.value }
    })
    alert('批量修改成功')
    showBatchEditModal.value = false
    selectedRecords.value = []
    fetchEditRecords()
  } catch (error) {
    alert(error.response?.data?.error || '批量修改失败')
  } finally {
    batchEditSaving.value = false
  }
}

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
  fetchDataTables()
  fetchCoefficients()
  fetchCategories()
  fetchArticles()
})

// 切换到知识库管理tab时自动加载列表
watch(activeTab, (newTab) => {
  if (newTab === 'knowledge') {
    if (knowledgeSubTab.value === 'general') {
      loadKnowledgeStats()
      loadKnowledgeDocs()
    } else if (knowledgeSubTab.value === 'standards' && !standardsListFetched.value) {
      fetchStandardsList()
    }
  }
})

// 切换知识库子标签时加载对应数据
watch(knowledgeSubTab, (newSubTab) => {
  if (activeTab.value === 'knowledge') {
    if (newSubTab === 'general') {
      loadKnowledgeStats()
      loadKnowledgeDocs()
    } else if (newSubTab === 'standards' && !standardsListFetched.value) {
      fetchStandardsList()
    }
  }
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

.standards-actions {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.btn-info {
  background: #3498db;
  color: white;
}

.btn-info:hover:not(:disabled) {
  background: #2980b9;
}

.standards-progress {
  padding: var(--space-4);
  background: var(--fill-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}

.standards-progress .progress-text {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.standards-progress .progress-bar {
  height: 8px;
  background: var(--border-lighter);
  border-radius: 4px;
  overflow: hidden;
}

.standards-progress .progress-fill {
  height: 100%;
  background: var(--primary-500);
  transition: width 0.3s;
}

.standards-progress .progress-summary {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}

.standards-result {
  padding: var(--space-3);
  background: var(--fill-light);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}

.standards-result p {
  margin: 0;
  font-size: 14px;
}

.standards-result p.success {
  color: #67c23a;
}

.standards-result p.error {
  color: #f56c6c;
}

.standards-table {
  margin-top: var(--space-4);
}

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
</style>