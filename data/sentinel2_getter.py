"""
Sentinel-2 L2A pixel extraction for maize stages V6-V10.

Pre first run once per machine:
    uv run earthengine authenticate
"""

import csv
import io
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests
import ee
import shapefile

# --- Configuration
GEE_PROJECT = "hackil-2026"
METADATA_CSV = Path("data/tmp/site_year_metadata.csv")
SHAPEFILE_ZIP = Path("data/tmp/Plot_Boundaries_Shapefiles.zip")
OUT_DIR = Path("data/processed/remote_sensing")

BUFFER_M = 30
MAX_CLOUD_PCT = 30  # maximum scene-level cloud % (ESA pre-computed property)

# QA60 bit flags for L1C pixel-level cloud masking
_QA60_CLOUD_BIT = 1 << 10  # opaque clouds
_QA60_CIRRUS_BIT = 1 << 11  # cirrus
V_STAGE_OFFSETS = {"V6": 30, "V7": 34, "V8": 38, "V9": 42, "V10": 46}

_BANDS_IN = ["B2", "B3", "B4", "B5", "B8"]
_BANDS_OUT = ["blue", "green", "red", "rededge", "nir"]
_INDEX_BANDS = [
    "NDVI",
    "GNDVI",
    "NDRE",
    "EVI2",
    "CIrededge",
    "NIRv",
    "SAVI",
    "OSAVI",
    "TGI",
    "MCARI",
    "OCARI",
]
_FINAL_BANDS_IN = ["blue", "green", "red", "rededge", "nir"] + _INDEX_BANDS
_FINAL_BANDS_OUT = [
    "blue_B02",
    "green_B03",
    "red_B04",
    "rededge_B05",
    "nir_B08",
] + _INDEX_BANDS


# Shapefile helpers
def find_shapefile_path(trial: dict) -> str | None:
    """Find the .shp path inside SHAPEFILE_ZIP for a given trial.

    Searches the year/state subdirectory for a filename containing the site name.
    """
    year = str(int(float(trial["year"])))
    state = trial["state"]
    site = trial["site"].lower()
    prefix = f"Plot Boundaries Shapefiles/{year}/{state}/"

    with zipfile.ZipFile(SHAPEFILE_ZIP) as zf:
        shps = [n for n in zf.namelist() if n.startswith(prefix) and n.endswith(".shp")]

    # Exact site-name match first, then best partial match
    exact = [p for p in shps if site in Path(p).stem.lower()]
    if exact:
        return exact[0]
    if shps:
        scored = sorted(
            shps,
            key=lambda p: sum(c in Path(p).stem.lower() for c in site),
            reverse=True,
        )
        return scored[0]
    return None


def shapefile_to_ee(shp_zip_path: str) -> ee.FeatureCollection:
    """Read a shapefile from SHAPEFILE_ZIP and return an ee.FeatureCollection."""
    base = shp_zip_path[:-4]
    with zipfile.ZipFile(SHAPEFILE_ZIP) as zf:
        shp_bytes = zf.read(shp_zip_path)
        dbf_bytes = zf.read(base + ".dbf")

    sf = shapefile.Reader(shp=io.BytesIO(shp_bytes), dbf=io.BytesIO(dbf_bytes))
    fields = [f[0] for f in sf.fields[1:]]  # skip deletion flag

    features = []
    for sr in sf.shapeRecords():
        geom = sr.shape.__geo_interface__
        props = {k: v for k, v in zip(fields, sr.record)}
        features.append(ee.Feature(ee.Geometry(geom), props))

    return ee.FeatureCollection(features)


# GEE image processing
def _cloud_mask(image: ee.Image) -> ee.Image:
    qa60 = image.select("QA60")
    return (
        qa60.bitwiseAnd(_QA60_CLOUD_BIT)
        .eq(0)
        .And(qa60.bitwiseAnd(_QA60_CIRRUS_BIT).eq(0))
    )


def _add_indices(image: ee.Image) -> ee.Image:
    blue = image.select("blue")
    green = image.select("green")
    red = image.select("red")
    rededge = image.select("rededge")
    nir = image.select("nir")

    ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
    gndvi = nir.subtract(green).divide(nir.add(green)).rename("GNDVI")
    ndre = nir.subtract(rededge).divide(nir.add(rededge)).rename("NDRE")
    evi2 = (
        nir.subtract(red)
        .divide(nir.add(red.multiply(2.4)).add(1))
        .multiply(2.5)
        .rename("EVI2")
    )
    ci_re = nir.divide(rededge).subtract(1).rename("CIrededge")
    nirv = nir.multiply(ndvi).rename("NIRv")
    savi = nir.subtract(red).divide(nir.add(red).add(0.5)).multiply(1.5).rename("SAVI")
    osavi = nir.subtract(red).divide(nir.add(red).add(0.16)).rename("OSAVI")
    tgi = green.subtract(red.multiply(0.39)).subtract(blue.multiply(0.61)).rename("TGI")
    mcari = (
        rededge.subtract(red)
        .subtract(rededge.subtract(green).multiply(0.2))
        .multiply(rededge.divide(red))
        .rename("MCARI")
    )
    ocari = (
        rededge.subtract(red)
        .subtract(rededge.subtract(green).multiply(0.2))
        .divide(rededge.divide(red))
        .rename("OCARI")
    )

    return image.addBands(
        [ndvi, gndvi, ndre, evi2, ci_re, nirv, savi, osavi, tgi, mcari, ocari]
    )


def _build_clear_collection(
    aoi: ee.Geometry, date_start: str, date_end: str
) -> ee.ImageCollection:
    return (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(date_start, date_end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUD_PCT))
    )


def _process_stage(
    stage: str,
    target_date: str,
    clear_imgs: ee.ImageCollection,
    plots: ee.FeatureCollection,
    trial_meta: dict,
) -> ee.FeatureCollection:
    target = ee.Date(target_date)

    # Sort by proximity to target date
    sorted_imgs = clear_imgs.map(
        lambda img: img.set("date_diff", img.date().difference(target, "day").abs())
    ).sort("date_diff")

    # Apply cloud mask + indices to each image, then mosaic in date-proximity order.
    # This picks the nearest-in-time cloud-free pixel at each location, so a plot
    # that is fully clouded in the closest image still gets valid values from the
    # second-closest image, etc.
    def _mask_and_prep(img):
        refl = (
            img.select(_BANDS_IN, _BANDS_OUT)
            .resample("bilinear")
            .multiply(0.0001)
            .updateMask(_cloud_mask(img))
        )
        return _add_indices(refl).select(_FINAL_BANDS_IN, _FINAL_BANDS_OUT)

    with_idx = sorted_imgs.map(_mask_and_prep).mosaic()

    # Use the closest image's metadata (date, id) for annotation
    closest = sorted_imgs.first()
    proj = closest.select("B2").projection()

    # Zonal statistics: mean of all 10 m pixels within each plot polygon
    plot_means = with_idx.reduceRegions(
        collection=plots,
        reducer=ee.Reducer.mean(),
        scale=10,
        crs=proj,
    )
    # Drop plots where all pixels were cloud-masked (mean will be null)
    plot_means = plot_means.filter(ee.Filter.notNull([_FINAL_BANDS_OUT[0]]))

    image_date = closest.date().format("YYYY-MM-dd")
    image_id = closest.get("system:index")
    trial_num = int(float(trial_meta["trial"]))
    site = trial_meta["site"]
    state = trial_meta["state"]
    year = int(float(trial_meta["year"]))

    def annotate_plot(f):
        return (
            f.set("stage", stage)
            .set("image_date", image_date)
            .set("image_id", image_id)
            .set("trial", trial_num)
            .set("site", site)
            .set("state", state)
            .set("year", year)
            # Normalize shapefile column names to lowercase
            .set("plot_id", f.get("Plot_ID"))
            .set("block", f.get("Block"))
            .set("n_trt", f.get("N_Trt"))
            .set("plant_n", f.get("Plant_N"))
            .set("side_n", f.get("Side_N"))
        )

    return plot_means.map(annotate_plot)


def download_trial(trial: dict) -> Path | None:
    """Compute and download GEE pixel data for one site-year directly to disk."""
    trial_id = int(float(trial["trial"]))
    fname = f"s2_trial{trial_id:02d}_{trial['state']}_{trial['site']}_{trial['year']}.geojson"
    out_path = OUT_DIR / fname

    if out_path.exists():
        # Validate existing file has spectral data (not just geometry/metadata)
        gj = json.loads(out_path.read_bytes())
        feats = gj.get("features", [])
        if feats and _FINAL_BANDS_OUT[0] not in (feats[0].get("properties") or {}):
            print(
                f"  [INVALID] {fname} has no spectral data — deleting and reprocessing"
            )
            out_path.unlink()
        else:
            print(f"  [SKIP] Already exists: {fname}")
            return out_path

    shp_path = find_shapefile_path(trial)
    if shp_path is None:
        print(
            f"  [SKIP] No shapefile: trial {trial_id} {trial['state']}-{trial['site']} {trial['year']}"
        )
        return None

    plots = shapefile_to_ee(shp_path)
    aoi = plots.union().geometry().buffer(BUFFER_M)

    planting = datetime.strptime(trial["planting_date"], "%Y-%m-%d")
    date_start = (planting + timedelta(days=V_STAGE_OFFSETS["V6"] - 4)).strftime(
        "%Y-%m-%d"
    )
    date_end = (planting + timedelta(days=V_STAGE_OFFSETS["V10"] + 4)).strftime(
        "%Y-%m-%d"
    )

    clear_imgs = _build_clear_collection(aoi, date_start, date_end)

    n_clear = clear_imgs.size().getInfo()
    if n_clear == 0:
        print(f"  [SKIP] No clear S2 images in {date_start} → {date_end}")
        return None
    print(f"  ({n_clear} clear images) ", end="", flush=True)

    all_pixels: ee.FeatureCollection | None = None
    for stage, offset in V_STAGE_OFFSETS.items():
        target = (planting + timedelta(days=offset)).strftime("%Y-%m-%d")
        fc = _process_stage(stage, target, clear_imgs, plots, trial)
        all_pixels = fc if all_pixels is None else all_pixels.merge(fc)

    n_features = all_pixels.size().getInfo()
    if n_features == 0:
        print(
            f"  [SKIP] All pixels masked after cloud filtering ({n_clear} images had full cloud cover over AOI)"
        )
        return None

    url = all_pixels.getDownloadURL(filetype="geojson", filename=fname[:-8])
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    out_path.write_bytes(response.content)

    # Validate: check that spectral columns actually exist in the downloaded file
    gj = json.loads(response.content)
    feats = gj.get("features", [])
    if feats and _FINAL_BANDS_OUT[0] not in (feats[0].get("properties") or {}):
        out_path.unlink()
        print(
            f"  [SKIP] Downloaded but all pixels cloud-masked (no spectral data); file deleted."
        )
        return None

    return out_path


def main() -> None:
    ee.Initialize(project=GEE_PROJECT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(METADATA_CSV) as f:
        site_years = list(csv.DictReader(f))

    print(f"Processing {len(site_years)} site-years → {OUT_DIR}/")
    ok, failed = 0, []

    for sy in site_years:
        trial_id = int(float(sy["trial"]))
        label = f"trial{trial_id:02d}_{sy['state']}_{sy['site']}_{sy['year']}"
        print(f"  {label} ...", end=" ", flush=True)
        try:
            path = download_trial(sy)
            if path:
                print(f"saved ({path.stat().st_size // 1024} KB)")
                ok += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append(label)

    print(f"\nDone: {ok} saved, {len(failed)} failed.")
    if failed:
        print("Failed trials:", failed)


if __name__ == "__main__":
    main()
