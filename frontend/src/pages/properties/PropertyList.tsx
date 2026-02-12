import React, { useState, useEffect } from 'react';
import { Search, Filter, Zap, Factory, Gauge, IndianRupee } from 'lucide-react';
import api from '../../services/api';
import type { Product, ProductListResponse } from '../../types/product';
import './Properties.css';

export const PropertyList: React.FC = () => {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [total, setTotal] = useState(0);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchProducts();
    }, []);

    const fetchProducts = async () => {
        try {
            setError(null);
            setLoading(true);
            const response = await api.get<ProductListResponse>('/products/');
            setProducts(response.data.products);
            setTotal(response.data.total);
        } catch (err) {
            setError('Failed to load products. Please try again.');
            setProducts([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    };

    const formatPrice = (price: number) => {
        if (price >= 10000000) return `₹${(price / 10000000).toFixed(2)} Cr`;
        if (price >= 100000) return `₹${(price / 100000).toFixed(2)} L`;
        return `₹${price.toLocaleString()}`;
    };

    const getTypeBadge = (type: string) => {
        const badges: Record<string, string> = {
            monocrystalline: 'badge-success',
            polycrystalline: 'badge-info',
            thin_film: 'badge-warning',
        };
        return badges[type] || 'badge-default';
    };

    const filteredProducts = products.filter((product) => {
        if (!search) return true;
        const term = search.toLowerCase();
        return (
            product.name.toLowerCase().includes(term) ||
            product.model_number.toLowerCase().includes(term) ||
            product.manufacturer.toLowerCase().includes(term)
        );
    });

    return (
        <div className="properties-page">
            <div className="page-header">
                <div>
                    <h1>Solar Panel Inventory</h1>
                    <p>{total} total products</p>
                </div>
            </div>

            <div className="filters-bar">
                <div className="search-box">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search by name, model or manufacturer..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <button className="btn btn-secondary">
                    <Filter size={18} /> Filters
                </button>
            </div>

            {loading && (
                <div className="loading">Loading products...</div>
            )}

            {!loading && error && (
                <div className="error-message">
                    {error}
                </div>
            )}

            {!loading && !error && (
                <div className="properties-grid">
                    {filteredProducts.map((product) => (
                        <div key={product.id} className="property-card">
                            <div className="property-image">
                                <Zap size={48} />
                                <span className={`badge ${getTypeBadge(product.type)}`}>
                                    {product.type.replace('_', ' ')}
                                </span>
                            </div>
                            <div className="property-content">
                                <h3>{product.name}</h3>
                                <p className="property-location">
                                    <Factory size={14} /> {product.manufacturer}
                                    {product.manufacturer_country ? ` • ${product.manufacturer_country}` : ''}
                                </p>
                                <div className="property-specs">
                                    <span>
                                        <Gauge size={14} /> {product.wattage} W
                                    </span>
                                    <span>
                                        <Gauge size={14} /> {product.efficiency.toFixed(1)}% efficiency
                                    </span>
                                </div>
                                <div className="property-price">
                                    <IndianRupee size={18} />
                                    {formatPrice(product.price_inr)}
                                </div>
                                <div className="property-specs">
                                    <span>Warranty: {product.warranty_years} years</span>
                                    <span>Model: {product.model_number}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
