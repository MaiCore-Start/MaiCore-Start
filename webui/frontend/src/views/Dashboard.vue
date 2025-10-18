<template>
  <div class="dashboard">
    <div class="controls">
      <h2>数据统计仪表盘</h2>
      <div class="selector-group">
        <label for="instance-select">选择实例:</label>
        <select id="instance-select" v-model="selectedInstance" @change="handleInstanceChange">
          <option disabled value="">请选择一个实例</option>
          <option v-for="(instance, name) in instances" :key="name" :value="name">
            {{ name }} ({{ instance.nickname_path || '无昵称' }})
          </option>
        </select>
      </div>
    </div>

    <div v-if="isLoading" class="loading">正在加载数据...</div>
    <div v-if="error" class="error">{{ error }}</div>

    <div v-if="chartData" class="charts-container">
      <div class="chart-wrapper">
        <canvas ref="totalCostChartCanvas"></canvas>
      </div>
      <div class="chart-wrapper">
        <canvas ref="costByModuleChartCanvas"></canvas>
      </div>
      <div class="chart-wrapper">
        <canvas ref="costByModelChartCanvas"></canvas>
      </div>
    </div>
    <div v-if="!selectedInstance && !error" class="placeholder">
      请从上方选择一个实例以查看其统计数据。
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, shallowRef } from 'vue';
import apiClient from '../api/client';
import Chart from 'chart.js/auto';

const instances = ref({});
const selectedInstance = ref('');
const chartData = ref(null);
const isLoading = ref(false);
const error = ref('');

// 用于持有图表实例的引用
const chartInstances = shallowRef({});

// Canvas 元素的引用
const totalCostChartCanvas = ref(null);
const costByModuleChartCanvas = ref(null);
const costByModelChartCanvas = ref(null);

// 获取所有实例列表以填充下拉菜单
const fetchInstances = async () => {
  try {
    const response = await apiClient.get('/instances');
    instances.value = response.data;
  } catch (err) {
    error.value = '无法加载实例列表。';
  }
};

// 当用户选择一个实例时触发
const handleInstanceChange = async () => {
  if (!selectedInstance.value) return;
  
  isLoading.value = true;
  error.value = '';
  chartData.value = null;
  destroyCharts();

  try {
    const response = await apiClient.get(`/statistics/${selectedInstance.value}`);
    chartData.value = response.data;
    // 数据加载后渲染图表
    renderCharts();
  } catch (err) {
    error.value = `加载实例 '${selectedInstance.value}' 的统计数据失败: ${err.response?.data?.detail || err.message}`;
  } finally {
    isLoading.value = false;
  }
};

const renderCharts = () => {
  if (!chartData.value) return;

  // 通常，我们会选择一个默认的时间范围，例如 '24h'
  const data = chartData.value['24h'];
  if (!data) {
    error.value = "所选实例的统计数据中缺少 '24h' 时间范围的数据。";
    return;
  }
  
  // 销毁旧图表
  destroyCharts();

  // 渲染新图表
  chartInstances.value.totalCost = createLineChart(totalCostChartCanvas.value, '总花费趋势', data.time_labels, [{ label: '总花费', data: data.total_cost_data }]);
  chartInstances.value.costByModule = createBarChart(costByModuleChartCanvas.value, '各模块花费', Object.keys(data.cost_by_module), Object.values(data.cost_by_module).map(arr => arr.reduce((a, b) => a + b, 0)));
  chartInstances.value.costByModel = createBarChart(costByModelChartCanvas.value, '各模型花费', Object.keys(data.cost_by_model), Object.values(data.cost_by_model).map(arr => arr.reduce((a, b) => a + b, 0)));
};

const createLineChart = (canvas, title, labels, datasets) => {
  if (!canvas) return null;
  const colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6'];
  return new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: datasets.map((ds, i) => ({
        ...ds,
        borderColor: colors[i % colors.length],
        tension: 0.1,
        fill: false,
      })),
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: title } },
    },
  });
};

const createBarChart = (canvas, title, labels, data) => {
    if (!canvas) return null;
    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: '总花费',
                data,
                backgroundColor: '#3498db',
            }]
        },
        options: {
            responsive: true,
            plugins: { title: { display: true, text: title } },
            scales: { y: { beginAtZero: true } }
        }
    });
};


const destroyCharts = () => {
  Object.values(chartInstances.value).forEach(chart => {
    if (chart) chart.destroy();
  });
  chartInstances.value = {};
};

onMounted(fetchInstances);
</script>

<style scoped>
.dashboard {
  max-width: 1200px;
  margin: 0 auto;
}
.controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.selector-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.charts-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2rem;
}
@media (min-width: 992px) {
  .charts-container {
    grid-template-columns: 1fr 1fr;
  }
}
.chart-wrapper {
  background: #fff;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.loading, .error, .placeholder {
  text-align: center;
  padding: 2rem;
  font-size: 1.2rem;
  color: #6c757d;
}
</style>