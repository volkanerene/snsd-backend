from supabase import create_client
from app.config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
# Not: service role ile backend güvenli; RLS varsa policy'e yine uyar ama geniş yetkilidir.
# İstersen anon key kullan ve RLS'ye tamamen bırak; kritik yazma işlemlerinde service role tercih edilir.