"""ContentFlow QA — FastAPI Application Entry Point"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
import logging, uuid, os

from .database import engine, Base
from .config import settings
from .validators.metadata import MetadataValidator
from .validators.xml_feed import XMLFeedValidator
from .validators.asset_check import AssetAvailabilityValidator
from .validators.media_probe import MediaProbeValidator
from .validators.duplicate_ids import DuplicateIDValidator
from .validators.golive import GoLiveValidator

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready")
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")
    logger.info("ContentFlow QA API started")
    yield
    logger.info("ContentFlow QA API shutting down")


app = FastAPI(
    title="ContentFlow QA API",
    description="Media partner onboarding validation platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALIDATORS = [
    ("metadata",      "Metadata validation",  MetadataValidator),
    ("xml_feed",      "XML / Feed parsing",   XMLFeedValidator),
    ("asset_check",   "Asset availability",   AssetAvailabilityValidator),
    ("media_probe",   "FFmpeg media probe",   MediaProbeValidator),
    ("duplicate_ids", "Duplicate ID scan",    DuplicateIDValidator),
    ("golive",        "Go-live readiness",    GoLiveValidator),
]

PARTNERS: dict = {
    "acme": {"id":"acme","name":"Acme Studios","initial":"A",
        "type":"Premium Content Partner · Hollywood, CA","tier":"Premium Tier",
        "contract":"CNT-2026-001","onboarded":"2026-01-10",
        "content_type":"Feature films, series","territories":"US, GB, CA, AU",
        "formats":"H.264, HEVC, AV1","feed_type":"XML (XSD v2.1)",
        "total_assets":500,"color1":"#8b7ff8","color2":"#06b6d4",
        "status":"queued","runs":[]},
    "globalmax": {"id":"globalmax","name":"GlobalMax Entertainment","initial":"G",
        "type":"International Distributor · London, UK","tier":"Enterprise Tier",
        "contract":"CNT-2026-002","onboarded":"2026-01-15",
        "content_type":"Documentaries, news","territories":"EU, UK, AU, NZ",
        "formats":"H.264, HEVC","feed_type":"JSON manifest",
        "total_assets":320,"color1":"#06b6d4","color2":"#10b981",
        "status":"queued","runs":[]},
    "indie": {"id":"indie","name":"Indie Films Co.","initial":"I",
        "type":"Independent Studio · Austin, TX","tier":"Starter Tier",
        "contract":"CNT-2026-003","onboarded":"2026-01-20",
        "content_type":"Short films, indie","territories":"US only",
        "formats":"H.264","feed_type":"XML (XSD v1.8)",
        "total_assets":80,"color1":"#f59e0b","color2":"#f43f5e",
        "status":"queued","runs":[]},
    "legacy": {"id":"legacy","name":"Legacy Media Group","initial":"L",
        "type":"Archive & Classics · New York, NY","tier":"Standard Tier",
        "contract":"CNT-2026-004","onboarded":"2026-01-22",
        "content_type":"Classic cinema, docs","territories":"US, CA",
        "formats":"H.264, MPEG-2","feed_type":"XML (XSD v2.0)",
        "total_assets":250,"color1":"#6366f1","color2":"#8b5cf6",
        "status":"queued","runs":[]},
}

RUNS: dict = {}


class PartnerCreate(BaseModel):
    name: str
    type: Optional[str] = "Media Partner"
    content_type: Optional[str] = "Not specified"
    territories: Optional[str] = "TBD"
    formats: Optional[str] = "TBD"
    feed_type: Optional[str] = "XML (XSD v2.1)"
    tier: Optional[str] = "Starter Tier"
    total_assets: Optional[int] = 100


async def _run_pipeline(run_id: str, partner_id: str, asset_count: int):
    from scripts.generate_sample_data import generate_sample_assets
    RUNS[run_id]["status"] = "running"
    assets = generate_sample_assets(count=asset_count, seed=42)

    results, categories = [], []
    t_pass = t_fail = t_warn = 0

    for key, label, Validator in VALIDATORS:
        started = datetime.now(timezone.utc)
        cat_results = await Validator().validate(assets)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        p = sum(1 for r in cat_results if r["status"] == "pass")
        f = sum(1 for r in cat_results if r["status"] == "fail")
        w = sum(1 for r in cat_results if r["status"] == "warn")
        t_pass += p; t_fail += f; t_warn += w
        for r in cat_results:
            results.append({"category": key, **r})
        categories.append({"key":key,"label":label,"pass":p,"fail":f,"warn":w,
            "total":p+f+w,"pass_rate":round(p/max(p+f+w,1)*100,1),
            "duration_s":round(elapsed,2)})

    total = t_pass + t_fail + t_warn
    pass_rate = round(t_pass / max(total, 1) * 100, 1)
    blocked = len({r["asset_id"] for r in results if r["status"] == "fail"})
    issues = [{"asset_id":r["asset_id"],"category":r["category"],
               "scenario":r["scenario"],"message":r["message"],
               "severity":r["status"],"detail":r.get("detail","")}
              for r in results if r["status"] in ("fail","warn")][:40]

    RUNS[run_id].update({"status":"complete",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "summary":{"total_checks":total,"pass":t_pass,"fail":t_fail,
                   "warn":t_warn,"pass_rate":pass_rate,
                   "asset_count":len(assets),"blocked_assets":blocked},
        "categories":categories,"issues":issues})

    p_obj = PARTNERS.get(partner_id)
    if p_obj:
        p_obj["runs"].insert(0, run_id)
        p_obj["last_run"] = run_id
        p_obj["passed"] = t_pass; p_obj["failed"] = t_fail
        p_obj["warned"] = t_warn; p_obj["pass_rate"] = pass_rate
        p_obj["status"] = ("live" if pass_rate >= 95
                           else "remediation" if pass_rate >= 85 else "blocked")
    logger.info(f"Run {run_id} complete: {pass_rate}% pass, {t_fail} failures")


def _summary(p: dict) -> dict:
    return {"id":p["id"],"name":p["name"],"initial":p["initial"],
        "type":p["type"],"tier":p["tier"],"contract":p["contract"],
        "onboarded":p["onboarded"],"content_type":p["content_type"],
        "territories":p["territories"],"formats":p["formats"],
        "feed_type":p["feed_type"],"total_assets":p["total_assets"],
        "color1":p["color1"],"color2":p["color2"],"status":p["status"],
        "run_count":len(p["runs"]),"passed":p.get("passed"),
        "failed":p.get("failed"),"warned":p.get("warned"),
        "pass_rate":p.get("pass_rate"),"last_run":p.get("last_run")}


@app.get("/")
async def root():
    return {"service":"ContentFlow QA","version":"1.0.0","status":"ok"}

@app.get("/api/health")
async def health():
    return {"status":"healthy","partners":len(PARTNERS),"runs":len(RUNS)}

@app.get("/api/partners")
async def list_partners():
    return [_summary(p) for p in PARTNERS.values()]

@app.get("/api/partners/{partner_id}")
async def get_partner(partner_id: str):
    p = PARTNERS.get(partner_id)
    if not p:
        raise HTTPException(404, f"Partner '{partner_id}' not found")
    d = _summary(p)
    lr = p.get("last_run")
    if lr and lr in RUNS:
        run = RUNS[lr]
        d["latest_run"] = {"run_id":run["run_id"],"status":run["status"],
            "created_at":run["created_at"],"summary":run.get("summary",{}),
            "categories":run.get("categories",[]),"issues":run.get("issues",[])}
    d["run_history"] = [{"run_id":r,"created_at":RUNS[r]["created_at"],
        "pass_rate":RUNS[r].get("summary",{}).get("pass_rate"),
        "status":RUNS[r]["status"]} for r in p["runs"] if r in RUNS]
    return d

@app.post("/api/partners", status_code=201)
async def create_partner(body: PartnerCreate):
    pid = "".join(c for c in body.name.lower().replace(" ","-") if c.isalnum() or c=="-")
    if pid in PARTNERS:
        raise HTTPException(409, f"Partner '{body.name}' already exists")
    palette = [("#8b7ff8","#ec4899"),("#10b981","#06b6d4"),
               ("#f59e0b","#f43f5e"),("#6366f1","#8b5cf6"),("#14b8a6","#6366f1")]
    c1, c2 = palette[len(PARTNERS) % len(palette)]
    PARTNERS[pid] = {"id":pid,"name":body.name,"initial":body.name[0].upper(),
        "type":body.type,"tier":body.tier,
        "contract":f"CNT-2026-{len(PARTNERS)+1:03d}",
        "onboarded":datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "content_type":body.content_type,"territories":body.territories,
        "formats":body.formats,"feed_type":body.feed_type,
        "total_assets":body.total_assets,"color1":c1,"color2":c2,
        "status":"queued","runs":[]}
    logger.info(f"Partner created: {body.name}")
    return _summary(PARTNERS[pid])

@app.delete("/api/partners/{partner_id}")
async def delete_partner(partner_id: str):
    if partner_id not in PARTNERS:
        raise HTTPException(404, "Partner not found")
    return {"deleted": partner_id, "name": PARTNERS.pop(partner_id)["name"]}

@app.post("/api/partners/{partner_id}/runs", status_code=202)
async def trigger_run(partner_id: str, background: BackgroundTasks, asset_count: int = 300):
    p = PARTNERS.get(partner_id)
    if not p:
        raise HTTPException(404, f"Partner '{partner_id}' not found")
    run_id = f"run-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6]}"
    RUNS[run_id] = {"run_id":run_id,"partner_id":partner_id,
        "partner_name":p["name"],"status":"queued","asset_count":asset_count,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "summary":{},"categories":[],"issues":[]}
    background.add_task(_run_pipeline, run_id, partner_id, asset_count)
    return {"run_id":run_id,"status":"queued","asset_count":asset_count,"partner":p["name"]}

@app.get("/api/runs")
async def list_runs():
    return sorted([{k:v for k,v in r.items() if k != "issues"} for r in RUNS.values()],
                  key=lambda x: x["created_at"], reverse=True)

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return RUNS[run_id]

@app.get("/api/runs/{run_id}/report")
async def get_report(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] != "complete":
        raise HTTPException(400, f"Run is {run['status']}, not complete")
    s = run["summary"]; rate = s["pass_rate"]
    if s["fail"] == 0:
        rec = "All assets passed. Content cleared for go-live."
    elif rate >= 95:
        rec = f"{s['fail']} checks failed. Minor remediation required."
    elif rate >= 85:
        rec = f"Pass rate {rate}% — significant issues. Escalate to partner."
    else:
        rec = f"Pass rate {rate}% — critical failures. Do not go live."
    return {"run_id":run_id,"partner":run["partner_name"],
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "summary":s,"by_category":run["categories"],
        "issues":run["issues"],"recommendation":rec}

@app.get("/api/metrics")
async def platform_metrics():
    rated = [p for p in PARTNERS.values() if p.get("pass_rate") is not None]
    return {"partners":len(PARTNERS),
        "total_assets":sum(p["total_assets"] for p in PARTNERS.values()),
        "total_runs":len(RUNS),
        "passed":sum(p.get("passed",0) for p in PARTNERS.values()),
        "failed":sum(p.get("failed",0) for p in PARTNERS.values()),
        "warned":sum(p.get("warned",0) for p in PARTNERS.values()),
        "avg_pass_rate":round(sum(p["pass_rate"] for p in rated)/len(rated),1) if rated else None,
        "scenarios":40,"categories":len(VALIDATORS)}

@app.get("/api/scenarios")
async def list_scenarios():
    return [
        {"key":"metadata","label":"Metadata validation","description":"title, genre, rating, language, duration, year","checks":12},
        {"key":"xml_feed","label":"XML / Feed parsing","description":"XSD schema, encoding, namespaces, required elements","checks":8},
        {"key":"asset_check","label":"Asset availability","description":"URL reachability, HTTPS, CDN headers, redirects","checks":6},
        {"key":"media_probe","label":"FFmpeg media probe","description":"codec, bitrate, resolution, container, audio track","checks":8},
        {"key":"duplicate_ids","label":"Duplicate ID scan","description":"content_id uniqueness within batch and cross-partner","checks":3},
        {"key":"golive","label":"Go-live readiness","description":"rights windows, launch dates, ratings lock, territories","checks":3},
    ]

@app.post("/api/upload")
async def upload_feed(file: UploadFile = File(...)):
    content = await file.read()
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".xml", ".json"):
        raise HTTPException(400, "Only .xml and .json accepted")
    return {"filename":file.filename,"size_bytes":len(content),
        "type":ext.lstrip("."),"status":"received",
        "message":"Feed uploaded. Create a partner and trigger a run to validate."}
