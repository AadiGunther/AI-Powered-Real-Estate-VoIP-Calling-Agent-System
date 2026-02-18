import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    User, MapPin, Zap, Home, ClipboardCheck,
    TrendingUp, Calendar, AlertCircle, CheckCircle2,
    ArrowLeft, Globe, Lightbulb
} from 'lucide-react';
import api from '../../services/api';
import type { Call } from '../../types/call';
import './SolarReportPage.css';

export const SolarReportPage: React.FC = () => {
    const { callId } = useParams<{ callId: string }>();
    const navigate = useNavigate();
    const [call, setCall] = useState<Call | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchCall = async () => {
            try {
                const response = await api.get<Call>(`/calls/${callId}`);
                setCall(response.data);
            } catch (err: any) {
                setError(err?.response?.data?.detail || 'Failed to load report');
            } finally {
                setLoading(false);
            }
        };
        fetchCall();
    }, [callId]);

    if (loading) return <div className="loading-state">Generating Insights...</div>;
    if (error || !call) return <div className="error-state">{error || 'Call not found'}</div>;

    const report = call.structured_report ? JSON.parse(call.structured_report) : null;

    if (!report) {
        return (
            <div className="report-not-ready">
                <AlertCircle size={48} />
                <h2>No structured data available</h2>
                <p>The AI is still processing this call or no transcript was available.</p>
                <button className="btn btn-primary" onClick={() => navigate('/calls')}>Back to History</button>
            </div>
        );
    }

    const { customer_info, requirement, interests, visit, lead_classification, call_analysis } = report;

    const getStatusClass = (status: string) => {
        const map: Record<string, string> = {
            hot: 'status-hot',
            warm: 'status-warm',
            cold: 'status-cold',
            not_interested: 'status-dead',
            callback: 'status-callback',
            invalid_number: 'status-invalid',
        };
        return map[status?.toLowerCase()] || '';
    };

    return (
        <div className="solar-report-container">
            <header className="report-header">
                <button className="back-button" onClick={() => navigate('/calls')}>
                    <ArrowLeft size={20} />
                </button>
                <div className="header-titles">
                    <h1>Solar Sales Analysis</h1>
                    <span className="call-sid">Call ID: {call.call_sid}</span>
                </div>
                <div className={`lead-badge ${getStatusClass(lead_classification.lead_status)}`}>
                    {lead_classification.lead_status.toUpperCase()} LEAD
                </div>
            </header>

            <div className="report-grid">
                {/* section: Customer & Classification */}
                <section className="report-card customer-section">
                    <div className="card-header">
                        <User size={20} />
                        <h2>Customer Profile</h2>
                    </div>
                    <div className="info-grid">
                        <div className="info-item">
                            <label>Name</label>
                            <span>{customer_info.name || 'Unknown'}</span>
                        </div>
                        <div className="info-item">
                            <label>Contact</label>
                            <span>{customer_info.contact_number}</span>
                        </div>
                        <div className="info-item">
                            <label>Preferred Language</label>
                            <span className="capitalize">{customer_info.preferred_language}</span>
                        </div>
                        <div className="info-item full-width">
                            <label>Address</label>
                            <div className="address-box">
                                <MapPin size={14} />
                                <span>{customer_info.address || 'No address provided'}, {customer_info.city}</span>
                            </div>
                        </div>
                    </div>

                    <div className="classification-box">
                        <div className="confidence-score">
                            <label>Confidence</label>
                            <div className="score-ring">
                                <TrendingUp size={16} />
                                <span>{lead_classification.confidence_score}/10</span>
                            </div>
                        </div>
                        <div className="timeline">
                            <label>Expected Timeline</label>
                            <span className="timeline-tag">{lead_classification.buying_timeline?.replace(/_/g, ' ') || 'Not specified'}</span>
                        </div>
                    </div>
                </section>

                {/* section: Technical Requirements */}
                <section className="report-card tech-section">
                    <div className="card-header">
                        <Zap size={20} />
                        <h2>Requirements</h2>
                    </div>
                    <div className="requirement-list">
                        <div className="req-item">
                            <Home size={18} />
                            <div>
                                <label>Installation Type</label>
                                <span>{requirement.installation_type}</span>
                            </div>
                        </div>
                        <div className="req-item">
                            <TrendingUp size={18} />
                            <div>
                                <label>Estimated Capacity</label>
                                <span>{requirement.estimated_kw && requirement.estimated_kw !== 'unknown' ? `${requirement.estimated_kw} kW` : 'Unknown'}</span>
                            </div>
                        </div>
                        <div className="req-item">
                            <Calendar size={18} />
                            <div>
                                <label>Avg. Monthly Bill</label>
                                <span>{requirement.monthly_electricity_bill && requirement.monthly_electricity_bill !== 'unknown' ? `₹${requirement.monthly_electricity_bill}` : 'Unknown'}</span>
                            </div>
                        </div>
                        <div className="req-item">
                            <Globe size={18} />
                            <div>
                                <label>Preferred Brand</label>
                                <span>{requirement.preferred_brand}</span>
                            </div>
                        </div>
                    </div>
                    <div className="status-pills">
                        <div className={`pill ${requirement.rooftop_available === 'yes' ? 'check' : 'cross'}`}>
                            Rooftop: {requirement.rooftop_available}
                        </div>
                        <div className={`pill ${requirement.existing_solar === 'yes' ? 'check' : 'cross'}`}>
                            Existing Solar: {requirement.existing_solar}
                        </div>
                    </div>
                </section>

                {/* section: Interests */}
                <section className="report-card interest-section">
                    <div className="card-header">
                        <Lightbulb size={20} />
                        <h2>Product Affinity</h2>
                    </div>
                    <div className="pills-container">
                        <div className={`affinity-item ${interests.subsidy_interested ? 'active' : ''}`}>
                            <CheckCircle2 size={16} /> Subsidy
                        </div>
                        <div className={`affinity-item ${interests.loan_emi_required ? 'active' : ''}`}>
                            <CheckCircle2 size={16} /> Loan / EMI
                        </div>
                        <div className={`affinity-item ${interests.net_metering_interested ? 'active' : ''}`}>
                            <CheckCircle2 size={16} /> Net Metering
                        </div>
                        <div className={`affinity-item ${interests.battery_storage_interested ? 'active' : ''}`}>
                            <CheckCircle2 size={16} /> Battery Storage
                        </div>
                    </div>
                </section>

                {/* section: Visit Details */}
                <section className="report-card visit-section">
                    <div className="card-header">
                        <Calendar size={20} />
                        <h2>Site Visit</h2>
                    </div>
                    {visit.visit_scheduled ? (
                        <div className="visit-info">
                            <div className="visit-datetime">
                                <span className="date">{visit.visit_date}</span>
                                <span className="time-slot capitalize">{visit.visit_time_slot}</span>
                            </div>
                            {visit.visit_address && (
                                <div className="visit-address">
                                    <MapPin size={14} />
                                    <span>{visit.visit_address}</span>
                                </div>
                            )}
                            <div className="scheduled-badge">Visit Scheduled</div>
                        </div>
                    ) : (
                        <div className="no-visit">
                            <Calendar size={32} />
                            <p>No site visit scheduled yet</p>
                        </div>
                    )}
                </section>

                {/* section: Call Analysis */}
                <section className="report-card analysis-section">
                    <div className="card-header">
                        <ClipboardCheck size={20} />
                        <h2>Analyst Insights</h2>
                    </div>
                    <div className="insights-content">
                        <div className="insight-block">
                            <h3>Outcome summary</h3>
                            <p>{call_analysis.call_outcome}</p>
                        </div>
                        <div className="insight-block hindi">
                            <h3>Hindi Summary (for Local Agents)</h3>
                            <p>{call_analysis.call_summary_hindi}</p>
                        </div>
                        <div className="analysis-tags">
                            <div className="tag-group">
                                <label>Objections</label>
                                <div className="tags">
                                    {call_analysis.objections_raised.map((v: string, i: number) => <span key={i} className="tag tag-warning">{v}</span>)}
                                </div>
                            </div>
                            <div className="tag-group">
                                <label>Key Concerns</label>
                                <div className="tags">
                                    {call_analysis.key_concerns.map((v: string, i: number) => <span key={i} className="tag tag-danger">{v}</span>)}
                                </div>
                            </div>
                            <div className="tag-group">
                                <label>Positive Signals</label>
                                <div className="tags">
                                    {call_analysis.positive_signals.map((v: string, i: number) => <span key={i} className="tag tag-success">{v}</span>)}
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* section: Next Actions */}
                <section className="report-card action-section">
                    <div className="card-header">
                        <TrendingUp size={20} />
                        <h2>Next Steps</h2>
                    </div>
                    <div className="next-action-box">
                        <div className="main-action">
                            <label>Immediate Action</label>
                            <p>{call_analysis.next_action}</p>
                        </div>
                        {call_analysis.follow_up_required && (
                            <div className="follow-up">
                                <div className="follow-up-meta">
                                    <label>Follow-up Date</label>
                                    <span>{call_analysis.follow_up_date || 'TBD'}</span>
                                </div>
                                <p>{call_analysis.follow_up_notes}</p>
                            </div>
                        )}
                    </div>
                </section>
            </div>
        </div>
    );
};
