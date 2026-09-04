import axios from "axios";

function resolveApiBaseUrl() {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }

  const { protocol, hostname } = window.location;
  const devTunnelMatch = hostname.match(/^(.+)-(\d+)\.inc1\.devtunnels\.ms$/);
  if (devTunnelMatch) {
    return `${protocol}//${devTunnelMatch[1]}-5001.inc1.devtunnels.ms/api`;
  }

  return "http://localhost:5001/api";
}

const API_BASE_URL = resolveApiBaseUrl();

const client = axios.create({
  baseURL: API_BASE_URL,
});

let guestRecoveryPromise = null;

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("cc_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isUnauthorized = error.response?.status === 401;
    const isAuthRequest = originalRequest?.url?.includes("/auth/");

    if (
      !isUnauthorized ||
      !originalRequest ||
      originalRequest._guestRecoveryAttempted ||
      isAuthRequest ||
      localStorage.getItem("cc_auth_mode") !== "guest"
    ) {
      return Promise.reject(error);
    }

    originalRequest._guestRecoveryAttempted = true;
    try {
      guestRecoveryPromise ||= axios.post(`${API_BASE_URL}/auth/guest`);
      const recoveryResponse = await guestRecoveryPromise;
      const token = recoveryResponse.data?.token;
      if (!token) return Promise.reject(error);
      localStorage.setItem("cc_token", token);
      originalRequest.headers = originalRequest.headers || {};
      originalRequest.headers.Authorization = `Bearer ${token}`;
      return client(originalRequest);
    } catch {
      return Promise.reject(error);
    } finally {
      guestRecoveryPromise = null;
    }
  },
);

export default client;
