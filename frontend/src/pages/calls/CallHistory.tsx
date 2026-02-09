
import React, { useState, useEffect } from 'react';
import { Phone, Calendar, Clock, User, ArrowUpRight, ArrowDownLeft, Search, Filter } from 'lucide-react';
import api from '../../services/api';
import type { Call, CallListResponse } from '../../types/call';
import { OutboundCallModal } from '../../components/OutboundCallModal';
import './CallHistory.css';

export const CallHistory: React.FC = () => {
    const [calls, setCalls] = useState<Call[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [isCallModalOpen, setIsCallModalOpen] = useState(false);
    const [selectedCall, setSelectedCall] = useState<Call | null>(null);

    // Filters
    const [statusFilter, setStatusFilter] = useState('');
    const [directionFilter, setDirectionFilter] = useState('');

    useEffect(() => {
        fetchCalls();
    }, [page, statusFilter, directionFilter]);

    const fetchCalls = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                page_size: '20'
            });

            if (statusFilter) params.append('status', statusFilter);
            if (directionFilter) params.append('direction', directionFilter);

            const response = await api.get<CallListResponse>(`/calls/?${params.toString()}`);
            console.log('Fetched calls:', response.data);
            setCalls(response.data.calls);
            setTotal(response.data.total);
        } catch (error) {
            console.error('Failed to fetch calls:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleString();
    };

    const formatDuration = (seconds?: number) => {
        if (!seconds) return '-';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const getStatusBadge = (status: string) => {
        const badges: Record<string, string> = {
            completed: 'badge-success',
            failed: 'badge-error',
            busy: 'badge-warning',
            no_answer: 'badge-warning',
            in_progress: 'badge-info',
            initiated: 'badge-default'
        };
        return badges[status] || 'badge-default';
    };

    return (
        <div className="call-history-page">
            <div className="page-header">
                <div>
                    <h1>Call History</h1>
                    <p>{total} total calls</p>
                </div>
                <div className="header-actions">
                    <button className="btn btn-primary" onClick={() => setIsCallModalOpen(true)}>
                        <Phone size={18} /> Place Call
                    </button>
                </div>
            </div>

            <div className="filters-bar">
                <div className="filter-group">
                    <Filter size={18} />
                    <select
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        className="filter-select"
                    >
                        <option value="">All Statuses</option>
                        <option value="completed">Completed</option>
                        <option value="failed">Failed</option>
                        <option value="no_answer">No Answer</option>
                        <option value="busy">Busy</option>
                    </select>

                    <select
                        value={directionFilter}
                        onChange={(e) => setDirectionFilter(e.target.value)}
                        className="filter-select"
                    >
                        <option value="">All Directions</option>
                        <option value="inbound">Inbound</option>
                        <option value="outbound">Outbound</option>
                    </select>
                </div>
            </div>

            {loading ? (
                <div className="loading">Loading call history...</div>
            ) : (
                <>
                    <div className="table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Direction</th>
                                    <th>From / To</th>
                                    <th>Status</th>
                                    <th>Duration</th>
                                    <th>Date & Time</th>
                                    <th>AI Handled</th>
                                    <th>Outcome</th>
                                </tr>
                            </thead>
                            <tbody>
                                {calls.map((call) => (
                                    <tr
                                        key={call.id}
                                        onClick={() => setSelectedCall(call)}
                                        className={selectedCall?.id === call.id ? 'row-selected' : ''}
                                    >
                                        <td>
                                            <div className="direction-cell">
                                                {call.direction === 'inbound' ? (
                                                    <ArrowDownLeft size={16} className="text-success" />
                                                ) : (
                                                    <ArrowUpRight size={16} className="text-primary" />
                                                )}
                                                <span className="capitalize">{call.direction}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <div className="phone-cell">
                                                <span className="phone-label">From:</span> {call.from_number}<br />
                                                <span className="phone-label">To:</span> {call.to_number}
                                            </div>
                                        </td>
                                        <td>
                                            <span className={`badge ${getStatusBadge(call.status)}`}>
                                                {call.status.replace('_', ' ')}
                                            </span>
                                        </td>
                                        <td>{formatDuration(call.duration_seconds)}</td>
                                        <td>
                                            <div className="date-cell">
                                                <Calendar size={14} />
                                                <span>{formatDate(call.created_at)}</span>
                                            </div>
                                        </td>
                                        <td>
                                            {call.handled_by_ai ? (
                                                <span className="badge badge-ai">AI Agent</span>
                                            ) : (
                                                <span className="badge badge-human">Human</span>
                                            )}
                                        </td>
                                        <td>
                                            {call.outcome ? (
                                                <span className="outcome-text">{call.outcome.replace('_', ' ')}</span>
                                            ) : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {selectedCall && (
                        <div className="call-details-panel">
                            <h2>Call Details</h2>
                            <div className="call-details-grid">
                                <div>
                                    <strong>Direction:</strong> {selectedCall.direction}
                                </div>
                                <div>
                                    <strong>Status:</strong> {selectedCall.status.replace('_', ' ')}
                                </div>
                                <div>
                                    <strong>From:</strong> {selectedCall.from_number}
                                </div>
                                <div>
                                    <strong>To:</strong> {selectedCall.to_number}
                                </div>
                                <div>
                                    <strong>Duration:</strong> {formatDuration(selectedCall.duration_seconds)}
                                </div>
                                <div>
                                    <strong>Date & Time:</strong> {formatDate(selectedCall.created_at)}
                                </div>
                                <div>
                                    <strong>Handled By:</strong> {selectedCall.handled_by_ai ? 'AI Agent' : 'Human'}
                                </div>
                                <div>
                                    <strong>Outcome:</strong> {selectedCall.outcome ? selectedCall.outcome.replace('_', ' ') : '-'}
                                </div>
                                {selectedCall.outcome_notes && (
                                    <div className="call-details-notes">
                                        <strong>Outcome Notes:</strong> {selectedCall.outcome_notes}
                                    </div>
                                )}
                                {selectedCall.transcript_summary && (
                                    <div className="call-details-notes">
                                        <strong>Transcript Summary:</strong> {selectedCall.transcript_summary}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* Simple Pagination */}
            <div className="pagination">
                <button
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                    className="btn btn-secondary"
                >
                    Previous
                </button>
                <span>Page {page}</span>
                <button
                    disabled={calls.length < 20}
                    onClick={() => setPage(p => p + 1)}
                    className="btn btn-secondary"
                >
                    Next
                </button>
            </div>


            {
                isCallModalOpen && (
                    <OutboundCallModal
                        onClose={() => setIsCallModalOpen(false)}
                        onCallInitiated={() => {
                            fetchCalls();
                        }}
                    />
                )
            }
        </div >
    );
};
