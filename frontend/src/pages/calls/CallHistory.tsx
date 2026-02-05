import React, { useState, useEffect } from 'react';
import { Phone, Search, Filter, Play, Clock, ArrowUpRight, ArrowDownLeft } from 'lucide-react';
import api from '../../services/api';
import type { Call, CallListResponse } from '../../types/call';
import { ReportModal } from '../../components/ReportModal';
import { OutboundCallModal } from '../../components/OutboundCallModal';
import '../properties/Properties.css';
import './Calls.css';

export const CallHistory: React.FC = () => {
    const [calls, setCalls] = useState<Call[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);

    useEffect(() => {
        fetchCalls();
    }, []);

    const fetchCalls = async () => {
        try {
            const response = await api.get<CallListResponse>('/calls/');
            setCalls(response.data.calls);
            setTotal(response.data.total);
        } catch (error) {
            console.error('Failed to fetch calls:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatDuration = (seconds?: number) => {
        if (!seconds) return '--';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const [selectedCall, setSelectedCall] = useState<Call | null>(null);
    const [showCallModal, setShowCallModal] = useState(false);

    return (
        <div className="calls-page">
            <div className="page-header">
                <div>
                    <h1>Call History</h1>
                    <p>{total} total calls</p>
                </div>
                <button className="btn btn-primary" onClick={() => setShowCallModal(true)}>
                    <Phone size={18} /> Make Call
                </button>
            </div>

            <div className="filters-bar">
                <div className="search-box">
                    <Search size={18} />
                    <input type="text" placeholder="Search by phone number..." />
                </div>
                <button className="btn btn-secondary">
                    <Filter size={18} /> Filters
                </button>
            </div>

            {loading ? (
                <div className="loading">Loading calls...</div>
            ) : (
                <div className="card">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Direction</th>
                                <th>From</th>
                                <th>Status</th>
                                <th>Duration</th>
                                <th>AI Handled</th>
                                <th>Outcome</th>
                                <th>Recording</th>
                                <th>Report</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {calls.map((call) => (
                                <tr key={call.id}>
                                    <td>
                                        <span className={`call-direction ${call.direction}`}>
                                            {call.direction === 'inbound' ? (
                                                <ArrowDownLeft size={16} />
                                            ) : (
                                                <ArrowUpRight size={16} />
                                            )}
                                        </span>
                                    </td>
                                    <td>
                                        <div className="call-number">
                                            <Phone size={14} /> {call.from_number}
                                        </div>
                                    </td>
                                    <td>
                                        <span className={`badge ${call.status === 'completed' ? 'badge-success' : 'badge-warning'}`}>
                                            {call.status}
                                        </span>
                                    </td>
                                    <td>
                                        <span className="call-duration">
                                            <Clock size={14} /> {formatDuration(call.duration_seconds)}
                                        </span>
                                    </td>
                                    <td>
                                        <span className={`badge ${call.handled_by_ai ? 'badge-info' : 'badge-warning'}`}>
                                            {call.handled_by_ai ? 'AI' : 'Human'}
                                        </span>
                                    </td>
                                    <td>{call.outcome || '--'}</td>
                                    <td>
                                        {call.recording_url && (
                                            <button className="btn btn-ghost btn-sm">
                                                <Play size={14} />
                                            </button>
                                        )}
                                    </td>
                                    <td>
                                        {(call.transcript_summary || call.transcript_id) && (
                                            <button
                                                className="btn btn-sm btn-outline-primary"
                                                onClick={() => setSelectedCall(call)}
                                            >
                                                View Report
                                            </button>
                                        )}
                                    </td>
                                    <td>
                                        {new Date(call.created_at).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {selectedCall && (
                <ReportModal
                    call={selectedCall}
                    onClose={() => setSelectedCall(null)}
                />
            )}

            {showCallModal && (
                <OutboundCallModal
                    onClose={() => setShowCallModal(false)}
                    onCallInitiated={() => {
                        fetchCalls();
                    }}
                />
            )}
        </div>
    );
};
