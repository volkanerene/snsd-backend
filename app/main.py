from fastapi import FastAPI

from app.routers import (
    ai_processing,
    audit_log,
    contractors,
    final_scores,
    frm32_answers,
    frm32_questions,
    frm32_scores,
    frm32_submissions,
    frm35_invites,
    k2_evaluations,
    payments,
    profiles,
    roles,
    tenants,
)

app = FastAPI(title="SnSD API")

app.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
app.include_router(roles.router, prefix="/roles", tags=["Roles"])
app.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])
app.include_router(contractors.router, prefix="/contractors", tags=["Contractors"])
app.include_router(frm32_questions.router, prefix="/frm32", tags=["FRM32 Questions"])
app.include_router(frm32_submissions.router, prefix="/frm32", tags=["FRM32 Submissions"])
app.include_router(frm32_answers.router, prefix="/frm32", tags=["FRM32 Answers"])
app.include_router(frm32_scores.router, prefix="/frm32", tags=["FRM32 Scores"])
app.include_router(k2_evaluations.router, prefix="/k2", tags=["K2 Evaluations"])
app.include_router(final_scores.router, prefix="/final-scores", tags=["Final Scores"])
app.include_router(frm35_invites.router, prefix="/frm35", tags=["FRM35 Invites"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(audit_log.router, prefix="/audit-log", tags=["Audit Log"])
app.include_router(ai_processing.router, prefix="/ai", tags=["AI Processing"])

@app.get("/")
def root():
    return {"ok": True}
@app.get("/health")
def health():
    return {"ok": True}