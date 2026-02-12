export type ProductType = 'monocrystalline' | 'polycrystalline' | 'thin_film';

export interface Product {
    id: number;
    name: string;
    model_number: string;
    type: ProductType;
    wattage: number;
    efficiency: number;
    length_mm?: number;
    width_mm?: number;
    thickness_mm?: number;
    weight_kg?: number;
    price_inr: number;
    warranty_years: number;
    manufacturer: string;
    manufacturer_country?: string;
    description?: string;
    technical_specifications?: string;
    images?: string[];
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface ProductListResponse {
    products: Product[];
    total: number;
    page: number;
    page_size: number;
}

