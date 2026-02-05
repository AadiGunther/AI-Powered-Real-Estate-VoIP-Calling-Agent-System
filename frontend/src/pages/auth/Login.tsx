import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, ArrowRight, Building2 } from 'lucide-react';
import { authService } from '../../services/authService';
import { useAuthStore } from '../../store';
import toast from 'react-hot-toast';
import './Auth.css';

export const Login: React.FC = () => {
    const navigate = useNavigate();
    const { setToken, setUser } = useAuthStore();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            const { access_token } = await authService.login({ email, password });
            setToken(access_token);
            const user = await authService.getCurrentUser();
            setUser(user);
            toast.success('Welcome back!');
            navigate('/dashboard');
        } catch (error: any) {
            toast.error(error.response?.data?.detail || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-background" />
            <div className="auth-card animate-fade-in">
                <div className="auth-logo">
                    <Building2 size={40} />
                    <span> Real Estate</span>
                </div>
                <h1 className="auth-title">Welcome Back</h1>
                <p className="auth-subtitle">Sign in to your account to continue</p>

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="input-group">
                        <Mail className="input-icon" size={18} />
                        <input
                            type="email"
                            className="input"
                            placeholder="Email address"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>

                    <div className="input-group">
                        <Lock className="input-icon" size={18} />
                        <input
                            type="password"
                            className="input"
                            placeholder="Password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>

                    <button type="submit" className="btn btn-primary auth-btn" disabled={loading}>
                        {loading ? 'Signing in...' : 'Sign In'}
                        <ArrowRight size={18} />
                    </button>
                </form>

                <p className="auth-footer">
                    Don't have an account? <Link to="/register">Sign up</Link>
                </p>
            </div>
        </div>
    );
};
