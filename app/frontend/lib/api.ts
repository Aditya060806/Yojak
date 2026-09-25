import axios, { AxiosError } from 'axios';

/** Base URL of the Yojak FastAPI backend. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

const ADMIN_TOKEN_KEY = 'yojak.adminToken';

/** Admin token for write routes, kept in sessionStorage for this tab only. */
export function getAdminToken(): string | null {
    if (typeof window === 'undefined') return null;
    try {
        return window.sessionStorage.getItem(ADMIN_TOKEN_KEY);
    } catch {
        return null;
    }
}

export function setAdminToken(token: string | null) {
    if (typeof window === 'undefined') return;
    try {
        if (token) window.sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
        else window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    } catch {
        // Storage blocked (private mode, site-data settings): admin writes will return 401.
    }
}

/** Error thrown by every service call, with the API's `detail` message when there is one. */
export class ApiError extends Error {
    constructor(
        message: string,
        public status: number | null,
    ) {
        super(message);
        this.name = 'ApiError';
    }
}

const api = axios.create({
    baseURL: API_URL,
    timeout: 60_000,
    headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
    const token = getAdminToken();
    if (token) config.headers.set('X-Admin-Token', token);
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error: AxiosError<{ detail?: unknown }>) => {
        if (!error.response) {
            return Promise.reject(
                new ApiError(`Can't reach the Yojak API at ${API_URL}. Is it running?`, null),
            );
        }
        const detail = error.response.data?.detail;
        const message =
            typeof detail === 'string'
                ? detail
                : Array.isArray(detail)
                  ? 'Some inputs were invalid. Please check and try again.'
                  : `Request failed (${error.response.status})`;
        return Promise.reject(new ApiError(message, error.response.status));
    },
);

export default api;
