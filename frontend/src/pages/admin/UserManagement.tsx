import React, { useState, useEffect } from 'react';
import { Users, Plus, Search, Shield, Edit, Trash2, X, Save } from 'lucide-react';
import api from '../../services/api';
import type { User } from '../../types/auth';
import '../properties/Properties.css';
import '../../components/OutboundCallModal.css';

export const UserManagement: React.FC = () => {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [editingUser, setEditingUser] = useState<User | null>(null);
    const [editFullName, setEditFullName] = useState('');
    const [editPhone, setEditPhone] = useState('');
    const [editRole, setEditRole] = useState<User['role']>('agent');
    const [editActive, setEditActive] = useState(true);

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

    const openEdit = (user: User) => {
        setEditingUser(user);
        setEditFullName(user.full_name);
        setEditPhone(user.phone || '');
        setEditRole(user.role);
        setEditActive(user.is_active);
        setError(null);
    };

    const closeEdit = () => {
        if (saving) return;
        setEditingUser(null);
        setEditFullName('');
        setEditPhone('');
        setEditRole('agent');
        setEditActive(true);
    };

    const handleSave = async () => {
        if (!editingUser) return;
        if (!editFullName.trim()) {
            setError('Name is required');
            return;
        }
        try {
            setSaving(true);
            setError(null);
            await api.put(`/admin/users/${editingUser.id}`, {
                full_name: editFullName.trim(),
                phone: editPhone.trim() || null,
                is_active: editActive,
            });
            await api.put(`/admin/users/${editingUser.id}/role`, {
                role: editRole,
            });
            await fetchUsers();
            closeEdit();
        } catch (err: any) {
            console.error('Failed to update user:', err);
            const message =
                err?.response?.data?.detail || 'Failed to update user. Please try again.';
            setError(message);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (user: User) => {
        const confirmed = window.confirm(
            `Are you sure you want to deactivate user ${user.full_name} (${user.email})?`,
        );
        if (!confirmed) return;
        try {
            setError(null);
            await api.delete(`/admin/users/${user.id}`);
            await fetchUsers();
        } catch (err: any) {
            console.error('Failed to delete user:', err);
            const message =
                err?.response?.data?.detail || 'Failed to delete user. Please try again.';
            setError(message);
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
                                <th>Phone</th>
                                <th>Last Login</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map((user) => (
                                <tr
                                    key={user.id}
                                    onClick={() => openEdit(user)}
                                    style={{ cursor: 'pointer' }}
                                >
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
                                        {user.phone || '-'}
                                    </td>
                                    <td>
                                        {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                                    </td>
                                    <td>
                                        <div className="action-buttons">
                                            <button
                                                className="btn btn-ghost btn-sm"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    openEdit(user);
                                                }}
                                            >
                                                <Edit size={14} />
                                            </button>
                                            <button
                                                className="btn btn-ghost btn-sm"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleDelete(user);
                                                }}
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
            {editingUser && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <div className="modal-header">
                            <h2>Edit User</h2>
                            <button className="icon-button" onClick={closeEdit} disabled={saving}>
                                <X size={16} />
                            </button>
                        </div>
                        <div className="modal-body">
                            <div className="form-group">
                                <label>Name</label>
                                <input
                                    type="text"
                                    value={editFullName}
                                    onChange={(e) => setEditFullName(e.target.value)}
                                />
                            </div>
                            <div className="form-group">
                                <label>Phone</label>
                                <input
                                    type="text"
                                    value={editPhone}
                                    onChange={(e) => setEditPhone(e.target.value)}
                                />
                            </div>
                            <div className="form-group">
                                <label>Role</label>
                                <select
                                    value={editRole}
                                    onChange={(e) => setEditRole(e.target.value as User['role'])}
                                >
                                    <option value="admin">Admin</option>
                                    <option value="manager">Manager</option>
                                    <option value="agent">Agent</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Status</label>
                                <label className="checkbox-inline">
                                    <input
                                        type="checkbox"
                                        checked={editActive}
                                        onChange={(e) => setEditActive(e.target.checked)}
                                    />
                                    <span>Active</span>
                                </label>
                            </div>
                        </div>
                        <div className="modal-footer">
                            <button
                                className="btn btn-secondary"
                                onClick={closeEdit}
                                disabled={saving}
                            >
                                <X size={14} /> Cancel
                            </button>
                            <button
                                className="btn btn-primary"
                                onClick={handleSave}
                                disabled={saving}
                            >
                                <Save size={14} /> {saving ? 'Saving...' : 'Save'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
