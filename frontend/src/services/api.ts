import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    console.debug('API Request:', {
        url: `${config.baseURL}${config.url}`,
        method: config.method,
        hasAuth: !!token,
        params: config.params,
    });
    return config;
});

// Handle auth errors
api.interceptors.response.use(
    (response) => {
        console.debug('API Response:', {
            url: response.config.url,
            status: response.status,
            dataKeys: response.data ? Object.keys(response.data) : [],
        });
        return response;
    },
    (error) => {
        console.error('API Error:', {
            url: error.config?.url,
            status: error.response?.status,
            detail: error.response?.data?.detail,
        });
        if (error.response?.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default api;
