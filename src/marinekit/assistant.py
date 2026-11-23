"""'Ask the Black Sea': a Claude assistant that answers questions about the loaded buoy data
by calling local pandas tools (stats, events, time series, charts).

Credentials: ANTHROPIC_API_KEY, or an `ant auth login` profile, are picked up automatically.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from . import buoy

MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 8

SYSTEM = """You are a marine-data assistant for the EfxINNOs project (Black Sea, NIMRD "Grigore Antipa", Constanța).
You answer questions from coastal managers, policymakers and scientists about monitoring data from smart buoys,
AUVs and ROVs. Use the tools to look at the actual data before answering; never invent numbers.
Keep answers short and plain-language: lead with the answer, then 1-3 supporting numbers with dates and units.
When a trend or event is easier to see than to read, call plot_timeseries. When relevant, mention which EU MSFD
descriptor an issue relates to (D5 eutrophication, D1 biodiversity, D10 litter, D6 seafloor integrity).
If the data cannot answer the question, say so and suggest what data would."""

TOOLS = [
    {
        "name": "describe_dataset",
        "description": "List the variables in the loaded buoy dataset with units, coverage, value ranges and the time span. Call this first if unsure what data exists.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_stats",
        "description": "Summary statistics (mean/min/max/std and the times of min and max) for one variable over a time window, optionally resampled (e.g. '1D' daily, '1W' weekly).",
        "input_schema": {
            "type": "object",
            "properties": {
                "variable": {"type": "string", "description": "Canonical column name, e.g. temp, sal, do, chl, turb, ph"},
                "start": {"type": "string", "description": "ISO date/time, optional"},
                "end": {"type": "string", "description": "ISO date/time, optional"},
                "resample": {"type": "string", "description": "Pandas offset alias like '1D' to get a resampled table, optional"},
            },
            "required": ["variable"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_events",
        "description": "Detected environmental events (hypoxia, algal bloom, warm-water episode, low pH, high turbidity, sensor anomalies) with start/end, peak value and severity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["hypoxia", "bloom", "heatwave", "low_ph", "turbidity", "anomaly", "all"]},
                "start": {"type": "string"},
                "end": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "plot_timeseries",
        "description": "Show the user a time-series chart of one or more variables over a window. Returns a short confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "variables": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["variables"],
            "additionalProperties": False,
        },
    },
]


@dataclass
class DataContext:
    df: pd.DataFrame
    events: pd.DataFrame
    charts: list[dict] = field(default_factory=list)  # filled by plot_timeseries; the UI renders these

    def window(self, start=None, end=None) -> pd.DataFrame:
        return self.df.loc[start or None: end or None]


def _fmt(x):
    if isinstance(x, pd.Timestamp):
        return x.isoformat(sep=" ", timespec="minutes")
    if isinstance(x, float):
        return round(x, 3)
    return x


def run_tool(name: str, args: dict, ctx: DataContext) -> str:
    df = ctx.df
    if name == "describe_dataset":
        units = df.attrs.get("units", {})
        cols = {v: {"unit": units.get(v, ""), "coverage_%": round(100 * df[v].notna().mean(), 1),
                    "min": _fmt(float(df[v].min())), "max": _fmt(float(df[v].max()))} for v in buoy.numeric_vars(df)}
        return json.dumps({"time_start": _fmt(df.index.min()), "time_end": _fmt(df.index.max()), "rows": len(df),
                           "location": {"lat": _fmt(float(df["lat"].iloc[0])), "lon": _fmt(float(df["lon"].iloc[0]))} if "lat" in df else None,
                           "variables": cols})
    if name == "get_stats":
        v = args["variable"]
        if v not in df:
            return json.dumps({"error": f"unknown variable {v}", "available": buoy.numeric_vars(df)})
        s = ctx.window(args.get("start"), args.get("end"))[v].dropna()
        if s.empty:
            return json.dumps({"error": "no data in that window"})
        if args.get("resample"):
            r = s.resample(args["resample"]).agg(["mean", "min", "max"]).round(3).tail(60)
            return r.reset_index().astype({s.index.name or "time": str}).to_json(orient="records")
        return json.dumps({"variable": v, "n": int(s.size), "mean": _fmt(float(s.mean())), "min": _fmt(float(s.min())),
                           "min_time": _fmt(s.idxmin()), "max": _fmt(float(s.max())), "max_time": _fmt(s.idxmax()),
                           "std": _fmt(float(s.std())), "from": _fmt(s.index.min()), "to": _fmt(s.index.max())})
    if name == "list_events":
        ev = ctx.events
        if args.get("kind") and args["kind"] != "all":
            ev = ev[ev.kind == args["kind"]]
        if args.get("start"):
            ev = ev[ev.end >= pd.Timestamp(args["start"])]
        if args.get("end"):
            ev = ev[ev.start <= pd.Timestamp(args["end"])]
        ev = ev.head(30).copy()
        for c in ("start", "end", "peak_time"):
            ev[c] = ev[c].map(_fmt)
        return ev.to_json(orient="records") if len(ev) else json.dumps({"events": [], "note": "no matching events"})
    if name == "plot_timeseries":
        vs = [v for v in args["variables"] if v in df]
        if not vs:
            return json.dumps({"error": "none of those variables exist", "available": buoy.numeric_vars(df)})
        ctx.charts.append({"variables": vs, "start": args.get("start"), "end": args.get("end"), "title": args.get("title", "")})
        return json.dumps({"ok": True, "shown": vs})
    return json.dumps({"error": f"unknown tool {name}"})


def ask(client, history: list, question: str, ctx: DataContext, effort: str = "medium") -> tuple[str, list]:
    """Run one user turn through the tool loop. Mutates and returns `history` (full content blocks kept)."""
    history.append({"role": "user", "content": question})
    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            messages=history,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # re-run on a fallback model if the request is declined
        )
        history.append({"role": "assistant", "content": resp.content})  # keep thinking/tool blocks intact
        if resp.stop_reason == "refusal":
            return "Sorry, I can't help with that request.", history
        if resp.stop_reason != "tool_use":
            return "\n".join(b.text for b in resp.content if b.type == "text"), history
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                try:
                    out, err = run_tool(b.name, dict(b.input), ctx), False
                except Exception as e:  # report tool failures to the model instead of crashing the UI
                    out, err = json.dumps({"error": str(e)}), True
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out, "is_error": err})
        history.append({"role": "user", "content": results})
    return "I needed too many steps to answer that. Try a narrower question.", history
