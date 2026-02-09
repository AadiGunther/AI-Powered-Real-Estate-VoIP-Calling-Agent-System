import React, { useState, useEffect } from 'react';
import { Building2, Plus, Search, Filter, MapPin, Bed, Square, IndianRupee } from 'lucide-react';
import api from '../../services/api';
import type { Property, PropertyListResponse } from '../../types/property';
import './Properties.css';

export const PropertyList: React.FC = () => {
    const [properties, setProperties] = useState<Property[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [total, setTotal] = useState(0);

    useEffect(() => {
        fetchProperties();
    }, []);

    const fetchProperties = async () => {
        try {
            const response = await api.get<PropertyListResponse>('/properties/');
            setProperties(response.data.properties);
            setTotal(response.data.total);
        } catch (error) {
            console.error('Failed to fetch properties:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatPrice = (price: number) => {
        if (price >= 10000000) return `₹${(price / 10000000).toFixed(2)} Cr`;
        if (price >= 100000) return `₹${(price / 100000).toFixed(2)} L`;
        return `₹${price.toLocaleString()}`;
    };

    const getStatusBadge = (status: string) => {
        const badges: Record<string, string> = {
            available: 'badge-success',
            sold: 'badge-error',
            reserved: 'badge-warning',
            under_construction: 'badge-info',
        };
        return badges[status] || 'badge-info';
    };

    return (
        <div className="properties-page">
            <div className="page-header">
                <div>
                    <h1>Properties</h1>
                    <p>{total} total properties</p>
                </div>
                {/* <button className="btn btn-primary">
                    <Plus size={18} /> Add Property
                </button> */}
            </div>

            <div className="filters-bar">
                <div className="search-box">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search properties..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <button className="btn btn-secondary">
                    <Filter size={18} /> Filters
                </button>
            </div>

            {loading ? (
                <div className="loading">Loading properties...</div>
            ) : (
                <div className="properties-grid">
                    {properties.map((property) => (
                        <div key={property.id} className="property-card">
                            <div className="property-image">
                                <Building2 size={48} />
                                <span className={`badge ${getStatusBadge(property.status)}`}>
                                    {property.status.replace('_', ' ')}
                                </span>
                            </div>
                            <div className="property-content">
                                <h3>{property.title}</h3>
                                <p className="property-location">
                                    <MapPin size={14} /> {property.locality || property.city}, {property.state}
                                </p>
                                <div className="property-specs">
                                    {property.bedrooms && (
                                        <span><Bed size={14} /> {property.bedrooms} BHK</span>
                                    )}
                                    <span><Square size={14} /> {property.size_sqft} sq.ft</span>
                                </div>
                                <div className="property-price">
                                    <IndianRupee size={18} />
                                    {formatPrice(property.price)}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
