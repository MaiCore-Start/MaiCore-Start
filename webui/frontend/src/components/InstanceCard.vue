<template>
  <div class="card" @click="emit('view')">
    <div class="card-header">
      <h3 class="card-title">{{ name }}</h3>
      <button class="delete-btn" @click.stop="emit('delete')">×</button>
    </div>
    <div class="card-body">
      <p><strong>序列号:</strong> {{ instance.serial_number || 'N/A' }}</p>
      <p><strong>Bot 类型:</strong> {{ instance.bot_type || 'N/A' }}</p>
      <p><strong>版本:</strong> {{ instance.version_path || 'N/A' }}</p>
      <p><strong>昵称:</strong> {{ instance.nickname_path || 'N/A' }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  name: {
    type: String,
    required: true
  },
  instance: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['view', 'delete']);
</script>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e9ecef;
}
.card-title {
  margin: 0;
  font-size: 1.25rem;
}
.card-body p {
  margin: 0.5rem 0;
  font-size: 0.9rem;
  color: #6c757d;
}
.delete-btn {
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}
</style>