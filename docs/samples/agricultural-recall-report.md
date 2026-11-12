# Agricultural search recall diagnostic

- Measured: 2026-11-10T23:39:42Z
- Audit snapshot: 11/10/2026 23:03:48; 270 deduplicated candidates from the captured first pages of 32 active searches.
- Panel: 1.0, 8 positive examples located through official BDNS detail pages after the initial audit.
- Overall first-page recovery: 3/8 (37.5%).

This purposive panel was assembled after the audit and intentionally includes recovered and missed records, so its rate is selection-biased. It is a descriptive diagnostic, not an independent blind benchmark or statistically representative estimate. The audit captured page 0 only, so a missing code means it was not in the captured first-page union; it does not prove the call is absent from later BDNS search pages. Open-call availability is separate from discovery relevance.

## Recovery by holding type

| Type | Recovered | Panel | First-page recovery |
|---|---:|---:|---:|
| Crop-only | 1 | 2 | 50% |
| Livestock-only | 0 | 3 | 0% |
| Mixed | 2 | 3 | 66.7% |

## Seed results

| BDNS | Type | Recovered | Query route(s) | Call | Official record |
|---|---|---|---|---|---|
| 909993 | crop_only | Yes | crop:frutícola | 2026 aid for replanting fruit plots destroyed by Xylella measures | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/909993) |
| 931649 | crop_only | No | — | 2026 cooperation aid for succession of agricultural holdings | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/931649) |
| 915152 | livestock_only | No | — | 2026 operating-cost subsidies for livestock holdings, line 2 | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/915152) |
| 860963 | livestock_only | No | — | 2026 aid for cattle holdings | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/860963) |
| 899941 | livestock_only | No | — | 2026 investment subsidies for livestock holdings | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/899941) |
| 938645 | mixed | Yes | crop:agrícola, livestock:ganadero | 2026 aid to the agricultural and livestock sector of Yecla | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/938645) |
| 938663 | mixed | Yes | crop:agrícola, livestock:apícola | 2026 direct aid to agricultural, livestock and beekeeping holdings affected by wildfires in Extremadura | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias/938663) |
| 708537 | mixed | No | — | 2023 drought aid for holders of agricultural and livestock holdings | [BDNS](https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/708537) |

## Interpretation

The misses show that the current first-page keyword audit is not sufficient as a nationwide collection strategy. Search result truncation and ordering hide relevant calls; relevant older calls may be pushed beyond page 0. The next experiment should paginate or partition by registration date, administration and territory, then run this fixed panel again. A production collector should not treat title-term hits or the agriculture-purpose filter as a complete record of farm aid.

Panel selection rules and excluded title-based false positives are documented in [agricultural-recall-seed-panel.json](agricultural-recall-seed-panel.json).
