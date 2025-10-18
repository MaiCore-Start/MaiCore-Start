<template>
  <div class="settings">
    <h2>程序设置</h2>
    <form v-if="settings" @submit.prevent="saveSettings">
      <div class="form-section">
        <h3>主题颜色 (Theme)</h3>
        <div class="form-grid">
          <div v-for="(color, key) in settings.theme" :key="key" class="form-group">
            <label :for="`theme-${key}`">{{ key }}</label>
            <input :id="`theme-${key}`" v-model="settings.theme[key]" type="text" />
          </div>
        </div>
      </div>

      <div class="form-section">
        <h3>日志 (Logging)</h3>
        <div class="form-group">
          <label for="log-rotation">日志保留天数</label>
          <input id="log-rotation" v-model.number="settings.logging.log_rotation_days" type="number" />
        </div>
      </div>

      <div class="form-section">
        <h3>显示 (Display)</h3>
        <div class="form-group">
          <label for="max-versions">最大显示版本数</label>
          <input id="max-versions" v-model.number="settings.display.max_versions_display" type="number" />
        </div>
      </div>

      <div class="form-section">
        <h3>WebUI 设置</h3>
        <div class="webui-settings-grid">
          <div class="form-group">
            <label for="backend-port">后端端口</label>
            <input id="backend-port" v-model.number="settings.webui.backend_port" type="number" />
          </div>
          <div class="form-group">
            <label for="frontend-port">前端端口</label>
            <input id="frontend-port" v-model.number="settings.webui.frontend_port" type="number" />
          </div>
        </div>
        <p style="font-size: 0.8rem; color: #6c757d; margin-top: 1rem;">注意：端口修改后需要重启 WebUI 服务才能生效。</p>
      </div>

      <button type="submit" class="save-btn">保存设置</button>
    </form>
    <div v-else>
      正在加载设置...
    </div>
    <p v-if="message" class="message">{{ message }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '../api/client';

const settings = ref(null);
const message = ref('');

// 不安全端口列表
const UNSAFE_PORTS = [
    1, 7, 9, 11, 13, 15, 17, 19, 20, 21, 22, 23, 25, 37, 42, 43, 53,
    69, 77, 79, 87, 95, 101, 102, 103, 104, 109, 110, 111, 113, 115,
    117, 119, 123, 135, 137, 139, 143, 161, 162, 179, 389, 427, 465,
    512, 513, 514, 515, 526, 530, 531, 532, 540, 548, 554, 556, 563,
    587, 601, 636, 989, 990, 993, 995, 1719, 1720, 1723, 2049, 3659,
    4045, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697,
    10080,
];


const fetchSettings = async () => {
  try {
    const response = await apiClient.get('/settings/program');
    settings.value = response.data;
  } catch (error) {
    console.error('获取设置失败:', error);
    message.value = '获取设置失败，请检查后端服务是否运行。';
  }
};

const saveSettings = async () => {
  if (!settings.value) return;

  const backendPort = settings.value.webui.backend_port;
  const frontendPort = settings.value.webui.frontend_port;

  // 前端校验
  if (UNSAFE_PORTS.includes(backendPort)) {
    message.value = `错误：后端端口 ${backendPort} 是浏览器限制的端口，请更换。`;
    return;
  }
  if (UNSAFE_PORTS.includes(frontendPort)) {
    message.value = `错误：前端端口 ${frontendPort} 是浏览器限制的端口，请更换。`;
    return;
  }
  if (backendPort === frontendPort) {
    message.value = '错误：后端和前端的端口不能相同。';
    return;
  }


  try {
    await apiClient.post('/settings/program', settings.value);
    message.value = '设置已成功保存！请注意，端口修改需要重启服务才能生效。';
  } catch (error) {
    console.error('保存设置失败:', error);
    message.value = `保存失败: ${error.response?.data?.detail || error.message}`;
  }
};

onMounted(fetchSettings);
</script>

<style scoped>
.settings {
  max-width: 800px;
  margin: 0 auto;
  text-align: left;
}
.form-section {
  margin-bottom: 2rem;
  padding: 1.5rem;
  border-radius: 8px;
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
}
.webui-settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.form-group {
  display: flex;
  flex-direction: column;
}
label {
  margin-bottom: 0.5rem;
  font-weight: bold;
}
input {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.save-btn {
  display: block;
  width: 100%;
  padding: 0.75rem;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.2s;
}
.save-btn:hover {
  background-color: #0056b3;
}
.message {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #e9ecef;
  border-radius: 4px;
}
</style>