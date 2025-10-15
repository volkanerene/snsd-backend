# Frontend Entegrasyon Rehberi

Bu dokümanda frontend projenize SnSD Backend'i entegre etmek için gereken tüm TypeScript tipleri, API client'ları ve hook'ları bulacaksınız.

## İçindekiler

1. [Kurulum](#kurulum)
2. [TypeScript Tipleri](#typescript-tipleri)
3. [API Client](#api-client)
4. [React Hooks](#react-hooks)
5. [Örnek Kullanımlar](#örnek-kullanımlar)

---

## Kurulum

```bash
npm install @supabase/supabase-js
# veya
yarn add @supabase/supabase-js
```

---

## TypeScript Tipleri

Aşağıdaki tipleri projenize kopyalayın: `src/types/api.ts`

```typescript
// src/types/api.ts

// ========================================
// Common Types
// ========================================

export type UUID = string
export type Timestamp = string // ISO 8601 format
export type JsonObject = Record<string, any>

// ========================================
// Tenant Types
// ========================================

export type LicensePlan = 'basic' | 'professional' | 'enterprise'
export type TenantStatus = 'active' | 'inactive' | 'suspended'

export interface Tenant {
  id: UUID
  name: string
  slug: string
  logo_url: string | null
  subdomain: string
  license_plan: LicensePlan
  modules_enabled: string[]
  max_users: number
  max_contractors: number
  max_video_requests_monthly: number
  settings: JsonObject
  contact_email: string
  contact_phone: string | null
  address: string | null
  status: TenantStatus
  trial_ends_at: Timestamp | null
  subscription_ends_at: Timestamp | null
  created_at: Timestamp
  updated_at: Timestamp
  created_by: UUID | null
}

export interface TenantCreate {
  name: string
  slug: string
  subdomain: string
  license_plan: LicensePlan
  contact_email: string
  logo_url?: string
  modules_enabled?: string[]
  max_users?: number
  max_contractors?: number
  max_video_requests_monthly?: number
  settings?: JsonObject
}

export interface TenantUpdate extends Partial<TenantCreate> {
  status?: TenantStatus
  trial_ends_at?: Timestamp | null
  subscription_ends_at?: Timestamp | null
}

// ========================================
// Role Types
// ========================================

export interface Role {
  id: number
  name: string
  slug: string
  description: string | null
  level: number
  permissions: string[]
  created_at: Timestamp
  updated_at: Timestamp
}

// ========================================
// Profile Types
// ========================================

export interface NotificationPreferences {
  email: boolean
  sms: boolean
  push: boolean
}

export interface Profile {
  id: UUID
  tenant_id: UUID
  full_name: string
  username: string
  avatar_url: string | null
  phone: string | null
  locale: string
  timezone: string
  role_id: number
  contractor_id: UUID | null
  department: string | null
  job_title: string | null
  notification_preferences: NotificationPreferences
  is_active: boolean
  last_login_at: Timestamp | null
  created_at: Timestamp
  updated_at: Timestamp
}

export interface ProfileUpdate {
  full_name?: string
  phone?: string
  avatar_url?: string
  metadata?: JsonObject
}

// ========================================
// Contractor Types
// ========================================

export type ContractorStatus = 'active' | 'inactive' | 'blacklisted'
export type RiskLevel = 'green' | 'yellow' | 'red'

export interface Contractor {
  id: UUID
  tenant_id: UUID
  name: string
  legal_name: string
  tax_number: string
  trade_registry_number: string | null
  contact_person: string
  contact_email: string
  contact_phone: string
  address: string | null
  city: string
  country: string
  documents: JsonObject[]
  status: ContractorStatus
  risk_level: RiskLevel | null
  last_evaluation_score: number | null
  last_evaluation_date: Timestamp | null
  metadata: JsonObject
  created_at: Timestamp
  updated_at: Timestamp
  created_by: UUID | null
}

export interface ContractorCreate {
  name: string
  legal_name: string
  tax_number: string
  contact_person: string
  contact_email: string
  contact_phone: string
  city: string
  country?: string
  trade_registry_number?: string
  address?: string
  documents?: JsonObject[]
  status?: ContractorStatus
  metadata?: JsonObject
}

export interface ContractorUpdate extends Partial<ContractorCreate> {
  risk_level?: RiskLevel
  last_evaluation_score?: number
  last_evaluation_date?: Timestamp
}

// ========================================
// FRM-32 Question Types
// ========================================

export type QuestionType = 'yes_no' | 'number' | 'multiple_choice' | 'text' | 'file_upload'

export interface FRM32Question {
  id: UUID
  question_code: string
  question_text_tr: string
  question_text_en: string | null
  k2_category: string
  k2_weight: number
  question_type: QuestionType
  options: string[] | null
  scoring_rules: JsonObject
  max_score: number
  is_required: boolean
  is_active: boolean
  position: number
  created_at: Timestamp
  updated_at: Timestamp
}

// ========================================
// FRM-32 Submission Types
// ========================================

export type SubmissionStatus = 'draft' | 'submitted' | 'in_review' | 'completed' | 'rejected'
export type EvaluationType = 'periodic' | 'incident' | 'audit'

export interface FRM32Submission {
  id: UUID
  tenant_id: UUID
  contractor_id: UUID
  evaluation_period: string
  evaluation_type: EvaluationType
  status: SubmissionStatus
  progress_percentage: number
  submitted_at: Timestamp | null
  completed_at: Timestamp | null
  final_score: number | null
  risk_classification: RiskLevel | null
  ai_summary: string | null
  attachments: JsonObject[]
  notes: string | null
  metadata: JsonObject
  created_at: Timestamp
  updated_at: Timestamp
  created_by: UUID | null
  reviewed_by: UUID | null
}

export interface FRM32SubmissionCreate {
  contractor_id: UUID
  evaluation_period: string
  evaluation_type?: EvaluationType
  status?: SubmissionStatus
}

export interface FRM32SubmissionUpdate {
  progress_percentage?: number
  notes?: string
  status?: SubmissionStatus
  final_score?: number
  risk_classification?: RiskLevel
  ai_summary?: string
  reviewed_by?: UUID
}

// ========================================
// FRM-32 Answer Types
// ========================================

export interface FRM32Answer {
  id: UUID
  submission_id: UUID
  question_id: UUID
  answer_value: any
  score: number | null
  attachments: JsonObject[] | null
  notes: string | null
  created_at: Timestamp
  updated_at: Timestamp
}

export interface FRM32AnswerCreate {
  submission_id: UUID
  question_id: UUID
  answer_value: any
  attachments?: JsonObject[]
  notes?: string
}

// ========================================
// Payment Types
// ========================================

export type PaymentStatus = 'pending' | 'completed' | 'failed' | 'refunded'
export type PaymentMethod = 'credit_card' | 'bank_transfer' | 'paypal' | 'wire_transfer'
export type PaymentProvider = 'stripe' | 'paytr' | 'iyzico' | 'bank'
export type SubscriptionPeriod = 'monthly' | 'yearly'

export interface Payment {
  id: UUID
  tenant_id: UUID
  amount: number
  currency: string
  payment_method: PaymentMethod
  provider: PaymentProvider | null
  provider_transaction_id: string | null
  provider_response: JsonObject | null
  status: PaymentStatus
  subscription_period: SubscriptionPeriod | null
  subscription_starts_at: Timestamp | null
  subscription_ends_at: Timestamp | null
  invoice_number: string | null
  invoice_url: string | null
  metadata: JsonObject
  created_at: Timestamp
  updated_at: Timestamp
  created_by: UUID | null
}

export interface PaymentCreate {
  amount: number
  currency?: string
  payment_method: PaymentMethod
  provider?: PaymentProvider
  subscription_period?: SubscriptionPeriod
  subscription_starts_at?: Timestamp
  subscription_ends_at?: Timestamp
}

// ========================================
// API Response Types
// ========================================

export interface ApiError {
  detail: string
}

export interface PaginationParams {
  limit?: number
  offset?: number
}

export interface ContractorFilters extends PaginationParams {
  status?: ContractorStatus
}

export interface SubmissionFilters extends PaginationParams {
  status?: SubmissionStatus
  contractor_id?: UUID
}

export interface PaymentFilters extends PaginationParams {
  status?: PaymentStatus
}

// ========================================
// Auth Types
// ========================================

export interface AuthUser {
  id: UUID
  email: string
  user_metadata?: JsonObject
}

export interface AuthSession {
  access_token: string
  refresh_token: string
  expires_in: number
  user: AuthUser
}
```

---

## API Client

API client kodunu projenize ekleyin: `src/lib/api.ts`

```typescript
// src/lib/api.ts
import { supabase } from './supabase'
import type { ApiError } from '@/types/api'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface ApiOptions extends RequestInit {
  tenantId?: string
  skipAuth?: boolean
}

export class ApiClient {
  private async getAuthHeaders(tenantId?: string): Promise<HeadersInit> {
    const {
      data: { session },
    } = await supabase.auth.getSession()

    if (!session) {
      throw new Error('No active session')
    }

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.access_token}`,
    }

    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId
    }

    return headers
  }

  private async request<T>(
    endpoint: string,
    options: ApiOptions = {}
  ): Promise<T> {
    const { tenantId, skipAuth, ...fetchOptions } = options

    let headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...fetchOptions.headers,
    }

    if (!skipAuth) {
      const authHeaders = await this.getAuthHeaders(tenantId)
      headers = { ...headers, ...authHeaders }
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
    })

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }))
      throw new Error(error.detail)
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T
    }

    return response.json()
  }

  // GET request
  async get<T>(endpoint: string, options?: ApiOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'GET' })
  }

  // POST request
  async post<T>(
    endpoint: string,
    data: any,
    options?: ApiOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // PUT request
  async put<T>(endpoint: string, data: any, options?: ApiOptions): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  // DELETE request
  async delete<T>(endpoint: string, options?: ApiOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' })
  }

  // PATCH request
  async patch<T>(
    endpoint: string,
    data: any,
    options?: ApiOptions
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }
}

export const api = new ApiClient()
```

---

## React Hooks

### useProfile Hook

```typescript
// src/hooks/useProfile.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Profile, ProfileUpdate } from '@/types/api'

export function useProfile() {
  const queryClient = useQueryClient()

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['profile', 'me'],
    queryFn: () => api.get<Profile>('/profiles/me'),
  })

  const updateProfile = useMutation({
    mutationFn: (data: ProfileUpdate) =>
      api.put<Profile>('/profiles/me', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile', 'me'] })
    },
  })

  return {
    profile,
    isLoading,
    error,
    updateProfile: updateProfile.mutate,
    isUpdating: updateProfile.isPending,
  }
}
```

### useContractors Hook

```typescript
// src/hooks/useContractors.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  Contractor,
  ContractorCreate,
  ContractorUpdate,
  ContractorFilters,
} from '@/types/api'

export function useContractors(tenantId: string, filters?: ContractorFilters) {
  const queryClient = useQueryClient()

  // Build query string
  const queryString = new URLSearchParams()
  if (filters?.status) queryString.append('status', filters.status)
  if (filters?.limit) queryString.append('limit', filters.limit.toString())
  if (filters?.offset) queryString.append('offset', filters.offset.toString())

  const endpoint = `/contractors${
    queryString.toString() ? `?${queryString}` : ''
  }`

  // Fetch contractors list
  const { data: contractors, isLoading, error } = useQuery({
    queryKey: ['contractors', tenantId, filters],
    queryFn: () => api.get<Contractor[]>(endpoint, { tenantId }),
    enabled: !!tenantId,
  })

  // Create contractor
  const createContractor = useMutation({
    mutationFn: (data: ContractorCreate) =>
      api.post<Contractor>('/contractors', data, { tenantId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contractors', tenantId] })
    },
  })

  // Update contractor
  const updateContractor = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ContractorUpdate }) =>
      api.put<Contractor>(`/contractors/${id}`, data, { tenantId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contractors', tenantId] })
    },
  })

  return {
    contractors: contractors || [],
    isLoading,
    error,
    createContractor: createContractor.mutate,
    isCreating: createContractor.isPending,
    updateContractor: updateContractor.mutate,
    isUpdating: updateContractor.isPending,
  }
}

// Hook for single contractor
export function useContractor(tenantId: string, contractorId: string) {
  const { data: contractor, isLoading, error } = useQuery({
    queryKey: ['contractors', tenantId, contractorId],
    queryFn: () =>
      api.get<Contractor>(`/contractors/${contractorId}`, { tenantId }),
    enabled: !!tenantId && !!contractorId,
  })

  return { contractor, isLoading, error }
}
```

### useSubmissions Hook

```typescript
// src/hooks/useSubmissions.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  FRM32Submission,
  FRM32SubmissionCreate,
  FRM32SubmissionUpdate,
  SubmissionFilters,
} from '@/types/api'

export function useSubmissions(tenantId: string, filters?: SubmissionFilters) {
  const queryClient = useQueryClient()

  const queryString = new URLSearchParams()
  if (filters?.status) queryString.append('status', filters.status)
  if (filters?.contractor_id)
    queryString.append('contractor_id', filters.contractor_id)
  if (filters?.limit) queryString.append('limit', filters.limit.toString())
  if (filters?.offset) queryString.append('offset', filters.offset.toString())

  const endpoint = `/frm32/submissions${
    queryString.toString() ? `?${queryString}` : ''
  }`

  const { data: submissions, isLoading, error } = useQuery({
    queryKey: ['submissions', tenantId, filters],
    queryFn: () => api.get<FRM32Submission[]>(endpoint, { tenantId }),
    enabled: !!tenantId,
  })

  const createSubmission = useMutation({
    mutationFn: (data: FRM32SubmissionCreate) =>
      api.post<FRM32Submission>('/frm32/submissions', data, { tenantId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['submissions', tenantId] })
    },
  })

  const updateSubmission = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FRM32SubmissionUpdate }) =>
      api.put<FRM32Submission>(`/frm32/submissions/${id}`, data, { tenantId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['submissions', tenantId] })
    },
  })

  return {
    submissions: submissions || [],
    isLoading,
    error,
    createSubmission: createSubmission.mutate,
    isCreating: createSubmission.isPending,
    updateSubmission: updateSubmission.mutate,
    isUpdating: updateSubmission.isPending,
  }
}

export function useSubmission(tenantId: string, submissionId: string) {
  const { data: submission, isLoading, error } = useQuery({
    queryKey: ['submissions', tenantId, submissionId],
    queryFn: () =>
      api.get<FRM32Submission>(`/frm32/submissions/${submissionId}`, {
        tenantId,
      }),
    enabled: !!tenantId && !!submissionId,
  })

  return { submission, isLoading, error }
}
```

### useQuestions Hook

```typescript
// src/hooks/useQuestions.ts
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { FRM32Question } from '@/types/api'

export function useQuestions(isActive?: boolean) {
  const queryString = isActive !== undefined ? `?is_active=${isActive}` : ''

  const { data: questions, isLoading, error } = useQuery({
    queryKey: ['questions', isActive],
    queryFn: () =>
      api.get<FRM32Question[]>(`/frm32/questions${queryString}`),
  })

  return {
    questions: questions || [],
    isLoading,
    error,
  }
}
```

---

## Örnek Kullanımlar

### 1. Login Page

```typescript
// src/pages/Login.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { signIn } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { error } = await signIn(email, password)

      if (error) {
        setError(error.message)
      } else {
        navigate('/dashboard')
      }
    } catch (err) {
      setError('Bir hata oluştu')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <h1>SnSD Giriş</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          required
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Şifre"
          required
        />
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={loading}>
          {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
        </button>
      </form>
    </div>
  )
}
```

### 2. Contractors List Page

```typescript
// src/pages/Contractors.tsx
import { useState } from 'react'
import { useContractors } from '@/hooks/useContractors'
import type { ContractorCreate } from '@/types/api'

export function ContractorsPage() {
  const tenantId = 'your-tenant-id' // Get from context or user profile
  const [showCreateModal, setShowCreateModal] = useState(false)

  const { contractors, isLoading, createContractor, isCreating } =
    useContractors(tenantId)

  const handleCreate = (data: ContractorCreate) => {
    createContractor(data, {
      onSuccess: () => {
        setShowCreateModal(false)
        alert('Tedarikçi başarıyla oluşturuldu!')
      },
      onError: (error) => {
        alert(`Hata: ${error.message}`)
      },
    })
  }

  if (isLoading) return <div>Yükleniyor...</div>

  return (
    <div>
      <h1>Tedarikçiler</h1>
      <button onClick={() => setShowCreateModal(true)}>
        Yeni Tedarikçi Ekle
      </button>

      <table>
        <thead>
          <tr>
            <th>İsim</th>
            <th>İletişim</th>
            <th>Şehir</th>
            <th>Risk Seviyesi</th>
            <th>Son Puan</th>
          </tr>
        </thead>
        <tbody>
          {contractors.map((contractor) => (
            <tr key={contractor.id}>
              <td>{contractor.name}</td>
              <td>{contractor.contact_email}</td>
              <td>{contractor.city}</td>
              <td>
                <span className={`risk-${contractor.risk_level}`}>
                  {contractor.risk_level}
                </span>
              </td>
              <td>{contractor.last_evaluation_score?.toFixed(1) || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {showCreateModal && (
        <CreateContractorModal
          onSubmit={handleCreate}
          onClose={() => setShowCreateModal(false)}
          isLoading={isCreating}
        />
      )}
    </div>
  )
}
```

### 3. Profile Page

```typescript
// src/pages/Profile.tsx
import { useState, useEffect } from 'react'
import { useProfile } from '@/hooks/useProfile'
import type { ProfileUpdate } from '@/types/api'

export function ProfilePage() {
  const { profile, isLoading, updateProfile, isUpdating } = useProfile()
  const [formData, setFormData] = useState<ProfileUpdate>({})

  useEffect(() => {
    if (profile) {
      setFormData({
        full_name: profile.full_name,
        phone: profile.phone || '',
        avatar_url: profile.avatar_url || '',
      })
    }
  }, [profile])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateProfile(formData, {
      onSuccess: () => {
        alert('Profil güncellendi!')
      },
      onError: (error) => {
        alert(`Hata: ${error.message}`)
      },
    })
  }

  if (isLoading) return <div>Yükleniyor...</div>
  if (!profile) return <div>Profil bulunamadı</div>

  return (
    <div>
      <h1>Profilim</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Ad Soyad</label>
          <input
            type="text"
            value={formData.full_name || ''}
            onChange={(e) =>
              setFormData({ ...formData, full_name: e.target.value })
            }
          />
        </div>
        <div>
          <label>Telefon</label>
          <input
            type="tel"
            value={formData.phone || ''}
            onChange={(e) =>
              setFormData({ ...formData, phone: e.target.value })
            }
          />
        </div>
        <div>
          <label>Avatar URL</label>
          <input
            type="url"
            value={formData.avatar_url || ''}
            onChange={(e) =>
              setFormData({ ...formData, avatar_url: e.target.value })
            }
          />
        </div>
        <button type="submit" disabled={isUpdating}>
          {isUpdating ? 'Güncelleniyor...' : 'Güncelle'}
        </button>
      </form>

      <div className="profile-info">
        <p>Email: {profile.username}</p>
        <p>Departman: {profile.department || '-'}</p>
        <p>Pozisyon: {profile.job_title || '-'}</p>
        <p>Role ID: {profile.role_id}</p>
      </div>
    </div>
  )
}
```

---

## Environment Variables

`.env` dosyanızı oluşturun:

```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://ojkqgvkzumbnmasmajkw.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA
```

---

## React Query Setup

```typescript
// src/main.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30000, // 30 seconds
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <YourAppRoutes />
      </AuthProvider>
    </QueryClientProvider>
  )
}
```

---

## Error Handling Best Practices

```typescript
// src/lib/errorHandler.ts

export function handleApiError(error: unknown): string {
  if (error instanceof Error) {
    // Auth errors
    if (error.message.includes('Invalid token')) {
      return 'Oturumunuz sona erdi. Lütfen tekrar giriş yapın.'
    }
    if (error.message.includes('Not allowed')) {
      return 'Bu işlem için yetkiniz yok.'
    }
    if (error.message.includes('Not found')) {
      return 'İstenen kayıt bulunamadı.'
    }

    return error.message
  }

  return 'Beklenmeyen bir hata oluştu.'
}

// Usage
try {
  await api.get('/contractors', { tenantId })
} catch (error) {
  const message = handleApiError(error)
  toast.error(message)
}
```

Bu dokümantasyonla frontend'inizi kolayca entegre edebilirsiniz!
