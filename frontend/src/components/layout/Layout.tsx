import React, { useEffect, useState, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard, PanelsTopLeft, Users, Phone, CalendarDays,
    Settings, LogOut, ChevronLeft, ChevronRight, Bell
} from 'lucide-react';
import { useAuthStore, useUIStore, useNotificationStore } from '../../store';
import { fetchNotifications, fetchUnreadCount, connectNotificationWebSocket, disconnectNotificationWebSocket, markNotificationRead } from '../../services/notifications';
import './Layout.css';

const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/properties', icon: PanelsTopLeft, label: 'Products' },
    { path: '/leads', icon: Users, label: 'Leads' },
    { path: '/appointments', icon: CalendarDays, label: 'Appointments' },
    { path: '/calls', icon: Phone, label: 'All Calls' },
    { path: '/calls/received', icon: Phone, label: 'Received Calls' },
    { path: '/calls/failed', icon: Phone, label: 'Failed Calls' },
];

const adminItems = [
    { path: '/admin/users', icon: Settings, label: 'User Management' },
];

interface LayoutProps {
    children: React.ReactNode;
}

const formatNotifTime = (iso: string | undefined): string => {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        const now = new Date();
        const diffMs = now.getTime() - d.getTime();
        const diffMin = Math.floor(diffMs / 60000);
        if (diffMin < 1) return 'Just now';
        if (diffMin < 60) return `${diffMin}m ago`;
        const diffHr = Math.floor(diffMin / 60);
        if (diffHr < 24) return `${diffHr}h ago`;
        const diffDay = Math.floor(diffHr / 24);
        if (diffDay < 7) return `${diffDay}d ago`;
        return d.toLocaleDateString();
    } catch {
        return '';
    }
};

export const Layout: React.FC<LayoutProps> = ({ children }) => {
    const navigate = useNavigate();
    const { user, logout } = useAuthStore();
    const { sidebarOpen, toggleSidebar } = useUIStore();
    const { items, unreadCount } = useNotificationStore();
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const handleLogout = () => {
        disconnectNotificationWebSocket();
        logout();
        navigate('/login');
    };

    // Click-outside handler
    useEffect(() => {
        if (!dropdownOpen) return;
        const handleClickOutside = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [dropdownOpen]);

    useEffect(() => {
        if (!user) {
            return;
        }
        fetchNotifications().catch(() => { });
        fetchUnreadCount().catch(() => { });
        connectNotificationWebSocket();
        return () => {
            disconnectNotificationWebSocket();
        };
    }, [user]);

    const handleNotificationClick = (id: number) => {
        markNotificationRead(id).catch(() => { });
    };

    return (
        <div className="layout">
            <aside className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
                <div className="sidebar-header">
                    <PanelsTopLeft className="sidebar-logo-icon" />
                    {sidebarOpen && <span className="sidebar-logo-text">Ujjwal Energies</span>}
                </div>

                <nav className="sidebar-nav">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                        >
                            <item.icon size={20} />
                            {sidebarOpen && <span>{item.label}</span>}
                        </NavLink>
                    ))}

                    {user?.role === 'admin' && (
                        <>
                            <div className="nav-divider" />
                            {adminItems.map((item) => (
                                <NavLink
                                    key={item.path}
                                    to={item.path}
                                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                                >
                                    <item.icon size={20} />
                                    {sidebarOpen && <span>{item.label}</span>}
                                </NavLink>
                            ))}
                        </>
                    )}
                </nav>

                <div className="sidebar-footer">
                    <button className="nav-item logout-btn" onClick={handleLogout}>
                        <LogOut size={20} />
                        {sidebarOpen && <span>Logout</span>}
                    </button>
                </div>

                <button className="sidebar-toggle" onClick={toggleSidebar}>
                    {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
                </button>
            </aside>

            <main className="main-content">
                <header className="top-header">
                    <div className="header-left">
                        <h1 className="page-title">Ujjwal Energies Solar Console</h1>
                    </div>
                    <div className="header-right">
                        <div className="notification-bell" ref={dropdownRef}>
                            <button
                                className="icon-button"
                                onClick={() => setDropdownOpen((open) => !open)}
                            >
                                <Bell size={20} />
                                {unreadCount > 0 && (
                                    <span className="notification-badge">
                                        {unreadCount > 9 ? '9+' : unreadCount}
                                    </span>
                                )}
                            </button>
                            {dropdownOpen && (
                                <div className="notification-dropdown">
                                    <div className="notification-dropdown-header">
                                        <span>Notifications</span>
                                        {unreadCount > 0 && <span>{unreadCount} unread</span>}
                                    </div>
                                    {items.length === 0 && (
                                        <div className="notification-empty">No notifications yet</div>
                                    )}
                                    {items.map((notification) => (
                                        <button
                                            key={notification.id}
                                            className={`notification-item ${notification.is_read ? 'read' : ''}`}
                                            onClick={() => handleNotificationClick(notification.id)}
                                        >
                                            <div className="notification-message">{notification.message}</div>
                                            <div className="notification-meta">
                                                <span className="notification-type">{notification.type.replace(/_/g, ' ')}</span>
                                                <span className="notification-time">{formatNotifTime(notification.created_at)}</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div className="user-info">
                            <span className="user-name">{user?.full_name}</span>
                            <span className="user-role">{user?.role}</span>
                        </div>
                    </div>
                </header>
                <div className="page-content">{children}</div>
            </main>
        </div>
    );
};
