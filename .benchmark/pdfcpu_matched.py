#!/usr/bin/env python3
"""Matched ImageMagick vs corrected vips+pdfcpu benchmark and parity QA."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path.cwd()
LABEL = os.environ["BENCHMARK_LABEL"]
HARNESS = ROOT / ".benchmark" / "run_benchmark.py"
PIPELINES = ("imagemagick", "vips-pdfcpu")


def load_harness():
    spec = importlib.util.spec_from_file_location("pdfcpu_matched_harness", HARNESS)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import benchmark harness")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_pipeline(bench, tools, pipeline: str, inputs, output: Path, workspace: Path) -> None:
    if pipeline == "imagemagick":
        bench.pipeline_imagemagick(tools, inputs, output)
    elif pipeline == "vips-pdfcpu":
        bench.pipeline_vips_pdfcpu(tools, inputs, output, workspace)
    else:
        raise RuntimeError(pipeline)


def validate(bench, tools, pdf: Path, pages: int) -> dict[str, object]:
    count, width, height = bench.parse_pdfinfo(tools, pdf, pages)
    checked = subprocess.run(
        [tools.qpdf, "--check", str(pdf)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if checked.returncode != 0:
        raise RuntimeError(checked.stderr.decode("utf-8", "replace"))
    return {
        "pages": count,
        "page_width_pt": width,
        "page_height_pt": height,
        "pdf_bytes": pdf.stat().st_size,
        "qpdf_check": True,
    }


def visual_qa(bench, tools, corpus, artifact: Path) -> dict[str, object]:
    pdf_dir = artifact / "visual-pdfs"
    render_dir = artifact / "renders"
    work_dir = artifact / "visual-work"
    pdf_dir.mkdir()
    render_dir.mkdir()
    work_dir.mkdir()
    pages_per_profile = 8
    structural: dict[str, object] = {}
    per_page: dict[str, list[dict[str, object]]] = {}
    all_errors: list[np.ndarray] = []
    for profile in bench.PROFILES:
        inputs = corpus[profile][:pages_per_profile]
        rendered: dict[str, dict[int, np.ndarray]] = {pipeline: {} for pipeline in PIPELINES}
        for pipeline in PIPELINES:
            workspace = work_dir / f"{profile}-{pipeline}"
            workspace.mkdir()
            pdf = pdf_dir / f"{profile}-{pipeline}.pdf"
            run_pipeline(bench, tools, pipeline, inputs, pdf, workspace)
            structural[f"{profile}/{pipeline}"] = validate(
                bench, tools, pdf, pages_per_profile
            )
            for page in range(1, pages_per_profile + 1):
                png = render_dir / f"{profile}-{pipeline}-p{page:02d}.png"
                bench.render_sample(tools, pdf, png, page)
                with Image.open(png) as image:
                    rendered[pipeline][page] = np.asarray(
                        image.convert("RGB"), dtype=np.int16
                    )
            shutil.rmtree(workspace)
        rows: list[dict[str, object]] = []
        for page in range(1, pages_per_profile + 1):
            baseline = rendered["imagemagick"][page]
            candidate = rendered["vips-pdfcpu"][page]
            if candidate.shape != baseline.shape:
                raise RuntimeError(
                    f"render shape mismatch {profile}/p{page}: "
                    f"{candidate.shape} != {baseline.shape}"
                )
            error = np.abs(candidate - baseline)
            all_errors.append(error.reshape(-1))
            nearest = min(
                rendered["imagemagick"],
                key=lambda other: float(
                    np.abs(candidate - rendered["imagemagick"][other]).mean()
                ),
            )
            rows.append(
                {
                    "page": page,
                    "nearest_imagemagick_page": nearest,
                    "order_match": nearest == page,
                    "mean_absolute_channel_error_0_255": float(error.mean()),
                    "p99_absolute_channel_error_0_255": float(
                        np.percentile(error, 99)
                    ),
                    "max_absolute_channel_error_0_255": int(error.max()),
                    "render_width": int(candidate.shape[1]),
                    "render_height": int(candidate.shape[0]),
                }
            )
        per_page[profile] = rows
    flattened = np.concatenate(all_errors)
    aggregate = {
        "pages_compared": len(bench.PROFILES) * pages_per_profile,
        "all_pages_in_correct_order": all(
            row["order_match"] for rows in per_page.values() for row in rows
        ),
        "mean_absolute_channel_error_0_255": float(flattened.mean()),
        "p99_absolute_channel_error_0_255": float(np.percentile(flattened, 99)),
        "max_absolute_channel_error_0_255": int(flattened.max()),
    }
    shutil.rmtree(pdf_dir)
    shutil.rmtree(work_dir)
    return {
        "contract": {
            "baseline": "imagemagick",
            "candidate": "vips-pdfcpu",
            "profiles": list(bench.PROFILES),
            "pages_per_profile": pages_per_profile,
            "render_dpi": 36,
        },
        "aggregate": aggregate,
        "structural": structural,
        "per_page": per_page,
    }


def main() -> int:
    bench = load_harness()
    artifact = ROOT / f"pdfcpu-matched-{LABEL}"
    artifact.mkdir()
    corpus = bench.generate_corpus(artifact / "corpus")
    bench.write_corpus_manifest(corpus, artifact / "corpus-manifest.csv")
    tools = bench.detect_toolchain()
    environment = bench.collect_environment(tools)
    environment["pdfcpu_correction"] = {
        "description": (
            "dim:A4-equivalent, centered, sc:1 rel; this overrides pdfcpu's "
            "default relative scale of 0.5 while retaining explicit A4 page size."
        )
    }
    (artifact / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.copy2(ROOT / ".benchmark" / "patched-harness-SHA256SUMS", artifact)
    shutil.copy2(HARNESS, artifact / "run_benchmark.py")
    run_root = artifact / "working" / "runs"
    run_root.mkdir(parents=True)
    measurements = []
    rng = random.Random(2026090403)
    for profile in bench.PROFILES:
        for size in bench.SCENARIO_SIZES:
            inputs = corpus[profile][:size]
            warmup_order = list(PIPELINES)
            rng.shuffle(warmup_order)
            print(f"WARMUP {profile}-{size}: {warmup_order}", flush=True)
            for position, pipeline in enumerate(warmup_order, start=1):
                measurements.append(
                    bench.measure_one(
                        tools=tools,
                        pipeline=pipeline,
                        profile=profile,
                        inputs=inputs,
                        repetition=0,
                        warmup=True,
                        order_position=position,
                        run_root=run_root,
                    )
                )
            for repetition in range(1, bench.MEASURED_REPEATS + 1):
                order = list(PIPELINES)
                rng.shuffle(order)
                print(f"MEASURE {profile}-{size} r{repetition}: {order}", flush=True)
                for position, pipeline in enumerate(order, start=1):
                    result = bench.measure_one(
                        tools=tools,
                        pipeline=pipeline,
                        profile=profile,
                        inputs=inputs,
                        repetition=repetition,
                        warmup=False,
                        order_position=position,
                        run_root=run_root,
                    )
                    measurements.append(result)
                    print(
                        f"  {pipeline}: {result.wall_seconds:.3f}s, "
                        f"RSS={result.peak_child_rss_bytes / (1024**2):.1f}MiB, "
                        f"out={result.final_pdf_bytes / (1024**2):.1f}MiB",
                        flush=True,
                    )
    bench.write_raw_csv(measurements, artifact / "raw-results.csv")
    summary = bench.summarize(measurements)
    bench.write_dict_csv(summary, artifact / "scenario-summary.csv")
    aggregates = []
    for pipeline in PIPELINES:
        rows = [row for row in summary if row["pipeline"] == pipeline]
        total_seconds = sum(float(row["wall_median_s"]) for row in rows)
        total_pages = sum(int(row["pages"]) for row in rows)
        aggregates.append(
            {
                "pipeline": pipeline,
                "scenario_count": len(rows),
                "sum_of_scenario_medians_seconds": total_seconds,
                "total_scenario_pages": total_pages,
                "aggregate_pages_per_second": total_pages / total_seconds,
                "median_peak_child_rss_mib": float(
                    np.median([float(row["peak_child_rss_median_mib"]) for row in rows])
                ),
                "max_peak_child_rss_mib": max(
                    float(row["peak_child_rss_median_mib"]) for row in rows
                ),
                "median_output_mib": float(
                    np.median([float(row["output_median_mib"]) for row in rows])
                ),
                "median_peak_workspace_mib": float(
                    np.median([float(row["peak_workspace_median_mib"]) for row in rows])
                ),
            }
        )
    bench.write_dict_csv(aggregates, artifact / "pipeline-summary.csv")
    visual = visual_qa(bench, tools, corpus, artifact)
    (artifact / "visual-qa.json").write_text(
        json.dumps(visual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(visual["aggregate"], indent=2, sort_keys=True), flush=True)
    shutil.rmtree(artifact / "corpus")
    shutil.rmtree(artifact / "working")
    checksum_lines = []
    for path in sorted(artifact.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            checksum_lines.append(f"{digest}  {path.relative_to(artifact).as_posix()}")
    (artifact / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
