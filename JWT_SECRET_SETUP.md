# JWT Secret Setup Guide

## ⚠️ Önemli: JWT Authentication Hatası Çözümü

Eğer şu hatayı alıyorsanız:
```
Error loading contractors: Invalid token: Signature verification failed
```

Bu, JWT token doğrulaması için doğru secret'ın kullanılmadığı anlamına gelir.

---

## 🔑 JWT Secret Nedir?

**JWT Secret**, Supabase'in kullanıcı token'larını imzalamak için kullandığı gizli anahtardır. Bu secret ile:
- Frontend'den gelen JWT token'ları doğrulanır
- Token'ların geçerli olup olmadığı kontrol edilir
- Sahte token'lar reddedilir

**ANON_KEY ≠ JWT_SECRET**
- `SUPABASE_ANON_KEY`: Frontend'de Supabase client oluşturmak için kullanılır
- `SUPABASE_JWT_SECRET`: Backend'de JWT token'ları doğrulamak için kullanılır

---

## 📋 Adım Adım Setup

### 1. Supabase Dashboard'a Git

1. https://supabase.com adresine git
2. Projenize login olun
3. Projenizi seçin: `ojkqgvkzumbnmasmajkw`

### 2. JWT Secret'ı Bul

**Yol 1: Settings -> API**
1. Sol menüden **Settings** (⚙️) → **API** tıklayın
2. Sayfayı aşağı kaydırın
3. **JWT Settings** bölümünü bulun
4. **JWT Secret** başlığını bulun
5. Secret'ı kopyalayın (genelde uzun bir string)

**Yol 2: Project Settings**
1. **Project Settings** → **API**
2. **Configuration** bölümü
3. **JWT Secret** alanı

### 3. .env Dosyasına Ekle

`.env` dosyanızı açın ve şunu ekleyin:

```env
SUPABASE_URL=https://ojkqgvkzumbnmasmajkw.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ⬇️ BU SATIRI EKLEYİN
SUPABASE_JWT_SECRET=your-actual-jwt-secret-from-dashboard

PORT=8000
```

**ÖNEMLİ**: `your-actual-jwt-secret-from-dashboard` yerine Supabase'den aldığınız gerçek secret'ı yapıştırın!

### 4. Docker'ı Yeniden Başlat

```bash
# Container'ı durdur
docker compose down

# Yeniden başlat (environment variable'ları yüklemek için)
docker compose up -d
```

### 5. Test Et

Frontend uygulamanızda tekrar login olun ve API'ye istek yapın.

Artık şu hatayı **almamalısınız**:
```
Invalid token: Signature verification failed ❌
```

---

## 🔍 JWT Secret'ı Doğrulama

JWT Secret doğru mu test edin:

### Manuel Test

```bash
# Container'a gir
docker compose exec app bash

# Python ile test et
python3 << 'EOF'
from app.config import settings
print(f"JWT Secret loaded: {settings.SUPABASE_JWT_SECRET is not None}")
print(f"JWT Secret length: {len(settings.SUPABASE_JWT_SECRET or '')}")
EOF
```

Beklenen çıktı:
```
JWT Secret loaded: True
JWT Secret length: 64  (veya benzer bir sayı)
```

### Logs Kontrolü

```bash
# Backend logs'a bak
docker compose logs app | grep -i "jwt\|secret\|signature"
```

---

## ❌ Common Hatalar

### Hata 1: "Invalid token signature"
**Neden**: JWT_SECRET yanlış veya eksik

**Çözüm**:
1. Supabase dashboard'dan secret'ı tekrar kontrol edin
2. `.env` dosyasına doğru kopyaladığınızdan emin olun
3. Docker'ı restart edin

### Hata 2: "Token has expired"
**Neden**: Frontend'deki token süresi dolmuş

**Çözüm**:
1. Frontend'de tekrar login olun
2. Yeni token alın
3. Token refresh mekanizması ekleyin

### Hata 3: Secret yüklenmiyor
**Neden**: `.env` dosyası Docker tarafından okunmuyor

**Çözüm**:
```bash
# .env dosyası mevcut mu?
ls -la .env

# Docker compose .env'i kullanıyor mu?
docker compose config | grep -i supabase

# Container'ı rebuild et
docker compose up -d --build
```

---

## 🔒 Güvenlik Notları

### ✅ Yapılması Gerekenler
- JWT Secret'ı **asla** git'e commit etmeyin
- `.env` dosyasını `.gitignore`'a ekleyin
- Production'da farklı secret kullanın
- Secret'ı environment variables olarak saklayın

### ❌ Yapılmaması Gerekenler
- Secret'ı kod içine hard-code etmeyin
- Secret'ı frontend'de kullanmayın
- Secret'ı public repo'lara koymayın
- Secret'ı log'lamayın

---

## 🧪 Test Senaryosu

### 1. Frontend'de Login
```typescript
import { supabase } from '@/lib/supabase'

const { data, error } = await supabase.auth.signInWithPassword({
  email: 'test@example.com',
  password: 'password123'
})

console.log('Access Token:', data.session?.access_token)
```

### 2. Backend'e İstek
```typescript
const response = await fetch('http://localhost:8000/profiles/me', {
  headers: {
    'Authorization': `Bearer ${data.session?.access_token}`,
  }
})

console.log(await response.json())
```

### 3. Beklenen Sonuç
```json
{
  "id": "user-uuid",
  "full_name": "Test User",
  "email": "test@example.com",
  ...
}
```

---

## 📞 Hala Çalışmıyor mu?

### Debug Checklist
- [ ] `.env` dosyası mevcut ve doğru yerde
- [ ] `SUPABASE_JWT_SECRET` doğru kopyalandı (boşluk/satır sonu yok)
- [ ] Docker restart yapıldı
- [ ] Frontend'de yeni login yapıldı
- [ ] Token header'da doğru gönderiliyor
- [ ] Backend logs'da hata yok

### Detaylı Log Alma
```bash
# Verbose logging
docker compose logs -f app --tail=100

# Auth specific logs
docker compose exec app python -c "
from app.utils.auth import get_current_user
from app.config import settings
print('JWT Secret:', settings.SUPABASE_JWT_SECRET[:10] + '...')
"
```

---

## 📚 Kaynaklar

- [Supabase JWT Documentation](https://supabase.com/docs/guides/auth/server-side/validating-jwts)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [JWT.io - Debug JWT Tokens](https://jwt.io/)

---

## ✅ Özet

1. **Supabase Dashboard** → **Settings** → **API** → **JWT Secret**
2. Secret'ı kopyala
3. `.env` dosyasına ekle: `SUPABASE_JWT_SECRET=...`
4. Docker restart: `docker compose restart`
5. Test et!

**JWT Secret ekledikten sonra authentication çalışacak! 🎉**
