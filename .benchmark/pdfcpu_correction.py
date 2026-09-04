#!/usr/bin/env python3
"""Corrected pdfcpu timing and parity follow-up for the image-to-PDF benchmark."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path.cwd()
LABEL = os.environ["BENCHMARK_LABEL"]
HARNESS = ROOT / ".benchmark" / "run_benchmark.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("corrected_benchmark_harness", HARNESS)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import benchmark harness")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_pdf(bench, tools, pdf: Path, pages: int) -> dict[str, object]:
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
        "qpdf_check": True,
    }


def run_visual_qa(bench, tools, corpus, artifact: Path) -> dict[str, object]:
    pdf_dir = artifact / "visual-pdfs"
    render_dir = artifact / "renders"
    work_dir = artifact / "visual-work"
    pdf_dir.mkdir()
    render_dir.mkdir()
    work_dir.mkdir()
    pages_per_profile = 8
    aggregate_errors: list[np.ndarray] = []
    per_page: dict[str, list[dict[str, object]]] = {}
    structural: dict[str, dict[str, object]] = {}
    for profile in bench.PROFILES:
        inputs = corpus[profile][:pages_per_profile]
        baseline_pdf = pdf_dir / f"{profile}-imagemagick.pdf"
        candidate_pdf = pdf_dir / f"{profile}-vips-pdfcpu.pdf"
        bench.pipeline_imagemagick(tools, inputs, baseline_pdf)
        workspace = work_dir / profile
        workspace.mkdir()
        bench.pipeline_vips_pdfcpu(tools, inputs, candidate_pdf, workspace)
        shutil.rmtree(workspace)
        structural[f"{profile}/imagemagick"] = validate_pdf(
            bench, tools, baseline_pdf, pages_per_profile
        )
        structural[f"{profile}/vips-pdfcpu"] = validate_pdf(
            bench, tools, candidate_pdf, pages_per_profile
        )
        baseline_pages: dict[int, np.ndarray] = {}
        candidate_pages: dict[int, np.ndarray] = {}
        for page in range(1, pages_per_profile + 1):
            baseline_png = render_dir / f"{profile}-imagemagick-p{page:02d}.png"
            candidate_png = render_dir / f"{profile}-vips-pdfcpu-p{page:02d}.png"
            bench.render_sample(tools, baseline_pdf, baseline_png, page)
            bench.render_sample(tools, candidate_pdf, candidate_png, page)
            with Image.open(baseline_png) as image:
                baseline_pages[page] = np.asarray(image.convert("RGB"), dtype=np.int16)
            with Image.open(candidate_png) as image:
                candidate_pages[page] = np.asarray(image.convert("RGB"), dtype=np.int16)
        rows: list[dict[str, object]] = []
        for page in range(1, pages_per_profile + 1):
            baseline = baseline_pages[page]
            candidate = candidate_pages[page]
            if baseline.shape != candidate.shape:
                raise RuntimeError(f"render shape mismatch: {profile} page {page}")
            error = np.abs(candidate - baseline)
            aggregate_errors.append(error.reshape(-1))
            nearest = min(
                baseline_pages,
                key=lambda other: float(np.abs(candidate - baseline_pages[other]).mean()),
            )
            rows.append(
                {
                    "page": page,
                    "nearest_imagemagick_page": nearest,
                    "order_match": nearest == page,
                    "mean_absolute_channel_error_0_255": float(error.mean()),
                    "p99_absolute_channel_error_0_255": float(np.percentile(error, 99)),
                    "max_absolute_channel_error_0_255": int(error.max()),
                }
            )
        per_page[profile] = rows
    flattened = np.concatenate(aggregate_errors)
    result = {
        "contract": {
            "baseline": "imagemagick",
            "profiles": list(bench.PROFILES),
            "pages_per_profile": pages_per_profile,
            "pages_compared": len(bench.PROFILES) * pages_per_profile,
            "render_dpi": 36,
        },
        "aggregate": {
            "all_pages_in_correct_order": all(
                row["order_match"] for rows in per_page.values() for row in rows
            ),
            "mean_absolute_channel_error_0_255": float(flattened.mean()),
            "p99_absolute_channel_error_0_255": float(np.percentile(flattened, 99)),
            "max_absolute_channel_error_0_255": int(flattened.max()),
        },
        "structural": structural,
        "per_page": per_page,
    }
    shutil.rmtree(pdf_dir)
    shutil.rmtree(work_dir)
    return result


def main() -> int:
    bench = load_harness()
    artifact = ROOT / f"pdfcpu-correction-{LABEL}"
    artifact.mkdir()
    corpus = bench.generate_corpus(artifact / "corpus")
    bench.write_corpus_manifest(corpus, artifact / "corpus-manifest.csv")
    tools = bench.detect_toolchain()
    environment = bench.collect_environment(tools)
    environment["correction"] = {
        "old_pdfcpu_description": "dim:595.44 841.68, pos:c, dpi:300",
        "new_pdfcpu_description": "dim:595.44 841.68, pos:full",
        "reason": (
            "Remove pdfcpu's default 0.5 relative scale and place the already "
            "page-sized JPEG over the full page."
        ),
    }
    (artifact / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.copy2(
        ROOT / ".benchmark" / "patched-harness-SHA256SUMS",
        artifact / "patched-harness-SHA256SUMS",
    )
    shutil.copy2(HARNESS, artifact / "run_benchmark.py")
    run_root = artifact / "working" / "runs"
    run_root.mkdir(parents=True)
    measurements = []
    for profile in bench.PROFILES:
        for size in bench.SCENARIO_SIZES:
            inputs = corpus[profile][:size]
            print(f"WARMUP {profile}-{size}", flush=True)
            measurements.append(
                bench.measure_one(
                    tools=tools,
                    pipeline="vips-pdfcpu",
                    profile=profile,
                    inputs=inputs,
                    repetition=0,
                    warmup=True,
                    order_position=1,
                    run_root=run_root,
                )
            )
            for repetition in range(1, bench.MEASURED_REPEATS + 1):
                result = bench.measure_one(
                    tools=tools,
                    pipeline="vips-pdfcpu",
                    profile=profile,
                    inputs=inputs,
                    repetition=repetition,
                    warmup=False,
                    order_position=1,
                    run_root=run_root,
                )
                measurements.append(result)
                print(
                    f"MEASURE {profile}-{size} r{repetition}: "
                    f"{result.wall_seconds:.3f}s, "
                    f"RSS={result.peak_child_rss_bytes / (1024**2):.1f}MiB, "
                    f"out={result.final_pdf_bytes / (1024**2):.1f}MiB",
                    flush=True,
                )
    bench.write_raw_csv(measurements, artifact / "raw-results.csv")
    bench.write_dict_csv(bench.summarize(measurements), artifact / "scenario-summary.csv")
    visual = run_visual_qa(bench, tools, corpus, artifact)
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
