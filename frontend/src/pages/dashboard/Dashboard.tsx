import React, { useEffect, useState } from 'react';
import { Phone, Users, Building2, TrendingUp, Clock, PhoneIncoming } from 'lucide-react';
import { XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import api from '../../services/api';
import './Dashboard.css';

interface DashboardStats {
    total_calls_today: number;
    total_calls_week: number;
    total_calls_month: number;
    active_calls: number;
    total_leads: number;
    hot_leads: number;
    warm_leads: number;
    cold_leads: number;
    total_properties: number;
    available_properties: number;
    conversion_rate: number;
}

interface RecentCall {
    id: number;
    call_sid: string;
    from_number: string;
    status: string;
    duration_seconds: number;
    handled_by_ai: boolean;
    transcript_summary: string;
    created_at: string;
}

interface ChartDataPoint {
    name: string;
    calls: number;
    leads: number;
}

interface PendingFollowUp {
    id: number;
    name: string | null;
    phone: string;
    quality: string;
    last_contact: string;
    notes: string | null;
}

export const Dashboard: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [recentCalls, setRecentCalls] = useState<RecentCall[]>([]);
    const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
    const [pendingFollowUps, setPendingFollowUps] = useState<PendingFollowUp[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, callsRes, chartsRes, followUpsRes] = await Promise.all([
                    api.get('/api/dashboard/stats'),
                    api.get('/api/dashboard/recent-calls?limit=5'),
                    api.get('/api/dashboard/charts'),
                    api.get('/api/dashboard/pending-followups')
                ]);
                setStats(statsRes.data);
                setRecentCalls(callsRes.data);
                setChartData(chartsRes.data);
                setPendingFollowUps(followUpsRes.data);
            } catch (error) {
                console.error('Failed to fetch dashboard data:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m ${secs}s`;
    };

    const getStatusBadgeClass = (status: string) => {
        const map: Record<string, string> = {
            'completed': 'success',
            'no_answer': 'warning',
            'busy': 'error',
            'failed': 'error',
            'in_progress': 'info',
            'ringing': 'info',
            'initiated': 'default'
        };
        return `badge badge-${map[status] || 'default'}`;
    };

    const isOngoing = (status: string) => {
        return ['initiated', 'ringing', 'in_progress'].includes(status);
    };

    if (loading) {
        return <div className="dashboard-loading">Loading dashboard data...</div>;
    }

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
                        <span className="stat-value">{stats?.total_calls_today || 0}</span>
                        <span className="stat-change positive">{stats?.total_calls_week || 0} this week</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon leads">
                        <Users size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Hot Leads</span>
                        <span className="stat-value">{stats?.hot_leads || 0}</span>
                        <span className="stat-change positive">{stats?.total_leads || 0} total leads</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon properties">
                        <Building2 size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Active Properties</span>
                        <span className="stat-value">{stats?.available_properties || 0}</span>
                        <span className="stat-change neutral">{stats?.total_properties || 0} total listings</span>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon conversion">
                        <TrendingUp size={24} />
                    </div>
                    <div className="stat-content">
                        <span className="stat-label">Conversion Rate</span>
                        <span className="stat-value">{stats?.conversion_rate || 0}%</span>
                        <span className="stat-change positive">Based on {stats?.total_leads || 0} leads</span>
                    </div>
                </div>
            </div>

            <div className="charts-grid">
                <div className="chart-card">
                    <h3>Call Activity</h3>
                    <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={chartData}>
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
                        <AreaChart data={chartData}>
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
                        {recentCalls.length > 0 ? (
                            recentCalls.map((call) => (
                                <div key={call.id} className="recent-item">
                                    <div className="recent-avatar">
                                        <Phone size={16} />
                                    </div>
                                    <div className="recent-info">
                                        <span className="recent-title">{call.from_number}</span>
                                        <span className="recent-subtitle">
                                            {call.transcript_summary ? call.transcript_summary.substring(0, 40) + '...' : 'No summary'}
                                            • {isOngoing(call.status) ? 'Ongoing' : formatDuration(call.duration_seconds || 0)}
                                        </span>
                                    </div>
                                    <span className={getStatusBadgeClass(call.status)}>
                                        {call.status.replace('_', ' ')}
                                    </span>
                                </div>
                            ))
                        ) : (
                            <p style={{ padding: '20px', color: '#64748b', textAlign: 'center' }}>No recent calls found</p>
                        )}
                    </div>
                </div>

                <div className="recent-card">
                    <h3><Clock size={20} /> Action Required (Leads)</h3>
                    <div className="recent-list">
                        {pendingFollowUps.length > 0 ? (
                            pendingFollowUps.map((lead) => (
                                <div key={lead.id} className="recent-item">
                                    <div className={`recent-avatar ${lead.quality === 'hot' ? 'hot' : (lead.quality === 'warm' ? 'warm' : 'cold')}`}>
                                        <Users size={16} />
                                    </div>
                                    <div className="recent-info">
                                        <span className="recent-title">{lead.name || lead.phone}</span>
                                        <span className="recent-subtitle" title={lead.notes || ''}>
                                            {lead.notes ? (
                                                lead.notes.length > 50 ? lead.notes.substring(0, 50) + '...' : lead.notes
                                            ) : 'New lead - No summary'}
                                        </span>
                                    </div>
                                    <span className={`badge badge-${lead.quality === 'hot' ? 'error' : (lead.quality === 'warm' ? 'warning' : 'info')}`}>
                                        {lead.quality}
                                    </span>
                                </div>
                            ))
                        ) : (
                            <p style={{ padding: '20px', color: '#64748b', textAlign: 'center' }}>All caught up!</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};
