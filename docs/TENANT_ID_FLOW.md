# Tenant ID Kullanım Rehberi

## Genel Bakış

SnSD backend'i **multi-tenant** mimariye sahiptir. Bu, her şirketin kendi verilerini izole bir şekilde tutması anlamına gelir. Çoğu API endpoint'i `X-Tenant-ID` header'ı gerektirir.

## Tenant ID Nereden Gelir?

Tenant ID, kullanıcının profil bilgilerinde (`profiles` tablosu) bulunur. Her kullanıcı bir tenant'a bağlıdır.

## Doğru Authentication ve Tenant ID Flow

### Adım 1: Kullanıcı Girişi

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://ojkqgvkzumbnmasmajkw.supabase.co',
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' // anon key
)

// Login
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password123'
})

if (error) {
  console.error('Login failed:', error.message)
  return
}

// JWT token otomatik olarak Supabase client tarafından yönetilir
const accessToken = data.session.access_token
```

### Adım 2: Kullanıcı Profilini ve Tenant ID'yi Al

Login başarılı olduktan **HEMEN** sonra, kullanıcının profil bilgilerini çekin:

```typescript
// Backend'e GET /profiles/me isteği
const response = await fetch('http://localhost:8000/profiles/me', {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
})

const profile = await response.json()

// Profile içinde tenant_id var!
const tenantId = profile.tenant_id

console.log('User Profile:', profile)
// {
//   id: "uuid-user-id",
//   tenant_id: "uuid-tenant-id",  ← BU ÖNEMLİ!
//   full_name: "Ahmet Yılmaz",
//   email: "user@example.com",
//   role_id: 2,
//   is_active: true,
//   ...
// }
```

### Adım 3: Tenant ID'yi Context'e Kaydet

React için örnek:

```typescript
// contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'

interface AuthContextType {
  user: any
  profile: any
  tenantId: string | null
  isLoading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any>(null)
  const [profile, setProfile] = useState<any>(null)
  const [tenantId, setTenantId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )

  // Check for existing session on mount
  useEffect(() => {
    checkSession()
  }, [])

  async function checkSession() {
    try {
      const { data: { session } } = await supabase.auth.getSession()

      if (session) {
        setUser(session.user)
        await fetchProfile(session.access_token)
      }
    } catch (error) {
      console.error('Session check failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  async function fetchProfile(accessToken: string) {
    try {
      const response = await fetch('http://localhost:8000/profiles/me', {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        }
      })

      if (!response.ok) {
        throw new Error('Failed to fetch profile')
      }

      const profileData = await response.json()
      setProfile(profileData)
      setTenantId(profileData.tenant_id) // ← Tenant ID'yi kaydet!
    } catch (error) {
      console.error('Failed to fetch profile:', error)
    }
  }

  async function signIn(email: string, password: string) {
    setIsLoading(true)
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
      })

      if (error) throw error

      setUser(data.user)
      await fetchProfile(data.session.access_token)
    } catch (error) {
      console.error('Sign in failed:', error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  async function signOut() {
    await supabase.auth.signOut()
    setUser(null)
    setProfile(null)
    setTenantId(null)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        tenantId, // ← Context'ten erişilebilir!
        isLoading,
        signIn,
        signOut
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
```

### Adım 4: API Çağrılarında Tenant ID Kullan

```typescript
// hooks/useContractors.tsx
import { useAuth } from '@/contexts/AuthContext'
import { useQuery } from '@tanstack/react-query'

export function useContractors() {
  const { tenantId } = useAuth() // ← Context'ten tenant ID al

  const { data: contractors, isLoading, error } = useQuery({
    queryKey: ['contractors', tenantId],
    queryFn: async () => {
      const { data: { session } } = await supabase.auth.getSession()

      if (!session || !tenantId) {
        throw new Error('Not authenticated or tenant ID missing')
      }

      const response = await fetch('http://localhost:8000/contractors?limit=50', {
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'X-Tenant-ID': tenantId, // ← Tenant ID header'da gönder!
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to fetch contractors')
      }

      return response.json()
    },
    enabled: !!tenantId, // ← Tenant ID yoksa çağrı yapma!
  })

  return { contractors, isLoading, error }
}
```

### Adım 5: Sayfalarda Kullan

```typescript
// pages/contractors.tsx
import { useAuth } from '@/contexts/AuthContext'
import { useContractors } from '@/hooks/useContractors'

export default function ContractorsPage() {
  const { tenantId, isLoading: authLoading } = useAuth()
  const { contractors, isLoading: contractorsLoading, error } = useContractors()

  // Auth yükleniyorsa bekle
  if (authLoading) {
    return <div>Loading authentication...</div>
  }

  // Tenant ID yoksa yönlendir
  if (!tenantId) {
    return <div>Please log in to view contractors</div>
  }

  // Contractors yükleniyorsa göster
  if (contractorsLoading) {
    return <div>Loading contractors...</div>
  }

  // Hata varsa göster
  if (error) {
    return <div>Error: {error.message}</div>
  }

  return (
    <div>
      <h1>Contractors (Tenant: {tenantId})</h1>
      <ul>
        {contractors?.map(contractor => (
          <li key={contractor.id}>{contractor.name}</li>
        ))}
      </ul>
    </div>
  )
}
```

## Hangi Endpoint'ler Tenant ID Gerektirir?

### ✅ Tenant ID GEREKTİRİR:
- `/tenants/*` - Tenant operations
- `/contractors/*` - Contractor operations
- `/frm32/submissions/*` - Submission operations
- `/frm32/scores/*` - Score operations
- `/k2/evaluations/*` - Evaluation operations
- `/final-scores/*` - Final score operations
- `/payments/*` - Payment operations
- `/audit-log` - Audit log

### ❌ Tenant ID GEREKTİRMEZ:
- `/profiles/me` - Current user profile (tenant_id response'da gelir)
- `/roles` - Role list
- `/frm32/questions` - Question list (global)
- `/health` - Health check

## Yaygın Hatalar ve Çözümleri

### Hata 1: "X-Tenant-ID required"

```
Error loading contractors: X-Tenant-ID required
```

**Sebep**: API çağrısında `X-Tenant-ID` header'ı eksik.

**Çözüm**:
1. Önce `/profiles/me` endpoint'ini çağırın
2. Response'dan `tenant_id`'yi alın
3. Bu ID'yi context'e kaydedin
4. Diğer API çağrılarında bu ID'yi `X-Tenant-ID` header'ında gönderin

### Hata 2: Tenant ID null veya undefined

```typescript
const { tenantId } = useAuth() // null
```

**Sebep**: Profile henüz yüklenmedi veya kullanıcı giriş yapmadı.

**Çözüm**:
```typescript
// Tenant ID yüklenene kadar bekle
if (!tenantId) {
  return <div>Loading...</div>
}

// veya query'yi disable et
useQuery({
  queryKey: ['contractors', tenantId],
  queryFn: fetchContractors,
  enabled: !!tenantId, // ← Bu satır önemli!
})
```

### Hata 3: "Not allowed" (403)

```
Error: Not allowed
```

**Sebep**: Yanlış tenant ID gönderiliyor veya kullanıcı o tenant'a erişim yetkisi yok.

**Çözüm**:
- Kullanıcının profile'ındaki `tenant_id` ile gönderilen `X-Tenant-ID` header'ının aynı olduğundan emin olun
- Kullanıcının role'ünü kontrol edin (`profile.role_id`)

## API Client Örneği (Genel Kullanım)

```typescript
// lib/api-client.ts
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

export class ApiClient {
  private baseUrl = 'http://localhost:8000'

  async request<T>(
    endpoint: string,
    options: RequestInit & { tenantId?: string } = {}
  ): Promise<T> {
    const { tenantId, ...fetchOptions } = options

    // Get auth token
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) {
      throw new Error('Not authenticated')
    }

    // Build headers
    const headers: HeadersInit = {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
      ...fetchOptions.headers
    }

    // Add tenant ID if provided
    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId
    }

    // Make request
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...fetchOptions,
      headers
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  async get<T>(endpoint: string, tenantId?: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET', tenantId })
  }

  async post<T>(endpoint: string, data: any, tenantId?: string): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      tenantId
    })
  }

  async put<T>(endpoint: string, data: any, tenantId?: string): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
      tenantId
    })
  }

  async delete<T>(endpoint: string, tenantId?: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE', tenantId })
  }
}

export const api = new ApiClient()
```

## Kullanım:

```typescript
import { api } from '@/lib/api-client'

// Profile çek (tenant ID gerekmez)
const profile = await api.get('/profiles/me')
const tenantId = profile.tenant_id

// Contractors listele (tenant ID gerekir)
const contractors = await api.get('/contractors?limit=50', tenantId)

// Contractor oluştur (tenant ID gerekir)
const newContractor = await api.post('/contractors', {
  name: 'ABC Ltd.',
  legal_name: 'ABC Limited Şirketi',
  tax_number: '1234567890'
}, tenantId)
```

## Özet: 5 Adımlı Hızlı Başlangıç

1. **Login** → Supabase auth ile giriş yap, JWT token al
2. **Profile** → `GET /profiles/me` ile profil bilgilerini çek
3. **Tenant ID** → Profile'dan `tenant_id`'yi al ve context'e kaydet
4. **Headers** → Diğer endpoint'lere `Authorization: Bearer TOKEN` + `X-Tenant-ID: UUID` gönder
5. **Use** → Context'ten tenant ID'yi alıp tüm API çağrılarında kullan

## Test Etme

Tarayıcı console'unda test:

```javascript
// 1. Login
const loginResponse = await fetch('https://ojkqgvkzumbnmasmajkw.supabase.co/auth/v1/token?grant_type=password', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'apikey': 'YOUR_ANON_KEY'
  },
  body: JSON.stringify({
    email: 'test@example.com',
    password: 'password123'
  })
})
const loginData = await loginResponse.json()
const token = loginData.access_token

// 2. Get profile with tenant_id
const profileResponse = await fetch('http://localhost:8000/profiles/me', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
const profile = await profileResponse.json()
console.log('Tenant ID:', profile.tenant_id)

// 3. Use tenant ID for other endpoints
const contractorsResponse = await fetch('http://localhost:8000/contractors?limit=50', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Tenant-ID': profile.tenant_id
  }
})
const contractors = await contractorsResponse.json()
console.log('Contractors:', contractors)
```

## Sorular?

Eğer hala "X-Tenant-ID required" hatası alıyorsanız:

1. ✅ `/profiles/me` endpoint'ini çağırdınız mı?
2. ✅ Response'da `tenant_id` var mı?
3. ✅ Bu `tenant_id`'yi state/context'te saklıyor musunuz?
4. ✅ API çağrılarında `X-Tenant-ID` header'ını gönderiyor musunuz?
5. ✅ Header ismini doğru yazdınız mı? (`X-Tenant-ID`, `X-tenant-id` değil!)

Tüm bunlar doğruysa ve hala sorun varsa, backend loglarını kontrol edin.
