import axios, { type InternalAxiosRequestConfig } from "axios";

import { useToastStore } from "@/stores/toast";

declare module "axios" {
  export interface InternalAxiosRequestConfig {
    /** 设为 true 时 interceptor 不主动 toast(由调用方自己处理错误)。 */
    silentError?: boolean;
  }
  export interface AxiosRequestConfig {
    silentError?: boolean;
  }
}

const client = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: 30000,
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    const cfg = err.config as InternalAxiosRequestConfig | undefined;
    const status = err.response?.status;

    if (status === 401) {
      const here = window.location.pathname + window.location.search;
      if (!here.startsWith("/login")) {
        window.location.href = `/login?from=${encodeURIComponent(here)}`;
      }
    } else if (!cfg?.silentError && status && status >= 500) {
      // 5xx 才统一 toast;4xx 由调用方按业务处理(避免 settings 测试连接重复弹)
      try {
        useToastStore().err(
          err.response?.data?.detail || `服务器错误 ${status}`
        );
      } catch {
        // pinia 还没装就忽略
      }
    } else if (!cfg?.silentError && !err.response) {
      // 网络断了
      try {
        useToastStore().err("网络不可达,请检查后端服务");
      } catch {}
    }
    return Promise.reject(err);
  }
);

export default client;
