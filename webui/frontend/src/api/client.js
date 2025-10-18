import axios from 'axios';

// 创建一个基础的axios实例，用于获取端口信息
// 它使用相对路径，所以会请求当前前端域的 /api/port-info
const portClient = axios.create({
  baseURL: '/api'
});

// 导出一个异步函数，它会返回一个已配置好正确后端口的axios实例
export const getApiClient = async () => {
  try {
    // 后端需要一个能返回自己端口的API, 我们假设它是 /api/service-info
    // 我们暂时硬编码，因为后端无法直接知道自己的端口，但这是一个改进点
    // 更好的做法是，后端启动时知道自己的端口，并能通过API提供
    // **更新：** 更好的方法是，前端直接使用相对路径，让代理（如Nginx）或Vite的开发服务器代理请求
    // 这样前端根本不需要知道后端的端口
    
    const apiClient = axios.create({
        baseURL: `http://${window.location.hostname}:8000/api`, // 默认指向8000
    });

    // 这里可以添加一个ping端点来动态发现端口，但为了简单起见，
    // 我们暂时依赖Vite的代理配置或假定开发端口。
    // 在生产环境中，通常会用Nginx等来反向代理，所以前端不需要关心端口。

    return apiClient;

  } catch (error) {
    console.error("无法获取API客户端:", error);
    // 返回一个无效的客户端或抛出错误
    throw new Error("API服务不可用");
  }
};


// 为了简化，我们将创建一个更简单的axios实例，并依赖Vite的开发代理
// 或者在生产环境中依赖Nginx等反向代理。
// 这意味着前端代码中不需要硬编码端口号。

const apiClient = axios.create({
    // baseURL 将是相对于前端域的。
    // Vite Dev Server 会将 /api 的请求代理到后端。
    baseURL: '/api', 
});

export default apiClient;