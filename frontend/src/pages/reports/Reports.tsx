import React from 'react';
import { BarChart3, TrendingUp, Users, Phone } from 'lucide-react';
import '../properties/Properties.css';

export const Reports: React.FC = () => {
    return (
        <div className="reports-page">
            <div className="page-header">
                <div>
                    <h1>Reports & Analytics</h1>
                    <p>View detailed reports and analytics</p>
                </div>
            </div>

            <div className="reports-grid">
                <div className="report-card">
                    <div className="report-icon">
                        <Phone size={24} />
                    </div>
                    <h3>Call Analytics</h3>
                    <p>View call volume, duration, and AI handling metrics</p>
                    <button className="btn btn-secondary">View Report</button>
                </div>

                <div className="report-card">
                    <div className="report-icon">
                        <Users size={24} />
                    </div>
                    <h3>Lead Performance</h3>
                    <p>Track lead conversion rates and pipeline health</p>
                    <button className="btn btn-secondary">View Report</button>
                </div>

                <div className="report-card">
                    <div className="report-icon">
                        <TrendingUp size={24} />
                    </div>
                    <h3>Agent Performance</h3>
                    <p>Monitor agent productivity and conversion metrics</p>
                    <button className="btn btn-secondary">View Report</button>
                </div>

                <div className="report-card">
                    <div className="report-icon">
                        <BarChart3 size={24} />
                    </div>
                    <h3>Custom Report</h3>
                    <p>Build custom reports with flexible filters</p>
                    <button className="btn btn-secondary">Create Report</button>
                </div>
            </div>
        </div>
    );
};
