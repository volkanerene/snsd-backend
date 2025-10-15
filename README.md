# SnSD Backend API

**Safety & Sustainability Database (SnSD)** - Tedarikçi Güvenlik Değerlendirme ve Yönetim Sistemi

Multi-tenant SaaS uygulaması için FastAPI tabanlı backend API.

## 🚀 Özellikler

- ✅ **Multi-Tenant Architecture**: Tenant bazlı veri izolasyonu
- ✅ **Supabase Authentication**: JWT tabanlı güvenli kimlik doğrulama
- ✅ **FRM-32 Evaluation System**: Tedarikçi güvenlik değerlendirme sistemi
- ✅ **K2 Category Framework**: Kategori bazlı puanlama sistemi
- ✅ **Risk Classification**: Otomatik risk seviyesi belirleme (Green/Yellow/Red)
- ✅ **Payment Management**: Ödeme ve abonelik yönetimi
- ✅ **Audit Logging**: Sistem aktivite kaydı
- ✅ **RESTful API**: Standart HTTP metodları
- ✅ **Auto Documentation**: Swagger UI
- ✅ **Docker Support**: Containerized deployment

## 📚 Tam Dokümantasyon

### Frontend Geliştiriciler İçin
Frontend entegrasyonu için gereken **TÜM** dokümantasyon [docs/](./docs/) klasöründe:

1. **[Authentication Rehberi](./docs/AUTHENTICATION.md)** 🔐
   - Supabase Auth entegrasyonu
   - Login/Logout/Register işlemleri
   - JWT token yönetimi
   - React hooks ve kod örnekleri

2. **[API Reference](./docs/API_REFERENCE.md)** 🌐
   - Tüm endpoint'ler (GET/POST/PUT/DELETE)
   - Request/Response örnekleri
   - Error handling
   - Filtering ve pagination

3. **[Frontend Entegrasyon Rehberi](./docs/FRONTEND_INTEGRATION.md)** 💻
   - **TypeScript tip tanımları** (Tüm modeller)
   - API Client implementasyonu
   - React Hooks (useProfile, useContractors, useSubmissions)
   - Örnek sayfa kodları
   - Error handling

4. **[Frontend Sayfa Yapısı](./docs/FRONTEND_STRUCTURE.md)** 🎨
   - Önerilen sayfa yapısı
   - Routing yapısı (React Router)
   - Component hiyerarşisi
   - Layout önerileri
   - Responsive design

5. **[Database Schema](./DATABASE_SCHEMA.md)** 🗂️
   - Tüm tablo yapıları
   - İlişkiler ve foreign key'ler
   - Kolon açıklamaları
   - Pydantic schema modelleri

### Hızlı Başlangıç
👉 **[docs/README.md](./docs/README.md)** - Tam dokümantasyon indeksi ve hızlı başlangıç rehberi

## 🛠️ Teknoloji Stack

- **Framework**: FastAPI (Python 3.12)
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth (JWT with RS256)
- **ORM**: Supabase Python Client
- **Validation**: Pydantic v2
- **Docker**: Multi-stage builds
- **Documentation**: OpenAPI (Swagger)

## 📦 Kurulum

### 1. Repository'yi Klonlayın

```bash
git clone https://github.com/your-org/snsd-backend.git
cd snsd-backend
```

### 2. Environment Variables

`.env` dosyası oluşturun:

```bash
cp .env.example .env
```

`.env` içeriği:
```env
SUPABASE_URL=https://ojkqgvkzumbnmasmajkw.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_JWT_SECRET=your_jwt_secret  # ⚠️ ÖNEMLİ: Supabase Dashboard'dan alın!
PORT=8000
```

**⚠️ SUPABASE_JWT_SECRET Gerekli!**

JWT token doğrulaması için `SUPABASE_JWT_SECRET` **zorunludur**. Nasıl alabileceğinizi öğrenmek için: **[JWT_SECRET_SETUP.md](./JWT_SECRET_SETUP.md)**

Kısa yol:
1. https://supabase.com → Projeniz → Settings → API
2. **JWT Secret** kısmını bulun ve kopyalayın
3. `.env` dosyasına ekleyin

### 3. Geliştirme Ortamı

#### Option A: Python Virtual Environment

```bash
# Virtual environment oluştur
python -m venv venv

# Aktifleştir (macOS/Linux)
source venv/bin/activate

# Aktifleştir (Windows)
venv\Scripts\activate

# Dependencies kur
pip install -r requirements.txt

# Sunucuyu başlat
uvicorn app.main:app --reload --port 8000
```

#### Option B: Docker

```bash
# Build ve run
docker-compose up --build

# Background'da çalıştır
docker-compose up -d

# Logları görüntüle
docker-compose logs -f

# Durdur
docker-compose down
```

### 4. API Erişimi

- **API Base URL**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Proje Yapısı

```
snsd-backend/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration settings
│   ├── db/
│   │   ├── supabase_client.py # Supabase client
│   │   └── pg_pool.py         # PostgreSQL pool (optional)
│   ├── routers/               # API endpoints
│   │   ├── tenants.py         # Tenant management
│   │   ├── profiles.py        # User profiles
│   │   ├── contractors.py     # Contractor management
│   │   ├── frm32_submissions.py # Evaluations
│   │   ├── frm32_questions.py   # Questions
│   │   ├── payments.py        # Payment management
│   │   └── ...
│   ├── schemas/               # Pydantic models
│   │   ├── tenants.py
│   │   ├── contractors.py
│   │   ├── frm32_submissions.py
│   │   └── ...
│   └── utils/
│       ├── auth.py            # JWT authentication
│       └── ...
├── docs/                      # 📚 Dokümantasyon
│   ├── README.md             # Dokümantasyon indeksi
│   ├── AUTHENTICATION.md     # Auth rehberi
│   ├── API_REFERENCE.md      # API referansı
│   ├── FRONTEND_INTEGRATION.md # TS types + hooks
│   └── FRONTEND_STRUCTURE.md  # Sayfa yapısı
├── tests/                     # Test files
├── .env.example              # Environment template
├── .dockerignore             # Docker ignore
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker Compose
├── requirements.txt          # Python dependencies
├── DATABASE_SCHEMA.md        # Database dokümantasyonu
└── README.md                 # Bu dosya
```

## 🔑 API Endpoints Özeti

### Authentication & Profile
- `GET /profiles/me` - Kullanıcı profili
- `PUT /profiles/me` - Profil güncelleme

### Tenants
- `GET /tenants` - Tenant listesi
- `GET /tenants/{id}` - Tenant detayı
- `POST /tenants` - Yeni tenant (Admin)
- `PUT /tenants/{id}` - Tenant güncelleme (Admin)

### Contractors
- `GET /contractors` - Tedarikçi listesi
- `GET /contractors/{id}` - Tedarikçi detayı
- `POST /contractors` - Yeni tedarikçi (Admin)
- `PUT /contractors/{id}` - Tedarikçi güncelleme (Admin)

### FRM-32 Evaluations
- `GET /frm32/questions` - Soru listesi
- `GET /frm32/submissions` - Değerlendirme listesi
- `GET /frm32/submissions/{id}` - Değerlendirme detayı
- `POST /frm32/submissions` - Yeni değerlendirme
- `PUT /frm32/submissions/{id}` - Değerlendirme güncelleme

### Payments
- `GET /payments` - Ödeme listesi
- `GET /payments/{id}` - Ödeme detayı
- `POST /payments` - Yeni ödeme (Admin)
- `POST /payments/webhook` - Ödeme webhook

### Roles
- `GET /roles` - Rol listesi

**Detaylı API dokümantasyonu için**: [docs/API_REFERENCE.md](./docs/API_REFERENCE.md)

## 🔐 Authentication

Backend **Supabase Auth** kullanır. Tüm korumalı endpoint'ler JWT token gerektirir.

**Header Format**:
```http
Authorization: Bearer YOUR_JWT_TOKEN
X-Tenant-ID: YOUR_TENANT_ID
```

**Detaylı auth dokümantasyonu**: [docs/AUTHENTICATION.md](./docs/AUTHENTICATION.md)

## 🗄️ Database

### Tables (13 tablo)

1. **tenants** - Kiracı şirketler
2. **roles** - Kullanıcı rolleri
3. **profiles** - Kullanıcı profilleri
4. **contractors** - Tedarikçi şirketler
5. **frm32_questions** - Değerlendirme soruları
6. **frm32_submissions** - Değerlendirme başvuruları
7. **frm32_answers** - Soru cevapları
8. **frm32_scores** - Kategori puanları
9. **k2_evaluations** - K2 değerlendirmeleri
10. **final_scores** - Final puanlar
11. **frm35_invites** - Dış davetler
12. **payments** - Ödeme kayıtları
13. **audit_log** - Sistem logları

**Detaylı schema dokümantasyonu**: [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)

## 🧪 Testing

```bash
# Unit tests
pytest tests/

# Specific test file
pytest tests/test_contractors.py

# Coverage report
pytest --cov=app tests/
```

## 🚢 Production Deployment

### Docker Deployment

```bash
# Build production image
docker build -t snsd-backend:latest .

# Run container
docker run -p 8000:8000 --env-file .env snsd-backend:latest
```

### Environment Variables (Production)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_production_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_production_service_role_key
PORT=8000
```

### Health Checks

```bash
# Health check endpoint
curl http://localhost:8000/health

# Expected response
{"ok": true}
```

## 📊 Monitoring

### Logs

```bash
# Docker logs
docker-compose logs -f app

# Application logs
tail -f logs/app.log
```

### Metrics

- Request count
- Response times
- Error rates
- Database query performance

## 🔒 Security

- ✅ JWT authentication with RS256
- ✅ Row Level Security (RLS) via Supabase
- ✅ HTTPS in production
- ✅ CORS configured
- ✅ Input validation with Pydantic
- ✅ SQL injection protection
- ✅ Rate limiting (TODO)

## 🤝 Frontend Entegrasyonu

### Frontend Developers İçin Checklist

- [ ] [AUTHENTICATION.md](./docs/AUTHENTICATION.md) okudum
- [ ] Supabase JS client kurdum
- [ ] [FRONTEND_INTEGRATION.md](./docs/FRONTEND_INTEGRATION.md)'den TypeScript tiplerini ekledim
- [ ] API client oluşturdum
- [ ] Auth hooks ekledim
- [ ] [FRONTEND_STRUCTURE.md](./docs/FRONTEND_STRUCTURE.md)'e göre sayfa yapısı oluşturdum
- [ ] İlk API çağrımı yaptım ve test ettim

### Hızlı Test

```typescript
// Test API connection
import { api } from '@/lib/api'

// Get current user profile
const profile = await api.get('/profiles/me')
console.log(profile)

// Get contractors
const contractors = await api.get('/contractors', {
  tenantId: 'your-tenant-id'
})
console.log(contractors)
```

## 📝 API Versioning

Şu anda: **v1** (default)

İleride versiyonlama planı:
- `/v1/contractors`
- `/v2/contractors`

## 🐛 Troubleshooting

### Common Issues

**401 Unauthorized**
- Token expire olmuş olabilir
- Token format yanlış (Bearer prefix eksik)
- Auth dokümantasyonunu kontrol edin

**403 Forbidden**
- Tenant ID header eksik veya yanlış
- Kullanıcının bu kaynağa erişim yetkisi yok
- Role kontrolü yapın

**404 Not Found**
- Endpoint yolu yanlış
- Kayıt bulunamadı
- API Reference'ı kontrol edin

**500 Internal Server Error**
- Backend loglarına bakın
- Database bağlantısı kontrol edin
- Environment variables kontrol edin

## 📞 Destek

- **Dokümantasyon**: [docs/README.md](./docs/README.md)
- **API Referans**: [docs/API_REFERENCE.md](./docs/API_REFERENCE.md)
- **Issues**: GitHub Issues
- **Wiki**: GitHub Wiki

## 📄 License

Private - All Rights Reserved

## 👥 Contributors

- Backend Team
- Frontend Team

---

**Başarılar! 🚀**

Frontend geliştirme için [docs/](./docs/) klasöründeki dokümantasyonu mutlaka inceleyin.
