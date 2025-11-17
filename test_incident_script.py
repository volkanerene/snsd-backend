"""Test script generation with 8-part format"""
import sys
import asyncio
from app.services.script_generation_service import generate_script_from_incident

async def test_incident_script():
    # Your example incident about hydrocarbon leakage
    what_happened = """Geçtiğimiz günlerde Platform A ile Platform B arasında deniz yüzeyinde geniş bir petrol tabakası fark edildi. 
Öncelikle topside kontrollerimizi yaptık ancak bir LOPC kaynağı bulamadık. 
Ardından Platform B'nin güneyinde deniz yüzeyine doğru yükselen hidrokarbon kabarcıkları tespit edildi. 
Bunun üzerine 07:45'te platform kontrol shutdown'ı ve manuel ESD devreye alındı. 
Platform A ile Platform B arasından geçen Platform 3 hattı da güvenli şekilde kademeli olarak basınçsızlaştırıldı."""

    why_did_it_happen = """Rutin barge operasyonları sırasında barç çapa halatının deniz altındaki sealine flanşına takıldığı ve hattı mekanik olarak hasara uğrattığı ortaya çıktı. 
Normalde risksiz gibi görünen bir operasyon, güncel olmayan bilgi nedeniyle altyapımıza doğrudan zarar verecek bir duruma dönüştü."""

    what_did_they_learn = """Güncel olmayan bilgiyle çalışmak, en iyi prosedürleri bile etkisiz hale getirir.
Deniz operasyonları ile deniz altı altyapısı arasındaki etkileşim her zaman kritik bir risktir ve titizlikle yönetilmelidir.
Yüzeyde yaptığımız bir hareketin deniz altında neye yol açabileceğini her zaman düşünmek zorundayız."""

    process_safety_violations = "We Respect Hazards"
    
    life_saving_rule_violations = "Control of Work"
    
    preventive_actions = """Anchor pattern analizinde kullanılan tüm bilgiler güncellendi.
Doğrulama süreçleri güçlendirildi.
Barge operasyonları için operasyon öncesi kontroller daha sıkı hale getirildi."""

    reference_case = """Thistle Field, North Sea - 21 Ocak 1981:
Bir dalış operasyonu sırasında umbilical hattının yüzey ekipmanına takılması sonucu ciddi bir kaza yaşanmıştı. 
Benzer şekilde, yüzey operasyonu ile deniz altı ekipmanı arasındaki etkileşim doğru analiz edilmediği için hat ciddi hasar görmüştü.
Bu örnek bize şunu gösteriyor: deniz ve deniz altı operasyonları, küçük bir veri hatasının bile çok büyük sonuçlara yol açabileceği alanlardır."""

    print("=" * 80)
    print("Testing 8-Part Incident Script Generation")
    print("=" * 80)
    print()
    
    result = await generate_script_from_incident(
        what_happened=what_happened,
        why_did_it_happen=why_did_it_happen,
        what_did_they_learn=what_did_they_learn,
        process_safety_violations=process_safety_violations,
        life_saving_rule_violations=life_saving_rule_violations,
        preventive_actions=preventive_actions,
        reference_case=reference_case,
        tenant_id=None
    )
    
    if result.get("success"):
        print("✅ Script Generated Successfully!")
        print()
        print("=" * 80)
        print("GENERATED SCRIPT:")
        print("=" * 80)
        print()
        print(result.get("script", ""))
        print()
        print("=" * 80)
        print(f"Total characters: {len(result.get('script', ''))}")
    else:
        print(f"❌ Error: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_incident_script())
