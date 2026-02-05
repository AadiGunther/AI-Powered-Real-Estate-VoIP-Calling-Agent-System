import api from './api';
import type { User, LoginCredentials, RegisterData } from '../types/auth';

export const authService = {
    async login(credentials: LoginCredentials) {
        const response = await api.post<{ access_token: string; expires_in: number }>(
            '/auth/login',
            credentials
        );
        localStorage.setItem('token', response.data.access_token);
        return response.data;
    },

    async register(data: RegisterData) {
        const response = await api.post<User>('/auth/register', data);
        return response.data;
    },

    async getCurrentUser() {
        const response = await api.get<User>('/auth/me');
        return response.data;
    },

    async changePassword(currentPassword: string, newPassword: string) {
        const response = await api.post('/auth/change-password', {
            current_password: currentPassword,
            new_password: newPassword,
        });
        return response.data;
    },

    logout() {
        localStorage.removeItem('token');
        window.location.href = '/login';
    },

    isAuthenticated() {
        return !!localStorage.getItem('token');
    },
};
