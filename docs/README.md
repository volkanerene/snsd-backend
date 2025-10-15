# SnSD Backend - Tam Dokümantasyon

**Safety & Sustainability Database (SnSD)** - Tedarikçi Güvenlik Değerlendirme Sistemi

## 📚 Dokümantasyon İndeksi

Bu klasörde SnSD Backend API'sini kullanmak için ihtiyacınız olan tüm dokümantasyonu bulabilirsiniz.

### 🔐 1. Authentication (Kimlik Doğrulama)
**Dosya**: [AUTHENTICATION.md](./AUTHENTICATION.md)

**İçerik**:
- Supabase Auth entegrasyonu
- JWT token yönetimi
- Login/Logout/Register işlemleri
- Password reset
- Token refresh
- Frontend implementation (React hooks)
- TypeScript examples

**Ne zaman kullanmalısınız?**
- Kullanıcı girişi implementasyonu yaparken
- Authentication flow'u anlamak isterken
- Token yönetimi için
- Session handling için

---

### 🏢 1.5. Tenant ID Kullanım Rehberi
**Dosya**: [TENANT_ID_FLOW.md](./TENANT_ID_FLOW.md)

**İçerik**:
- Multi-tenant mimari açıklaması
- Tenant ID'nin nereden geldiği
- Login → Profile → Tenant ID → API çağrıları akışı
- Auth Context implementasyonu
- Hangi endpoint'lerin tenant ID gerektirdiği
- Yaygın hatalar ve çözümleri
- Detaylı kod örnekleri

**Ne zaman kullanmalısınız?**
- ⚠️ "X-Tenant-ID required" hatası aldığınızda (EN ÖNEMLİ!)
- Frontend'de authentication implementasyonu yaparken
- API çağrılarında tenant ID nasıl kullanılacağını öğrenmek için
- Context/state management setup için

---

### 🌐 2. API Reference (API Referansı)
**Dosya**: [API_REFERENCE.md](./API_REFERENCE.md)

**İçerik**:
- Tüm endpoint'lerin detaylı dokümantasyonu
- HTTP metodları (GET, POST, PUT, DELETE)
- Request/Response örnekleri
- Query parameters
- Error handling
- Status codes
- Pagination ve filtering

**Endpoint Kategorileri**:
- Health Check
- Profiles (Profil)
- Tenants (Kiracılar)
- Roles (Roller)
- Contractors (Tedarikçiler)
- FRM-32 Questions (Sorular)
- FRM-32 Submissions (Değerlendirmeler)
- Payments (Ödemeler)

**Ne zaman kullanmalısınız?**
- API endpoint'lerini öğrenmek için
- Request/response formatlarını görmek için
- Hata kodlarını anlamak için
- Filtering ve pagination yaparken

---

### 💻 3. Frontend Integration (Frontend Entegrasyonu)
**Dosya**: [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md)

**İçerik**:
- Tam TypeScript tip tanımları
- API Client implementasyonu
- React hooks (useProfile, useContractors, useSubmissions)
- Örnek sayfa implementasyonları
- Error handling best practices
- Environment variables
- React Query setup

**TypeScript Tipleri**:
- Tenant, Profile, Contractor
- FRM32Question, FRM32Submission, FRM32Answer
- Payment, Role
- API Response types
- Filter ve pagination types

**Ne zaman kullanmalısınız?**
- Frontend projesine TypeScript tipleri eklerken
- API client oluştururken
- React hooks yazarken
- State management için

---

### 🎨 4. Frontend Structure (Frontend Yapısı)
**Dosya**: [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md)

**İçerik**:
- Önerilen sayfa yapısı
- Routing yapısı (React Router)
- Component hiyerarşisi
- Layout components
- State management önerileri
- Responsive design guidelines
- Detaylı sayfa tanımları

**Sayfa Önerileri**:
- Dashboard (Ana sayfa)
- Contractors List/Detail
- Evaluations List/Form/Review
- Reports & Analytics
- Profile & Settings
- Admin pages

**Ne zaman kullanmalısınız?**
- Frontend projesi başlatırken
- Sayfa yapısı planlarken
- Routing tasarlarken
- Component mimarisi belirlerken

---

## 🚀 Hızlı Başlangıç

### Backend'i Çalıştırma

```bash
# Dependencies kurulumu
pip install -r requirements.txt

# .env dosyası oluşturma
cp .env.example .env

# Backend'i başlatma
uvicorn app.main:app --reload --port 8000

# Docker ile çalıştırma
docker-compose up --build
```

Backend: http://localhost:8000

API Docs (Swagger): http://localhost:8000/docs

### Frontend Başlangıç

1. **Authentication Kurulumu**:
   - [AUTHENTICATION.md](./AUTHENTICATION.md) dosyasını okuyun
   - Supabase client'ı kurun
   - Auth hooks'ları ekleyin

2. **TypeScript Tiplerini Ekleme**:
   - [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md)'den tipleri kopyalayın
   - `src/types/api.ts` dosyasına yapıştırın

3. **API Client Oluşturma**:
   - API client kodunu kopyalayın
   - `src/lib/api.ts` dosyasına ekleyin

4. **İlk Sayfanızı Oluşturun**:
   - [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md)'den örnek kodları kullanın
   - Login sayfası ile başlayın

---

## 📖 Örnek Kullanım Senaryoları

### Senaryo 1: Kullanıcı Girişi Eklemek

1. [AUTHENTICATION.md](./AUTHENTICATION.md) → "Frontend Implementation" bölümünü okuyun
2. Supabase client'ı kurun
3. `useAuth` hook'unu ekleyin
4. Login sayfasını oluşturun

### Senaryo 2: Tedarikçi Listesi Sayfası Yapmak

1. [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md) → Contractor tiplerini kopyalayın
2. `useContractors` hook'unu ekleyin
3. [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md) → Contractors List örneğini kullanın
4. [API_REFERENCE.md](./API_REFERENCE.md) → `/contractors` endpoint'ini inceleyin

### Senaryo 3: Değerlendirme Formu Yapmak

1. [API_REFERENCE.md](./API_REFERENCE.md) → FRM-32 endpoint'lerini inceleyin
2. [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md) → Submission tiplerini ekleyin
3. `useSubmissions` ve `useQuestions` hook'larını kullanın
4. [FRONTEND_STRUCTURE.md](./FRONTEND_STRUCTURE.md) → Evaluation Form örneğini uygulayın

---

## 🗂️ Database Schema

**Dosya**: [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) (Root klasörde)

Database schema dokümantasyonu için root klasördeki dosyaya bakın:

```
snsd-backend/
├── docs/                    # Bu klasör
│   ├── README.md           # Bu dosya
│   ├── AUTHENTICATION.md
│   ├── API_REFERENCE.md
│   ├── FRONTEND_INTEGRATION.md
│   └── FRONTEND_STRUCTURE.md
└── DATABASE_SCHEMA.md      # Database schema dokümantasyonu
```

---

## 🔑 API Keys ve Environment

### Backend (.env)

```env
SUPABASE_URL=https://ojkqgvkzumbnmasmajkw.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
PORT=8000
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://ojkqgvkzumbnmasmajkw.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

⚠️ **UYARI**: `SERVICE_ROLE_KEY`'i asla frontend'de kullanmayın!

---

## 🛠️ Teknoloji Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth (JWT)
- **Deployment**: Docker

### Frontend (Önerilen)
- **Framework**: React + TypeScript
- **Routing**: React Router v6
- **State Management**: React Query (TanStack Query)
- **Auth**: Supabase JS Client
- **UI**: Tailwind CSS / Material-UI / Ant Design
- **Forms**: React Hook Form + Zod

---

## 📊 API Workflow Örnekleri

### Kullanıcı Kaydı ve Login Flow

```
1. Frontend: Supabase Auth ile kayıt
   ↓
2. Supabase: User oluşturur, JWT döner
   ↓
3. Frontend: JWT'yi kaydeder
   ↓
4. Frontend: /profiles/me ile profil bilgisi alır
   ↓
5. Frontend: tenant_id'yi context'e kaydeder
   ↓
6. Frontend: Diğer API çağrılarında JWT + X-Tenant-ID header'ı kullanır
```

### Tedarikçi Değerlendirme Flow

```
1. GET /contractors → Tedarikçi seç
   ↓
2. POST /frm32/submissions → Yeni submission oluştur
   ↓
3. GET /frm32/questions → Soruları çek
   ↓
4. POST /frm32/answers → Cevapları kaydet (her soru için)
   ↓
5. PUT /frm32/submissions/{id} → Progress güncelle
   ↓
6. PUT /frm32/submissions/{id} → Status: 'submitted'
   ↓
7. (Admin) GET /frm32/submissions/{id}/review → Gözden geçir
   ↓
8. (Admin) PUT /frm32/submissions/{id} → Onay/red + final_score
```

---

## 🧪 Testing

### Backend Testing

```bash
# Unit tests
pytest tests/

# API tests
pytest tests/api/

# Coverage report
pytest --cov=app tests/
```

### Frontend Testing

```bash
# Unit tests (Jest)
npm test

# E2E tests (Cypress/Playwright)
npm run e2e

# Component tests (Storybook)
npm run storybook
```

---

## 🚦 Status Codes ve Error Handling

### Başarılı Responses
- `200 OK` - Başarılı GET/PUT
- `201 Created` - Başarılı POST
- `204 No Content` - Başarılı DELETE

### Client Errors
- `400 Bad Request` - Geçersiz request
- `401 Unauthorized` - Token gerekli/geçersiz
- `403 Forbidden` - Yetki yetersiz
- `404 Not Found` - Kayıt bulunamadı

### Server Errors
- `500 Internal Server Error` - Sunucu hatası

**Detaylar için**: [API_REFERENCE.md](./API_REFERENCE.md) → "Error Handling" bölümü

---

## 📞 Destek ve İletişim

### API Issues
- Backend hatası için: Backend loglarına bakın
- 401/403 hatası için: [AUTHENTICATION.md](./AUTHENTICATION.md) kontrol edin
- 400 hatası için: [API_REFERENCE.md](./API_REFERENCE.md) request formatını kontrol edin

### Development Tips
- Swagger UI kullanın: http://localhost:8000/docs
- Browser Developer Tools → Network tab'ı inceleyin
- Backend console loglarına bakın
- React Query DevTools kullanın

---

## 🔄 Güncellemeler ve Versiyonlama

### Dokümantasyon Versiyonu
- **Current**: v1.0.0
- **Son Güncelleme**: 2025-01-15
- **Backend Versiyon**: v1.0.0

### Değişiklik Takibi
Büyük API değişikliklerinde bu dokümantasyonlar güncellenecektir.

---

## ✅ Checklist: Frontend Projesine Entegrasyon

- [ ] Supabase JS client kuruldu
- [ ] Environment variables ayarlandı
- [ ] TypeScript tipleri eklendi (`src/types/api.ts`)
- [ ] API client oluşturuldu (`src/lib/api.ts`)
- [ ] Auth hooks eklendi (`src/hooks/useAuth.ts`)
- [ ] Auth context oluşturuldu
- [ ] Protected routes implementasyonu yapıldı
- [ ] React Query setup tamamlandı
- [ ] İlk sayfa (Login) oluşturuldu
- [ ] Dashboard sayfası oluşturuldu
- [ ] API test edildi

---

## 📝 Notlar

1. **Tenant ID**: Çoğu endpoint `X-Tenant-ID` header'ı gerektirir
2. **JWT Expiry**: Token'lar 1 saat geçerli, otomatik refresh yapın
3. **Pagination**: Varsayılan limit 50, max 100
4. **CORS**: Development'ta localhost:3000 izin verilmiş
5. **Rate Limiting**: Şu anda yok, production'da eklenecek

---

## 🎯 Sonraki Adımlar

1. ✅ Backend'i çalıştırın
2. ✅ API docs'u inceleyin (http://localhost:8000/docs)
3. ✅ Authentication'ı test edin
4. ✅ Frontend projesini oluşturun
5. ✅ TypeScript tiplerini ekleyin
6. ✅ İlk sayfanızı yapın
7. ✅ Backend'e bağlanın
8. ✅ Diğer sayfaları oluşturun

---

**Başarılar! 🚀**

Bu dokümantasyon frontend ekibinizin backend API'sini kolayca entegre edebilmesi için hazırlanmıştır.
Sorularınız için dokümantasyonları detaylı inceleyin veya backend ekibiyle iletişime geçin.
