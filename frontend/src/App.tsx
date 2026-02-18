import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAuthStore } from './store';
import { authService } from './services/authService';
import { Login } from './pages/auth/Login';
import { Signup } from './pages/auth/Signup';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/dashboard/Dashboard';
import { PropertyList } from './pages/properties/PropertyList';
import { ProductAdmin } from './pages/admin/ProductAdmin';
import { LeadList } from './pages/leads/LeadList';
import { CallHistory } from './pages/calls/CallHistory';
import { Reports } from './pages/reports/Reports';
import { UserManagement } from './pages/admin/UserManagement';
import { Appointments } from './pages/appointments/Appointments';
import { SolarReportPage } from './pages/calls/SolarReportPage';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isAuthenticated, setUser } = useAuthStore();
    const navigate = useNavigate();

    useEffect(() => {
        if (authService.isAuthenticated() && !isAuthenticated) {
            authService.getCurrentUser()
                .then(user => setUser(user))
                .catch(() => navigate('/login'));
        }
    }, []);

    if (!authService.isAuthenticated()) {
        return <Navigate to="/login" replace />;
    }

    return <Layout>{children}</Layout>;
};

const App: React.FC = () => {
    return (
        <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Signup />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/properties" element={<ProtectedRoute><PropertyList /></ProtectedRoute>} />
            <Route path="/leads" element={<ProtectedRoute><LeadList /></ProtectedRoute>} />
            <Route path="/appointments" element={<ProtectedRoute><Appointments /></ProtectedRoute>} />
            <Route path="/calls" element={<ProtectedRoute><CallHistory /></ProtectedRoute>} />
            <Route path="/calls/received" element={<ProtectedRoute><CallHistory receptionFilter="received" /></ProtectedRoute>} />
            <Route path="/calls/failed" element={<ProtectedRoute><CallHistory receptionFilter="not_received" /></ProtectedRoute>} />
            <Route path="/calls/:callId/report" element={<ProtectedRoute><SolarReportPage /></ProtectedRoute>} />
            <Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
            <Route path="/admin/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
            <Route path="/admin/products" element={<ProtectedRoute><ProductAdmin /></ProtectedRoute>} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
};

export default App;
