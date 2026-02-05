export interface Lead {
    id: number;
    name?: string;
    phone: string;
    email?: string;
    quality: 'hot' | 'warm' | 'cold';
    status: 'new' | 'contacted' | 'qualified' | 'negotiating' | 'converted' | 'lost';
    source: string;
    preferred_location?: string;
    budget_min?: number;
    budget_max?: number;
    assigned_agent_id?: number;
    next_follow_up?: string;
    created_at: string;
}

export interface LeadListResponse {
    leads: Lead[];
    total: number;
    page: number;
    page_size: number;
}
