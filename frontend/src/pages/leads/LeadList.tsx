import React, { useMemo, useState, useEffect } from 'react';
import { Users, Search, Filter, Phone } from 'lucide-react';
import api from '../../services/api';
import type { Lead, LeadListResponse } from '../../types/lead';
import type { Call, CallListResponse } from '../../types/call';
import type { User } from '../../types/auth';
import { useAuthStore } from '../../store';
import '../properties/Properties.css';
import './LeadList.css';

interface LeadAiSummary {
    lead_id: number;
    lead_quality_score: number;
    engagement_level: 'low' | 'medium' | 'high' | string;
    likelihood_to_convert: number;
    recommended_next_actions: string[];
    key_conversation_points: string[];
    patterns: string[];
    generated_at: string;
    source_call_ids: number[];
}

type SortDirection = 'asc' | 'desc';
type SortKey = 'contact' | 'quality' | 'status' | 'assignedTo' | 'source' | 'created';

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

    const [aiSummaryExpanded, setAiSummaryExpanded] = useState<Record<number, boolean>>({});
    const [aiSummaryByLeadId, setAiSummaryByLeadId] = useState<Record<number, LeadAiSummary>>({});
    const [aiSummaryLoading, setAiSummaryLoading] = useState<Record<number, boolean>>({});
    const [aiSummaryErrors, setAiSummaryErrors] = useState<Record<number, string>>({});

    const [sortKey, setSortKey] = useState<SortKey>('created');
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

    const [activeLeadId, setActiveLeadId] = useState<number | null>(null);
    const [callsForActiveLead, setCallsForActiveLead] = useState<Call[]>([]);
    const [callsLoading, setCallsLoading] = useState(false);
    const [callsError, setCallsError] = useState<string | null>(null);
    const [callsLastUpdatedAt, setCallsLastUpdatedAt] = useState<string | null>(null);

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

    const fetchLeadAiSummary = async (leadId: number) => {
        if (aiSummaryByLeadId[leadId] || aiSummaryLoading[leadId]) {
            return;
        }
        setAiSummaryLoading((current) => ({ ...current, [leadId]: true }));
        setAiSummaryErrors((current) => {
            const next = { ...current };
            delete next[leadId];
            return next;
        });
        try {
            const response = await api.get<LeadAiSummary>(`/leads/${leadId}/ai-summary`);
            setAiSummaryByLeadId((current) => ({ ...current, [leadId]: response.data }));
        } catch (err: any) {
            const message =
                err?.response?.data?.detail || 'Failed to load AI summary. Please try again.';
            setAiSummaryErrors((current) => ({ ...current, [leadId]: message }));
        } finally {
            setAiSummaryLoading((current) => ({ ...current, [leadId]: false }));
        }
    };

    const toggleAiSummary = (leadId: number) => {
        setAiSummaryExpanded((current) => {
            const nextValue = !current[leadId];
            return { ...current, [leadId]: nextValue };
        });
        const isOpening = !aiSummaryExpanded[leadId];
        if (isOpening) {
            fetchLeadAiSummary(leadId);
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

    const setSorting = (nextKey: SortKey) => {
        setSortKey((currentKey) => {
            const isSameKey = currentKey === nextKey;
            if (!isSameKey) {
                setSortDirection(() => {
                    if (nextKey === 'created' || nextKey === 'quality') {
                        return 'desc';
                    }
                    return 'asc';
                });
                return nextKey;
            }
            setSortDirection((currentDirection) =>
                currentDirection === 'asc' ? 'desc' : 'asc'
            );
            return currentKey;
        });
    };

    const sortedLeads = useMemo(() => {
        const directionMultiplier = sortDirection === 'asc' ? 1 : -1;
        const qualityRank: Record<string, number> = { hot: 3, warm: 2, cold: 1 };
        const statusRank: Record<string, number> = {
            new: 1,
            contacted: 2,
            qualified: 3,
            negotiating: 4,
            converted: 5,
            lost: 6,
        };

        const getComparableString = (value: string | undefined | null) =>
            (value || '').trim().toLowerCase();

        const compare = (a: Lead, b: Lead) => {
            if (sortKey === 'contact') {
                const aName = getComparableString(a.name);
                const bName = getComparableString(b.name);
                if (aName && bName && aName !== bName) {
                    return aName.localeCompare(bName) * directionMultiplier;
                }
                if (aName !== bName) {
                    return (aName ? -1 : 1) * directionMultiplier;
                }
                return getComparableString(a.phone).localeCompare(getComparableString(b.phone)) * directionMultiplier;
            }

            if (sortKey === 'quality') {
                const aRank = qualityRank[a.quality] ?? 0;
                const bRank = qualityRank[b.quality] ?? 0;
                if (aRank !== bRank) {
                    return (aRank - bRank) * directionMultiplier;
                }
                return getComparableString(a.phone).localeCompare(getComparableString(b.phone)) * directionMultiplier;
            }

            if (sortKey === 'status') {
                const aRank = statusRank[a.status] ?? 0;
                const bRank = statusRank[b.status] ?? 0;
                if (aRank !== bRank) {
                    return (aRank - bRank) * directionMultiplier;
                }
                return getComparableString(a.phone).localeCompare(getComparableString(b.phone)) * directionMultiplier;
            }

            if (sortKey === 'assignedTo') {
                const aAssigned = a.assigned_agent_id ?? 0;
                const bAssigned = b.assigned_agent_id ?? 0;
                if (aAssigned !== bAssigned) {
                    return (aAssigned - bAssigned) * directionMultiplier;
                }
                return getComparableString(a.phone).localeCompare(getComparableString(b.phone)) * directionMultiplier;
            }

            if (sortKey === 'source') {
                return getComparableString(a.source).localeCompare(getComparableString(b.source)) * directionMultiplier;
            }

            const aCreated = new Date(a.created_at).getTime();
            const bCreated = new Date(b.created_at).getTime();
            if (aCreated !== bCreated) {
                return (aCreated - bCreated) * directionMultiplier;
            }
            return getComparableString(a.phone).localeCompare(getComparableString(b.phone)) * directionMultiplier;
        };

        return leads
            .map((lead, index) => ({ lead, index }))
            .sort((a, b) => {
                const primary = compare(a.lead, b.lead);
                if (primary !== 0) {
                    return primary;
                }
                return a.index - b.index;
            })
            .map(({ lead }) => lead);
    }, [leads, sortDirection, sortKey]);

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

    const activeLead = activeLeadId
        ? leads.find((lead) => lead.id === activeLeadId) || null
        : null;

    const formatDuration = (seconds?: number) => {
        if (!seconds || Number.isNaN(seconds)) {
            return '-';
        }
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    };

    const getCallTimestamp = (call: Call) => {
        const timestamp = call.started_at || call.created_at;
        const date = timestamp ? new Date(timestamp) : null;
        if (!date || Number.isNaN(date.getTime())) {
            return '-';
        }
        return date.toLocaleString();
    };

    const extractKeyPoints = (text?: string | null) => {
        if (!text) {
            return [];
        }
        const normalized = text
            .replace(/\r\n/g, '\n')
            .replace(/[•·]/g, '\n')
            .replace(/^-+/gm, '')
            .trim();
        const parts = normalized
            .split(/\n|\.|;|•/g)
            .map((value) => value.trim())
            .filter(Boolean);
        const unique: string[] = [];
        for (const part of parts) {
            const lowered = part.toLowerCase();
            if (!unique.some((existing) => existing.toLowerCase() === lowered)) {
                unique.push(part);
            }
            if (unique.length >= 4) {
                break;
            }
        }
        return unique;
    };

    const loadCallsForLead = async (leadId: number) => {
        const response = await api.get<CallListResponse>('/calls/', {
            params: {
                lead_id: leadId,
                page: 1,
                page_size: 10,
            },
        });
        const incomingCalls = response.data.calls || [];
        return [...incomingCalls].sort((a, b) => {
            const aTs = new Date(a.started_at || a.created_at).getTime();
            const bTs = new Date(b.started_at || b.created_at).getTime();
            return bTs - aTs;
        });
    };

    useEffect(() => {
        if (!activeLeadId) {
            setCallsForActiveLead([]);
            setCallsError(null);
            setCallsLoading(false);
            setCallsLastUpdatedAt(null);
            return;
        }

        let isCurrent = true;
        const refresh = async () => {
            setCallsLoading(true);
            setCallsError(null);
            try {
                const calls = await loadCallsForLead(activeLeadId);
                if (!isCurrent) {
                    return;
                }
                setCallsForActiveLead(calls);
                setCallsLastUpdatedAt(new Date().toISOString());
            } catch (err: any) {
                if (!isCurrent) {
                    return;
                }
                const message =
                    err?.response?.data?.detail ||
                    'Failed to load conversation summary. Please try again.';
                setCallsError(message);
                setCallsForActiveLead([]);
                setCallsLastUpdatedAt(null);
            } finally {
                if (isCurrent) {
                    setCallsLoading(false);
                }
            }
        };

        refresh();

        const intervalId = window.setInterval(() => {
            if (isCurrent) {
                refresh();
            }
        }, 30_000);

        return () => {
            isCurrent = false;
            window.clearInterval(intervalId);
        };
    }, [activeLeadId]);

    return (
        <div className="leads-page leads-light">
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
                <>
                    <div className="card">
                        <div className="leads-table-container">
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
                                                    onClick={(event) => event.stopPropagation()}
                                                />
                                            </th>
                                        )}
                                        <th aria-sort={sortKey === 'contact' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                            <button
                                                type="button"
                                                className="leads-sort-header"
                                                onClick={() => setSorting('contact')}
                                            >
                                                <span>Contact</span>
                                                <span className={`leads-sort-indicator${sortKey === 'contact' ? ' active' : ''}`}>
                                                    {sortKey === 'contact' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                                                </span>
                                            </button>
                                        </th>
                                        <th aria-sort={sortKey === 'quality' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                            <button
                                                type="button"
                                                className="leads-sort-header"
                                                onClick={() => setSorting('quality')}
                                            >
                                                <span>Quality</span>
                                                <span className={`leads-sort-indicator${sortKey === 'quality' ? ' active' : ''}`}>
                                                    {sortKey === 'quality' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                                                </span>
                                            </button>
                                        </th>
                                        <th aria-sort={sortKey === 'status' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                            <button
                                                type="button"
                                                className="leads-sort-header"
                                                onClick={() => setSorting('status')}
                                            >
                                                <span>Status</span>
                                                <span className={`leads-sort-indicator${sortKey === 'status' ? ' active' : ''}`}>
                                                    {sortKey === 'status' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                                                </span>
                                            </button>
                                        </th>
                                        <th aria-sort={sortKey === 'assignedTo' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                            <button
                                                type="button"
                                                className="leads-sort-header"
                                                onClick={() => setSorting('assignedTo')}
                                            >
                                                <span>Assigned To</span>
                                                <span className={`leads-sort-indicator${sortKey === 'assignedTo' ? ' active' : ''}`}>
                                                    {sortKey === 'assignedTo' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                                                </span>
                                            </button>
                                        </th>
                                        <th aria-sort={sortKey === 'source' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                            <button
                                                type="button"
                                                className="leads-sort-header"
                                                onClick={() => setSorting('source')}
                                            >
                                                <span>Source</span>
                                                <span className={`leads-sort-indicator${sortKey === 'source' ? ' active' : ''}`}>
                                                    {sortKey === 'source' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                                                </span>
                                            </button>
                                        </th>
                                        <th>Preferences</th>
                                        <th>Notes</th>
                                        <th>AI Summary</th>
                                        <th aria-sort={sortKey === 'created' ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                            <button
                                                type="button"
                                                className="leads-sort-header"
                                                onClick={() => setSorting('created')}
                                            >
                                                <span>Created</span>
                                                <span className={`leads-sort-indicator${sortKey === 'created' ? ' active' : ''}`}>
                                                    {sortKey === 'created' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                                                </span>
                                            </button>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sortedLeads.map((lead) => {
                                        const isSelected = selectedLeadIds.includes(lead.id);
                                        const isActive = activeLeadId === lead.id;
                                        return (
                                            <tr
                                                key={lead.id}
                                                className={isActive ? 'leads-row-selected' : undefined}
                                                onClick={() => setActiveLeadId(lead.id)}
                                                style={{ cursor: 'pointer' }}
                                            >
                                                {isAdmin && (
                                                    <td onClick={(event) => event.stopPropagation()}>
                                                        {!lead.assigned_agent_id && (
                                                            <input
                                                                type="checkbox"
                                                                checked={isSelected}
                                                                onChange={() => toggleLeadSelection(lead.id)}
                                                                onClick={(event) => event.stopPropagation()}
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
                                                    <span className={`badge ${getQualityBadge(lead.quality)}`}>
                                                        {lead.quality}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span className="lead-status">
                                                        {lead.status.replace('_', ' ')}
                                                    </span>
                                                </td>
                                                <td>{getAssignedAgentLabel(lead.assigned_agent_id)}</td>
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
                                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                                        <div className="lead-summary" title={lead.ai_summary}>
                                                            {lead.ai_summary ? (
                                                                lead.ai_summary.length > 50
                                                                    ? lead.ai_summary.substring(0, 50) + '...'
                                                                    : lead.ai_summary
                                                            ) : (
                                                                <span className="text-muted">-</span>
                                                            )}
                                                        </div>

                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                            <button
                                                                className="btn btn-ghost"
                                                                type="button"
                                                                onClick={(event) => {
                                                                    event.stopPropagation();
                                                                    toggleAiSummary(lead.id);
                                                                }}
                                                                style={{ padding: '0.35rem 0.6rem' }}
                                                            >
                                                                {aiSummaryExpanded[lead.id] ? 'Hide details' : 'View details'}
                                                            </button>
                                                            {aiSummaryLoading[lead.id] && (
                                                                <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                                                                    Loading...
                                                                </span>
                                                            )}
                                                        </div>

                                                        {aiSummaryExpanded[lead.id] && aiSummaryErrors[lead.id] && (
                                                            <div className="error-message" onClick={(event) => event.stopPropagation()}>
                                                                {aiSummaryErrors[lead.id]}
                                                            </div>
                                                        )}

                                                        {aiSummaryExpanded[lead.id] && aiSummaryByLeadId[lead.id] && (
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }} onClick={(event) => event.stopPropagation()}>
                                                                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                                                    <span className="badge badge-info">
                                                                        Score: {aiSummaryByLeadId[lead.id].lead_quality_score}/100
                                                                    </span>
                                                                    <span className="badge badge-default">
                                                                        Engagement: {aiSummaryByLeadId[lead.id].engagement_level}
                                                                    </span>
                                                                    <span className="badge badge-warning">
                                                                        Convert: {aiSummaryByLeadId[lead.id].likelihood_to_convert}/100
                                                                    </span>
                                                                </div>

                                                                {aiSummaryByLeadId[lead.id].recommended_next_actions?.length > 0 && (
                                                                    <div style={{ fontSize: '0.8rem' }}>
                                                                        <div style={{ color: 'var(--text-muted)', marginBottom: '0.15rem' }}>
                                                                            Next actions
                                                                        </div>
                                                                        <div>
                                                                            {aiSummaryByLeadId[lead.id].recommended_next_actions.slice(0, 3).join(' • ')}
                                                                        </div>
                                                                    </div>
                                                                )}

                                                                {aiSummaryByLeadId[lead.id].key_conversation_points?.length > 0 && (
                                                                    <div style={{ fontSize: '0.8rem' }}>
                                                                        <div style={{ color: 'var(--text-muted)', marginBottom: '0.15rem' }}>
                                                                            Key points
                                                                        </div>
                                                                        <div>
                                                                            {aiSummaryByLeadId[lead.id].key_conversation_points.slice(0, 3).join(' • ')}
                                                                        </div>
                                                                    </div>
                                                                )}

                                                                {aiSummaryByLeadId[lead.id].patterns?.length > 0 && (
                                                                    <div style={{ fontSize: '0.8rem' }}>
                                                                        <div style={{ color: 'var(--text-muted)', marginBottom: '0.15rem' }}>
                                                                            Patterns
                                                                        </div>
                                                                        <div>
                                                                            {aiSummaryByLeadId[lead.id].patterns.slice(0, 2).join(' • ')}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </div>
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
                    </div>

                    <div className="conversation-summary">
                        <div className="conversation-summary-header">
                            <div className="conversation-summary-title">
                                <h2>Conversation summary</h2>
                                <div className="conversation-summary-meta">
                                    {activeLead ? (
                                        <>
                                            <span>{activeLead.name || 'Unknown'} • {activeLead.phone}</span>
                                            {callsLastUpdatedAt && (
                                                <span>
                                                    Updated {new Date(callsLastUpdatedAt).toLocaleTimeString()}
                                                </span>
                                            )}
                                        </>
                                    ) : (
                                        <span>Select a lead to view recent conversations</span>
                                    )}
                                </div>
                            </div>
                        </div>
                        <div className="conversation-summary-body">
                            {!activeLead && (
                                <div className="text-muted">
                                    Click any lead row to load its latest call summary, timestamps, and key points.
                                </div>
                            )}

                            {activeLead && callsLoading && (
                                <div className="loading">Loading conversation summary...</div>
                            )}

                            {activeLead && !callsLoading && callsError && (
                                <div className="error-message">{callsError}</div>
                            )}

                            {activeLead && !callsLoading && !callsError && (
                                <>
                                    {callsForActiveLead.length === 0 ? (
                                        <div className="text-muted">No calls found for this lead.</div>
                                    ) : (
                                        (() => {
                                            const latestCall = callsForActiveLead[0];
                                            const summaryText =
                                                latestCall.transcript_summary ||
                                                latestCall.outcome_notes ||
                                                '';
                                            const keyPoints = extractKeyPoints(summaryText);
                                            return (
                                                <div className="conversation-summary-grid">
                                                    <div className="conversation-summary-block">
                                                        <div className="conversation-summary-block-title">Key points</div>
                                                        <div className="conversation-summary-points">
                                                            {keyPoints.length > 0 ? (
                                                                keyPoints.map((point) => (
                                                                    <div key={point} className="conversation-summary-point">
                                                                        <span className="conversation-summary-bullet" />
                                                                        <span>{point}</span>
                                                                    </div>
                                                                ))
                                                            ) : (
                                                                <div className="text-muted">-</div>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="conversation-summary-block">
                                                        <div className="conversation-summary-block-title">Call details</div>
                                                        <div className="conversation-summary-meta">
                                                            <span>Timestamp: {getCallTimestamp(latestCall)}</span>
                                                            <span>Duration: {formatDuration(latestCall.duration_seconds)}</span>
                                                            <span>Status: {latestCall.status?.replace('_', ' ') || '-'}</span>
                                                            <span>Direction: {latestCall.direction || '-'}</span>
                                                        </div>
                                                    </div>
                                                    <div className="conversation-summary-block" style={{ gridColumn: '1 / -1' }}>
                                                        <div className="conversation-summary-block-title">Summary</div>
                                                        <div className="conversation-summary-text">
                                                            {summaryText || '-'}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })()
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};
