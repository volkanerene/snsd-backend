# CORS Sorunları ve Çözümler

## 🔧 CORS Nedir?

**CORS (Cross-Origin Resource Sharing)** - Farklı domain'lerden API'ye erişim güvenlik mekanizmasıdır.

Browser güvenlik nedeniyle, bir web sitesi (örnek: `http://localhost:3000`) başka bir domain'deki API'ye (örnek: `http://localhost:8000`) istek yaparken CORS header'larını kontrol eder.

---

## ✅ Backend CORS Yapılandırması

Backend'iniz şu origin'lerden gelen isteklere izin verir:

```python
# app/main.py
allow_origins=[
    "http://localhost:3000",      # React default
    "http://localhost:5173",      # Vite default
    "http://localhost:5174",      # Vite alternative
    "http://localhost:8080",      # Vue default
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8080",
]
```

---

## 🚨 CORS Hatası Görüyorsanız

### Hata Mesajı Örneği

```
Access to fetch at 'http://localhost:8000/profiles/me' from origin
'http://localhost:3000' has been blocked by CORS policy: Response to
preflight request doesn't pass access control check
```

### Çözüm Adımları

#### 1. Frontend Port'unuzu Kontrol Edin

Frontend uygulamanız hangi port'ta çalışıyor?

```bash
# Terminal'de kontrol edin
# React: genelde 3000
# Vite: genelde 5173
# Vue: genelde 8080
```

#### 2. Backend'e Port Ekleyin (Gerekirse)

Eğer frontend'iniz farklı bir port'ta çalışıyorsa (örnek: 4000), backend'e ekleyin:

```python
# app/main.py
allow_origins=[
    # ... existing origins
    "http://localhost:4000",      # Yeni port
    "http://127.0.0.1:4000",
]
```

#### 3. Docker Container'ı Restart Edin

```bash
# Değişiklikleri uygulamak için
docker compose restart

# veya
docker compose down
docker compose up -d
```

---

## 🌐 Production CORS Ayarları

### Environment Variable ile Yapılandırma

Production'da environment variable kullanın:

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    PORT: int | None = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000"  # Comma-separated

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
```

```python
# app/main.py
from app.config import settings

allowed_origins = settings.ALLOWED_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### .env Dosyası

```env
# Development
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Production
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

---

## 🧪 CORS Test Etme

### 1. Browser Console'da Test

```javascript
// Browser console'da çalıştır
fetch('http://localhost:8000/health')
  .then(res => res.json())
  .then(data => console.log('✅ CORS çalışıyor:', data))
  .catch(err => console.error('❌ CORS hatası:', err))
```

### 2. OPTIONS Request Test

```bash
# Terminal'den test
curl -X OPTIONS http://localhost:8000/profiles/me \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization" \
  -v
```

Başarılı response:
```
< HTTP/1.1 200 OK
< access-control-allow-origin: http://localhost:3000
< access-control-allow-credentials: true
< access-control-allow-methods: *
< access-control-allow-headers: *
```

### 3. Frontend'den Test

```typescript
// src/test/corsTest.ts
import { api } from '@/lib/api'

export async function testCORS() {
  try {
    // Simple GET request
    const response = await fetch('http://localhost:8000/health')
    const data = await response.json()
    console.log('✅ Simple request OK:', data)

    // Authenticated request (with preflight)
    const profile = await api.get('/profiles/me')
    console.log('✅ Authenticated request OK:', profile)

    return true
  } catch (error) {
    console.error('❌ CORS Error:', error)
    return false
  }
}
```

---

## 🔍 Common CORS Issues

### Issue 1: "405 Method Not Allowed" for OPTIONS

**Semptom**: OPTIONS request'leri 405 döner

**Neden**: CORS middleware eksik veya yanlış yapılandırılmış

**Çözüm**:
```python
# CORS middleware'in router'lardan ÖNCE eklenmesi gerekir
app = FastAPI(title="SnSD API")

# ✅ Doğru - Router'lardan önce
app.add_middleware(CORSMiddleware, ...)

# Router'ları ekle
app.include_router(tenants.router, ...)
```

### Issue 2: "No 'Access-Control-Allow-Origin' header"

**Semptom**: Response'ta CORS header'ı yok

**Neden**: Origin izin verilen listede değil

**Çözüm**: Frontend URL'inizi `allow_origins` listesine ekleyin

### Issue 3: "Credentials flag is 'true', but Access-Control-Allow-Credentials is not present"

**Semptom**: Cookie/token gönderirken hata

**Neden**: `allow_credentials=True` eksik

**Çözüm**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,  # ✅ Bu gerekli
    ...
)
```

### Issue 4: Wildcard Origin with Credentials

**Yanlış**:
```python
allow_origins=["*"],           # ❌ Wildcard
allow_credentials=True,        # ❌ Credentials
```

Bu kombinasyon browser tarafından reddedilir!

**Doğru**:
```python
# Spesifik origin'ler belirt
allow_origins=[
    "http://localhost:3000",
    "https://yourdomain.com"
],
allow_credentials=True,
```

---

## 📝 Development vs Production

### Development (Localhost)

```python
# Liberal CORS settings
allow_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
allow_methods=["*"]
allow_headers=["*"]
```

### Production (Deployed)

```python
# Strict CORS settings
allow_origins=[
    "https://yourdomain.com",
    "https://app.yourdomain.com",
    # NO http, NO wildcards
]
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allow_headers=[
    "Authorization",
    "Content-Type",
    "X-Tenant-ID",
]
```

---

## 🛡️ Security Best Practices

### 1. Never Use Wildcard in Production

❌ **Asla yapma**:
```python
allow_origins=["*"]  # Tehlikeli!
```

✅ **Doğru**:
```python
allow_origins=["https://yourdomain.com"]
```

### 2. Validate Origin Dynamically (Advanced)

```python
from fastapi import Request

def validate_origin(origin: str) -> bool:
    # Custom validation logic
    allowed_domains = ["yourdomain.com", "app.yourdomain.com"]
    return any(origin.endswith(domain) for domain in allowed_domains)

@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and validate_origin(origin):
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    return await call_next(request)
```

### 3. Use Environment Variables

```python
# ✅ Flexible and secure
import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    ...
)
```

---

## 🔄 CORS Flow Diagram

```
1. Frontend (localhost:3000) → API (localhost:8000)
   Request: OPTIONS /profiles/me
   Headers:
     - Origin: http://localhost:3000
     - Access-Control-Request-Method: GET
     - Access-Control-Request-Headers: Authorization

2. Backend CORS Middleware
   - Check: Is origin allowed? ✅
   - Check: Is method allowed? ✅
   - Check: Are headers allowed? ✅

3. Backend → Frontend
   Response: 200 OK
   Headers:
     - Access-Control-Allow-Origin: http://localhost:3000
     - Access-Control-Allow-Credentials: true
     - Access-Control-Allow-Methods: *
     - Access-Control-Allow-Headers: *

4. Browser: Preflight passed ✅

5. Frontend → API
   Actual Request: GET /profiles/me
   Headers:
     - Authorization: Bearer TOKEN
     - X-Tenant-ID: uuid

6. Backend → Frontend
   Response: 200 OK
   Body: { "id": "...", "name": "..." }
```

---

## 📞 Hala Sorun mu Var?

### Debug Checklist

- [ ] Backend çalışıyor mu? `http://localhost:8000/health`
- [ ] Frontend hangi port'ta? Browser URL'e bak
- [ ] Browser console'da CORS hatası var mı?
- [ ] Network tab'da OPTIONS request görünüyor mu?
- [ ] OPTIONS response'u 200 dönüyor mu?
- [ ] Backend logs'da error var mı?
- [ ] Docker restart yaptın mı?
- [ ] .env dosyası doğru mu?

### Browser Console'da Debug

```javascript
// 1. Check fetch
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(console.log)

// 2. Check CORS headers
fetch('http://localhost:8000/health')
  .then(r => {
    console.log('CORS headers:', {
      origin: r.headers.get('access-control-allow-origin'),
      methods: r.headers.get('access-control-allow-methods'),
      headers: r.headers.get('access-control-allow-headers'),
    })
  })
```

### Backend Logs Kontrol

```bash
# Docker logs
docker compose logs -f app

# Look for:
# INFO: 192.168.65.1:xxx - "OPTIONS /profiles/me HTTP/1.1" 200 OK
```

---

## ✅ CORS Çalışıyor mu Test

Bu sayfayı browser'da açıp console'da çalıştırın:

```html
<!DOCTYPE html>
<html>
<head>
  <title>CORS Test</title>
</head>
<body>
  <h1>SnSD CORS Test</h1>
  <button onclick="testCORS()">Test CORS</button>
  <pre id="result"></pre>

  <script>
    async function testCORS() {
      const result = document.getElementById('result')
      result.textContent = 'Testing...\n'

      try {
        // Test 1: Health check
        const health = await fetch('http://localhost:8000/health')
        const healthData = await health.json()
        result.textContent += '✅ Health check: OK\n'

        // Test 2: OPTIONS preflight
        const options = await fetch('http://localhost:8000/profiles/me', {
          method: 'OPTIONS',
          headers: {
            'Origin': window.location.origin,
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Authorization',
          }
        })
        result.textContent += '✅ OPTIONS preflight: OK\n'

        result.textContent += '\n🎉 CORS is working correctly!'
      } catch (error) {
        result.textContent += `\n❌ Error: ${error.message}`
      }
    }
  </script>
</body>
</html>
```

---

**CORS sorununuz çözüldü mü? Artık frontend'den backend'e sorunsuz istek yapabilirsiniz! 🎉**
