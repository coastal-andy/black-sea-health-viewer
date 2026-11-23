# Challenge 04: Ecosystem Health (English summary of the Romanian scan)

Original scan: [challenge4_scan.pdf](challenge4_scan.pdf)

**Theme:** Integrate marine observations and environmental indicators to support ecosystem-health assessment.

**Team question:** How can complementary marine monitoring technologies, environmental datasets and digital analysis tools be integrated to assess ecosystem state, identify potential environmental risks and support evidence-based marine management?
The solution should be scientifically credible, technically feasible and potentially scalable.

## Key points from the brief
- Ecosystem state depends on many factors: temperature, salinity, dissolved oxygen, nutrients, water transparency, hydrodynamic circulation, biological communities.
- Human pressures: pollution, coastal development, maritime operations, habitat disturbance.
- **Integrate complementary observations, not a single parameter.**
- Variability is not automatically degradation. Upwelling, mixing, river inputs (Danube) and sediment resuspension change the parameters without meaning the ecosystem is degrading.
- A credible assessment needs scientifically justified indicators, **reference conditions**, validation and a clear view of **uncertainty**.

## Data and technologies they list
Instrumented buoys, water-quality sensors (temp, salinity, DO, turbidity), micro-AUV observations, ROV images and video (benthic habitats), **satellite observations** (SST, ocean colour), **Copernicus Marine products** (physical and biogeochemical fields), hydrodynamic models, lab analyses (nutrients, contaminants), **GIS platforms**, data analysis and machine learning (anomalies, patterns).
Note: dataset availability depends on what the organisers confirm.

The team's markings on the scan: ticked buoys, sensors, micro-AUV, ROV, satellite, Copernicus, GIS. "?" on hydrodynamic models, crossed out lab analyses, "~" on ML.

## Example solutions (team starred A, B, C, D, F; "~" on E)
- **A. Integrated ecosystem-monitoring dashboard**: combine observations and indicators to visualise marine conditions. *(starred)*
- **B. Environmental anomaly detection**: unusual changes in temperature, DO, turbidity etc. **relative to reference conditions**. *(starred)*
- **C. Coastal water-quality explorer**: GIS app integrating in-situ, satellite and model outputs to study spatial and temporal variability. *(starred)*
- **D. Ecosystem-risk screening tool**: identifies conditions associated with ecological stress and recommends further investigation. *(starred)*
- E. Benthic habitat state viewer. *(maybe)*
- **F. AI-assisted environmental monitoring**: ML to find patterns, detect anomalies, help interpretation. *(starred)*

## Five sprints (what must be produced)
1. **Pressure map across the five blue-economy sectors**: ports and maritime logistics, shipyards and marine engineering, coastal and marine tourism, fishing, aquaculture. Output: problem statement plus a map of pressures and monitoring needs per sector.
2. **Monitoring architecture**: parameters, platforms and sensors, satellite and model info, spatial and temporal requirements, QC, validation, storage and processing. Output: architecture diagram.
3. **Data-to-decision canvas**: integration and harmonisation, QC, indicators, reference conditions and thresholds, spatial and temporal analysis, anomaly detection, validation and uncertainty, users and management decisions. Output: data-processing and decision-support workflow.
4. **Prototype / dashboard mock-up**: monitoring dashboard, maps of selected parameters, time-series views, anomaly indicators, conceptual risk-assessment interface, **observations vs model comparison**, multi-parameter platform. Output: prototype or visual demonstrator.
5. **Impact and roadmap**: problems addressed, users, management support, extra data needed, limitations, validation, path to an operational tool.

## Scientific questions the jury will ask
- Natural variability vs significant change (seasons, depth, area): how do we tell them apart? -> climatology-based anomalies.
- Indicator selection: why these parameters?
- Reference conditions and thresholds: historical observations, seasonal climatologies, justified thresholds?
- Data integration: satellite vs in-situ vs model differ in resolution, coverage, measurement. How do we handle it?
- Direct measurement vs derived indicator: show the origin and reliability of each value.
- Ecological interpretation: an anomaly is not necessarily damage. What extra evidence is needed?
- Validation and uncertainty: how do we evaluate and communicate them?
- Operational relevance: which decisions does it support?

## Final deliverables
Problem definition; relevance for the five sectors; monitoring architecture; data-processing method; prototype; validation approach; impact and roadmap; final presentation. A fully working app is NOT mandatory.

## Scoring (100)
| Criterion | Points |
|---|---|
| Integration across the five sectors | 15 |
| Technical monitoring logic | 20 |
| Turning data into decisions | 15 |
| Impact on environment and blue growth | 20 |
| Feasibility and realism of the pilot | 15 |
| Ease of use for stakeholders | 10 |
| Presentation and teamwork | 5 |
