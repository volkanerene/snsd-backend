"""
Seed incident report dialogues for MarcelGPT video generation

This script populates the database with pre-generated incident report dialogues
that can be used to quickly create safety videos.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase_client import supabase

INCIDENT_REPORT_DIALOGUES = [
    {
        "title": "Slip and Fall Incident - Warehouse",
        "category": "Workplace Safety",
        "dialogue": """Good morning team. I want to discuss an important incident that occurred yesterday in our warehouse facility.

At approximately 2:30 PM, one of our team members experienced a slip and fall accident near the loading dock area. The employee was walking through the storage section when they slipped on a wet surface that had not been properly marked with warning signs.

Fortunately, the injuries were minor - the employee sustained a bruised elbow and some minor scrapes. They received immediate first aid treatment and were cleared to return to work after being evaluated by our on-site medical team.

This incident reminds us why our safety protocols exist. All spills must be cleaned immediately and warning signs must be placed around wet areas. We're scheduling additional safety training sessions for all warehouse staff next week.

Please remember: if you see a hazard, report it immediately. Your safety is our top priority.""",
        "severity": "minor",
        "department": "warehouse",
        "tags": ["slip_and_fall", "warehouse_safety", "wet_floor"]
    },
    {
        "title": "Chemical Exposure - Laboratory",
        "category": "Chemical Safety",
        "dialogue": """Attention all laboratory personnel. We need to address a serious chemical exposure incident that took place this morning in Lab 3.

During a routine procedure at 9:15 AM, a research assistant was exposed to chemical fumes when a ventilation hood malfunctioned. The employee was following proper protocols but the equipment failure led to brief exposure to organic solvents.

The employee immediately activated the emergency shower and evacuation procedures. They were transported to the medical facility and have been cleared with no serious injuries. All lab operations in that section have been temporarily suspended pending a full safety inspection.

Our facilities team is conducting a comprehensive review of all fume hoods and ventilation systems. We're also scheduling emergency response refresher training for all lab staff.

Remember: always verify your ventilation system is functioning before beginning any procedure involving volatile chemicals. Never hesitate to stop work if equipment isn't operating correctly.""",
        "severity": "moderate",
        "department": "laboratory",
        "tags": ["chemical_exposure", "lab_safety", "equipment_failure"]
    },
    {
        "title": "Near Miss - Forklift Operation",
        "category": "Equipment Safety",
        "dialogue": """Team, I want to bring your attention to a near-miss incident that occurred yesterday afternoon in the distribution center.

At approximately 3:45 PM, a forklift operator was moving pallets in aisle 7 when a pedestrian walked into the designated forklift zone without wearing proper high-visibility vest. The operator noticed the person just in time and was able to stop, avoiding what could have been a serious accident.

While no one was injured, this is exactly the type of situation we need to prevent. This near-miss serves as a critical learning opportunity for everyone.

Moving forward, we're implementing enhanced controls: additional signage in forklift zones, mandatory safety vest checks at zone entrances, and refresher training on pedestrian and vehicle separation protocols.

If you witness a near-miss, please report it immediately. These reports help us identify and correct potential hazards before anyone gets hurt.""",
        "severity": "near_miss",
        "department": "distribution",
        "tags": ["near_miss", "forklift_safety", "pedestrian_safety"]
    },
    {
        "title": "Electrical Shock - Maintenance",
        "category": "Electrical Safety",
        "dialogue": """This is an urgent safety message regarding an electrical incident in the maintenance department.

This morning at 10:30 AM, a maintenance technician received an electrical shock while performing repairs on a control panel. The technician was working on what they believed to be a de-energized circuit, but the lockout-tagout procedure had not been properly completed.

The employee experienced a minor shock and was immediately evaluated by medical personnel. They've been released with no serious injuries, but this incident could have been much worse.

We are immediately suspending all electrical work until every technician completes mandatory lockout-tagout recertification. Additionally, we're implementing a buddy system for all electrical maintenance tasks.

Never assume a circuit is de-energized. Always follow lockout-tagout procedures completely. Always test before touch. Your life depends on it.""",
        "severity": "serious",
        "department": "maintenance",
        "tags": ["electrical_safety", "lockout_tagout", "maintenance_safety"]
    },
    {
        "title": "Ergonomic Injury - Office",
        "category": "Ergonomics",
        "dialogue": """Hello everyone. I want to discuss an important topic that affects all of us who work at desks and computers.

Last week, one of our team members reported persistent back and neck pain that developed over several months of working without proper ergonomic setup. The employee had been experiencing discomfort but didn't report it until the pain became severe.

This is a reminder that ergonomic injuries develop gradually and are completely preventable with proper workspace setup and regular breaks.

We're scheduling ergonomic assessments for all office staff. Our safety team will visit each workspace to ensure proper chair height, monitor positioning, keyboard placement, and lighting.

Please remember to take regular breaks, stretch every hour, and report any discomfort early. Don't wait until pain becomes severe. We have resources available to help optimize your workspace for long-term health.""",
        "severity": "minor",
        "department": "office",
        "tags": ["ergonomics", "office_safety", "repetitive_strain"]
    }
]


async def seed_incident_reports():
    """Seed the database with incident report dialogues"""

    print("Starting incident report dialogue seeding...")

    # Get or create a system tenant for incident reports
    # In production, you'd assign these to specific tenants or create a "library" tenant
    tenant_id = "550e8400-e29b-41d4-a716-446655440001"  # Default tenant

    inserted_count = 0

    for report in INCIDENT_REPORT_DIALOGUES:
        try:
            # Check if this report already exists
            existing = supabase.table("incident_report_dialogues")\
                .select("id")\
                .eq("title", report["title"])\
                .execute()

            if existing.data and len(existing.data) > 0:
                print(f"  ⏭️  Skipping '{report['title']}' - already exists")
                continue

            # Insert the incident report
            data = {
                "tenant_id": tenant_id,
                "title": report["title"],
                "category": report["category"],
                "dialogue": report["dialogue"],
                "severity": report["severity"],
                "department": report["department"],
                "tags": report["tags"],
                "is_template": True  # Mark as template/example
            }

            result = supabase.table("incident_report_dialogues").insert(data).execute()

            if result.data:
                inserted_count += 1
                print(f"  ✅ Inserted: {report['title']}")
            else:
                print(f"  ❌ Failed to insert: {report['title']}")

        except Exception as e:
            print(f"  ❌ Error inserting '{report['title']}': {str(e)}")

    print(f"\n✨ Seeding complete! Inserted {inserted_count} new incident reports.")
    print(f"📊 Total reports in database: {inserted_count + (len(INCIDENT_REPORT_DIALOGUES) - inserted_count)}")


# Create the table if it doesn't exist
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS incident_report_dialogues (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    dialogue TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('minor', 'moderate', 'serious', 'critical', 'near_miss')),
    department TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    is_template BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_incident_dialogues_tenant ON incident_report_dialogues(tenant_id);
CREATE INDEX IF NOT EXISTS idx_incident_dialogues_category ON incident_report_dialogues(category);
CREATE INDEX IF NOT EXISTS idx_incident_dialogues_severity ON incident_report_dialogues(severity);
"""


if __name__ == "__main__":
    print("=" * 60)
    print("Incident Report Dialogue Seeding Script")
    print("=" * 60)
    print()
    print("⚠️  Note: Make sure the 'incident_report_dialogues' table exists")
    print("   in your database before running this script.")
    print()
    print("SQL to create table:")
    print(CREATE_TABLE_SQL)
    print()
    input("Press Enter to continue with seeding...")
    print()

    # Run the seeding
    asyncio.run(seed_incident_reports())
