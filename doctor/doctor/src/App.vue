<template>
  <div class="app-container">
    <!-- 顶部导航栏 -->
    <header class="header">
      <div class="header-inner">
        <h1 class="logo">肺炎辅助检测系统</h1>
      </div>
    </header>

    <!-- 主体内容 -->
    <main class="main-content">
      <div class="content-inner">
        <!-- 左侧上传区域 -->
        <div class="upload-section">
          <div class="section-title">上传检测图片</div>
          <div class="upload-card" @click="triggerFileInput" @dragover.prevent @dragleave.prevent @drop.prevent="handleDrop">
            <div class="upload-icon">📷</div>
            <div class="upload-text">点击或拖拽图片到此处上传</div>
            <div class="upload-hint">支持 JPG/PNG 格式，最大 10MB</div>
            <input
                type="file"
                ref="fileInput"
                accept="image/*"
                class="file-input"
                @change="handleFileChange"
            >
          </div>
          <button class="detect-btn" :disabled="!selectedFile" @click="detectImage">
            <span v-if="!isLoading">开始检测</span>
            <span v-if="isLoading">检测中...</span>
          </button>
        </div>

        <!-- 右侧结果展示 -->
        <div class="result-section">
          <div class="section-title">检测结果</div>
          <div class="result-card" v-if="!showResult">
            <div class="empty-result">
              <div class="empty-icon">📊</div>
              <div class="empty-text">上传图片后点击检测，结果将显示在此处</div>
            </div>
          </div>

          <div class="result-card" v-if="showResult">
            <div class="loading-wrapper" v-if="isLoading">
              <div class="loading-spinner"></div>
              <div class="loading-text">正在分析图片，请稍候...</div>
            </div>

            <div class="result-content" v-else>
              <!-- 图片预览 -->
              <div class="image-preview">
                <img :src="previewImage" alt="检测图片" />
              </div>

              <!-- 结果信息 -->
              <div class="result-info">
                <div class="result-item">
                  <label class="result-label">分类结果：</label>
                  <span class="result-value" :class="resultClass">{{ predResult }}</span>
                </div>
                <div class="result-item">
                  <label class="result-label">置信度：</label>
                  <span class="result-value">{{ confidence }}</span>
                </div>
                <div class="result-item">
                  <label class="result-label">模型类型：</label>
                  <span class="result-value">{{ modelType }}</span>
                </div>
              </div>

              <!-- 豆包AI建议区域 -->
              <div class="ai-advice-section">
                <div class="section-title">豆包AI建议</div>
                <div class="ai-advice-card" v-if="isAiLoading">
                  <div class="loading-spinner small"></div>
                  <div class="loading-text">豆包正在生成建议...</div>
                </div>
                <div class="ai-advice-card" v-else>
                  <div class="ai-advice-content" v-html="aiAdvice"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部版权 -->
    <footer class="footer">
      <div class="footer-inner">
        <p>肺炎辅助检测系统</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import {ref} from 'vue'
import axios from 'axios'

// ====================== 需自行配置的参数 ======================
// 1. 后端检测接口地址
const SERVER_URL = "https://uu857653-8224-9bcd913a.westb.seetacloud.com:8443/api/detect"
// 2. 豆包API密钥（前往https://www.doubao.com/developer获取）
const DOUBAN_API_KEY = "" // 填入你的豆包API密钥
// =============================================================

const DOUBAN_API_URL = "https://api.doubao.com/v1/chat/completions"

// 响应式数据
const fileInput = ref(null)
const selectedFile = ref(null)
const previewImage = ref('')
const isLoading = ref(false)
const showResult = ref(false)
const predResult = ref('-')
const confidence = ref('-')
const modelType = ref('-')
const resultClass = ref('')
// 豆包AI相关
const aiAdvice = ref('')
const isAiLoading = ref(false)

// 触发文件选择框
const triggerFileInput = () => {
  fileInput.value.click()
}

// 处理文件选择
const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (file) {
    handleFile(file)
  }
}

// 处理拖拽上传
const handleDrop = (e) => {
  const file = e.dataTransfer.files[0]
  if (file) {
    handleFile(file)
  }
}

// 通用文件处理逻辑
const handleFile = (file) => {
  // 验证文件大小（10MB以内）
  if (file.size > 10 * 1024 * 1024) {
    alert('图片大小不能超过10MB！')
    return
  }
  // 验证文件类型
  if (!file.type.startsWith('image/')) {
    alert('请选择图片文件（JPG/PNG）！')
    return
  }

  selectedFile.value = file
  // 生成预览图
  const reader = new FileReader()
  reader.onload = (e) => {
    previewImage.value = e.target.result
    showResult.value = true // 选择图片后显示结果区域
  }
  reader.readAsDataURL(file)
  // 重置结果
  resetResult()
}

// 重置检测结果
const resetResult = () => {
  predResult.value = '-'
  confidence.value = '-'
  modelType.value = '-'
  resultClass.value = ''
  aiAdvice.value = DOUBAN_API_KEY ? '' : '请先配置豆包API密钥以获取建议'
}

// 发送检测请求（修复400错误核心）
const detectImage = async () => {
  if (!selectedFile.value) return

  isLoading.value = true
  try {
    // 1. 正确构建FormData（修复400错误关键）
    const formData = new FormData()
    formData.append('image', selectedFile.value) // 确保字段名和后端一致

    // 2. 简化请求头，避免跨域/格式问题
    const response = await axios.post(
        SERVER_URL,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data' // 显式指定表单格式
          },
          withCredentials: false // 关闭跨域凭证，避免后端校验失败
        }
    )

    const data = response.data
    if (data.code === 0 && data.data?.detectResults.length) {
      // 解析检测结果
      const result = data.data.detectResults[0]
      predResult.value = result.className
      resultClass.value = 'success'
      confidence.value = `${(result.confidence * 100).toFixed(2)}%`
      modelType.value = data.data.modelInfo?.modelType || 'YOLO分类模型'

      // 检测完成后，调用豆包AI生成建议（仅配置密钥后执行）
      if (DOUBAN_API_KEY) {
        await getDoubanAdvice(result.className)
      }
    } else {
      // 无有效检测结果
      predResult.value = '未检测到有效结果'
      resultClass.value = 'error'
      confidence.value = '0%'
      modelType.value = '未知'
    }
  } catch (error) {
    // 错误处理（更详细的提示）
    predResult.value = '检测失败'
    resultClass.value = 'error'
    confidence.value = '-'
    modelType.value = '-'

    // 区分错误类型，方便排查
    if (error.response?.status === 400) {
      alert(`检测失败：请求参数错误，请检查文件格式/后端接口配置\n错误详情：${error.message}`)
    } else if (error.response?.status === 500) {
      alert(`检测失败：后端服务器错误，请联系管理员`)
    } else if (error.message.includes('Network')) {
      alert(`检测失败：网络异常，请检查后端服务是否可用`)
    } else {
      alert(`检测失败：${error.message}`)
    }
  } finally {
    isLoading.value = false
  }
}

// 调用豆包API生成建议
const getDoubanAdvice = async (diseaseType) => {
  if (!DOUBAN_API_KEY) {
    aiAdvice.value = '请配置豆包API密钥以获取建议'
    return
  }

  isAiLoading.value = true
  try {
    const response = await axios.post(
        DOUBAN_API_URL,
        {
          model: "doubao-pro", // 豆包模型版本
          messages: [
            {
              role: "user",
              content: `请针对${diseaseType}，给出简洁、专业的日常护理建议和注意事项，内容分点，适合普通用户阅读，语言通俗易懂`
            }
          ],
          temperature: 0.7, // 建议多样性
          max_tokens: 500 // 最大回复长度
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${DOUBAN_API_KEY}`
          }
        }
    )
    // 格式化返回结果（适配前端展示）
    const rawAdvice = response.data.choices[0].message.content
    aiAdvice.value = rawAdvice.replace(/\n/g, '<br>').replace(/\*+/g, '').replace(/- /g, '● ')
  } catch (error) {
    aiAdvice.value = `豆包建议获取失败：${error.response?.data?.error?.message || error.message}`
  } finally {
    isAiLoading.value = false
  }
}
</script>

<style scoped>
/* 全局布局 - 全屏核心 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  height: 100%;
  overflow-x: hidden;
}

.app-container {
  min-height: 100vh;
  width: 100vw; /* 宽度占满视口 */
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

/* 顶部导航 - 全屏 */
.header {
  background-color: #2c3e50;
  color: white;
  height: 70px;
  line-height: 70px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  width: 100%; /* 宽度占满 */
}

.header-inner {
  width: 100%; /* 去掉固定宽度，占满 */
  padding: 0 40px; /* 左右留白，避免贴边 */
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

/* 主体内容 - 全屏核心 */
.main-content {
  flex: 1;
  width: 100%; /* 宽度占满 */
  padding: 40px; /* 内边距，避免内容贴边 */
}

.content-inner {
  width: 100%; /* 去掉固定宽度，占满 */
  height: 100%; /* 高度占满父容器 */
  display: flex;
  gap: 40px; /* 加大间距，适配大屏 */
}

/* 左侧上传区域 - 全屏适配 */
.upload-section {
  flex: 1; /* 按比例分配宽度 */
  display: flex;
  flex-direction: column;
  gap: 30px;
  height: 100%; /* 高度占满 */
}

/* 右侧结果区域 - 全屏适配 */
.result-section {
  flex: 2; /* 右侧占比更大，适配全屏 */
  display: flex;
  flex-direction: column;
  gap: 30px;
  height: 100%; /* 高度占满 */
}

.section-title {
  font-size: 20px; /* 放大标题，适配大屏 */
  font-weight: 600;
  color: #2c3e50;
  border-left: 4px solid #3498db;
  padding-left: 15px;
  margin-bottom: 15px;
}

/* 上传卡片 - 全屏放大 */
.upload-card {
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 80px 40px; /* 加大内边距，适配全屏 */
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px dashed #3498db;
  flex: 1; /* 高度自动占满剩余空间 */
  display: flex;
  flex-direction: column;
  justify-content: center; /* 内容垂直居中 */
}

.upload-card:hover {
  border-color: #2980b9;
  background-color: #f8fbff;
  transform: translateY(-2px);
}

.upload-icon {
  font-size: 90px; /* 放大图标，适配大屏 */
  color: #3498db;
  margin-bottom: 30px;
}

.upload-text {
  font-size: 22px; /* 放大文字，适配大屏 */
  color: #34495e;
  margin-bottom: 15px;
}

.upload-hint {
  font-size: 16px; /* 放大提示文字 */
  color: #7f8c8d;
}

.file-input {
  display: none;
}

/* 检测按钮 - 全屏放大 */
.detect-btn {
  height: 60px; /* 加高按钮 */
  line-height: 60px;
  background-color: #3498db;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 18px; /* 放大按钮文字 */
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 8px rgba(52, 152, 219, 0.2);
}

.detect-btn:hover {
  background-color: #2980b9;
  transform: translateY(-2px);
}

.detect-btn:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 结果卡片 - 全屏占满 */
.result-card {
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 40px; /* 加大内边距 */
  flex: 1; /* 高度占满剩余空间 */
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.empty-result {
  text-align: center;
  color: #7f8c8d;
}

.empty-icon {
  font-size: 90px; /* 放大空状态图标 */
  margin-bottom: 30px;
  color: #bdc3c7;
}

.empty-text {
  font-size: 20px; /* 放大空状态文字 */
}

/* 加载中 - 全屏放大 */
.loading-wrapper {
  text-align: center;
}

.loading-spinner {
  border: 6px solid #f3f3f3;
  border-top: 6px solid #3498db;
  border-radius: 50%;
  width: 70px; /* 放大加载动画 */
  height: 70px;
  animation: spin 1s linear infinite;
  margin: 0 auto 30px;
}

.loading-spinner.small {
  width: 30px;
  height: 30px;
  margin: 0 10px 0 0;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 20px; /* 放大加载文字 */
  color: #34495e;
}

/* 结果内容 - 全屏适配 */
.result-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
  height: 100%;
}

.image-preview {
  text-align: center;
  flex: 1; /* 图片区域占满高度 */
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-preview img {
  max-width: 100%;
  max-height: 100%; /* 图片高度占满父容器 */
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 20px;
}

.result-item {
  font-size: 20px; /* 放大结果文字 */
  display: flex;
  align-items: center;
  gap: 15px;
}

.result-label {
  font-weight: 600;
  color: #2c3e50;
  min-width: 100px; /* 加宽标签宽度 */
  font-size: 20px;
}

.result-value {
  color: #34495e;
  font-size: 20px;
}

.success {
  color: #2ecc71;
  font-weight: 600;
}

.error {
  color: #e74c3c;
  font-weight: 600;
}

/* 豆包AI建议区域 */
.ai-advice-section {
  margin-top: 30px;
}

.ai-advice-card {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-top: 10px;
  display: flex;
  align-items: flex-start;
  line-height: 1.8;
}

.ai-advice-content {
  width: 100%;
  font-size: 16px;
  color: #34495e;
}

/* 底部版权 - 全屏 */
.footer {
  background-color: #2c3e50;
  color: white;
  text-align: center;
  padding: 20px 0;
  font-size: 16px;
  width: 100%; /* 宽度占满 */
  margin-top: auto;
}

.footer-inner {
  width: 100%;
  padding: 0 20px;
}

/* 响应式适配 - 大屏优先 */
@media (max-width: 1200px) {
  .content-inner {
    gap: 30px;
  }

  .upload-card {
    padding: 60px 30px;
  }

  .upload-icon {
    font-size: 70px;
  }

  .upload-text {
    font-size: 18px;
  }
}

@media (max-width: 992px) {
  .content-inner {
    flex-direction: column;
  }

  .upload-section, .result-section {
    height: auto;
  }

  .upload-card {
    padding: 40px 20px;
    min-height: 400px;
  }
}
</style>