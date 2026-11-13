"""The run server. The private viewer hands out short tokens; nothing else gets in."""

import base64
import hashlib
import hmac
import io
import json
import os
import queue
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image
from pydantic import BaseModel

from . import live, run_store, safety

CLIENT = os.environ.get("CLIENT", "example")
DAILY_RUNS = int(os.environ.get("DAILY_RUNS", "20"))
DAILY_IDEAS = int(os.environ.get("DAILY_IDEAS", "100"))
DAILY_MEASURES = int(os.environ.get("DAILY_MEASURES", "200"))
MEASURE_MAX_PAGES = 8
SECRET = os.environ.get("RUN_SECRET", "")
# KEEP_RUNS=0: nothing about a run is saved. Screenshots go back inline with the
# result and the working files are deleted when the run ends. Only the daily run
# count is kept, as a cap on spend.
KEEP_RUNS = os.environ.get("KEEP_RUNS", "1") != "0"
INLINE_WIDTH = 720
RUN_ID = "abcdef0123456789"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("VIEWER_ORIGIN", "").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def no_index(request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def require_token(authorization: str = Header("")):
    token = authorization.removeprefix("Bearer ")
    expires, _, signature = token.partition(".")
    good = hmac.new(SECRET.encode(), expires.encode(), hashlib.sha256).hexdigest()
    if not SECRET or not hmac.compare_digest(signature, good) or not expires.isdigit() or int(expires) < time.time():
        raise HTTPException(401)


class Job(BaseModel):
    csv: str
    selected: list[str] = []
    custom: list[dict] = []
    words: bool = True


class IdeaJob(Job):
    count: int = 5


def store_shot(run_id, name, data):
    if not KEEP_RUNS:
        return inline_shot(name, data)
    run_store.put(f"{run_id}/{name}", data, "image/jpeg")
    return f"{os.environ.get('PUBLIC_URL', '')}/runs/{run_id}/{name}"


def inline_shot(name, data):
    """The top of the page only, small, as a data URL. Full-page shots are dropped."""
    if not name.endswith("-fold.jpg"):
        return None
    image = Image.open(io.BytesIO(data))
    if image.width > INLINE_WIDTH:
        image = image.resize((INLINE_WIDTH, round(image.height * INLINE_WIDTH / image.width)))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def stream(job, rows, metric):
    """Runs a few minutes, so progress goes out line by line over one open request."""
    events = queue.Queue()

    def work():
        try:
            result = live.execute(rows, metric, job.selected, job.custom, CLIENT, events.put, store_shot, job.words)
            if KEEP_RUNS:
                run_store.put(f"{result['run_id']}/result.json", json.dumps(result, default=str), "application/json")
            events.put({"stage": "done", "result": result})
        except live.BadInput as err:
            events.put({"stage": "error", "message": str(err)})
        except Exception as err:
            print(f"Run failed: {err}", flush=True)
            events.put({"stage": "error", "message": "The run failed. Try again."})
        events.put(None)

    threading.Thread(target=work, daemon=True).start()
    while (event := events.get()) is not None:
        yield json.dumps(event, default=str) + "\n"


@app.post("/run", dependencies=[Depends(require_token)])
def run(job: Job):
    try:
        rows, metric = live.parse_rows(job.csv)
        for row in rows:
            safety.check_url(row["url"])
    except (live.BadInput, safety.UnsafeUrl) as err:
        raise HTTPException(422, str(err)) from None
    if not run_store.take_daily_slot(DAILY_RUNS):
        raise HTTPException(429, "Today's run limit is used up. Try again tomorrow.")
    return StreamingResponse(stream(job, rows, metric), media_type="application/x-ndjson")


@app.post("/ideas", dependencies=[Depends(require_token)])
def ideas(job: IdeaJob):
    if not run_store.take_daily_slot(DAILY_IDEAS, kind="ideas"):
        raise HTTPException(429, "Today's ideas limit is used up. Try again tomorrow.")
    try:
        return {"ideas": live.ideas(job.csv, job.count, job.selected, job.custom, CLIENT)}
    except (live.BadInput, safety.UnsafeUrl, ValueError) as err:
        raise HTTPException(422, str(err)) from None
    except Exception:
        raise HTTPException(502, "Couldn't get ideas right now. Try again.") from None


class MeasureJob(BaseModel):
    urls: list[str]


@app.post("/measure", dependencies=[Depends(require_token)])
def measure(job: MeasureJob):
    """Screenshots, text and code measures for up to 8 pages. No AI runs; the caller's
    assistant tags the pages. Capped per day because a browser run costs compute."""
    urls = [u.strip() for u in job.urls if u.strip()]
    if not 1 <= len(urls) <= MEASURE_MAX_PAGES:
        raise HTTPException(422, f"Send 1 to {MEASURE_MAX_PAGES} page addresses at a time.")
    try:
        for url in urls:
            safety.check_url(url)
    except safety.UnsafeUrl as err:
        raise HTTPException(422, str(err)) from None
    if not run_store.take_daily_slot(DAILY_MEASURES, kind="measure"):
        raise HTTPException(429, "Today's page limit is used up. Try again tomorrow.")
    try:
        return live.measure_pages(urls, CLIENT)
    except Exception:
        raise HTTPException(502, "Couldn't open those pages right now. Try again.") from None


@app.get("/catalog")
def catalog():
    """The attributes a run can check, with the defaults marked. Not secret."""
    return {"attributes": live.catalog(CLIENT), "min_pages": live.MIN_PAGES, "max_pages": live.MAX_PAGES}


@app.get("/runs/{run_id}/{name}")
def stored(run_id: str, name: str):
    """Run ids are long and random, so an image tag can load these without a token."""
    if len(run_id) != 32 or set(run_id) - set(RUN_ID) or "/" in name or ".." in name:
        raise HTTPException(404)
    data = run_store.get(f"{run_id}/{name}")
    if data is None:
        raise HTTPException(404)
    return Response(data, media_type="application/json" if name.endswith(".json") else "image/jpeg")


@app.get("/health")
def health():
    return {"ok": True}
