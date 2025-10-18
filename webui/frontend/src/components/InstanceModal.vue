<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal-content">
      <div class="modal-header">
        <h2>{{ isNew ? '新建配置集' : `编辑: ${editableName}` }}</h2>
        <button @click="emit('close')" class="close-btn">&times;</button>
      </div>
      <form @submit.prevent="handleSubmit">
        <div class="modal-body">
          <!-- 新建时可编辑配置集名称 -->
          <div v-if="isNew" class="form-group">
            <label for="config-name">配置集名称</label>
            <input id="config-name" v-model="editableName" required placeholder="例如: my_instance_1" />
          </div>

          <!-- 循环渲染所有字段 -->
          <div v-for="key in Object.keys(formState)" :key="key" class="form-group">
            <label :for="`field-${key}`">{{ fieldLabels[key] || key }}</label>
            <input 
              :id="`field-${key}`"
              v-model="formState[key]" 
              :readonly="key === 'absolute_serial_number'"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="emit('close')">取消</button>
          <button type="submit" class="btn btn-primary">{{ isNew ? '创建' : '保存' }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue';

const props = defineProps({
  show: Boolean,
  instance: Object,
  name: String
});

const emit = defineEmits(['close', 'save']);

const formState = ref({});
const editableName = ref('');

const isNew = computed(() => !props.instance || !props.name);

// 字段标签映射，用于显示更友好的名称
const fieldLabels = {
    serial_number: "用户序列号",
    absolute_serial_number: "绝对序列号 (自动分配)",
    version_path: "版本号",
    nickname_path: "实例昵称",
    bot_type: "Bot类型",
    qq_account: "QQ账号",
    mai_path: "MaiBot 本体路径",
    mofox_path: "MoFox 本体路径",
    adapter_path: "适配器路径",
    napcat_path: "NapCat 路径",
    venv_path: "虚拟环境路径",
    mongodb_path: "MongoDB 路径",
    webui_path: "WebUI 路径",
};

// 侦听prop变化，更新内部表单状态
watch(() => props.show, (newVal) => {
  if (newVal) {
    // 深拷贝一个可编辑的对象，避免直接修改prop
    formState.value = JSON.parse(JSON.stringify(props.instance || {
        serial_number: "",
        version_path: "",
        nickname_path: "",
        bot_type: "MaiBot",
        qq_account: "",
        mai_path: "",
        mofox_path: "",
        adapter_path: "",
        napcat_path: "",
        venv_path: "",
        mongodb_path: "",
        webui_path: "",
    }));
    // absolute_serial_number 在编辑时不应该存在于表单中
    if (!isNew.value) {
      delete formState.value.absolute_serial_number;
    }
    editableName.value = props.name || '';
  }
}, { immediate: true });

const handleSubmit = () => {
  emit('save', { name: editableName.value, config: formState.value });
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}
.modal-body {
  overflow-y: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.form-group {
  display: flex;
  flex-direction: column;
}
.modal-footer {
  border-top: 1px solid #dee2e6;
  padding-top: 1rem;
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}
.btn-primary { background-color: #007bff; color: white; }
.btn-secondary { background-color: #6c757d; color: white; }
.close-btn { background: none; border: none; font-size: 1.5rem; cursor: pointer; }
</style>