# Authentication Rehberi

SnSD Backend, Supabase Authentication kullanarak JWT tabanlı kimlik doğrulama sağlar.

## Genel Bakış

- **Auth Provider**: Supabase Auth
- **Token Type**: JWT (JSON Web Token)
- **Token Algorithm**: RS256 (RSA with SHA-256)
- **Token Location**: HTTP Authorization header (Bearer token)
- **JWKS Endpoint**: `https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/jwks`

## Supabase Auth Endpoints

Tüm authentication işlemleri Supabase'in kendi endpoint'leri üzerinden yapılır:

**Base URL**: `https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1`

### 1. Sign Up (Kayıt Olma)

```http
POST https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/signup
Content-Type: application/json
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA

{
  "email": "user@example.com",
  "password": "securePassword123",
  "options": {
    "data": {
      "full_name": "Ahmet Yılmaz",
      "phone": "+90 532 123 4567"
    }
  }
}
```

**Response**:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "user_metadata": {
      "full_name": "Ahmet Yılmaz",
      "phone": "+90 532 123 4567"
    }
  }
}
```

### 2. Sign In (Giriş Yapma)

```http
POST https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/token?grant_type=password
Content-Type: application/json
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA

{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response**:
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "user": {
    "id": "uuid",
    "email": "user@example.com"
  }
}
```

### 3. Refresh Token (Token Yenileme)

```http
POST https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/token?grant_type=refresh_token
Content-Type: application/json
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA

{
  "refresh_token": "your-refresh-token"
}
```

### 4. Sign Out (Çıkış Yapma)

```http
POST https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/logout
Content-Type: application/json
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### 5. Password Reset (Şifre Sıfırlama)

```http
POST https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/recover
Content-Type: application/json
apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA

{
  "email": "user@example.com"
}
```

## Backend API ile Authentication

Supabase'den aldığınız `access_token`'ı tüm backend API isteklerinizde kullanmanız gerekiyor.

### Request Header Format

```http
GET /api/endpoint
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: 550e8400-e29b-41d4-a716-446655440001
```

**Gerekli Header'lar**:
- `Authorization`: Bearer token ile JWT
- `X-Tenant-ID`: Kullanıcının tenant ID'si (çoğu endpoint için)

## Frontend Implementation (TypeScript/JavaScript)

### Supabase Client Kurulumu

```bash
npm install @supabase/supabase-js
```

### Supabase Client Oluşturma

```typescript
// src/lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://ojkqgvkzumbnmasmajkw.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9qa3Fndmt6dW1ibm1hc21hamt3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzMjM2MDUsImV4cCI6MjA3NDg5OTYwNX0.nRWXZjkJjZgfDi87uksrElnDZmLK6Diueh7u3jPfAXA'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

### Authentication Hook (React Example)

```typescript
// src/hooks/useAuth.ts
import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import type { User, Session } from '@supabase/supabase-js'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    return { data, error }
  }

  const signUp = async (email: string, password: string, metadata?: any) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: metadata,
      },
    })
    return { data, error }
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    return { error }
  }

  const resetPassword = async (email: string) => {
    const { data, error } = await supabase.auth.resetPasswordForEmail(email)
    return { data, error }
  }

  return {
    user,
    session,
    loading,
    signIn,
    signUp,
    signOut,
    resetPassword,
  }
}
```

### API Client with Authentication

```typescript
// src/lib/api.ts
import { supabase } from './supabase'

const API_BASE_URL = 'http://localhost:8000'

interface ApiOptions extends RequestInit {
  tenantId?: string
}

export async function apiRequest<T>(
  endpoint: string,
  options: ApiOptions = {}
): Promise<T> {
  const { tenantId, ...fetchOptions } = options

  // Get current session
  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (!session) {
    throw new Error('No active session')
  }

  // Build headers
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${session.access_token}`,
    ...fetchOptions.headers,
  }

  // Add tenant ID if provided
  if (tenantId) {
    headers['X-Tenant-ID'] = tenantId
  }

  // Make request
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `API Error: ${response.status}`)
  }

  return response.json()
}

// Helper methods
export const api = {
  get: <T>(endpoint: string, options?: ApiOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, data: any, options?: ApiOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    }),

  put: <T>(endpoint: string, data: any, options?: ApiOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: <T>(endpoint: string, options?: ApiOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'DELETE' }),
}
```

### Kullanım Örneği

```typescript
// Login sayfası
import { useAuth } from '@/hooks/useAuth'

function LoginPage() {
  const { signIn } = useAuth()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    const { data, error } = await signIn(email, password)

    if (error) {
      console.error('Login failed:', error.message)
    } else {
      console.log('Login successful:', data)
      // Redirect to dashboard
    }
  }

  return (
    <form onSubmit={handleLogin}>
      {/* Form fields */}
    </form>
  )
}

// API kullanımı
import { api } from '@/lib/api'

async function fetchContractors(tenantId: string) {
  const contractors = await api.get('/contractors', { tenantId })
  return contractors
}
```

## Auth Context Provider (React)

```typescript
// src/contexts/AuthContext.tsx
import { createContext, useContext, ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'

const AuthContext = createContext<ReturnType<typeof useAuth> | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuth()
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

export function useAuthContext() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return context
}
```

## Protected Routes (React Router)

```typescript
// src/components/ProtectedRoute.tsx
import { Navigate } from 'react-router-dom'
import { useAuthContext } from '@/contexts/AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthContext()

  if (loading) {
    return <div>Loading...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Kullanım
<Route path="/dashboard" element={
  <ProtectedRoute>
    <Dashboard />
  </ProtectedRoute>
} />
```

## Hata Yönetimi

```typescript
// Common auth errors
const AUTH_ERRORS = {
  'Invalid login credentials': 'Geçersiz email veya şifre',
  'Email not confirmed': 'Email adresinizi onaylamanız gerekiyor',
  'User already registered': 'Bu email adresi zaten kayıtlı',
  'Invalid token': 'Oturum süreniz doldu, lütfen tekrar giriş yapın',
}

function getErrorMessage(error: any): string {
  return AUTH_ERRORS[error.message] || error.message || 'Bir hata oluştu'
}
```

## Best Practices

1. **Token Yönetimi**: Supabase client otomatik olarak token'ları yönetir ve refresh eder
2. **Secure Storage**: Token'lar localStorage'da güvenli şekilde saklanır
3. **Auto Refresh**: Token süresi dolmadan otomatik yenilenir
4. **Session Persistence**: Sayfa yenilense bile session korunur
5. **Logout on Expire**: Token geçersiz olduğunda kullanıcıyı logout et

## Security Notes

- ⚠️ **ANON KEY**: Frontend'de kullanmak için güvenli (RLS kuralları geçerli)
- 🔒 **SERVICE ROLE KEY**: Asla frontend'de kullanma! Sadece backend için
- 🔐 **JWT Verification**: Backend tüm istekleri doğrular
- 🛡️ **HTTPS**: Production'da mutlaka HTTPS kullan
