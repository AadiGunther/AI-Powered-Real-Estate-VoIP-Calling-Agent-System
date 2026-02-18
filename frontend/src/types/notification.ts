export type NotificationType =
    | 'lead_created'
    | 'lead_assigned'
    | 'lead_status_changed'
    | 'product_created'
    | 'product_updated'
    | 'product_deleted'
    | 'appointment_booked'
    | 'call_report_generated';

export interface Notification {
    id: number;
    user_id: number;
    message: string;
    type: NotificationType;
    is_read: boolean;
    related_lead_id?: number | null;
    related_call_id?: number | null;
    created_at: string;
}

export interface NotificationPreferenceItem {
    notification_type: NotificationType;
    enabled: boolean;
}

export interface NotificationPreferencesResponse {
    items: NotificationPreferenceItem[];
}

export interface NotificationListResponse {
    notifications: Notification[];
    total: number;
    page: number;
    page_size: number;
}
