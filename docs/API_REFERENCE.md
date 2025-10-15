# API Reference

SnSD Backend API - Detaylı Endpoint Dokümantasyonu

**Base URL**: `http://localhost:8000` (Development)
**Production URL**: `https://your-domain.com` (Production)

## Genel Bilgiler

### Authentication
Tüm endpoint'ler (health check hariç) JWT authentication gerektirir.

```http
Authorization: Bearer YOUR_JWT_TOKEN
```

### Tenant Context
Çoğu endpoint tenant ID gerektirir:

```http
X-Tenant-ID: 550e8400-e29b-41d4-a716-446655440001
```

### Response Format
Tüm response'lar JSON formatındadır.

**Success Response**:
```json
{
  "id": "uuid",
  "name": "Example",
  ...
}
```

**Error Response**:
```json
{
  "detail": "Error message"
}
```

### HTTP Status Codes
- `200 OK` - Başarılı
- `201 Created` - Kayıt oluşturuldu
- `400 Bad Request` - Geçersiz istek
- `401 Unauthorized` - Kimlik doğrulama gerekli
- `403 Forbidden` - Yetki yetersiz
- `404 Not Found` - Kayıt bulunamadı
- `500 Internal Server Error` - Sunucu hatası

---

## Health Check

### GET /
Sistem sağlık kontrolü (authentication gerektirmez)

**Request**:
```http
GET /
```

**Response**:
```json
{
  "ok": true
}
```

### GET /health
Detaylı health check

**Response**:
```json
{
  "ok": true
}
```

---

## Authentication & Profile

### GET /profiles/me
Mevcut kullanıcının profil bilgilerini getirir

**Headers**:
```
Authorization: Bearer TOKEN
```

**Response**:
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "full_name": "Ahmet Yılmaz",
  "username": "ahmet.yilmaz",
  "avatar_url": "https://...",
  "phone": "+90 532 123 4567",
  "locale": "tr",
  "timezone": "Europe/Istanbul",
  "role_id": 2,
  "contractor_id": null,
  "department": "HSE",
  "job_title": "Safety Manager",
  "notification_preferences": {
    "email": true,
    "sms": false,
    "push": true
  },
  "is_active": true,
  "last_login_at": "2025-01-15T10:30:00Z",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### PUT /profiles/me
Kullanıcı profilini günceller

**Güncellenebilir Alanlar**: `full_name`, `phone`, `avatar_url`, `metadata`

**Request**:
```json
{
  "full_name": "Ahmet Mehmet Yılmaz",
  "phone": "+90 532 999 8877",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

**Response**: Güncellenmiş profil

---

## Tenants

### GET /tenants
Tenant listesi (sadece kendi tenant'ı döner)

**Headers**:
```
Authorization: Bearer TOKEN
X-Tenant-ID: TENANT_UUID
```

**Response**:
```json
[
  {
    "id": "uuid",
    "name": "SOCAR Turkey",
    "slug": "socar",
    "logo_url": "https://...",
    "subdomain": "socar.snsdconsultant.com",
    "license_plan": "enterprise",
    "modules_enabled": ["evren_gpt", "marcel_gpt", "safety_bud"],
    "max_users": 100,
    "max_contractors": 200,
    "max_video_requests_monthly": 50,
    "settings": {
      "language": "tr",
      "theme_color": "#004B87"
    },
    "contact_email": "hse@socar.com.tr",
    "contact_phone": "+90 212 123 4567",
    "address": null,
    "status": "active",
    "trial_ends_at": null,
    "subscription_ends_at": "2026-12-31T20:59:59Z",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-15T00:00:00Z",
    "created_by": null
  }
]
```

### GET /tenants/{tenant_id}
Belirli bir tenant'ın detaylarını getirir

**Response**: Yukarıdaki tenant objesi

### POST /tenants
Yeni tenant oluşturur (Sadece admin)

**Request**:
```json
{
  "name": "Example Corp",
  "slug": "example",
  "subdomain": "example.snsdconsultant.com",
  "license_plan": "professional",
  "contact_email": "admin@example.com",
  "max_users": 50,
  "max_contractors": 100,
  "modules_enabled": ["evren_gpt"]
}
```

### PUT /tenants/{tenant_id}
Tenant bilgilerini günceller (Sadece admin)

**Request**: Güncellenecek alanlar

---

## Roles

### GET /roles
Tüm rolleri listeler

**Query Parameters**:
- `limit` (int, default: 50) - Sayfa başına kayıt sayısı
- `offset` (int, default: 0) - Başlangıç pozisyonu

**Response**:
```json
[
  {
    "id": 1,
    "name": "SNSD Admin",
    "slug": "snsd_admin",
    "description": "Platform yöneticisi",
    "level": 0,
    "permissions": [],
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  },
  {
    "id": 2,
    "name": "Company Admin",
    "slug": "company_admin",
    "description": "Müşteri yöneticisi",
    "level": 1,
    "permissions": ["manage_contractors", "view_reports"],
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  }
]
```

---

## Contractors (Tedarikçiler)

### GET /contractors
Tedarikçi listesini getirir

**Headers**:
```
Authorization: Bearer TOKEN
X-Tenant-ID: TENANT_UUID
```

**Query Parameters**:
- `status` (string, optional) - Durum filtresi (active, inactive, blacklisted)
- `limit` (int, default: 50, max: 100) - Sayfa başına kayıt
- `offset` (int, default: 0) - Başlangıç pozisyonu

**Response**:
```json
[
  {
    "id": "uuid",
    "tenant_id": "uuid",
    "name": "Güvenli İnşaat A.Ş.",
    "legal_name": "Güvenli İnşaat Sanayi ve Ticaret A.Ş.",
    "tax_number": "1234567890",
    "trade_registry_number": null,
    "contact_person": "Ali Güven",
    "contact_email": "ali@guvenlinsaat.com",
    "contact_phone": "+90 532 555 0101",
    "address": "Atatürk Mah. Sanayi Cad. No:45",
    "city": "Istanbul",
    "country": "TR",
    "documents": [],
    "status": "active",
    "risk_level": "green",
    "last_evaluation_score": 87.5,
    "last_evaluation_date": "2025-09-15T11:30:00Z",
    "metadata": {},
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-10T00:00:00Z",
    "created_by": "uuid"
  }
]
```

### GET /contractors/{contractor_id}
Belirli bir tedarikçinin detaylarını getirir

**Response**: Yukarıdaki contractor objesi

### POST /contractors
Yeni tedarikçi oluşturur (Admin gerekli)

**Request**:
```json
{
  "name": "Örnek İnşaat Ltd.",
  "legal_name": "Örnek İnşaat Limited Şirketi",
  "tax_number": "9876543210",
  "contact_person": "Mehmet Örnek",
  "contact_email": "info@ornekinsaat.com",
  "contact_phone": "+90 532 111 2233",
  "city": "Ankara",
  "country": "TR",
  "status": "active"
}
```

**Response**: Oluşturulan contractor objesi

### PUT /contractors/{contractor_id}
Tedarikçi bilgilerini günceller (Admin gerekli)

**Request**: Güncellenecek alanlar

---

## FRM-32 Questions

### GET /frm32/questions
FRM-32 soru listesini getirir

**Query Parameters**:
- `is_active` (boolean, optional) - Aktif/pasif filtresi

**Response**:
```json
[
  {
    "id": "uuid",
    "question_code": "Q1",
    "question_text_tr": "Firmanızın İSG organizasyon şeması mevcut mu?",
    "question_text_en": "Does your company have an OHS organization chart?",
    "k2_category": "general_info",
    "k2_weight": 1.0,
    "question_type": "yes_no",
    "options": ["Evet", "Hayır"],
    "scoring_rules": {
      "Evet": 100,
      "Hayır": 0
    },
    "max_score": 100.0,
    "is_required": true,
    "is_active": true,
    "position": 1,
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  }
]
```

**Question Types**:
- `yes_no` - Evet/Hayır soruları
- `number` - Sayısal cevap
- `multiple_choice` - Çoktan seçmeli
- `text` - Metin cevap
- `file_upload` - Dosya yükleme

---

## FRM-32 Submissions

### GET /frm32/submissions
Değerlendirme başvurularını listeler

**Query Parameters**:
- `status` (string, optional) - Durum filtresi (draft, submitted, in_review, completed, rejected)
- `contractor_id` (uuid, optional) - Tedarikçiye göre filtre
- `limit` (int, default: 50)
- `offset` (int, default: 0)

**Response**:
```json
[
  {
    "id": "uuid",
    "tenant_id": "uuid",
    "contractor_id": "uuid",
    "evaluation_period": "2025-Q3",
    "evaluation_type": "periodic",
    "status": "completed",
    "progress_percentage": 100,
    "submitted_at": "2025-09-10T07:30:00Z",
    "completed_at": "2025-09-15T11:30:00Z",
    "final_score": 87.5,
    "risk_classification": "green",
    "ai_summary": "Güvenli İnşaat A.Ş., İSG standartlarına yüksek uyum göstermektedir...",
    "attachments": [],
    "notes": null,
    "metadata": {},
    "created_at": "2025-09-01T00:00:00Z",
    "updated_at": "2025-09-15T11:30:00Z",
    "created_by": "uuid",
    "reviewed_by": "uuid"
  }
]
```

**Status Values**:
- `draft` - Taslak
- `submitted` - Gönderildi
- `in_review` - İnceleniyor
- `completed` - Tamamlandı
- `rejected` - Reddedildi

**Evaluation Types**:
- `periodic` - Periyodik değerlendirme
- `incident` - Olay sonrası değerlendirme
- `audit` - Denetim

**Risk Classifications**:
- `green` - Düşük risk (80-100 puan)
- `yellow` - Orta risk (50-79 puan)
- `red` - Yüksek risk (0-49 puan)

### GET /frm32/submissions/{submission_id}
Belirli bir başvurunun detaylarını getirir

**Response**: Yukarıdaki submission objesi

### POST /frm32/submissions
Yeni değerlendirme başvurusu oluşturur

**Request**:
```json
{
  "contractor_id": "uuid",
  "evaluation_period": "2025-Q4",
  "evaluation_type": "periodic",
  "status": "draft"
}
```

**Response**: Oluşturulan submission objesi

### PUT /frm32/submissions/{submission_id}
Başvuru bilgilerini günceller

**Normal Kullanıcı Güncelleyebilir**:
- `progress_percentage`
- `notes`

**Admin Güncelleyebilir**: Tüm alanlar

**Request**:
```json
{
  "progress_percentage": 75,
  "notes": "Dokümantasyon eksiklikleri tamamlanıyor"
}
```

**Admin Request**:
```json
{
  "status": "completed",
  "final_score": 85.5,
  "risk_classification": "green",
  "ai_summary": "Genel değerlendirme olumlu...",
  "reviewed_by": "uuid"
}
```

---

## Payments

### GET /payments
Ödeme kayıtlarını listeler

**Query Parameters**:
- `status` (string, optional) - Durum filtresi (pending, completed, failed, refunded)
- `limit` (int, default: 50)
- `offset` (int, default: 0)

**Response**:
```json
[
  {
    "id": "uuid",
    "tenant_id": "uuid",
    "amount": 450000.0,
    "currency": "TRY",
    "payment_method": "bank_transfer",
    "provider": "bank",
    "provider_transaction_id": "BNK-2025-001234",
    "provider_response": null,
    "status": "completed",
    "subscription_period": "yearly",
    "subscription_starts_at": "2024-12-31T21:00:00Z",
    "subscription_ends_at": "2026-12-31T20:59:59Z",
    "invoice_number": "INV-2025-SOCAR-001",
    "invoice_url": "https://storage.snsdconsultant.com/invoices/2025-socar-001.pdf",
    "metadata": {},
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z",
    "created_by": "uuid"
  }
]
```

**Payment Methods**:
- `credit_card` - Kredi kartı
- `bank_transfer` - Banka havalesi
- `paypal` - PayPal
- `wire_transfer` - EFT

**Providers**:
- `stripe` - Stripe
- `paytr` - PayTR
- `iyzico` - iyzico
- `bank` - Direkt banka

### GET /payments/{payment_id}
Belirli bir ödemenin detaylarını getirir

### POST /payments
Yeni ödeme kaydı oluşturur (Admin gerekli)

**Request**:
```json
{
  "amount": 150000.0,
  "currency": "TRY",
  "payment_method": "credit_card",
  "provider": "paytr",
  "subscription_period": "yearly",
  "subscription_starts_at": "2025-01-01T00:00:00Z",
  "subscription_ends_at": "2026-01-01T00:00:00Z"
}
```

### POST /payments/webhook
Ödeme sağlayıcı webhook'u (Signature verification gerekli)

**Headers**:
```
X-Signature: webhook_signature
```

**Request**: Provider'dan gelen payload

---

## Pagination

Tüm liste endpoint'leri pagination destekler:

**Query Parameters**:
- `limit` - Sayfa başına kayıt (max: 100)
- `offset` - Başlangıç pozisyonu

**Example**:
```http
GET /contractors?limit=20&offset=40
```

Bu, 41-60 arası kayıtları getirir.

---

## Filtering

Bazı endpoint'ler filtering destekler:

**Contractors**:
```http
GET /contractors?status=active
```

**Submissions**:
```http
GET /frm32/submissions?status=completed&contractor_id=uuid
```

**Questions**:
```http
GET /frm32/questions?is_active=true
```

---

## Error Handling

### Common Errors

**400 Bad Request**:
```json
{
  "detail": "contractor_id required"
}
```

**401 Unauthorized**:
```json
{
  "detail": "Invalid token"
}
```

**403 Forbidden**:
```json
{
  "detail": "Not allowed"
}
```

**404 Not Found**:
```json
{
  "detail": "Not found"
}
```

### Error Codes

Frontend'de bu hataları yakalayıp kullanıcıya uygun mesajlar gösterin:

```typescript
try {
  await api.get('/contractors', { tenantId })
} catch (error) {
  if (error.message.includes('Invalid token')) {
    // Redirect to login
  } else if (error.message.includes('Not allowed')) {
    // Show permission error
  } else if (error.message.includes('Not found')) {
    // Show not found message
  } else {
    // Show general error
  }
}
```

---

## Rate Limiting

Şu anda rate limiting yok, ancak production'da eklenecek:
- Per user: 100 requests/minute
- Per IP: 200 requests/minute

---

## API Versioning

Şu anda tek versiyon mevcut. İleride versiyonlama için:
- `/v1/contractors`
- `/v2/contractors`

formatı kullanılacak.
