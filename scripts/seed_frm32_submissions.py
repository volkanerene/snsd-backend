#!/usr/bin/env python3
"""
Seed randomized FRM32 submissions for a tenant.

Usage:
    poetry run python scripts/seed_frm32_submissions.py --tenant-id <UUID>

The script will:
  * Fetch all contractors that belong to the tenant (or --limit subset)
  * Ensure each contractor has an FRM32 submission for the requested evaluation period
  * Randomly populate answers/notes/progress so some submissions look partially completed
  * Mark a configurable ratio (--submitted-ratio) of contractors as fully submitted,
    attach placeholder documents, and generate random K2 scores/final scores
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Allow importing backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase_client import supabase  # noqa: E402
from app.routers.frm32_submissions import REQUIRED_DOCUMENT_IDS  # noqa: E402

MONTH_LABELS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
]

ANSWER_TEMPLATES = [
    "Documentation for \"{question}\" is maintained in our HSE portal. Procedures were last refreshed in {month} {year} and evidence is filed under reference {code}.",
    "Contractor teams conduct toolbox meetings covering {question_lower}. Minutes from the {month} {year} session demonstrate compliance and are audited quarterly.",
    "We track {question_lower} via KPI dashboards. The current revision ({code}) shows green status after mitigation workshops completed in {month} {year}.",
    "A detailed narrative describing \"{question}\" is attached to the project execution plan. Supervisors sign off monthly; the latest approval is dated {month} {year}.",
    "Digital forms capture all field observations for {question_lower}. Analytics in PowerBI confirm closure actions taken within {days} days on average.",
    "Engineering prepared a dedicated SOP for {question_lower}. Training rosters show {staff_count}+ personnel completed refreshers during {month}.",
    "Risk registers reflect control owners for \"{question}\". We verified effectiveness during the {month} {year} internal audit cycle.",
]

NOTE_TEMPLATES = [
    "Auto-seeded draft: awaiting document uploads from contractor.",
    "Reminder sent to contractor admin to finish outstanding sections.",
    "Follow up scheduled with HSE lead next week.",
    "AI summary pending – contractor paused form midway.",
]

# Tiny valid-ish PDF so downloads work when we seed attachments
DUMMY_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<<>>endobj\n"
    b"2 0 obj<< /Length 44 >>stream\n"
    b"BT /F1 18 Tf 36 700 Td (Seeded FRM32 Document) Tj ET\n"
    b"endstream\nendobj\n"
    b"3 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
    b"4 0 obj<< /Type /Page /Parent 5 0 R /MediaBox [0 0 612 792] /Contents 2 0 R /Resources << /Font << /F1 3 0 R >> >> >>endobj\n"
    b"5 0 obj<< /Type /Pages /Kids [4 0 R] /Count 1 >>endobj\n"
    b"6 0 obj<< /Type /Catalog /Pages 5 0 R >>endobj\n"
    b"xref\n0 7\n0000000000 65535 f \n0000000010 00000 n \n0000000031 00000 n \n0000000132 00000 n \n0000000201 00000 n \n0000000330 00000 n \n0000000384 00000 n \n"
    b"trailer<< /Size 7 /Root 6 0 R >>\nstartxref\n442\n%%EOF"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed randomized FRM32 submissions")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID to seed")
    parser.add_argument(
        "--evaluation-period",
        default=datetime.now(timezone.utc).strftime("%Y-%m"),
        help="Evaluation period label (default: current YYYY-MM)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of contractors to seed (0 = all)",
    )
    parser.add_argument(
        "--submitted-ratio",
        type=float,
        default=0.45,
        help="Fraction of contractors to mark as fully submitted (0-1, default 0.45)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible runs",
    )
    parser.add_argument(
        "--skip-file-upload",
        action="store_true",
        help="Skip uploading placeholder PDFs (attachments will reference external dummy URL)",
    )
    return parser.parse_args()


def fetch_contractors(tenant_id: str, limit: int) -> List[Dict]:
    query = (
        supabase.table("contractors")
        .select("id, name, contact_email")
        .eq("tenant_id", tenant_id)
        .order("created_at")
    )
    if limit and limit > 0:
        query = query.range(0, max(limit - 1, 0))
    res = query.execute()
    return res.data or []


def fetch_questions() -> List[Dict]:
    res = (
        supabase.table("frm32_questions")
        .select("question_code, question_text_en, position")
        .order("position")
        .execute()
    )
    return res.data or []


def fetch_k2_metrics() -> List[Dict]:
    res = (
        supabase.table("frm32_k2_metrics")
        .select("k2_code, scope_en, weight_percentage")
        .order("k2_code")
        .execute()
    )
    return res.data or []


def build_random_answer(question: Dict) -> str:
    template = random.choice(ANSWER_TEMPLATES)
    question_text = question.get("question_text_en") or "this topic"
    month = random.choice(MONTH_LABELS)
    year = random.randint(2019, datetime.now().year)
    days = random.randint(3, 14)
    staff = random.randint(25, 120)
    return template.format(
        question=question_text,
        question_lower=question_text.lower(),
        code=question.get("question_code", "Q"),
        idx=question.get("position", 0),
        month=month,
        year=year,
        days=days,
        staff_count=staff,
    )


def generate_answers(questions: List[Dict], completion_ratio: float) -> Dict[str, str]:
    if not questions:
        return {}
    completion_ratio = max(0.05, min(1.0, completion_ratio))
    target_count = max(1, int(len(questions) * completion_ratio))
    selected = set(q["question_code"] for q in random.sample(questions, target_count))
    answers: Dict[str, str] = {}
    for question in questions:
        code = question["question_code"]
        if code in selected:
            answers[code] = build_random_answer(question)
    return answers


def compute_progress(answer_count: int, total_questions: int) -> int:
    if total_questions == 0:
        return 0
    return min(100, round((answer_count / total_questions) * 100))


def determine_risk_class(final_score: float) -> str:
    if final_score >= 85:
        return "green"
    if final_score >= 70:
        return "yellow"
    return "red"


def random_note() -> str:
    return random.choice(NOTE_TEMPLATES)


def fetch_submission(tenant_id: str, contractor_id: str, evaluation_period: str) -> Optional[Dict]:
    res = (
        supabase.table("frm32_submissions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("contractor_id", contractor_id)
        .eq("evaluation_period", evaluation_period)
        .limit(1)
        .execute()
    )
    data = res.data or []
    return data[0] if data else None


def create_blank_submission(tenant_id: str, contractor_id: str, evaluation_period: str) -> Dict:
    payload = {
        "tenant_id": tenant_id,
        "contractor_id": contractor_id,
        "evaluation_period": evaluation_period,
        "status": "draft",
        "answers": {},
        "attachments": [],
        "metadata": {"seeded_placeholder": True},
    }
    res = supabase.table("frm32_submissions").insert(payload).execute()
    data = res.data or []
    if not data:
        raise RuntimeError("Failed to create submission stub")
    return data[0]


def upload_placeholder_file(
    tenant_id: str,
    submission_id: str,
    doc_id: str,
    skip_upload: bool,
) -> Dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    filename = f"{doc_id}-seed.pdf"
    if skip_upload:
        return {
            "docId": doc_id,
            "filename": filename,
            "storage_path": None,
            "file_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "size": len(DUMMY_PDF_BYTES),
            "content_type": "application/pdf",
            "uploaded_at": now_iso,
        }

    storage_path = f"{tenant_id}/frm32/submissions/{submission_id}/{doc_id}/{filename}"
    try:
        supabase.storage.from_("frm32-documents").upload(
            path=storage_path,
            file=DUMMY_PDF_BYTES,
            file_options={"content-type": "application/pdf"},
        )
    except Exception:
        # File might exist already; remove and retry
        try:
            supabase.storage.from_("frm32-documents").remove([storage_path])
        except Exception:
            pass
        supabase.storage.from_("frm32-documents").upload(
            path=storage_path,
            file=DUMMY_PDF_BYTES,
            file_options={"content-type": "application/pdf"},
        )

    file_url = supabase.storage.from_("frm32-documents").get_public_url(storage_path)
    return {
        "docId": doc_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_url": file_url,
        "size": len(DUMMY_PDF_BYTES),
        "content_type": "application/pdf",
        "uploaded_at": now_iso,
    }


def ensure_attachments(
    tenant_id: str,
    submission_id: str,
    existing: List[Dict],
    skip_upload: bool,
) -> List[Dict]:
    existing_map = {att.get("docId"): att for att in existing or []}
    attachments: List[Dict] = []
    for doc_id in sorted(REQUIRED_DOCUMENT_IDS):
        if doc_id in existing_map:
            attachments.append(existing_map[doc_id])
            continue
        attachments.append(upload_placeholder_file(tenant_id, submission_id, doc_id, skip_upload))
    return attachments


def generate_k2_scores(submission_id: str, k2_metrics: List[Dict]) -> float:
    """
    Upsert randomized K2 scores for a submission and return the computed final score.
    """
    if not k2_metrics:
        return 0.0

    score_rows: List[Dict] = []
    total = 0.0
    for metric in k2_metrics:
        k2_code = metric["k2_code"]
        score = random.choices([0, 3, 6, 10], weights=[0.05, 0.2, 0.35, 0.4])[0]
        comment_en = f"Seeded score {score} for {metric['scope_en']}."
        comment_tr = f"Otomatik oluşturulan {score} puanı."
        score_rows.append(
            {
                "submission_id": submission_id,
                "k2_code": k2_code,
                "score": score,
                "comment_en": comment_en,
                "comment_tr": comment_tr,
            }
        )
        total += (float(metric["weight_percentage"]) * score) / 10

    supabase.table("frm32_submission_scores").upsert(
        score_rows,
        on_conflict="submission_id,k2_code",
    ).execute()
    return round(total, 2)


def seed_for_contractor(
    contractor: Dict,
    tenant_id: str,
    evaluation_period: str,
    questions: List[Dict],
    k2_metrics: List[Dict],
    completed: bool,
    skip_file_upload: bool,
) -> str:
    contractor_id = contractor["id"]
    submission = fetch_submission(tenant_id, contractor_id, evaluation_period)
    created_new = False
    if not submission:
        submission = create_blank_submission(tenant_id, contractor_id, evaluation_period)
        created_new = True

    submission_id = submission["id"]
    existing_attachments = submission.get("attachments") or []
    now_iso = datetime.now(timezone.utc).isoformat()

    if completed:
        answers = generate_answers(questions, 1.0)
        attachments = ensure_attachments(tenant_id, submission_id, existing_attachments, skip_file_upload)
        final_score = generate_k2_scores(submission_id, k2_metrics)
        payload = {
            "answers": answers,
            "progress_percentage": 100,
            "status": "submitted",
            "attachments": attachments,
            "submitted_at": now_iso,
            "final_score": final_score,
            "risk_classification": determine_risk_class(final_score),
            "notes": None,
            "metadata": {
                **(submission.get("metadata") or {}),
                "seeded_by": "seed_frm32_submissions.py",
                "seeded_state": "submitted",
                "seeded_at": now_iso,
            },
        }
        supabase.table("frm32_submissions").update(payload).eq("id", submission_id).execute()
        return "submitted" if not created_new else "created_submitted"

    # Draft / partial completion path
    completion_ratio = random.uniform(0.35, 0.8)
    answers = generate_answers(questions, completion_ratio)
    progress = compute_progress(len(answers), len(questions))
    attachments = existing_attachments

    payload = {
        "answers": answers,
        "progress_percentage": progress,
        "status": "draft",
        "attachments": attachments,
        "notes": random_note(),
        "submitted_at": None,
        "final_score": None,
        "risk_classification": None,
        "metadata": {
            **(submission.get("metadata") or {}),
            "seeded_by": "seed_frm32_submissions.py",
            "seeded_state": "draft",
            "seeded_at": now_iso,
        },
    }
    supabase.table("frm32_submissions").update(payload).eq("id", submission_id).execute()
    return "draft" if not created_new else "created_draft"


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    contractors = fetch_contractors(args.tenant_id, args.limit)
    if not contractors:
        print("No contractors found for tenant. Aborting.")
        return

    questions = fetch_questions()
    if not questions:
        print("No FRM32 questions found. Ensure migrations are applied.")
        return

    k2_metrics = fetch_k2_metrics()
    total_contractors = len(contractors)
    submitted_target = max(0, min(total_contractors, int(round(total_contractors * args.submitted_ratio))))
    submitted_ids = set(
        random.sample([c["id"] for c in contractors], submitted_target)
    ) if submitted_target > 0 else set()

    stats = {"submitted": 0, "draft": 0, "created": 0}

    print(f"Seeding {total_contractors} contractors ({submitted_target} will be submitted).")
    for contractor in contractors:
        completed = contractor["id"] in submitted_ids
        result = seed_for_contractor(
            contractor,
            args.tenant_id,
            args.evaluation_period,
            questions,
            k2_metrics,
            completed=completed,
            skip_file_upload=args.skip_file_upload,
        )
        if result.startswith("created"):
            stats["created"] += 1
        if "submitted" in result:
            stats["submitted"] += 1
        else:
            stats["draft"] += 1
        print(f" - {contractor['name']}: {result}")

    print("\nDone.")
    print(f" Draft/in-progress submissions: {stats['draft']}")
    print(f" Submitted submissions    : {stats['submitted']}")
    print(f" Newly created rows       : {stats['created']}")


if __name__ == "__main__":
    main()

