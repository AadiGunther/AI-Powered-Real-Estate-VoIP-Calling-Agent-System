import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Filter, Search, X, Save, RefreshCw } from 'lucide-react';
import api from '../../services/api';
import { useAuthStore } from '../../store';
import '../properties/Properties.css';
import '../../components/OutboundCallModal.css';

type AppointmentStatus = 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show';

interface Appointment {
    id: number;
    call_id: number;
    lead_id: number;
    scheduled_for: string;
    address: string;
    notes?: string | null;
    status: AppointmentStatus | string;
    client_name?: string | null;
    service_type?: string;
    duration_minutes?: number;
    assigned_staff_id?: number | null;
    assigned_staff_name?: string | null;
    contact_phone?: string | null;
    contact_email?: string | null;
    created_at: string;
    updated_at: string;
}

interface AppointmentListResponse {
    appointments: Appointment[];
    total: number;
    page: number;
    page_size: number;
}

interface StaffUser {
    id: number;
    full_name: string;
    email: string;
}

const toLocalDateInput = (iso: string): string => {
    try {
        const d = new Date(iso);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    } catch {
        return '';
    }
};

const toLocalTimeInput = (iso: string): string => {
    try {
        const d = new Date(iso);
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        return `${hh}:${mm}`;
    } catch {
        return '';
    }
};

const combineLocalDateTimeToIso = (date: string, time: string): string => {
    const iso = new Date(`${date}T${time}:00`).toISOString();
    return iso;
};

export const Appointments: React.FC = () => {
    const { user } = useAuthStore();
    const isAdmin = user?.role === 'admin';
    const isManager = user?.role === 'manager';

    const [appointments, setAppointments] = useState<Appointment[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [total, setTotal] = useState(0);

    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [staffFilter, setStaffFilter] = useState<number | ''>('');
    const [dateFrom, setDateFrom] = useState<string>('');
    const [dateTo, setDateTo] = useState<string>('');

    const [sortBy, setSortBy] = useState<'scheduled_for' | 'client_name' | 'status' | 'staff' | 'created_at'>('scheduled_for');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

    const [staffOptions, setStaffOptions] = useState<StaffUser[]>([]);

    const [activeAppointment, setActiveAppointment] = useState<Appointment | null>(null);
    const [editOpen, setEditOpen] = useState(false);
    const [editing, setEditing] = useState(false);

    const [editDate, setEditDate] = useState('');
    const [editTime, setEditTime] = useState('');
    const [editAddress, setEditAddress] = useState('');
    const [editNotes, setEditNotes] = useState('');
    const [editStatus, setEditStatus] = useState<AppointmentStatus>('scheduled');
    const [editAssignedStaffId, setEditAssignedStaffId] = useState<number | ''>('');

    const canReassignStaff = isAdmin || isManager;

    const fetchAppointments = async () => {
        try {
            setLoading(true);
            setError(null);
            const params: Record<string, any> = {
                page: 1,
                page_size: 50,
                sort_by: sortBy,
                sort_order: sortOrder,
            };
            if (search.trim()) params.search = search.trim();
            if (statusFilter) params.status = statusFilter;
            if (staffFilter !== '') params.staff_id = staffFilter;
            if (dateFrom) params.date_from = new Date(`${dateFrom}T00:00:00`).toISOString();
            if (dateTo) params.date_to = new Date(`${dateTo}T23:59:59`).toISOString();

            const response = await api.get<AppointmentListResponse>('/appointments', { params });
            setAppointments(response.data.appointments || []);
            setTotal(response.data.total || 0);
        } catch (err: any) {
            const message = err?.response?.data?.detail || 'Failed to load appointments. Please try again.';
            setError(message);
            setAppointments([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAppointments();
    }, [statusFilter, staffFilter, dateFrom, dateTo, sortBy, sortOrder]);

    useEffect(() => {
        if (!canReassignStaff) return;
        const fetchStaff = async () => {
            try {
                const response = await api.get('/admin/users', {
                    params: { role: 'agent', is_active: true, page: 1, page_size: 200 },
                });
                setStaffOptions(response.data.users || []);
            } catch {
                setStaffOptions([]);
            }
        };
        fetchStaff();
    }, [canReassignStaff]);

    const statusBadgeClass = (statusValue: string) => {
        const value = statusValue.toLowerCase();
        if (value === 'completed') return 'badge-success';
        if (value === 'confirmed') return 'badge-info';
        if (value === 'scheduled') return 'badge-warning';
        if (value === 'cancelled' || value === 'no_show') return 'badge-error';
        return 'badge-default';
    };

    const openEdit = (appt: Appointment) => {
        setActiveAppointment(appt);
        setEditDate(toLocalDateInput(appt.scheduled_for));
        setEditTime(toLocalTimeInput(appt.scheduled_for));
        setEditAddress(appt.address || '');
        setEditNotes(appt.notes || '');
        setEditStatus((appt.status as AppointmentStatus) || 'scheduled');
        setEditAssignedStaffId(appt.assigned_staff_id ?? '');
        setEditOpen(true);
    };

    const closeEdit = () => {
        setEditOpen(false);
        setActiveAppointment(null);
    };

    const handleSave = async () => {
        if (!activeAppointment) return;
        try {
            setEditing(true);
            setError(null);
            const payload: Record<string, any> = {
                scheduled_for: combineLocalDateTimeToIso(editDate, editTime),
                address: editAddress,
                notes: editNotes || null,
                status: editStatus,
            };
            if (canReassignStaff) {
                payload.assigned_staff_id = editAssignedStaffId === '' ? null : editAssignedStaffId;
            }
            await api.put(`/appointments/${activeAppointment.id}`, payload);
            await fetchAppointments();
            closeEdit();
        } catch (err: any) {
            const message = err?.response?.data?.detail || 'Failed to update appointment. Please try again.';
            setError(message);
        } finally {
            setEditing(false);
        }
    };

    const handleCancel = async (apptId: number) => {
        try {
            setError(null);
            await api.post(`/appointments/${apptId}/cancel`);
            await fetchAppointments();
        } catch (err: any) {
            const message = err?.response?.data?.detail || 'Failed to cancel appointment. Please try again.';
            setError(message);
        }
    };

    const sortLabel = useMemo(() => {
        const labels: Record<string, string> = {
            scheduled_for: 'Date/Time',
            client_name: 'Client',
            status: 'Status',
            staff: 'Staff',
            created_at: 'Created',
        };
        return labels[sortBy] || 'Date/Time';
    }, [sortBy]);

    return (
        <div className="appointments-page">
            <div className="page-header">
                <div>
                    <h1>Appointments</h1>
                    <p>{total} total appointments</p>
                </div>
            </div>

            <div className="filters-bar">
                <div className="search-box">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search by client, phone, email, address..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') fetchAppointments();
                        }}
                    />
                </div>
                <input
                    className="input"
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    style={{ maxWidth: 170 }}
                    aria-label="From date"
                />
                <input
                    className="input"
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    style={{ maxWidth: 170 }}
                    aria-label="To date"
                />
                <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                    <option value="">All statuses</option>
                    <option value="scheduled">Scheduled</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                </select>

                {canReassignStaff && (
                    <select
                        className="select"
                        value={staffFilter === '' ? '' : staffFilter}
                        onChange={(e) => setStaffFilter(e.target.value ? Number(e.target.value) : '')}
                    >
                        <option value="">All staff</option>
                        {staffOptions.map((staff) => (
                            <option key={staff.id} value={staff.id}>
                                {staff.full_name} ({staff.email})
                            </option>
                        ))}
                    </select>
                )}

                <select className="select" value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
                    <option value="scheduled_for">Sort: Date/Time</option>
                    <option value="client_name">Sort: Client</option>
                    <option value="status">Sort: Status</option>
                    <option value="staff">Sort: Staff</option>
                    <option value="created_at">Sort: Created</option>
                </select>
                <button
                    className="btn btn-secondary"
                    onClick={() => setSortOrder((v) => (v === 'asc' ? 'desc' : 'asc'))}
                    aria-label="Toggle sort order"
                >
                    <CalendarDays size={18} /> {sortLabel} {sortOrder === 'asc' ? '↑' : '↓'}
                </button>

                <button className="btn btn-secondary" onClick={fetchAppointments}>
                    <Filter size={18} /> Apply
                </button>
            </div>

            {loading && <div className="loading">Loading appointments...</div>}
            {!loading && error && <div className="error-message">{error}</div>}

            {!loading && !error && (
                <div className="card">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Time</th>
                                <th>Client</th>
                                <th>Service</th>
                                <th>Status</th>
                                <th>Duration</th>
                                <th>Staff</th>
                                <th>Contact</th>
                                <th>Notes</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {appointments.map((appt) => (
                                <tr key={appt.id} onClick={() => openEdit(appt)} style={{ cursor: 'pointer' }}>
                                    <td>{new Date(appt.scheduled_for).toLocaleDateString()}</td>
                                    <td>{new Date(appt.scheduled_for).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                                    <td>{appt.client_name || `Lead #${appt.lead_id}`}</td>
                                    <td>{appt.service_type || 'Site Visit'}</td>
                                    <td>
                                        <span className={`badge ${statusBadgeClass(appt.status)}`}>
                                            {String(appt.status).replace('_', ' ')}
                                        </span>
                                    </td>
                                    <td>{appt.duration_minutes || 60} min</td>
                                    <td>{appt.assigned_staff_name || (appt.assigned_staff_id ? `Staff #${appt.assigned_staff_id}` : '-')}</td>
                                    <td>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                            <span>{appt.contact_phone || '-'}</span>
                                            <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                                                {appt.contact_email || ''}
                                            </span>
                                        </div>
                                    </td>
                                    <td>
                                        <div className="lead-summary" title={appt.notes || ''}>
                                            {appt.notes ? (appt.notes.length > 40 ? `${appt.notes.substring(0, 40)}...` : appt.notes) : <span className="text-muted">-</span>}
                                        </div>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                            <button
                                                className="btn btn-secondary"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    openEdit(appt);
                                                }}
                                            >
                                                Edit
                                            </button>
                                            <button
                                                className="btn btn-ghost"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    fetchAppointments();
                                                }}
                                                aria-label="Refresh list"
                                            >
                                                <RefreshCw size={16} />
                                            </button>
                                            <button
                                                className="btn btn-secondary"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleCancel(appt.id);
                                                }}
                                                disabled={String(appt.status).toLowerCase() === 'cancelled'}
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {appointments.length === 0 && (
                                <tr>
                                    <td colSpan={10} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                                        No appointments found
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {editOpen && activeAppointment && (
                <div className="modal-overlay" role="dialog" aria-modal="true">
                    <div className="modal-content">
                        <div className="modal-header">
                            <h2><CalendarDays size={20} /> Edit Appointment</h2>
                            <button className="close-btn" onClick={closeEdit}>
                                <X size={20} />
                            </button>
                        </div>

                        <div className="modal-body">
                            <div className="form-group">
                                <label>Date</label>
                                <input type="date" value={editDate} onChange={(e) => setEditDate(e.target.value)} required />
                            </div>
                            <div className="form-group">
                                <label>Time</label>
                                <input type="time" value={editTime} onChange={(e) => setEditTime(e.target.value)} required />
                            </div>
                            <div className="form-group">
                                <label>Address</label>
                                <input value={editAddress} onChange={(e) => setEditAddress(e.target.value)} required />
                            </div>
                            <div className="form-group">
                                <label>Status</label>
                                <select className="select" value={editStatus} onChange={(e) => setEditStatus(e.target.value as AppointmentStatus)}>
                                    <option value="scheduled">Scheduled</option>
                                    <option value="confirmed">Confirmed</option>
                                    <option value="completed">Completed</option>
                                    <option value="cancelled">Cancelled</option>
                                </select>
                            </div>
                            {canReassignStaff && (
                                <div className="form-group">
                                    <label>Assigned Staff</label>
                                    <select
                                        className="select"
                                        value={editAssignedStaffId === '' ? '' : editAssignedStaffId}
                                        onChange={(e) => setEditAssignedStaffId(e.target.value ? Number(e.target.value) : '')}
                                    >
                                        <option value="">Unassigned</option>
                                        {staffOptions.map((staff) => (
                                            <option key={staff.id} value={staff.id}>
                                                {staff.full_name} ({staff.email})
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            )}
                            <div className="form-group">
                                <label>Notes / Requirements</label>
                                <input value={editNotes} onChange={(e) => setEditNotes(e.target.value)} />
                            </div>
                        </div>

                        <div className="modal-footer">
                            <button type="button" className="btn btn-secondary" onClick={closeEdit} disabled={editing}>
                                Close
                            </button>
                            <button
                                type="button"
                                className="btn btn-primary"
                                onClick={handleSave}
                                disabled={editing || !editDate || !editTime || !editAddress}
                            >
                                <Save size={16} /> {editing ? 'Saving...' : 'Save'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
