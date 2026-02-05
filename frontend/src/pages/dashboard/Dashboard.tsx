import React, { useEffect, useState } from 'react';
import { Phone, Users, Building2, TrendingUp, Clock, PhoneIncoming } from 'lucide-react';
import { XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import api from '../../services/api';
import './Dashboard.css';

interface DashboardStats {
    calls: { today: number; this_week: number };
    leads: { total: number; hot: number };
    properties: { active: number };
    metrics: { conversion_rate: number; avg_call_duration_seconds: number };
}

const mockChartData = [
    { name: 'Mon', calls: 45, leads: 12 },
    { name: 'Tue', calls: 52, leads: 18 },
    { name: 'Wed', calls: 38, leads: 8 },
    { name: 'Thu', calls: 61, leads: 22 },
    { name: 'Fri', calls: 55, leads: 15 },
    { name: 'Sat', calls: 32, leads: 10 },
    { name: 'Sun', calls: 28, leads: 6 },
];

export const Dashboard: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [, setLoading] = useState(true);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await api.get('/reports/summary');
                setStats(response.data);
            } catch (error) {
                console.error('Failed to fetch stats:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchStats();
    }, []);

    return (
        <div className="dashboard">
            <div className="dashboard-header">
                <h1>Dashboard</h1>
                <p>Overview of your real estate operations</p>
            </div>

            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon calls">
                        <Phone size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Calls Today</span>
                        <span className="stat-value">{stats?.calls.today || 0}</span>
                        <span className="stat-change positive">+12% from yesterday</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon leads">
                        <Users size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Hot Leads</span>
                        <span className="stat-value">{stats?.leads.hot || 0}</span>
                        <span className="stat-change positive">+5 this week</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon properties">
                        <Building2 size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Active Properties</span>
                        <span className="stat-value">{stats?.properties.active || 0}</span>
                        <span className="stat-change neutral">3 new listings</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon conversion">
                        <TrendingUp size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Conversion Rate</span>
                        <span className="stat-value">{stats?.metrics.conversion_rate || 0}%</span>
                        <span className="stat-change positive">+2.5% improvement</span>
                    </div>
                </div>
            </div>

            <div className="charts-grid">
                <div className="chart-card">
                    <h3>Call Activity</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={mockChartData}>
                            <defs>
                                <linearGradient id="callGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <XAxis dataKey="name" stroke="#64748b" />
                            <YAxis stroke="#64748b" />
                            <Tooltip
                                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                                labelStyle={{ color: '#f8fafc' }}
                            />
                            <Area type="monotone" dataKey="calls" stroke="#6366f1" fill="url(#callGradient)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>

                <div className="chart-card">
                    <h3>Lead Generation</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={mockChartData}>
                            <defs>
                                <linearGradient id="leadGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <XAxis dataKey="name" stroke="#64748b" />
                            <YAxis stroke="#64748b" />
                            <Tooltip
                                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                                labelStyle={{ color: '#f8fafc' }}
                            />
                            <Area type="monotone" dataKey="leads" stroke="#10b981" fill="url(#leadGradient)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="recent-section">
                <div className="recent-card">
                    <h3><PhoneIncoming size={20} /> Recent Calls</h3>
                    <div className="recent-list">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="recent-item">
                                <div className="recent-avatar">
                                    <Phone size={16} />
                                </div>
                                <div className="recent-info">
                                    <span className="recent-title">+91 98765 4321{i}</span>
                                    <span className="recent-subtitle">Property inquiry • 3m 45s</span>
                                </div>
                                <span className="badge badge-success">Completed</span>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="recent-card">
                    <h3><Clock size={20} /> Pending Follow-ups</h3>
                    <div className="recent-list">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="recent-item">
                                <div className="recent-avatar hot">
                                    <Users size={16} />
                                </div>
                                <div className="recent-info">
                                    <span className="recent-title">Customer {i}</span>
                                    <span className="recent-subtitle">Follow up in {i} hour{i > 1 ? 's' : ''}</span>
                                </div>
                                <span className="badge badge-warning">Hot Lead</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};
