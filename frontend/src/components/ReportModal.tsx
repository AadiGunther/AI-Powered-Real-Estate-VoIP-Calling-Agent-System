import React from 'react';
import { X, CheckCircle, AlertTriangle, List, FileText } from 'lucide-react';
import { Call } from '../types/call';
import './ReportModal.css';

interface ReportModalProps {
    call: Call;
    onClose: () => void;
}

interface AnalysisData {
    summary: string;
    customer_intent: string;
    interest_level: 'High' | 'Medium' | 'Low';
    follow_up_required: boolean;
    action_items: string[];
}

export const ReportModal: React.FC<ReportModalProps> = ({ call, onClose }) => {
    // Parse the analysis if available (it might be stored in outcome_notes or we fetch it)
    // For now, we assume the backend might return the full analysis in a future endpoint.
    // However, based on our current backend, we have transcript_summary and outcome_notes.
    // The FULL JSON report is in MongoDB, accessible via /calls/{id}/transcript endpoint if we expand it.
    // But wait, get_call_transcript returns { messages, summary }. It does NOT return the full analysis JSON.
    // To show the full analysis, we should use the data we have or assume the user wants to see the summary/outcome.

    // Let's rely on transcript_summary and outcome_notes for now, 
    // as fetching the full JSON might require an API update.

    // Parse outcome notes to extract interest/follow-up if configured that way
    const interestLevel = call.outcome_notes?.match(/Interest: (High|Medium|Low)/)?.[1] || 'Unknown';
    const followUp = call.outcome_notes?.includes('Follow-up: True') || false;

    return (
        <div className="modal-overlay">
            <div className="modal-content report-modal">
                <div className="modal-header">
                    <h2>Call Analysis Report</h2>
                    <button className="close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="modal-body">
                    <div className="report-section summary-section">
                        <h3><FileText size={18} /> Executive Summary</h3>
                        <p>{call.transcript_summary || "No summary available."}</p>
                    </div>

                    <div className="report-grid">
                        <div className="report-card">
                            <h4>Intent</h4>
                            <div className="intent-badge">{call.outcome || "Unknown"}</div>
                        </div>
                        <div className="report-card">
                            <h4>Interest Level</h4>
                            <div className={`interest-badge ${interestLevel.toLowerCase()}`}>
                                {interestLevel}
                            </div>
                        </div>
                        <div className="report-card">
                            <h4>Follow Up?</h4>
                            <div className={`follow-up-badge ${followUp ? 'required' : 'optional'}`}>
                                {followUp ? <AlertTriangle size={16} /> : <CheckCircle size={16} />}
                                {followUp ? "Required" : "No"}
                            </div>
                        </div>
                    </div>

                    {call.outcome_notes && (
                        <div className="report-section">
                            <h3><List size={18} /> Creation Notes / Action Items</h3>
                            <pre className="notes-pre">{call.outcome_notes}</pre>
                        </div>
                    )}
                </div>

                <div className="modal-footer">
                    <button className="btn btn-primary" onClick={onClose}>Close</button>
                </div>
            </div>
        </div>
    );
};
