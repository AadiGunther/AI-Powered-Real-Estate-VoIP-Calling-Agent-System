export interface Property {
    id: number;
    title: string;
    description?: string;
    property_type: 'apartment' | 'villa' | 'plot' | 'commercial' | 'office';
    address: string;
    city: string;
    state: string;
    pincode: string;
    locality?: string;
    price: number;
    size_sqft: number;
    bedrooms?: number;
    bathrooms?: number;
    status: 'available' | 'sold' | 'reserved' | 'under_construction';
    is_featured: boolean;
    created_at: string;
}

export interface PropertyListResponse {
    properties: Property[];
    total: number;
    page: number;
    page_size: number;
}
