import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard, PanelsTopLeft, Users, Phone, BarChart3,
    Settings, LogOut, ChevronLeft, ChevronRight
} from 'lucide-react';
import { useAuthStore, useUIStore } from '../../store';
import './Layout.css';

const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/properties', icon: PanelsTopLeft, label: 'Products' },
    { path: '/leads', icon: Users, label: 'Leads' },
    { path: '/calls', icon: Phone, label: 'Calls' },
    { path: '/reports', icon: BarChart3, label: 'Reports' },
];

const adminItems = [
    { path: '/admin/users', icon: Settings, label: 'User Management' },
];

interface LayoutProps {
    children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
    const navigate = useNavigate();
    const { user, logout } = useAuthStore();
    const { sidebarOpen, toggleSidebar } = useUIStore();

    const handleLogout = () => {
        logout();
        navigate('/login');
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
