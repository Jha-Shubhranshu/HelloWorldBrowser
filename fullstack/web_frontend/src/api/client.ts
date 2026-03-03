// src/api/client.ts
import axios from 'axios'

export const http = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

http.interceptors.request.use((config) => {
  console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.data)
  return config
})

http.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.status} ${response.config.url}`, response.data)
    return response
  },
  (error) => {
    console.error(`[API Error] ${error.response?.status} ${error.config?.url}`, error.response?.data || error.message)
    return Promise.reject(error)
  }
)