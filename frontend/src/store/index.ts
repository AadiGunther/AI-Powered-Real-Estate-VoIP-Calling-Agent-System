import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types/auth';
import type { Notification } from '../types/notification';

interface AuthStore {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    setUser: (user: User | null) => void;
    setToken: (token: string | null) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthStore>()(
    persist(
        (set) => ({
            user: null,
            token: null,
            isAuthenticated: false,
            setUser: (user) => set({ user, isAuthenticated: !!user }),
            setToken: (token) => {
                if (token) {
                    localStorage.setItem('token', token);
                } else {
                    localStorage.removeItem('token');
                }
                set({ token, isAuthenticated: !!token });
            },
            logout: () => {
                localStorage.removeItem('token');
                set({ user: null, token: null, isAuthenticated: false });
            },
        }),
        {
            name: 'auth-storage',
            partialize: (state) => ({ token: state.token }),
        }
    )
);

interface UIStore {
    sidebarOpen: boolean;
    toggleSidebar: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
    sidebarOpen: true,
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));

interface NotificationStore {
    items: Notification[];
    unreadCount: number;
    setNotifications: (notifications: Notification[]) => void;
    setUnreadCount: (count: number) => void;
    addNotification: (notification: Notification) => void;
    markAsRead: (id: number) => void;
}

export const useNotificationStore = create<NotificationStore>((set) => ({
    items: [],
    unreadCount: 0,
    setNotifications: (notifications) =>
        set({
            items: notifications,
            unreadCount: notifications.filter((n) => !n.is_read).length,
        }),
    setUnreadCount: (count) => set({ unreadCount: count }),
    addNotification: (notification) =>
        set((state) => ({
            items: [notification, ...state.items],
            unreadCount: state.unreadCount + (notification.is_read ? 0 : 1),
        })),
    markAsRead: (id) =>
        set((state) => ({
            items: state.items.map((n) =>
                n.id === id ? { ...n, is_read: true } : n
            ),
            unreadCount: state.unreadCount > 0 ? state.unreadCount - 1 : 0,
        })),
}));
