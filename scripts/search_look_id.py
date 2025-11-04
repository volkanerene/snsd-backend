"""
Search for a specific look ID across all avatar groups
"""
import httpx
import asyncio

HEYGEN_API_KEY = "sk_V2_hgu_kmLB8XDi2mZ_ivL65prGVgSf1NcRCcJakGxhxAvvuOd2"
TARGET_LOOK_ID = "4992bcd0c5594cebb40d881144f8c412"

async def main():
    async with httpx.AsyncClient() as client:
        # Get all avatar groups
        response = await client.get(
            "https://api.heygen.com/v2/avatar_group.list",
            headers={"X-Api-Key": HEYGEN_API_KEY}
        )
        data = response.json()
        data = data.get("data") or {}
        groups = (
            data.get("avatar_group_list")
            or data.get("avatar_groups")
            or data.get("list")
            or data.get("items")
            or []
        )

        print(f"Searching {len(groups)} avatar groups for look ID: {TARGET_LOOK_ID}\n")

        found = False
        for group in groups:
            group_id = (
                group.get("group_id")
                or group.get("avatar_group_id")
                or group.get("id")
            )
            group_name = group.get("name")
            num_looks = (
                group.get("num_looks")
                if group.get("num_looks") is not None
                else group.get("look_count")
                if group.get("look_count") is not None
                else group.get("num_avatars")
                if group.get("num_avatars") is not None
                else group.get("avatar_count", 0)
            )

            if num_looks == 0:
                continue

            # Fetch looks in this group
            response = await client.get(
                f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars",
                headers={"X-Api-Key": HEYGEN_API_KEY}
            )
            avatars_data = response.json()
            avatars_data = avatars_data.get("data") or {}
            avatars = (
                avatars_data.get("avatar_list")
                or avatars_data.get("avatars")
                or avatars_data.get("list")
                or avatars_data.get("items")
                or []
            )

            for avatar in avatars:
                avatar_id = avatar.get("avatar_id")
                avatar_name = avatar.get("avatar_name")

                if avatar_id == TARGET_LOOK_ID:
                    print(f"✅ FOUND IT!")
                    print(f"   Group: {group_name} ({group_id})")
                    print(f"   Look Name: {avatar_name}")
                    print(f"   Look ID: {avatar_id}")
                    found = True
                    break

            if found:
                break

        if not found:
            print(f"❌ Look ID {TARGET_LOOK_ID} NOT FOUND in any avatar group")
            print("\n🔍 Available avatar groups:")
            for group in groups:
                fallback_count = (
                    group.get("num_looks")
                    if group.get("num_looks") is not None
                    else group.get("look_count")
                    if group.get("look_count") is not None
                    else group.get("num_avatars")
                    if group.get("num_avatars") is not None
                    else group.get("avatar_count", 0)
                )
                print(f"   - {group.get('name')}: {fallback_count} looks")

if __name__ == "__main__":
    asyncio.run(main())
