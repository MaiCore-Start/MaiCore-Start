<template>
  <div class="instances-page">
    <div class="header">
      <h2>实例配置管理</h2>
      <button @click="openModalForNew" class="btn btn-primary">新建配置集</button>
    </div>

    <div v-if="instances" class="card-grid">
      <InstanceCard
        v-for="(instance, name) in instances"
        :key="name"
        :name="name"
        :instance="instance"
        @view="openModalForEdit(name, instance)"
        @delete="handleDelete(name)"
      />
    </div>
    <p v-else>正在加载实例列表...</p>
    
    <InstanceModal
      v-if="isModalVisible"
      :show="isModalVisible"
      :instance="currentInstance"
      :name="currentInstanceName"
      @close="closeModal"
      @save="handleSave"
    />
    <p v-if="message" class="message">{{ message }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import apiClient from '../api/client';
import InstanceCard from '../components/InstanceCard.vue';
import InstanceModal from '../components/InstanceModal.vue';

const instances = ref(null);
const isModalVisible = ref(false);
const currentInstance = ref(null);
const currentInstanceName = ref('');
const message = ref('');

const fetchInstances = async () => {
  try {
    const response = await apiClient.get('/instances');
    instances.value = response.data;
  } catch (error) {
    message.value = '获取实例列表失败。';
    console.error(error);
  }
};

const openModalForNew = () => {
  currentInstance.value = null;
  currentInstanceName.value = '';
  isModalVisible.value = true;
};

const openModalForEdit = (name, instance) => {
  currentInstance.value = instance;
  currentInstanceName.value = name;
  isModalVisible.value = true;
};

const closeModal = () => {
  isModalVisible.value = false;
};

const handleSave = async ({ name, config }) => {
  const isNew = !currentInstance.value;
  try {
    if (isNew) {
      // 新建
      await apiClient.post('/instances', { name, config });
      message.value = `实例 '${name}' 创建成功！`;
    } else {
      // 更新
      await apiClient.post(`/instances/${name}`, config);
      message.value = `实例 '${name}' 更新成功！`;
    }
    closeModal();
    fetchInstances(); // 重新加载列表
  } catch (error) {
    message.value = `保存失败: ${error.response?.data?.detail || error.message}`;
    console.error(error);
  }
};

const handleDelete = async (name) => {
  if (confirm(`确定要删除配置集 "${name}" 吗？`)) {
    try {
      await apiClient.delete(`/instances/${name}`);
      message.value = `实例 '${name}' 已删除。`;
      fetchInstances(); // 重新加载列表
    } catch (error) {
      message.value = `删除失败: ${error.response?.data?.detail || error.message}`;
      console.error(error);
    }
  }
};

onMounted(fetchInstances);
</script>

<style scoped>
.instances-page {
  max-width: 1200px;
  margin: 0 auto;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}
.message {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #e9ecef;
  border-radius: 4px;
}
</style>