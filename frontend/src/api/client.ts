import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";
import type { ApiError } from "@/types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: ApiError["details"];
  readonly requestId: string;

  constructor(status: number, body: ApiError) {
    super(body.message);
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

function createClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: BASE_URL,
    withCredentials: false,
    timeout: 30000,
  });

  // Attach the access token on every request.
  instance.interceptors.request.use((config) => {
    const { accessToken } = useAuthStore.getState();
    if (accessToken) {
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  });

  // Normalise errors into ApiClientError so React Query can key on them.
  instance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError<ApiError>) => {
      if (error.response) {
        const body = error.response.data;
        // Attempt a one-shot refresh on 401 for non-auth endpoints
        if (
          error.response.status === 401 &&
          !error.config?.url?.includes("/auth/login") &&
          !error.config?.url?.includes("/auth/refresh")
        ) {
          const refreshed = await useAuthStore.getState().tryRefresh();
          if (refreshed && error.config) {
            return instance.request(error.config);
          }
          // Refresh failed — sign the user out
          useAuthStore.getState().logout();
        }
        if (body && typeof body === "object" && "code" in body) {
          throw new ApiClientError(error.response.status, body);
        }
      }
      throw new ApiClientError(error.response?.status ?? 0, {
        code: "NETWORK_ERROR",
        message: error.message ?? "Network error",
        request_id: "unknown",
      });
    },
  );

  return instance;
}

export const api = createClient();

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await api.request<T>(config);
  return response.data;
}
