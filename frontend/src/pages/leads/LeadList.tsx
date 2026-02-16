import React, { useState, useEffect } from 'react';
import { Users, Search, Filter, Phone } from 'lucide-react';
import api from '../../services/api';
import type { Lead, LeadListResponse } from '../../types/lead';
import type { User } from '../../types/auth';
import { useAuthStore } from '../../store';
import '../properties/Properties.css';

export const LeadList: React.FC = () => {
    const { user } = useAuthStore();
    const isAdmin = user?.role === 'admin';

    const [leads, setLeads] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const [search, setSearch] = useState('');
    const [qualityFilter, setQualityFilter] = useState<string>('');
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [unassignedOnly, setUnassignedOnly] = useState(false);

    const [agents, setAgents] = useState<User[]>([]);
    const [selectedAgentId, setSelectedAgentId] = useState<number | ''>('');
    const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);
    const [assigning, setAssigning] = useState(false);

    useEffect(() => {
        fetchLeads();
    }, [qualityFilter, statusFilter, unassignedOnly]);

    useEffect(() => {
        if (!isAdmin) {
            return;
        }
        const fetchAgents = async () => {
            try {
                const response = await api.get('/admin/users', {
                    params: {
                        role: 'agent',
                        is_active: true,
                        page: 1,
                        page_size: 100,
                    },
                });
                setAgents(response.data.users || []);
            } catch (err) {
                console.error('Failed to load agents', err);
            }
        };
        fetchAgents();
    }, [isAdmin]);

    const fetchLeads = async () => {
        try {
            setError(null);
            setLoading(true);
            const params: Record<string, any> = {
                page: 1,
                page_size: 50,
            };
            if (search.trim()) {
                params.phone = search.trim();
            }
            if (qualityFilter) {
                params.quality = qualityFilter;
            }
            if (statusFilter) {
                params.status = statusFilter;
            }
            if (unassignedOnly) {
                params.unassigned = true;
            }
            const response = await api.get<LeadListResponse>('/leads/', { params });
            setLeads(response.data.leads);
            setTotal(response.data.total);
            setSelectedLeadIds([]);
        } catch (err: any) {
            console.error('Failed to fetch leads:', err);
            const message =
                err?.response?.data?.detail || 'Failed to load leads. Please try again.';
            setError(message);
            setLeads([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    };

    const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
        if (event.key === 'Enter') {
            fetchLeads();
        }
    };

    const toggleLeadSelection = (leadId: number) => {
        setSelectedLeadIds((current) =>
            current.includes(leadId)
                ? current.filter((id) => id !== leadId)
                : [...current, leadId]
        );
    };

    const toggleSelectAll = () => {
        const selectableIds = leads
            .filter((lead) => !lead.assigned_agent_id)
            .map((lead) => lead.id);
        if (
            selectableIds.length > 0 &&
            selectableIds.every((id) => selectedLeadIds.includes(id))
        ) {
            setSelectedLeadIds([]);
        } else {
            setSelectedLeadIds(selectableIds);
        }
    };

    const handleBulkAssign = async () => {
        if (!isAdmin || !selectedAgentId || selectedLeadIds.length === 0) {
            return;
        }
        try {
            setAssigning(true);
            setError(null);
            await api.put('/leads/assign/bulk', {
                agent_id: selectedAgentId,
                lead_ids: selectedLeadIds,
            });
            await fetchLeads();
        } catch (err: any) {
            console.error('Failed to assign leads:', err);
            const message =
                err?.response?.data?.detail || 'Failed to assign leads. Please try again.';
            setError(message);
        } finally {
            setAssigning(false);
        }
    };

    const getQualityBadge = (quality: string) => {
        const badges: Record<string, string> = {
            hot: 'badge-error',
            warm: 'badge-warning',
            cold: 'badge-info',
        };
        return badges[quality] || 'badge-info';
    };

    const selectedCount = selectedLeadIds.length;

    const selectableLeadIds = leads
        .filter((lead) => !lead.assigned_agent_id)
        .map((lead) => lead.id);
    const allSelectableSelected =
        selectableLeadIds.length > 0 &&
        selectableLeadIds.every((id) => selectedLeadIds.includes(id));

    const getAssignedAgentLabel = (assignedAgentId?: number) => {
        if (!assignedAgentId) {
            return 'Unassigned';
        }
        const agent = agents.find((a) => a.id === assignedAgentId);
        if (!agent) {
            return `Agent #${assignedAgentId}`;
        }
        return `${agent.full_name} (${agent.email})`;
    };

    return (
        <div className="leads-page">
            <div className="page-header">
                <div>
                    <h1>Leads</h1>
                    <p>{total} total leads</p>
                </div>
            </div>

            <div className="filters-bar">
                <div className="search-box">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search by phone..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={handleSearchKeyDown}
                    />
                </div>
                <select
                    className="select"
                    value={qualityFilter}
                    onChange={(e) => setQualityFilter(e.target.value)}
                >
                    <option value="">All qualities</option>
                    <option value="hot">Hot</option>
                    <option value="warm">Warm</option>
                    <option value="cold">Cold</option>
                </select>
                <select
                    className="select"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                >
                    <option value="">All statuses</option>
                    <option value="new">New</option>
                    <option value="contacted">Contacted</option>
                    <option value="qualified">Qualified</option>
                    <option value="negotiating">Negotiating</option>
                    <option value="converted">Converted</option>
                    <option value="lost">Lost</option>
                </select>
                <label className="checkbox-inline">
                    <input
                        type="checkbox"
                        checked={unassignedOnly}
                        onChange={(e) => setUnassignedOnly(e.target.checked)}
                    />
                    <span>Unassigned only</span>
                </label>
                <button className="btn btn-secondary" onClick={fetchLeads}>
                    <Filter size={18} /> Apply
                </button>
            </div>

            {isAdmin && (
                <div className="card" style={{ marginTop: '1rem' }}>
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '1rem',
                        }}
                    >
                        <div>
                            <h2 style={{ fontSize: '0.95rem', marginBottom: '0.25rem' }}>
                                Bulk assignment
                            </h2>
                            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
                                Select one or more leads and assign them to an active agent.
                            </p>
                            {agents.length === 0 && (
                                <p style={{ fontSize: '0.8rem', color: '#ef4444' }}>
                                    No active agents found. Create at least one agent user first.
                                </p>
                            )}
                        </div>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                            }}
                        >
                            <select
                                className="select"
                                value={selectedAgentId === '' ? '' : selectedAgentId}
                                onChange={(e) =>
                                    setSelectedAgentId(
                                        e.target.value ? Number(e.target.value) : ''
                                    )
                                }
                                disabled={agents.length === 0}
                            >
                                <option value="">Select agent</option>
                                {agents.map((agent) => (
                                    <option key={agent.id} value={agent.id}>
                                        {agent.full_name} ({agent.email})
                                    </option>
                                ))}
                            </select>
                            <button
                                className="btn btn-primary"
                                onClick={handleBulkAssign}
                                disabled={
                                    assigning ||
                                    !selectedAgentId ||
                                    selectedCount === 0 ||
                                    loading ||
                                    agents.length === 0
                                }
                            >
                                {assigning ? 'Assigning...' : 'Assign selected'}
                                {selectedCount > 0 ? ` (${selectedCount})` : ''}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {loading && (
                <div className="loading">Loading leads...</div>
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
                                {isAdmin && (
                                    <th>
                                        <input
                                            type="checkbox"
                                            checked={allSelectableSelected}
                                            disabled={selectableLeadIds.length === 0}
                                            onChange={toggleSelectAll}
                                        />
                                    </th>
                                )}
                                <th>Contact</th>
                                <th>Quality</th>
                                <th>Status</th>
                                <th>Assigned To</th>
                                <th>Source</th>
                                <th>Preferences</th>
                                <th>Notes</th>
                                <th>AI Summary</th>
                                <th>Created</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leads.map((lead) => {
                                const isSelected = selectedLeadIds.includes(lead.id);
                                return (
                                    <tr key={lead.id}>
                                        {isAdmin && (
                                            <td>
                                                {!lead.assigned_agent_id && (
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => toggleLeadSelection(lead.id)}
                                                    />
                                                )}
                                            </td>
                                        )}
                                        <td>
                                            <div className="lead-contact">
                                                <div className="lead-avatar">
                                                    <Users size={16} />
                                                </div>
                                                <div>
                                                    <div className="lead-name">
                                                        {lead.name || 'Unknown'}
                                                    </div>
                                                    <div className="lead-phone">
                                                        <Phone size={12} /> {lead.phone}
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                        <td>
                                            {getAssignedAgentLabel(lead.assigned_agent_id)}
                                        </td>
                                        <td>
                                            <span className={`badge ${getQualityBadge(lead.quality)}`}>
                                                {lead.quality}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="lead-status">
                                                {lead.status.replace('_', ' ')}
                                            </span>
                                        </td>
                                        <td>{lead.source.replace('_', ' ')}</td>
                                        <td>
                                            {lead.preferred_location && (
                                                <span className="lead-pref">
                                                    {lead.preferred_location}
                                                </span>
                                            )}
                                            {lead.budget_max && (
                                                <span className="lead-budget">
                                                    Up to ₹
                                                    {(lead.budget_max / 100000).toFixed(0)}L
                                                </span>
                                            )}
                                        </td>
                                        <td>
                                            <div
                                                className="lead-summary"
                                                title={
                                                    lead.last_call_notes ||
                                                    lead.notes ||
                                                    ''
                                                }
                                            >
                                                {lead.last_call_notes
                                                    ? lead.last_call_notes.length > 50
                                                        ? lead.last_call_notes.substring(0, 50) +
                                                          '...'
                                                        : lead.last_call_notes
                                                    : lead.notes
                                                    ? lead.notes.length > 50
                                                        ? lead.notes.substring(0, 50) + '...'
                                                        : lead.notes
                                                    : (
                                                        <span className="text-muted">-</span>
                                                    )}
                                            </div>
                                        </td>
                                        <td>
                                            <div className="lead-summary" title={lead.ai_summary}>
                                                {lead.ai_summary ? (
                                                    lead.ai_summary.length > 50
                                                        ? lead.ai_summary.substring(0, 50) + '...'
                                                        : lead.ai_summary
                                                ) : (
                                                    <span className="text-muted">-</span>
                                                )}
                                            </div>
                                        </td>
                                        <td>
                                            <span className="lead-date">
                                                {new Date(lead.created_at).toLocaleDateString()}
                                            </span>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
