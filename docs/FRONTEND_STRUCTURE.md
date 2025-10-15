# Frontend Sayfa Yapısı ve Routing

Bu dokümanda SnSD uygulaması için önerilen frontend sayfa yapısı, routing ve component hiyerarşisi bulunmaktadır.

## İçindekiler

1. [Genel Mimari](#genel-mimari)
2. [Sayfa Yapısı](#sayfa-yapısı)
3. [Routing Yapısı](#routing-yapısı)
4. [Sayfa Detayları](#sayfa-detayları)
5. [Component Yapısı](#component-yapısı)
6. [State Management](#state-management)

---

## Genel Mimari

```
src/
├── components/          # Reusable components
│   ├── auth/           # Auth related components
│   ├── contractors/    # Contractor components
│   ├── submissions/    # Submission components
│   ├── layout/         # Layout components
│   └── ui/             # Generic UI components
├── pages/              # Page components
│   ├── auth/           # Auth pages
│   ├── dashboard/      # Dashboard pages
│   ├── contractors/    # Contractor pages
│   ├── submissions/    # Submission pages
│   ├── profile/        # Profile pages
│   └── admin/          # Admin pages
├── hooks/              # Custom hooks
├── lib/                # Utility libraries
├── types/              # TypeScript types
├── contexts/           # React contexts
└── routes/             # Route definitions
```

---

## Sayfa Yapısı

### 1. Public Pages (Kimlik doğrulamasız)

#### `/login` - Login Page
**Amaç**: Kullanıcı girişi
**Features**:
- Email/password login form
- "Beni hatırla" checkbox
- "Şifremi unuttum" linki
- Hata mesajları
- Loading state

```typescript
// src/pages/auth/Login.tsx
import { LoginForm } from '@/components/auth/LoginForm'

export function LoginPage() {
  return (
    <div className="auth-layout">
      <div className="auth-card">
        <img src="/logo.svg" alt="SnSD" />
        <h1>Hoş Geldiniz</h1>
        <LoginForm />
      </div>
    </div>
  )
}
```

#### `/register` - Register Page
**Amaç**: Yeni kullanıcı kaydı
**Features**:
- Kayıt formu (email, şifre, ad soyad, telefon)
- Şifre güçlülük göstergesi
- Kullanım koşulları onayı
- Email doğrulama bildirimi

#### `/forgot-password` - Password Reset
**Amaç**: Şifre sıfırlama
**Features**:
- Email girişi
- Reset link gönderimi
- Başarı mesajı

---

### 2. Authenticated Pages (Kimlik doğrulamalı)

#### `/dashboard` - Dashboard/Ana Sayfa
**Amaç**: Genel bakış ve önemli metrikler
**Features**:
- Özet kartlar (toplam tedarikçi, aktif değerlendirme, risk dağılımı)
- Son aktiviteler listesi
- Risk dağılım grafiği
- Yaklaşan değerlendirmeler
- Hızlı aksiyonlar (yeni değerlendirme, yeni tedarikçi)

```typescript
// src/pages/dashboard/Dashboard.tsx
export function DashboardPage() {
  return (
    <div>
      <h1>Dashboard</h1>
      <div className="stats-grid">
        <StatCard title="Toplam Tedarikçi" value={145} icon={<BuildingIcon />} />
        <StatCard title="Aktif Değerlendirme" value={12} icon={<ClipboardIcon />} />
        <StatCard title="Yüksek Risk" value={3} status="danger" />
        <StatCard title="Düşük Risk" value={98} status="success" />
      </div>

      <div className="grid-2">
        <RiskDistributionChart />
        <RecentActivity />
      </div>

      <UpcomingEvaluations />
    </div>
  )
}
```

---

### 3. Contractor Management

#### `/contractors` - Contractors List
**Amaç**: Tüm tedarikçileri listeleme ve yönetme
**Features**:
- Tedarikçi listesi (tablo görünümü)
- Arama ve filtreleme (isim, durum, risk seviyesi)
- Sıralama (isim, puan, tarih)
- Pagination
- "Yeni Tedarikçi" butonu
- Risk seviyesi badge'leri
- Son değerlendirme puanı
- Hızlı aksiyonlar (görüntüle, düzenle, değerlendir)

```typescript
// src/pages/contractors/ContractorsList.tsx
export function ContractorsListPage() {
  const [filters, setFilters] = useState({
    status: 'all',
    riskLevel: 'all',
    search: '',
  })

  return (
    <div>
      <div className="page-header">
        <h1>Tedarikçiler</h1>
        <button>+ Yeni Tedarikçi</button>
      </div>

      <ContractorFilters filters={filters} onChange={setFilters} />

      <ContractorsTable filters={filters} />
    </div>
  )
}
```

#### `/contractors/:id` - Contractor Detail
**Amaç**: Tek bir tedarikçinin detaylı bilgileri
**Features**:
- Genel bilgiler (isim, iletişim, adres)
- Risk profili ve trendler
- Değerlendirme geçmişi
- Dokümanlar
- İletişim kayıtları
- "Değerlendir" butonu
- "Düzenle" butonu (admin)

**Tabs**:
1. **Genel Bilgiler**: Temel bilgiler
2. **Değerlendirmeler**: Geçmiş değerlendirmeler listesi
3. **Dokümanlar**: Yüklenen belgeler
4. **Aktivite**: Değişiklik geçmişi

```typescript
// src/pages/contractors/ContractorDetail.tsx
export function ContractorDetailPage() {
  const { id } = useParams()
  const { contractor, isLoading } = useContractor(tenantId, id)

  return (
    <div>
      <ContractorHeader contractor={contractor} />

      <Tabs>
        <Tab label="Genel Bilgiler">
          <ContractorInfo contractor={contractor} />
        </Tab>
        <Tab label="Değerlendirmeler">
          <ContractorEvaluations contractorId={id} />
        </Tab>
        <Tab label="Dokümanlar">
          <ContractorDocuments contractorId={id} />
        </Tab>
        <Tab label="Aktivite">
          <ContractorActivity contractorId={id} />
        </Tab>
      </Tabs>
    </div>
  )
}
```

#### `/contractors/new` - Create Contractor
**Amaç**: Yeni tedarikçi ekleme
**Features**:
- Multi-step form (3 adım)
  1. Temel Bilgiler
  2. İletişim Bilgileri
  3. Ek Bilgiler
- Form validasyonu
- Taslak kaydetme
- İptal butonu

---

### 4. Evaluation/Submission Management

#### `/evaluations` - Evaluations List
**Amaç**: Tüm değerlendirmeleri listeleme
**Features**:
- Değerlendirme listesi
- Filtreleme (durum, tedarikçi, dönem)
- Durum badge'leri
- İlerleme çubukları
- Hızlı aksiyonlar
- "Yeni Değerlendirme" butonu

```typescript
// src/pages/evaluations/EvaluationsList.tsx
export function EvaluationsListPage() {
  return (
    <div>
      <div className="page-header">
        <h1>Değerlendirmeler</h1>
        <button>+ Yeni Değerlendirme</button>
      </div>

      <EvaluationFilters />

      <EvaluationsTable />
    </div>
  )
}
```

#### `/evaluations/:id` - Evaluation Detail
**Amaç**: Değerlendirme detayı ve doldurma
**Features**:
- Değerlendirme bilgileri
- Soru listesi (kategorilere göre gruplu)
- İlerleme göstergesi
- Otomatik kaydetme
- Cevap formu
- Dosya yükleme
- Notlar ekleme
- "Taslak Kaydet", "Gönder" butonları

**Layout**:
- Sol sidebar: Kategori navigasyonu
- Ana alan: Sorular ve cevaplar
- Sağ sidebar: İlerleme ve notlar

```typescript
// src/pages/evaluations/EvaluationForm.tsx
export function EvaluationFormPage() {
  const { id } = useParams()
  const { submission } = useSubmission(tenantId, id)
  const { questions } = useQuestions(true)

  const categories = groupQuestionsByCategory(questions)

  return (
    <div className="evaluation-layout">
      <aside className="category-nav">
        <CategoryNavigation categories={categories} />
        <ProgressCard progress={submission.progress_percentage} />
      </aside>

      <main className="questions-area">
        <EvaluationHeader submission={submission} />

        {categories.map((category) => (
          <QuestionSection
            key={category.name}
            category={category}
            submissionId={id}
          />
        ))}

        <div className="actions">
          <button variant="outline">Taslak Kaydet</button>
          <button variant="primary">Gönder</button>
        </div>
      </main>

      <aside className="notes-sidebar">
        <NotesPanel submissionId={id} />
      </aside>
    </div>
  )
}
```

#### `/evaluations/:id/review` - Evaluation Review
**Amaç**: Değerlendirmeyi gözden geçirme ve onaylama (Admin)
**Features**:
- Tüm cevaplar
- Otomatik hesaplanan puanlar
- Kategori bazlı puanlar
- AI özet
- Risk sınıflandırması
- Onay/red butonları
- Yorum ekleme

---

### 5. Reports & Analytics

#### `/reports` - Reports Dashboard
**Amaç**: Raporlar ve analizler
**Features**:
- Rapor türü seçimi
- Tarih aralığı filtresi
- Export butonları (PDF, Excel)
- Grafik ve tablolar

**Rapor Türleri**:
1. **Tedarikçi Risk Raporu**: Tedarikçilerin risk dağılımı
2. **Değerlendirme Trend Raporu**: Zaman içinde değerlendirme trendleri
3. **K2 Kategori Raporu**: Kategori bazlı performans
4. **Karşılaştırma Raporu**: Tedarikçi karşılaştırmaları

```typescript
// src/pages/reports/Reports.tsx
export function ReportsPage() {
  const [reportType, setReportType] = useState('risk-distribution')
  const [dateRange, setDateRange] = useState({ start: null, end: null })

  return (
    <div>
      <h1>Raporlar ve Analizler</h1>

      <div className="report-controls">
        <ReportTypeSelector value={reportType} onChange={setReportType} />
        <DateRangePicker value={dateRange} onChange={setDateRange} />
        <ExportButton reportType={reportType} dateRange={dateRange} />
      </div>

      <ReportViewer reportType={reportType} dateRange={dateRange} />
    </div>
  )
}
```

---

### 6. Profile & Settings

#### `/profile` - User Profile
**Amaç**: Kullanıcı profil yönetimi
**Features**:
- Profil bilgileri düzenleme
- Avatar değiştirme
- Bildirim tercihleri
- Dil/timezone ayarları
- Şifre değiştirme

```typescript
// src/pages/profile/Profile.tsx
export function ProfilePage() {
  return (
    <div className="profile-layout">
      <aside className="profile-nav">
        <ProfileNavigation />
      </aside>

      <main>
        <Routes>
          <Route path="/" element={<ProfileInfo />} />
          <Route path="/security" element={<SecuritySettings />} />
          <Route path="/notifications" element={<NotificationSettings />} />
          <Route path="/preferences" element={<UserPreferences />} />
        </Routes>
      </main>
    </div>
  )
}
```

---

### 7. Admin Pages

#### `/admin` - Admin Dashboard
**Amaç**: Admin yönetim paneli

#### `/admin/tenants` - Tenant Management
**Features**:
- Tenant listesi
- Tenant oluşturma/düzenleme
- Subscription yönetimi
- Kullanıcı limitleri

#### `/admin/users` - User Management
**Features**:
- Kullanıcı listesi
- Rol atama
- Kullanıcı aktivasyonu/deaktivasyonu

#### `/admin/questions` - Question Bank Management
**Features**:
- Soru listesi
- Soru ekleme/düzenleme/silme
- Kategori yönetimi
- Sıralama

#### `/admin/payments` - Payment Management
**Features**:
- Ödeme geçmişi
- Fatura görüntüleme
- Subscription durumları

---

## Routing Yapısı

```typescript
// src/routes/index.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import { AdminRoute } from '@/components/auth/AdminRoute'

export function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />

        {/* Protected Routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<DashboardPage />} />

            {/* Contractors */}
            <Route path="/contractors" element={<ContractorsListPage />} />
            <Route path="/contractors/new" element={<CreateContractorPage />} />
            <Route path="/contractors/:id" element={<ContractorDetailPage />} />

            {/* Evaluations */}
            <Route path="/evaluations" element={<EvaluationsListPage />} />
            <Route path="/evaluations/new" element={<CreateEvaluationPage />} />
            <Route path="/evaluations/:id" element={<EvaluationFormPage />} />
            <Route path="/evaluations/:id/review" element={<EvaluationReviewPage />} />

            {/* Reports */}
            <Route path="/reports" element={<ReportsPage />} />

            {/* Profile */}
            <Route path="/profile/*" element={<ProfilePage />} />

            {/* Admin Routes */}
            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminDashboardPage />} />
              <Route path="/admin/tenants" element={<TenantsManagementPage />} />
              <Route path="/admin/users" element={<UsersManagementPage />} />
              <Route path="/admin/questions" element={<QuestionsManagementPage />} />
              <Route path="/admin/payments" element={<PaymentsManagementPage />} />
            </Route>
          </Route>
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
```

---

## Component Yapısı

### Layout Components

```typescript
// src/components/layout/MainLayout.tsx
export function MainLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <Header />
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

// src/components/layout/Sidebar.tsx
export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="logo">SnSD</div>
      <nav>
        <NavLink to="/dashboard" icon={<HomeIcon />}>
          Dashboard
        </NavLink>
        <NavLink to="/contractors" icon={<BuildingIcon />}>
          Tedarikçiler
        </NavLink>
        <NavLink to="/evaluations" icon={<ClipboardIcon />}>
          Değerlendirmeler
        </NavLink>
        <NavLink to="/reports" icon={<ChartIcon />}>
          Raporlar
        </NavLink>
      </nav>
      <div className="sidebar-footer">
        <UserMenu />
      </div>
    </aside>
  )
}

// src/components/layout/Header.tsx
export function Header() {
  return (
    <header className="app-header">
      <Breadcrumbs />
      <div className="header-actions">
        <NotificationsButton />
        <ThemeToggle />
        <UserAvatar />
      </div>
    </header>
  )
}
```

### Reusable Components

```
src/components/ui/
├── Button.tsx              # Buton komponenti
├── Input.tsx               # Input komponenti
├── Select.tsx              # Select komponenti
├── Modal.tsx               # Modal komponenti
├── Table.tsx               # Tablo komponenti
├── Badge.tsx               # Badge komponenti
├── Card.tsx                # Card komponenti
├── Tabs.tsx                # Tabs komponenti
├── Loading.tsx             # Loading spinner
├── EmptyState.tsx          # Boş durum görseli
└── Toast.tsx               # Bildirim komponenti
```

---

## State Management

### Global State (React Context)

```typescript
// src/contexts/TenantContext.tsx
interface TenantContextType {
  tenantId: string
  tenant: Tenant | null
  isLoading: boolean
}

export const TenantContext = createContext<TenantContextType | undefined>(
  undefined
)

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { profile } = useProfile()
  const tenantId = profile?.tenant_id

  return (
    <TenantContext.Provider value={{ tenantId, tenant, isLoading }}>
      {children}
    </TenantContext.Provider>
  )
}
```

### URL State (React Router)

- Pagination: `/contractors?page=2&limit=20`
- Filters: `/contractors?status=active&risk=yellow`
- Search: `/contractors?search=güvenli`

### Form State (React Hook Form)

```typescript
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const contractorSchema = z.object({
  name: z.string().min(2, 'En az 2 karakter'),
  email: z.string().email('Geçerli email giriniz'),
  phone: z.string().regex(/^\+90/, 'Telefon +90 ile başlamalı'),
})

export function ContractorForm() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(contractorSchema),
  })

  return <form onSubmit={handleSubmit(onSubmit)}>{/* ... */}</form>
}
```

---

## Responsive Design

### Breakpoints

```css
/* Mobile First */
--mobile: 640px
--tablet: 768px
--desktop: 1024px
--wide: 1280px
```

### Mobile Adaptasyonları

1. **Sidebar**: Hamburger menu'ye dönüşür
2. **Tables**: Kart görünümüne geçer
3. **Forms**: Tek sütun layout
4. **Charts**: Basitleştirilmiş görünüm

---

Bu yapı ile modern, ölçeklenebilir ve kullanıcı dostu bir frontend oluşturabilirsiniz!
