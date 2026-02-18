import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Edit2, Save, X, UploadCloud } from 'lucide-react';
import api from '../../services/api';
import type { Product, ProductListResponse, ProductType } from '../../types/product';
import './ProductAdmin.css';

type FormMode = 'create' | 'edit';

const emptyProductForm: Omit<Product, 'id' | 'is_active' | 'created_at' | 'updated_at'> = {
    name: '',
    model_number: '',
    type: 'monocrystalline',
    wattage: 400,
    efficiency: 20,
    length_mm: undefined,
    width_mm: undefined,
    thickness_mm: undefined,
    weight_kg: undefined,
    price_inr: 10000,
    warranty_years: 25,
    manufacturer: '',
    manufacturer_country: '',
    description: '',
    technical_specifications: '',
    images: [],
};

export const ProductAdmin: React.FC = () => {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const [formMode, setFormMode] = useState<FormMode>('create');
    const [editingId, setEditingId] = useState<number | null>(null);
    const [form, setForm] = useState<typeof emptyProductForm>(emptyProductForm);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [imageUploading, setImageUploading] = useState(false);

    useEffect(() => {
        loadProducts();
    }, []);

    const loadProducts = async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await api.get<ProductListResponse>('/products/');
            setProducts(response.data.products);
        } catch (err: any) {
            setError('Failed to load products');
        } finally {
            setLoading(false);
        }
    };

    const resetForm = () => {
        setForm(emptyProductForm);
        setFormErrors({});
        setFormMode('create');
        setEditingId(null);
    };

    const validateForm = () => {
        const errors: Record<string, string> = {};

        if (!form.name.trim()) errors.name = 'Product name is required';
        if (!form.model_number.trim()) errors.model_number = 'Model number is required';
        if (!form.manufacturer.trim()) errors.manufacturer = 'Manufacturer is required';
        if (!form.wattage || form.wattage <= 0) errors.wattage = 'Wattage must be positive';
        if (!form.efficiency || form.efficiency <= 0) errors.efficiency = 'Efficiency must be positive';
        if (!form.price_inr || form.price_inr <= 0) errors.price_inr = 'Price must be positive';
        if (!form.warranty_years || form.warranty_years <= 0) errors.warranty_years = 'Warranty must be positive';

        setFormErrors(errors);
        return Object.keys(errors).length === 0;
    };

    const handleChange = (field: keyof typeof form, value: any) => {
        setForm((prev) => ({ ...prev, [field]: value }));
        setFormErrors((prev) => ({ ...prev, [field]: '' }));
    };

    const handleNumberChange = (field: keyof typeof form, value: string) => {
        if (!value) {
            handleChange(field, undefined);
            return;
        }
        const num = Number(value);
        handleChange(field, Number.isNaN(num) ? undefined : num);
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        setSuccess(null);
        if (!validateForm()) return;

        try {
            setError(null);
            if (formMode === 'create') {
                await api.post('/products/', {
                    ...form,
                });
                setSuccess('Product created successfully');
            } else if (formMode === 'edit' && editingId !== null) {
                await api.put(`/products/${editingId}`, {
                    ...form,
                });
                setSuccess('Product updated successfully');
            }
            await loadProducts();
            resetForm();
        } catch (err: any) {
            const message =
                err?.response?.data?.detail ||
                'Failed to save product. Please check the fields and try again.';
            setError(message);
        }
    };

    const handleEdit = (product: Product) => {
        setForm({
            name: product.name,
            model_number: product.model_number,
            type: product.type,
            wattage: product.wattage,
            efficiency: product.efficiency,
            length_mm: product.length_mm,
            width_mm: product.width_mm,
            thickness_mm: product.thickness_mm,
            weight_kg: product.weight_kg,
            price_inr: product.price_inr,
            warranty_years: product.warranty_years,
            manufacturer: product.manufacturer,
            manufacturer_country: product.manufacturer_country || '',
            description: product.description || '',
            technical_specifications: product.technical_specifications || '',
            images: product.images || [],
        });
        setFormMode('edit');
        setEditingId(product.id);
        setFormErrors({});
        setSuccess(null);
        setError(null);
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm('Are you sure you want to delete this product?')) return;
        try {
            setError(null);
            await api.delete(`/products/${id}`);
            setSuccess('Product deleted successfully');
            if (editingId === id) {
                resetForm();
            }
            await loadProducts();
        } catch (err: any) {
            const message =
                err?.response?.data?.detail ||
                'Failed to delete product. Please try again.';
            setError(message);
        }
    };

    const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setImageUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await api.post('/products/upload-image', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            const url = response.data.url as string;
            setForm((prev) => ({
                ...prev,
                images: [...(prev.images || []), url],
            }));
            setSuccess('Image uploaded successfully');
        } catch (err: any) {
            const message =
                err?.response?.data?.detail ||
                'Failed to upload image. Please try again.';
            setError(message);
        } finally {
            setImageUploading(false);
        }
    };

    return (
        <div className="admin-page">
            <div className="page-header">
                <div>
                    <h1>Solar Products Admin</h1>
                    <p>Manage solar panel inventory, pricing and specifications</p>
                </div>
            </div>

            {error && (
                <div className="error-message">
                    {error}
                </div>
            )}

            {success && (
                <div className="success-message">
                    {success}
                </div>
            )}

            <div className="product-admin-layout">
                <div className="product-form-card">
                    <div className="card-header">
                        <h2>{formMode === 'create' ? 'Add New Product' : 'Edit Product'}</h2>
                        {formMode === 'edit' && (
                            <button className="btn btn-secondary btn-sm" onClick={resetForm}>
                                <X size={14} /> Cancel Edit
                            </button>
                        )}
                    </div>
                    <form onSubmit={handleSubmit} className="product-form">
                        <div className="form-row">
                            <div className="form-group">
                                <label>Product Name</label>
                                <input
                                    type="text"
                                    value={form.name}
                                    onChange={(e) => handleChange('name', e.target.value)}
                                />
                                {formErrors.name && <span className="field-error">{formErrors.name}</span>}
                            </div>
                            <div className="form-group">
                                <label>Model Number</label>
                                <input
                                    type="text"
                                    value={form.model_number}
                                    onChange={(e) => handleChange('model_number', e.target.value)}
                                />
                                {formErrors.model_number && <span className="field-error">{formErrors.model_number}</span>}
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Panel Type</label>
                                <select
                                    value={form.type}
                                    onChange={(e) => handleChange('type', e.target.value as ProductType)}
                                >
                                    <option value="monocrystalline">Monocrystalline</option>
                                    <option value="polycrystalline">Polycrystalline</option>
                                    <option value="thin_film">Thin-film</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Wattage (W)</label>
                                <input
                                    type="number"
                                    value={form.wattage ?? ''}
                                    onChange={(e) => handleNumberChange('wattage', e.target.value)}
                                />
                                {formErrors.wattage && <span className="field-error">{formErrors.wattage}</span>}
                            </div>
                            <div className="form-group">
                                <label>Efficiency (%)</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={form.efficiency ?? ''}
                                    onChange={(e) => handleNumberChange('efficiency', e.target.value)}
                                />
                                {formErrors.efficiency && <span className="field-error">{formErrors.efficiency}</span>}
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Length (mm)</label>
                                <input
                                    type="number"
                                    value={form.length_mm ?? ''}
                                    onChange={(e) => handleNumberChange('length_mm', e.target.value)}
                                />
                            </div>
                            <div className="form-group">
                                <label>Width (mm)</label>
                                <input
                                    type="number"
                                    value={form.width_mm ?? ''}
                                    onChange={(e) => handleNumberChange('width_mm', e.target.value)}
                                />
                            </div>
                            <div className="form-group">
                                <label>Thickness (mm)</label>
                                <input
                                    type="number"
                                    value={form.thickness_mm ?? ''}
                                    onChange={(e) => handleNumberChange('thickness_mm', e.target.value)}
                                />
                            </div>
                            <div className="form-group">
                                <label>Weight (kg)</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={form.weight_kg ?? ''}
                                    onChange={(e) => handleNumberChange('weight_kg', e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Price (₹)</label>
                                <input
                                    type="number"
                                    value={form.price_inr ?? ''}
                                    onChange={(e) => handleNumberChange('price_inr', e.target.value)}
                                />
                                {formErrors.price_inr && <span className="field-error">{formErrors.price_inr}</span>}
                            </div>
                            <div className="form-group">
                                <label>Warranty (years)</label>
                                <input
                                    type="number"
                                    value={form.warranty_years ?? ''}
                                    onChange={(e) => handleNumberChange('warranty_years', e.target.value)}
                                />
                                {formErrors.warranty_years && <span className="field-error">{formErrors.warranty_years}</span>}
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Manufacturer</label>
                                <input
                                    type="text"
                                    value={form.manufacturer}
                                    onChange={(e) => handleChange('manufacturer', e.target.value)}
                                />
                                {formErrors.manufacturer && <span className="field-error">{formErrors.manufacturer}</span>}
                            </div>
                            <div className="form-group">
                                <label>Manufacturer Country</label>
                                <input
                                    type="text"
                                    value={form.manufacturer_country || ''}
                                    onChange={(e) => handleChange('manufacturer_country', e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label>Description</label>
                            <textarea
                                rows={3}
                                value={form.description || ''}
                                onChange={(e) => handleChange('description', e.target.value)}
                            />
                        </div>

                        <div className="form-group">
                            <label>Technical Specifications</label>
                            <textarea
                                rows={4}
                                value={form.technical_specifications || ''}
                                onChange={(e) => handleChange('technical_specifications', e.target.value)}
                            />
                        </div>

                        <div className="form-group">
                            <label>Product Images</label>
                            <div className="image-upload-row">
                                <label className="btn btn-secondary btn-sm upload-btn">
                                    <UploadCloud size={16} />
                                    <span>{imageUploading ? 'Uploading...' : 'Upload Image'}</span>
                                    <input
                                        type="file"
                                        accept="image/*"
                                        onChange={handleImageUpload}
                                        disabled={imageUploading}
                                    />
                                </label>
                                {form.images && form.images.length > 0 && (
                                    <div className="image-list">
                                        {form.images.map((url) => (
                                            <span key={url} className="image-pill">
                                                {url}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="form-actions">
                            <button type="submit" className="btn btn-primary">
                                {formMode === 'create' ? (
                                    <>
                                        <Plus size={16} /> Add Product
                                    </>
                                ) : (
                                    <>
                                        <Save size={16} /> Save Changes
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                </div>

                <div className="product-list-card">
                    <div className="card-header">
                        <h2>Existing Products</h2>
                    </div>

                    {loading ? (
                        <div className="loading">Loading products...</div>
                    ) : (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Model</th>
                                    <th>Type</th>
                                    <th>Wattage</th>
                                    <th>Efficiency</th>
                                    <th>Price</th>
                                    <th>Warranty</th>
                                    <th>Manufacturer</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {products.map((product) => (
                                    <tr
                                        key={product.id}
                                        onClick={() => handleEdit(product)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <td>{product.name}</td>
                                        <td>{product.model_number}</td>
                                        <td>{product.type.replace('_', ' ')}</td>
                                        <td>{product.wattage} W</td>
                                        <td>{product.efficiency.toFixed(1)}%</td>
                                        <td>₹{product.price_inr.toLocaleString()}</td>
                                        <td>{product.warranty_years} years</td>
                                        <td>{product.manufacturer}</td>
                                        <td>
                                            <button
                                                className="btn btn-secondary btn-icon"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleEdit(product);
                                                }}
                                            >
                                                <Edit2 size={14} />
                                            </button>
                                            <button
                                                className="btn btn-danger btn-icon"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleDelete(product.id);
                                                }}
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
};
