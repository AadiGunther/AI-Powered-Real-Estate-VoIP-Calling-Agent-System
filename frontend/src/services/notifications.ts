import api from './api';
import toast from 'react-hot-toast';
import type {
    Notification,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferenceItem,
} from '../types/notification';
import { useNotificationStore, useAuthStore } from '../store';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchNotifications(page = 1, pageSize = 20): Promise<void> {
    const response = await api.get<NotificationListResponse>('/notifications', {
        params: {
            page,
            page_size: pageSize,
        },
    });
    const data = response.data;
    useNotificationStore.getState().setNotifications(data.notifications);
}

export async function fetchUnreadCount(): Promise<void> {
    const response = await api.get<number>('/notifications/unread/count');
    useNotificationStore.getState().setUnreadCount(response.data);
}

export async function markNotificationRead(id: number): Promise<void> {
    await api.post(`/notifications/${id}/read`);
    useNotificationStore.getState().markAsRead(id);
}

export async function deleteNotification(id: number): Promise<void> {
    await api.delete(`/notifications/${id}`);
    const store = useNotificationStore.getState();
    const remaining = store.items.filter((n) => n.id !== id);
    store.setNotifications(remaining);
}

export async function getNotificationPreferences(): Promise<NotificationPreferencesResponse> {
    const response = await api.get<NotificationPreferencesResponse>('/notifications/preferences');
    return response.data;
}

export async function updateNotificationPreferences(
    items: NotificationPreferenceItem[]
): Promise<NotificationPreferencesResponse> {
    const response = await api.put<NotificationPreferencesResponse>('/notifications/preferences', {
        items,
    });
    return response.data;
}

let ws: WebSocket | null = null;

export function connectNotificationWebSocket(): void {
    const token = useAuthStore.getState().token || localStorage.getItem('token');
    if (!token) {
        return;
    }
    const url = new URL('/notifications/ws', API_BASE_URL.replace(/^http/, 'ws'));
    url.searchParams.set('token', token);
    if (ws) {
        ws.close();
    }
    ws = new WebSocket(url.toString());
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data) as Notification;
            useNotificationStore.getState().addNotification(payload);
            toast(payload.message, {
                icon: '🔔',
                duration: 4000,
            });
        } catch {
        }
    };
    ws.onclose = () => {
        ws = null;
    };
}

export function disconnectNotificationWebSocket(): void {
    if (ws) {
        ws.close();
        ws = null;
    }
}

