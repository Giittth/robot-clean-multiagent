import axios from 'axios'

const request = axios.create({
  baseURL: '/api',    // 与后端聚合路由前缀一致
  timeout: 10000,
})

// 请求拦截器（添加 token 等）
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器（处理错误）
request.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API 错误:', error)
    return Promise.reject(error)
  }
)

export default request