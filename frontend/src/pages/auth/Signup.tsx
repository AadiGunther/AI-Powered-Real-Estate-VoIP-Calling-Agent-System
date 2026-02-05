import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, User, Phone, ArrowRight, Building2 } from 'lucide-react';
import { authService } from '../../services/authService';
import toast from 'react-hot-toast';
import './Auth.css';

export const Signup: React.FC = () => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        full_name: '',
        phone: ''
    });
    const [loading, setLoading] = useState(false);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            // 1. Register
            await authService.register(formData);
            toast.success('Account created successfully! Please sign in.');

            // 2. Redirect to login
            navigate('/login');

            // Optional: Auto-login could be implemented here if the backend returned a token on register
            // or if we called login immediately after register.
        } catch (error: any) {
            toast.error(error.response?.data?.detail || 'Registration failed');
            console.error(error);
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
                <h1 className="auth-title">Create Account</h1>
                <p className="auth-subtitle">Join us to manage your real estate calls</p>

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="input-group">
                        <User className="input-icon" size={18} />
                        <input
                            type="text"
                            name="full_name"
                            className="input"
                            placeholder="Full Name"
                            value={formData.full_name}
                            onChange={handleChange}
                            required
                        />
                    </div>

                    <div className="input-group">
                        <Mail className="input-icon" size={18} />
                        <input
                            type="email"
                            name="email"
                            className="input"
                            placeholder="Email address"
                            value={formData.email}
                            onChange={handleChange}
                            required
                        />
                    </div>

                    <div className="input-group">
                        <Phone className="input-icon" size={18} />
                        <input
                            type="tel"
                            name="phone"
                            className="input"
                            placeholder="Phone Number (Optional)"
                            value={formData.phone}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="input-group">
                        <Lock className="input-icon" size={18} />
                        <input
                            type="password"
                            name="password"
                            className="input"
                            placeholder="Password"
                            value={formData.password}
                            onChange={handleChange}
                            required
                            minLength={6}
                        />
                    </div>

                    <button type="submit" className="btn btn-primary auth-btn" disabled={loading}>
                        {loading ? 'Creating Account...' : 'Sign Up'}
                        <ArrowRight size={18} />
                    </button>
                </form>

                <p className="auth-footer">
                    Already have an account? <Link to="/login">Sign in</Link>
                </p>
            </div>
        </div>
    );
};
