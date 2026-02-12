import React, { useState, useEffect } from 'react';
import { Users, Plus, Search, Shield, Edit, Trash2 } from 'lucide-react';
import api from '../../services/api';
import type { User } from '../../types/auth';
import '../properties/Properties.css';

export const UserManagement: React.FC = () => {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        try {
            setError(null);
            setLoading(true);
            const response = await api.get('/admin/users');
            console.log('Fetched users:', response.data);
            setUsers(response.data.users);
        } catch (error) {
            console.error('Failed to fetch users:', error);
            setError('Failed to load users. Please try again.');
            setUsers([]);
        } finally {
            setLoading(false);
        }
    };

    const getRoleBadge = (role: string) => {
        const badges: Record<string, string> = {
            admin: 'badge-error',
            manager: 'badge-warning',
            agent: 'badge-info',
        };
        return badges[role] || 'badge-info';
    };

    return (
        <div className="admin-page">
            <div className="page-header">
                <div>
                    <h1>User Management</h1>
                    <p>Manage user accounts and permissions</p>
                </div>
                <button className="btn btn-primary">
                    <Plus size={18} /> Add User
                </button>
            </div>

            <div className="filters-bar">
                <div className="search-box">
                    <Search size={18} />
                    <input type="text" placeholder="Search users..." />
                </div>
            </div>

            {loading && (
                <div className="loading">Loading users...</div>
            )}

            {!loading && error && (
                <div className="error-message">
                    {error}
                </div>
            )}

            {!loading && !error && (
                <div className="card">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Role</th>
                                <th>Status</th>
                                <th>Last Login</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map((user) => (
                                <tr key={user.id}>
                                    <td>
                                        <div className="lead-contact">
                                            <div className="lead-avatar">
                                                <Users size={16} />
                                            </div>
                                            <div>
                                                <div className="lead-name">{user.full_name}</div>
                                                <div className="lead-phone">{user.email}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td>
                                        <span className={`badge ${getRoleBadge(user.role)}`}>
                                            <Shield size={12} /> {user.role}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge ${user.is_active ? 'badge-success' : 'badge-error'}`}>
                                            {user.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td>
                                        {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                                    </td>
                                    <td>
                                        <div className="action-buttons">
                                            <button className="btn btn-ghost btn-sm"><Edit size={14} /></button>
                                            <button className="btn btn-ghost btn-sm"><Trash2 size={14} /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
