-- =====================================================================
-- Seed Data: Incident Report Dialogues
-- Purpose : Global template incidents for all users
-- Date    : 2025-11-10
-- =====================================================================

INSERT INTO incident_report_dialogues (
  id, title, what_happened, why_did_it_happen,
  what_did_they_learn, ask_yourself_or_crew, severity, department,
  category, is_template, created_at, updated_at
) VALUES
(
  gen_random_uuid(),
  'Electrical arc near high-voltage powerline',
  'Crew conducting access path repair work near a 33 kV powerline experienced electrical arc hazard. The team was working in close proximity to the live line during equipment repositioning, creating a dangerous approach scenario.',
  'Mobile equipment operation conducted near live electrical lines without adequate pre-hazard identification and distance planning. Lack of proper assessment for electrical hazard exposure during the work setup.',
  'Working with mobile equipment near energized powerlines requires mandatory planning, marking procedures, and comprehensive control measures. Line clearance distances and physical barriers must be clearly defined and communicated to all team members.',
  'Are we conducting any work with mobile equipment near live powerlines? How do we identify electrical hazards before starting? What specific controls and distance measures do we implement?',
  'high',
  'Field Operations',
  'Electrical Safety',
  true,
  NOW(),
  NOW()
),
(
  gen_random_uuid(),
  'Tool fall near-miss at height',
  'A 1.5 kg wrench fell from 20 meters height through a pipe passage during closing operations. The tool landed in a crowded walkway below. Fortunately, no injuries occurred, but the potential consequences were severe.',
  'Tool bag was improperly left on grating. Dropped object barrier and tool-securing procedures were not properly implemented or enforced during the work.',
  'Drop prevention measures are critical for tool and equipment safety. Implementing tether systems, mesh closures, and clearly designated drop zones are mandatory for work at height.',
  'Do we always secure and tether our tools during overhead work? Have we covered all mesh and grating gaps? Is the drop zone clearly marked and restricted from personnel traffic?',
  'high',
  'Maintenance',
  'Dropped Objects',
  true,
  NOW(),
  NOW()
),
(
  gen_random_uuid(),
  'Fatal road accident from driver fatigue',
  'A driver completed an 8-hour shift, had only 4 hours of rest, then began a new shift. While returning from the second shift, the driver fell asleep, left the road, and the vehicle rolled. The incident resulted in a fatality.',
  'Insufficient recovery time between shifts. There were no effective fatigue prevention measures or rest period management protocols in place.',
  'Road safety cannot be achieved without proper fatigue management. This requires comprehensive shift planning, minimum rest intervals between duties, and mandatory fit-for-duty assessments before each shift.',
  'Are our rest intervals between shifts adequate? Do we have route or driving restrictions based on fatigue risk? How is fit-for-duty status verified and documented before shift start?',
  'critical',
  'Transportation',
  'Fatigue Management',
  true,
  NOW(),
  NOW()
),
(
  gen_random_uuid(),
  'Cargo handling fatality - structural failure',
  'A worker carrying equipment on a grated bridge experienced sudden structural failure. One grating panel gave way beneath the worker, who fell approximately 12 meters, resulting in a fatality.',
  'The grating and floor integrity was compromised. Assembly safety practices were deficient. Cross-disciplinary communication and handover inspections between maintenance and operations were inadequate.',
  'Structural element changes and integrity concerns require mandatory post-installation inspections and periodic maintenance verification. Work platforms must be verified safe before loading and occupancy.',
  'Who conducted the last inspection of the grating panels and when? Was the ground and structural condition verified before cargo handling began? What is our structural integrity verification protocol?',
  'critical',
  'Infrastructure',
  'Structural Integrity',
  true,
  NOW(),
  NOW()
),
(
  gen_random_uuid(),
  'Electrical shock exposure during converter service',
  'Two workers were assigned to replace converter fan connections during service work. Both workers were exposed to electrical hazard during this task.',
  'Inadequate safe work system implementation including missing SOP documentation, LOTO (Lockout/Tagout) procedures, and work permits. Communication deficiencies and insufficient audit/supervision of electrical work activities.',
  'Electrical work operations require written permits, proper energy isolation (LOTO procedures), verified worker competency, and defined inspection frequency. Team communication regarding procedures and hazards must be clear and documented.',
  'Is there a written work permit and LOTO procedure in place for this task? Who supervises the work and how frequently? Were the electrical hazards and safety procedures explained to all team members?',
  'high',
  'Maintenance',
  'Electrical Safety',
  true,
  NOW(),
  NOW()
),
(
  gen_random_uuid(),
  'Nitrogen cylinder rupture from corrosion',
  'One of twelve high-pressure nitrogen cylinders in a bundle ruptured due to advanced corrosion on the cylinder base. The rupture caused the support rack to collapse and scattered the remaining cylinders.',
  'Severe corrosion existed on the cylinder bottom and hidden surfaces. Visual inspection procedures failed to detect or appropriately respond to the corrosion damage.',
  'High-pressure vessel corrosion management requires targeted inspection of base areas and blind spots not visible in routine inspection, periodic pressure testing, and established decommissioning criteria based on corrosion severity.',
  'How do we inspect high-pressure cylinders for corrosion on their bases and blind spots? What are our acceptance limits and decommissioning criteria for corroded equipment?',
  'high',
  'Equipment Storage',
  'Pressure Equipment',
  true,
  NOW(),
  NOW()
),
(
  gen_random_uuid(),
  'Well control failure and platform fire - fatality',
  'A deflagration event occurred below the rotary during well circulation operations. Fire initiated and spread from the tower base through tanks and to the main deck. The incident resulted in a fatality.',
  'Hydrocarbon traces remained in the drilling fluid, and ignition sources were not properly controlled. Barrier management during BOP operations and circulation procedures was inconsistent and inadequate to prevent the event.',
  'Well control operations depend critically on verified barrier management, disciplined ignition source controls, and comprehensive emergency preparedness. Barrier verification and isolation steps must be documented and audited.',
  'How is barrier integrity and verification documented during BOP and circulation operations? Is our ignition source control checklist complete and verified before each operation begins?',
  'critical',
  'Well Operations',
  'Well Control',
  true,
  NOW(),
  NOW()
);

-- Print summary
SELECT 'Successfully inserted 7 global incident template examples.' AS status;
SELECT COUNT(*) as total_templates FROM incident_report_dialogues WHERE is_template = true AND tenant_id IS NULL;
