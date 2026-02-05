import React, { useState } from 'react';
import { Phone, X, Loader } from 'lucide-react';
import api from '../services/api';
import './OutboundCallModal.css';

interface OutboundCallModalProps {
    onClose: () => void;
    onCallInitiated: () => void;
}

export const OutboundCallModal: React.FC<OutboundCallModalProps> = ({ onClose, onCallInitiated }) => {
    const [phoneNumber, setPhoneNumber] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleCall = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            await api.post('/calls/dial', {
                to_number: phoneNumber
            });
            onCallInitiated();
            onClose();
        } catch (err: any) {
            console.error('Failed to initiate call:', err);
            setError(err.response?.data?.detail || 'Failed to initiate call. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay">
            <div className="modal-content outbound-modal">
                <div className="modal-header">
                    <h2><Phone size={20} /> Make a Call</h2>
                    <button className="close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleCall}>
                    <div className="modal-body">
                        <div className="form-group">
                            <label htmlFor="phone">Phone Number</label>
                            <input
                                id="phone"
                                type="tel"
                                placeholder="+1234567890"
                                value={phoneNumber}
                                onChange={(e) => setPhoneNumber(e.target.value)}
                                required
                                pattern="^\+?[1-9]\d{1,14}$"
                                title="Please enter a valid phone number (E.164 format preferred)"
                            />
                            <small className="help-text">Enter number in E.164 format (e.g., +15551234567)</small>
                        </div>

                        {error && (
                            <div className="error-message">
                                {error}
                            </div>
                        )}
                    </div>

                    <div className="modal-footer">
                        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>
                            Cancel
                        </button>
                        <button type="submit" className="btn btn-primary" disabled={loading || !phoneNumber}>
                            {loading ? <><Loader size={16} className="spin" /> Calling...</> : 'Call Now'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};
