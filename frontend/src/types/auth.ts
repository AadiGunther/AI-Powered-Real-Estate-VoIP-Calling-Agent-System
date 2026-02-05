export interface User {
    id: number;
    email: string;
    full_name: string;
    phone?: string;
    role: 'admin' | 'manager' | 'agent';
    is_active: boolean;
    created_at: string;
    last_login?: string;
}

export interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
}

export interface LoginCredentials {
    email: string;
    password: string;
}

export interface RegisterData {
    email: string;
    password: string;
    full_name: string;
    phone?: string;
}
