from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.routers import (
    ai_processing,
    audit_log,
    contractor_auth,
    contractors,
    evaluations,
    evren_gpt,
    final_scores,
    frm32_answers,
    frm32_questions,
    frm32_scores,
    frm32_submissions,
    frm35_invites,
    invitations,
    k2_evaluations,
    payments,
    permissions,
    profiles,
    roles,
    subscription_tiers,
    tenant_users,
    tenants,
    users,
    files,
    marcel_gpt,
    marcel_webhook,
    marcel_gpt_library,
    marcel_gpt_training,
    heygen_debug,
)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to handle HTTPS forwarding from ALB"""
    async def dispatch(self, request: Request, call_next):
        # Trust X-Forwarded-Proto header from ALB
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto == "https":
            request.scope["scheme"] = "https"

        response = await call_next(request)

        # Fix any HTTP redirects to use HTTPS when behind ALB
        if forwarded_proto == "https" and response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if location and location.startswith("http://"):
                # Replace http:// with https://
                response.headers["location"] = location.replace("http://", "https://", 1)

        return response


app = FastAPI(title="SnSD API", version="1.1.0")

# HTTPS redirect ilk
app.add_middleware(HTTPSRedirectMiddleware)

# CORS en sondan (ilk çalışacak şekilde)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8080",
        "https://www.snsdconsultant.com",
        "https://snsdconsultant.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)
# Admin & User Management
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
app.include_router(tenant_users.router, prefix="/tenant-users", tags=["Tenant Users"])
app.include_router(roles.router, prefix="/roles", tags=["Roles"])
app.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
app.include_router(invitations.router, prefix="/invitations", tags=["Invitations"])
app.include_router(subscription_tiers.router, prefix="/tiers", tags=["Subscription Tiers"])

# Contractor Auth (Public - no authentication required)
app.include_router(contractor_auth.router)

# User Profiles
app.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])

# Contractors & Evaluations
app.include_router(contractors.router, prefix="/contractors", tags=["Contractors"])
app.include_router(evaluations.router, prefix="/api", tags=["Evaluations"])  # Evaluations Overview
app.include_router(evren_gpt.router, prefix="/api", tags=["EvrenGPT"])  # EvrenGPT Process
app.include_router(frm32_questions.router, prefix="/frm32", tags=["FRM32 Questions"])
app.include_router(frm32_submissions.router, prefix="/frm32", tags=["FRM32 Submissions"])
app.include_router(frm32_answers.router, prefix="/frm32", tags=["FRM32 Answers"])
app.include_router(frm32_scores.router, prefix="/frm32", tags=["FRM32 Scores"])
app.include_router(k2_evaluations.router, prefix="/k2", tags=["K2 Evaluations"])
app.include_router(final_scores.router, prefix="/final-scores", tags=["Final Scores"])
app.include_router(frm35_invites.router, prefix="/frm35", tags=["FRM35 Invites"])

# Payments & Billing
app.include_router(payments.router, prefix="/payments", tags=["Payments"])

# MarcelGPT - Video Generation
app.include_router(marcel_gpt.router, prefix="/marcel-gpt", tags=["MarcelGPT"])
app.include_router(marcel_webhook.router, prefix="/marcel-gpt", tags=["MarcelGPT Webhook"])
app.include_router(marcel_gpt_library.router, prefix="/marcel-gpt/library", tags=["MarcelGPT Library"])
app.include_router(marcel_gpt_training.router, prefix="/marcel-gpt/training", tags=["MarcelGPT Training"])

# HeyGen Debug/Test
app.include_router(heygen_debug.router, tags=["HeyGen Debug"])

# System
app.include_router(audit_log.router, prefix="/audit-log", tags=["Audit Log"])
app.include_router(ai_processing.router, prefix="/ai", tags=["AI Processing"])
app.include_router(files.router)

@app.get("/")
def root():
    return {"ok": True}
@app.get("/health")
def health():
    return {"ok": True}