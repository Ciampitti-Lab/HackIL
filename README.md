<div align="center">

# Boilermakers Bushels: N Scout
***[Precision & Digital Agriculture Hackathon (UIUC - 2026)](https://digitalag.illinois.edu/precision-digital-agriculture-hackathon/)***

**Nitrogen deficiency detection and scouting for corn fields**  

<h3>
  <a href="https://gustavosantiago.shinyapps.io/WebResume/">Gustavo Santiago</a> · 
  <a href="https://www.linkedin.com/in/leonardo-bosche/">Leonardo Bosche</a> · 
  <a href="https://www.linkedin.com/in/natalia-volpato/">Natalia Volpato</a> · 
  <a href="https://www.cisdeli.dev/">Pedro Cisdeli</a>
</h3>
<a href="https://ciampitti-lab.github.io/">Ciampitti Lab</a>

</div>

## The Problem

To compensate for the efficiency of nitrogen (N) fertilizers in corn production, farmers over-apply N beyond what the crop can use. On average, **50% of applied N is lost to the environment** through leaching, volatilization, and denitrification, never reaching the plant. This excess N drives nitrate contamination of waterways, greenhouse gas emissions, and algal blooms. While the economic cost of the wasted fertilizer exists, the environmental damage is the more pressing and systemic concern.

The challenge is that the tools to detect N deficiency early enough to intervene are fragmented. Farmers and agronomists typically observe symptoms only after visual signs appear, often too late for a cost-effective rescue application. Satellite-based early warning exists in research settings but lacks the tooling to connect spectral signals, soil context, and in-field confirmation into a single actionable workflow.

N Scout addresses this by combining:
- **Sentinel-2 multispectral imagery** (10 m, V6–V10 growth stages) for early, spatially explicit remote sensing
- **Soil nitrate and growing-season weather records** for agronomic context that satellites alone cannot supply
- **A leaf-image neural classifier** for rapid in-field confirmation at the plant level

The goal is not to eliminate N application but to make it more efficient: apply the right amount, in the right place, at the right time.

The system is demonstrated on the **PRNT dataset**: 49 site-years of public-industry N rate response trials across 8 U.S. Midwest states (2014–2016), with 7 trials from 2016 used in this prototype.

---

## Technical Approach

### Data

| Source | Content | Coverage |
|---|---|---|
| PRNT (Dryad) | Plot boundaries, N treatments, plant tissue N, biomass, soil nitrate, weather | 7 trials, 2016 |
| Sentinel-2 (`COPERNICUS/S2_HARMONIZED`) | 10 m multispectral imagery, L1C/TOA | V6–V10 per trial |
| Maize leaf image dataset | 8,820 labeled images across 6 nutrient classes | Train/Val/Test split |

### Ground-Truth Label: Nitrogen Nutrition Index (NNI)

```
biomass_Mgha = VTBdryY / 1000
N_critical   = 3.49 × biomass_Mgha^(−0.38)
NNI          = VT_TissN / N_critical
```

Plots with **NNI < 1.0** are labelled **deficient** (25.9 % of training plots).

NNI was calculated using the critical N dilution curve proposed by **Ciampitti et al., 2021**:  
> Ciampitti, I.A., Fernandez, J., Tamagno, S., Zhao, B., Lemaire, G., & Makowski, D. (2021). *Does the critical N dilution curve for maize crop vary across genotype x environment x management scenarios? A Bayesian analysis.* European Journal of Agronomy, 123, 126215.  
> https://www.sciencedirect.com/science/article/pii/S1161030120302094

### Remote Sensing Features

- 16 features per V-stage (5 bands: B02, B03, B04, B05, B08; 11 indices: NDVI, GNDVI, NDRE, EVI2, CIrededge, NIRv, SAVI, OSAVI, TGI, MCARI, OCARI)
- Up to 5 stages (V6–V10) → **80 RS features total**
- Cloud gaps filled via nearest-in-time mosaic strategy
- Plot-level zonal means via GEE `reduceRegions`

### Fusion Features (Soil + Weather)

- 9 soil columns: PPNT preplant nitrate/ammonium + PSNT presidedress nitrate (kg/ha, SI units)
- 6 weather metrics: GDD and precipitation (planting→V6 and V6→V10), heat days, solar radiation
- **95 total features** in the fusion model (RS + soil/weather)

### Training Setup

- **Task:** binary classification; deficient (NNI < 1) vs. sufficient
- **Filter:** treatments 1–8 only (treatments 9–16 had in-season N applied at or after V9, confounding the spectral signal; they are shown on the map with a hatched overlay)
- **Augmentation:** stage-dropout; each training plot is copied 5x with 1-4 stages replaced by training-mean values, making the model robust to any number of available stages at inference
- **Threshold:** F-beta (β=2) found on training predictions only, applied fixed to the test set (recall-weighted, because missing a deficient field costs more than a false alarm)
- **Split:** 80/20 stratified, seed=42 · 179 train / 45 test plots · best model: Logistic Regression

### Proximal Sensing: Leaf Image Classifier

- **Model:** MobileNetV3-Small ([Howard et al., 2019](https://arxiv.org/abs/1905.02244)), fine-tuned from ImageNet weights via timm
- **Dataset:** 7,056 train / 882 val / 882 test maize leaf images across 6 nutrient classes ([Patel et al., 2024](https://www.americaspg.com/articleinfo/3/show/3093))
- **HPO:** Optuna on a 20 % subset; AdamW + cosine annealing LR, mixed precision (AMP)
- **Classes:** All Present · N Absent · K Absent · P Absent · Zn Absent · All Absent

---

## Results

### Highlights

> #### Early-warning potential: V6 only, multimodal
> With a **single V6 image** plus soil and weather records, the fusion model achieves **AUC = 0.919, F1 = 0.880**.  
> This means that by the time a scout first enters the field (~V6), the system can already classify plots with near-full accuracy; giving growers a 3-4 week head start before visual symptoms appear.

> #### Limitation: V6 only, satellite only
> Without soil and weather context, V6-only satellite imagery achieves only **AUC = 0.601, F1 = 0.385**.  
> Spectral signals at early stages are too subtle to reliably separate deficient from sufficient plots on satellite imagery alone. Soil context is essential at this stage.

> #### Best RS-only scenario: all 5 stages (V6–V10)
> Using all available imagery through V10, the satellite-only model reaches **AUC = 0.634, F1 = 0.514**, with a recall of **0.750**.  
> Satellite imagery alone provides a meaningful early signal and achieves 75 % recall; meaning 3 out of 4 deficient plots are correctly flagged for follow-up scouting.

---

### Full Results: Satellite Only (RS model, test set, treatments 1-8)

| Model | AUC | F1 | Recall | Specificity |
|---|---|---|---|---|
| **Logistic Regression** | **0.634** | **0.514** | **0.750** | 0.576 |
| XGBoost | 0.586 | 0.300 | 0.250 | 0.848 |
| LightGBM | 0.540 | 0.286 | 0.250 | 0.818 |
| Random Forest | 0.542 | 0.111 | 0.083 | 0.848 |

#### RS Stage-Availability Curve (Logistic Regression)

| Stages available | AUC | F1 |
|---|---|---|
| V6 only | 0.601 | 0.385 |
| V6 + V7 | 0.682 | 0.476 |
| V6 + V7 + V8 | 0.687 | 0.457 |
| V6 + V7 + V8 + V9 | 0.659 | 0.514 |
| All 5 stages (V6–V10) | 0.634 | 0.514 |

---

### Full Results: Satellite + Soil & Weather (Fusion model, test set, treatments 1-8)

| Model | AUC | F1 | Recall | Specificity |
|---|---|---|---|---|
| **Logistic Regression** | **0.904** | **0.870** | **0.833** | **0.970** |
| LightGBM | 0.902 | 0.667 | 0.583 | 0.939 |
| XGBoost | 0.897 | 0.727 | 0.667 | 0.939 |
| Random Forest | 0.861 | 0.632 | 0.500 | 0.970 |

#### Fusion Stage-Availability Curve (Logistic Regression)

| RS stages available | AUC | F1 |
|---|---|---|
| V6 only | **0.919** | **0.880** |
| V6 + V7 | 0.922 | 0.833 |
| V6 + V7 + V8 | 0.919 | 0.870 |
| V6 + V7 + V8 + V9 | 0.914 | 0.870 |
| All 5 stages (V6–V10) | 0.904 | 0.870 |

Adding soil and weather context improves AUC by **+0.27** and F1 from 0.514 → 0.870 compared to RS-only.

---

### Proximal Sensing: Leaf Image Classifier (MobileNetV3, test set)

| Class | Accuracy |
|---|---|
| All Present | 97.3 % |
| N Absent | 100.0 % |
| K Absent | 100.0 % |
| P Absent | 98.6 % |
| Zn Absent | 95.2 % |
| All Absent | 100.0 % |
| **Overall** | **98.5 %** |

882 held-out test images. The single misclassified Zn-absent sample is shown in the proximal scouting UI as a transparent edge-case demonstration.

---

## Demo

> **Video demo:** *(recording in progress; will be linked here)*

The live prototype is served as a Docker image on Render. It includes:
- An interactive scouting map for all 7 PRNT trial sites
- Controls for growth stage (V6–V10) and model type (Satellite only / Satellite + Soil & Weather)
- Per-plot popup with predicted status, confidence, ground-truth NNI, and N application rates (kg/ha SI)
- Hatched grey overlay for in-season N treatments (9–16) excluded from model training
- A proximal scouting page with 6 representative leaf images run through the MobileNetV3 classifier

> **Honesty disclaimer:** Predictions displayed on the scouting map include plots used during model training and are for demonstration only. Honest performance metrics are those reported above from the held-out test set.

---

## Running the Prototype

### Option A: Docker (recommended)

```bash
docker build -t nscout .
docker run -p 8000:8000 nscout
```

Open `http://localhost:8000`.

**Health check:** `http://localhost:8000/api/ping`

### Option B: Local development (no Docker)

**Backend:**
```bash
uv sync
uv run gunicorn -w 2 -b 0.0.0.0:8000 "app.backend.server:app"
```

**Frontend (hot-reload dev server):**
```bash
cd app/frontend
npm ci
npm run dev          # → http://localhost:3000
```

### Reproducing the ML pipeline from scratch

> Requires Google Earth Engine authentication (`uv run earthengine authenticate`) and GEE project `hackil-2026`.

```bash
uv sync

# 1. Site metadata
uv run python data/prnt_metadata.py

# 2. Sentinel-2 extraction (needs GEE auth)
uv run python data/sentinel2_getter.py

# 3. NNI ground truth
uv run python data/nni_getter.py

# 4. Build datasets
uv run python data/build_dataset.py           # RS features + NNI
uv run python data/filter_dataset.py          # remove unreliable trials
uv run python data/soil_weather_getter.py     # soil + weather features
uv run python data/build_fusion_dataset.py    # RS + soil/weather fusion

# 5. Train models
uv run python pipelines/remote/train_models.py   # RS-only classifier
uv run python pipelines/fusion/train_models.py   # fusion classifier

# 6. Precompute predictions for the dashboard
uv run --with pandas python data/precompute_predictions.py

# 7. Build frontend
cd app/frontend && npm ci && npm run build
```

### Proximal sensing model (not needed for runtime)

The proximal MobileNetV3 weights (`models/MobileNetv3.pth`) are precomputed. To retrain:

```bash
uv add torch torchvision timm optuna pillow
# then run notebooks/train_models.ipynb
```

---

## Repository Layout

```
├── app/
│   ├── backend/server.py          Flask API + static file server
│   └── frontend/                  Next.js 15 static export
├── data/
│   ├── raw/                       PRNT dataset zip (committed)
│   ├── processed/                 Pre-computed outputs (committed)
│   │   ├── predictions/           Per-trial GeoJSONs with all prediction combos
│   │   └── fusion/                Soil + weather features
│   └── *.py                       Pipeline scripts
├── models/
│   ├── remote_sensing/            LogisticRegression_clf.pkl
│   └── fusion/                    LogisticRegression_clf.pkl (fusion)
├── pipelines/
│   ├── remote/train_models.py
│   └── fusion/train_models.py
├── notebooks/                     Proximal sensing training + analysis
├── Dockerfile
└── pyproject.toml                 uv-managed Python env
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML pipeline | Python · scikit-learn · XGBoost · LightGBM · Google Earth Engine |
| Proximal model | PyTorch · timm · MobileNetV3-Small · Optuna |
| Backend | Flask 3 · Gunicorn · Python 3.14 · uv |
| Frontend | Next.js 15 (static export) · Leaflet · TypeScript |
| Deployment | Docker multi-stage build → Render |

---
