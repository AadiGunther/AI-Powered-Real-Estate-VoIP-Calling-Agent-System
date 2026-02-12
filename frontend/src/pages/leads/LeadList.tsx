import React, { useState, useEffect } from 'react';
import { Users, Search, Filter, Phone } from 'lucide-react';
import api from '../../services/api';
import type { Lead, LeadListResponse } from '../../types/lead';
import '../properties/Properties.css';

export const LeadList: React.FC = () => {
    const [leads, setLeads] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(true);
    const [total, setTotal] = useState(0);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchLeads();
    }, []);

    const fetchLeads = async () => {
        try {
            setError(null);
            setLoading(true);
            const response = await api.get<LeadListResponse>('/leads/');
            console.log('Fetched leads:', response.data);
            setLeads(response.data.leads);
            setTotal(response.data.total);
        } catch (error) {
            console.error('Failed to fetch leads:', error);
            setError('Failed to load leads. Please try again.');
            setLeads([]);
            setTotal(0);
        } finally {
            setLoading(false);
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
                    <input type="text" placeholder="Search leads..." />
                </div>
                <button className="btn btn-secondary">
                    <Filter size={18} /> Filters
                </button>
            </div>

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
                                <th>Contact</th>
                                <th>Quality</th>
                                <th>Status</th>
                                <th>Source</th>
                                <th>Preferences</th>
                                <th>AI Summary</th>
                                <th>Created</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leads.map((lead) => (
                                <tr key={lead.id}>
                                    <td>
                                        <div className="lead-contact">
                                            <div className="lead-avatar">
                                                <Users size={16} />
                                            </div>
                                            <div>
                                                <div className="lead-name">{lead.name || 'Unknown'}</div>
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
                                        <span className="lead-status">{lead.status.replace('_', ' ')}</span>
                                    </td>
                                    <td>{lead.source.replace('_', ' ')}</td>
                                    <td>
                                        {lead.preferred_location && (
                                            <span className="lead-pref">{lead.preferred_location}</span>
                                        )}
                                        {lead.budget_max && (
                                            <span className="lead-budget">Up to ₹{(lead.budget_max / 100000).toFixed(0)}L</span>
                                        )}
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
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};
