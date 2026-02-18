export interface Call {
    id: number;
    call_sid: string;
    direction: 'inbound' | 'outbound';
    from_number: string;
    to_number: string;
    status: string;
    duration_seconds?: number;
    started_at?: string;
    answered_at?: string;
    ended_at?: string;
    handled_by_ai: boolean;
    escalated_to_human: boolean;
    escalated_to_agent_id?: number;
    escalation_reason?: string;
    recording_url?: string;
    transcript_summary?: string;
    outcome?: string;
    outcome_notes?: string;
    lead_id?: number;
    transcript_id?: string;
    properties_discussed?: string; // JSON string of IDs
    reception_status?: 'received' | 'not_received';
    reception_timestamp?: string;
    caller_username?: string;
    created_at: string;
    updated_at?: string;
    lead_created?: boolean;
    sentiment_score?: number;
    customer_satisfaction?: number;
    structured_report?: string;
}

export interface CallListResponse {
    calls: Call[];
    total: number;
    page: number;
    page_size: number;
}

export interface TranscriptMessage {
    role: 'customer' | 'agent';
    content: string;
    timestamp: string;
}

export interface CallTranscript {
    call_id: number;
    call_sid: string;
    messages: TranscriptMessage[];
    summary?: string;
}
