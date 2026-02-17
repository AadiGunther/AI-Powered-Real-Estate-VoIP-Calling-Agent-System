import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'

const mockGet = vi.fn()

vi.mock('../../services/api', () => ({
    default: {
        get: mockGet,
        put: vi.fn(),
    },
}))

vi.mock('../../store', () => ({
    useAuthStore: () => ({
        user: { role: 'agent' },
    }),
}))

describe('LeadList', () => {
    beforeEach(() => {
        mockGet.mockReset()
    })

    it('sorts by contact when header is clicked', async () => {
        const leads = [
            {
                id: 1,
                name: 'Bob',
                phone: '222222',
                quality: 'warm',
                status: 'new',
                source: 'website',
                created_at: '2026-01-02T00:00:00.000Z',
            },
            {
                id: 2,
                name: 'Alice',
                phone: '111111',
                quality: 'hot',
                status: 'contacted',
                source: 'referral',
                created_at: '2026-01-01T00:00:00.000Z',
            },
        ]

        mockGet.mockImplementation((url: string) => {
            if (url === '/leads/') {
                return Promise.resolve({
                    data: { leads, total: 2, page: 1, page_size: 50 },
                })
            }
            if (url === '/calls/') {
                return Promise.resolve({
                    data: { calls: [], total: 0, page: 1, page_size: 10 },
                })
            }
            return Promise.resolve({ data: {} })
        })

        const { LeadList } = await import('./LeadList')
        const { container } = render(<LeadList />)

        await screen.findByText('Alice')
        const contactHeader = screen.getByRole('button', { name: /Contact/i })
        fireEvent.click(contactHeader)

        const bodyRows = Array.from(container.querySelectorAll<HTMLTableRowElement>('tbody tr'))
        expect(within(bodyRows[0]).getByText('Alice')).toBeInTheDocument()

        fireEvent.click(contactHeader)
        const bodyRowsAfter = Array.from(container.querySelectorAll<HTMLTableRowElement>('tbody tr'))
        expect(within(bodyRowsAfter[0]).getByText('Bob')).toBeInTheDocument()
    })

    it('loads conversation summary when a lead row is clicked', async () => {
        const leads = [
            {
                id: 1,
                name: 'Alice',
                phone: '111111',
                quality: 'warm',
                status: 'new',
                source: 'website',
                created_at: '2026-01-02T00:00:00.000Z',
            },
            {
                id: 2,
                name: 'Bob',
                phone: '222222',
                quality: 'hot',
                status: 'contacted',
                source: 'referral',
                created_at: '2026-01-03T00:00:00.000Z',
            },
        ]

        mockGet.mockImplementation((url: string, config?: any) => {
            if (url === '/leads/') {
                return Promise.resolve({
                    data: { leads, total: 2, page: 1, page_size: 50 },
                })
            }
            if (url === '/calls/') {
                const leadId = config?.params?.lead_id
                if (leadId === 2) {
                    return Promise.resolve({
                        data: {
                            calls: [
                                {
                                    id: 10,
                                    call_sid: 'CA123',
                                    direction: 'inbound',
                                    from_number: '+100',
                                    to_number: '+200',
                                    status: 'completed',
                                    duration_seconds: 65,
                                    handled_by_ai: true,
                                    escalated_to_human: false,
                                    transcript_summary: 'Point one. Point two.',
                                    created_at: '2026-01-03T10:00:00.000Z',
                                    updated_at: '2026-01-03T10:00:00.000Z',
                                    lead_id: 2,
                                },
                            ],
                            total: 1,
                            page: 1,
                            page_size: 10,
                        },
                    })
                }
                return Promise.resolve({
                    data: { calls: [], total: 0, page: 1, page_size: 10 },
                })
            }
            return Promise.resolve({ data: {} })
        })

        const { LeadList } = await import('./LeadList')
        const { container } = render(<LeadList />)

        await screen.findByText('Bob')
        const bodyRows = Array.from(container.querySelectorAll<HTMLTableRowElement>('tbody tr'))
        const bobRow = bodyRows.find((row) => within(row).queryByText('Bob'))
        expect(bobRow).toBeTruthy()
        fireEvent.click(bobRow as HTMLTableRowElement)

        await screen.findByText(/Bob • 222222/i)
        await screen.findByText('Point one')
        await screen.findByText(/Duration: 1:05/i)
    })
})
