
import React, { useState, useEffect, useRef } from 'react';
import { Phone, Calendar, ArrowUpRight, ArrowDownLeft, Filter, PlayCircle, Download } from 'lucide-react';
import api from '../../services/api';
import type { Call, CallListResponse, CallTranscript } from '../../types/call';
import { OutboundCallModal } from '../../components/OutboundCallModal';
import { useAuthStore } from '../../store';
import './CallHistory.css';

interface CallHistoryProps {
    receptionFilter?: 'received' | 'not_received';
}

export const CallHistory: React.FC<CallHistoryProps> = ({ receptionFilter }) => {
    const [calls, setCalls] = useState<Call[]>([]);
    const [recordings, setRecordings] = useState<Call[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [isCallModalOpen, setIsCallModalOpen] = useState(false);
    const [selectedCall, setSelectedCall] = useState<Call | null>(null);

    const [statusFilter, setStatusFilter] = useState('');
    const [directionFilter, setDirectionFilter] = useState('');

    const [transcript, setTranscript] = useState<CallTranscript | null>(null);
    const [transcriptLoading, setTranscriptLoading] = useState(false);
    const [transcriptError, setTranscriptError] = useState<string | null>(null);

    const [recordingsLoading, setRecordingsLoading] = useState(false);
    const [recordingsError, setRecordingsError] = useState<string | null>(null);

    const { user } = useAuthStore();
    const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
    const [recordingError, setRecordingError] = useState<string | null>(null);
    const [autoplayPending, setAutoplayPending] = useState(false);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const [recordingUrlLoadingFor, setRecordingUrlLoadingFor] = useState<number | null>(null);
    const recordingRequestIdRef = useRef(0);

    const downloadRecording = async (url: string, fileName: string) => {
        try {
            const resp = await fetch(url);
            if (!resp.ok) {
                throw new Error(`Failed to download recording (${resp.status})`);
            }
            const blob = await resp.blob();
            const objectUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = objectUrl;
            link.download = fileName;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(objectUrl);
        } catch {
            window.open(url, '_blank', 'noopener,noreferrer');
        }
    };


    useEffect(() => {
        fetchCalls();
    }, [page, statusFilter, directionFilter]);

    useEffect(() => {
        if (user?.role === 'admin') {
            fetchRecordings();
        } else {
            setRecordings([]);
            setRecordingsError(null);
            setRecordingsLoading(false);
        }
    }, [user]);

    const fetchCalls = async () => {
        setLoading(true);
        setError(null);
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
        } catch (err: any) {
            console.error('Failed to fetch calls:', err);
            const message =
                err?.response?.data?.detail ||
                'Failed to load call history. Please try again.';
            setError(message);
            setCalls([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectCall = async (call: Call, opts?: { autoplay?: boolean }) => {
        const requestId = ++recordingRequestIdRef.current;

        setSelectedCall(call);
        setTranscript(null);
        setTranscriptError(null);
        setRecordingUrl(null);
        setRecordingError(null);
        setAutoplayPending(Boolean(opts?.autoplay));
        setRecordingUrlLoadingFor(null);
    };

    const handlePlayRecording = async (call: Call, e?: React.MouseEvent) => {
        if (e) e.stopPropagation();
        setRecordingUrlLoadingFor(call.id);
        try {
            const response = await api.get<{ recording_url: string }>(`/calls/${call.id}/recording-url`);
            if (response.data.recording_url) {
                window.open(response.data.recording_url, '_blank');
            } else {
                alert("Recording URL not found");
            }
        } catch (err) {
            console.error("Failed to get recording URL", err);
            alert("Failed to open recording");
        } finally {
            setRecordingUrlLoadingFor(null);
        }
    };

    // Transcript fetching
    const fetchTranscript = async (callId: number) => {
        setTranscriptLoading(true);
        setTranscriptError(null);
        try {
            const response = await api.get<CallTranscript>(`/calls/${callId}/transcript`);
            setTranscript(response.data);
        } catch (err: any) {
            console.error('Failed to fetch transcript:', err);
            const message =
                err?.response?.data?.detail ||
                'Transcript not available for this call.';
            setTranscriptError(message);
            setTranscript(null);
        } finally {
            setTranscriptLoading(false);
        }
    };

    const fetchRecordings = async () => {
        // This function is no longer needed since we fetch recording URL on demand
        // But keeping it as a placeholder if we need to bulk fetch recordings later
        setRecordingsLoading(false);
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

    const normalizeReceptionStatus = (call: Call): 'received' | 'not_received' => {
        if (call.reception_status === 'received' || call.reception_status === 'not_received') {
            return call.reception_status;
        }
        return call.direction === 'inbound' && call.status === 'completed' ? 'received' : 'not_received';
    };

    const filteredCalls = calls.filter((call) => {
        if (!receptionFilter) return true;
        const receptionStatus = normalizeReceptionStatus(call);
        return receptionFilter === receptionStatus;
    });

    return (
        <div className="min-h-screen bg-slate-50 px-4 py-6 md:px-8">
            <div className="call-history-page">
                <div className="page-header">
                    <div>
                        <h1 className="text-2xl font-semibold text-slate-900">Call History</h1>
                        <p className="mt-1 text-sm text-slate-500">{total} total calls</p>
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

                {selectedCall && recordingError && (
                    <div className="error-message">
                        {recordingError}
                    </div>
                )}

                {selectedCall &&
                    recordingUrlLoadingFor === selectedCall.id &&
                    (
                        <div className="loading">Loading recording...</div>
                    )}

                {selectedCall && selectedCall.recording_url && (
                    <div className="recording-player">
                        <div className="recording-player-header">
                            <span className="recording-player-title">
                                Call Recording –{' '}
                                {selectedCall.caller_username ||
                                    `${selectedCall.from_number} → ${selectedCall.to_number}`}
                            </span>
                        </div>
                        
                        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginTop: '0.5rem' }}>
                            <button
                                type="button"
                                className="btn btn-primary"
                                onClick={() => handlePlayRecording(selectedCall)}
                                disabled={recordingUrlLoadingFor === selectedCall.id}
                                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                            >
                                <PlayCircle size={16} />
                                <span>{recordingUrlLoadingFor === selectedCall.id ? 'Opening...' : 'Open Recording in New Tab'}</span>
                            </button>
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="loading">Loading call history...</div>
                )}

                {!loading && error && (
                    <div className="error-message">
                        {error}
                    </div>
                )}

                {!loading && !error && filteredCalls.length === 0 && (
                    <div className="empty-state">
                        No calls found for the selected filters.
                    </div>
                )}

                {!loading && !error && calls.length > 0 && (
                    <>
                        <div className="table-and-sidebar">
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
                                            <th>Recording</th>
                                            <th>Outcome</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredCalls.map((call) => (
                                            <tr
                                                key={call.id}
                                                onClick={() => handleSelectCall(call)}
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
                                                        <span className="phone-label">From:</span> {call.from_number}
                                                        <br />
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
                                                    {call.recording_url ? (
                                                        <button
                                                            type="button"
                                                            className="recording-icon-button"
                                                            onClick={(e) => {
                                                                handlePlayRecording(call, e);
                                                            }}
                                                            disabled={recordingUrlLoadingFor === call.id}
                                                        >
                                                            <PlayCircle size={16} />
                                                            <span>
                                                                {recordingUrlLoadingFor === call.id ? 'Loading...' : 'Play'}
                                                            </span>
                                                        </button>
                                                    ) : (
                                                        '-'
                                                    )}
                                                </td>
                                                <td>
                                                    {call.outcome ? (
                                                        <span className="outcome-text">{call.outcome.replace('_', ' ')}</span>
                                                    ) : (
                                                        '-'
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {selectedCall && (
                            <div className="call-details-layout">
                                <div className="call-details-panel">
                                    <h2>Call Details</h2>
                                    <div className="call-details-grid">
                                        <div>
                                            <strong>Call ID:</strong> {selectedCall.id}
                                        </div>
                                        <div>
                                            <strong>Call SID:</strong> {selectedCall.call_sid}
                                        </div>
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
                                            <strong>Created At:</strong> {formatDate(selectedCall.created_at)}
                                        </div>
                                        {selectedCall.started_at && (
                                            <div>
                                                <strong>Started At:</strong> {formatDate(selectedCall.started_at)}
                                            </div>
                                        )}
                                        {selectedCall.answered_at && (
                                            <div>
                                                <strong>Answered At:</strong> {formatDate(selectedCall.answered_at)}
                                            </div>
                                        )}
                                        {selectedCall.ended_at && (
                                            <div>
                                                <strong>Ended At:</strong> {formatDate(selectedCall.ended_at)}
                                            </div>
                                        )}
                                        <div>
                                            <strong>Handled By:</strong> {selectedCall.handled_by_ai ? 'AI Agent' : 'Human'}
                                        </div>
                                        <div>
                                            <strong>Outcome:</strong> {selectedCall.outcome ? selectedCall.outcome.replace('_', ' ') : '-'}
                                        </div>
                                        {selectedCall.escalated_to_human && (
                                            <div className="call-details-notes">
                                                <strong>Escalated To Human:</strong> Yes
                                                {selectedCall.escalation_reason && (
                                                    <> – {selectedCall.escalation_reason}</>
                                                )}
                                            </div>
                                        )}
                                        {selectedCall.lead_created !== undefined && (
                                            <div className="call-details-notes">
                                                <strong>Lead Created:</strong> {selectedCall.lead_created ? 'Yes' : 'No'}
                                            </div>
                                        )}
                                        {(selectedCall.sentiment_score !== undefined || selectedCall.customer_satisfaction !== undefined) && (
                                            <div className="call-details-notes">
                                                {selectedCall.sentiment_score !== undefined && (
                                                    <div>
                                                        <strong>Sentiment Score:</strong> {selectedCall.sentiment_score.toFixed(2)}
                                                    </div>
                                                )}
                                                {selectedCall.customer_satisfaction !== undefined && (
                                                    <div>
                                                        <strong>Customer Satisfaction:</strong> {selectedCall.customer_satisfaction}/5
                                                    </div>
                                                )}
                                            </div>
                                        )}
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

                                        <div className="call-details-notes">
                                            <button
                                                className="btn btn-secondary"
                                                onClick={() => fetchTranscript(selectedCall.id)}
                                                disabled={transcriptLoading}
                                            >
                                                {transcriptLoading ? 'Loading transcript...' : 'View Transcript'}
                                            </button>
                                            {transcriptError && (
                                                <div className="transcript-error">
                                                    {transcriptError}
                                                </div>
                                            )}
                                        </div>
                                        {transcript && (
                                            <div className="call-details-transcript">
                                                <h3>Full Transcript</h3>
                                                <div className="transcript-messages">
                                                    {transcript.messages.map((msg, index) => (
                                                        <div
                                                            key={index}
                                                            className={`transcript-message transcript-${msg.role === 'agent' ? 'agent' : 'customer'}`}
                                                        >
                                                            <div className="transcript-meta">
                                                                <span className="transcript-role">
                                                                    {msg.role === 'agent' ? 'AI / Agent' : 'Customer'}
                                                                </span>
                                                                <span className="transcript-timestamp">
                                                                    {formatDate(msg.timestamp)}
                                                                </span>
                                                            </div>
                                                            <div className="transcript-content">
                                                                {msg.content}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {user?.role === 'admin' && (
                                    <div className="recordings-sidebar">
                                        <h3>Recordings</h3>
                                        {recordingsLoading && (
                                            <div className="recordings-empty">
                                                Loading recordings...
                                            </div>
                                        )}
                                        {recordingsError && !recordingsLoading && (
                                            <div className="error-message">
                                                {recordingsError}
                                            </div>
                                        )}
                                        <div className="recordings-list">
                                            {!recordingsLoading && !recordingsError && recordings.filter(c => c.recording_url).length === 0 && (
                                                <div className="recordings-empty">
                                                    No recordings available.
                                                </div>
                                            )}
                                            {recordings
                                                .filter(c => c.recording_url)
                                                .map((c) => (
                                                    <div
                                                        key={c.id}
                                                        className={`recording-item ${selectedCall?.id === c.id ? 'recording-selected' : ''}`}
                                                        onClick={() => handleSelectCall(c)}
                                                    >
                                                        <div className="recording-main">
                                                            <div className="recording-title">
                                                                {c.caller_username || `${c.from_number} → ${c.to_number}`}
                                                            </div>
                                                            <div className="recording-meta">
                                                                <span>{formatDate(c.created_at)}</span>
                                                                <span>• {formatDuration(c.duration_seconds)}</span>
                                                                <span>• {c.handled_by_ai ? 'AI' : 'Human'}</span>
                                                            </div>
                                                        </div>
                                                        <div className="recording-actions">
                                                            <button
                                                                type="button"
                                                                className="recording-icon-button"
                                                                onClick={(e) => {
                                                                    e.preventDefault();
                                                                    e.stopPropagation();
                                                                    (e.nativeEvent as any)?.stopImmediatePropagation?.();
                                                                    void handleSelectCall(c, { autoplay: true });
                                                                }}
                                                                disabled={recordingUrlLoadingFor === c.id}
                                                            >
                                                                <PlayCircle size={18} />
                                                                <span>
                                                                    {recordingUrlLoadingFor === c.id ? 'Loading...' : 'Play'}
                                                                </span>
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                        </div>
                                    </div>
                                )}
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


                {isCallModalOpen && (
                    <OutboundCallModal
                        onClose={() => setIsCallModalOpen(false)}
                        onCallInitiated={() => {
                            fetchCalls();
                        }}
                    />
                )}
            </div>
        </div>
    );
};
