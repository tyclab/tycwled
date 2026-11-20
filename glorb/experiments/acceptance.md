# GLORB acceptance measurements

The four hardware runs below used 100-second windows per preset.

| Date       | Run                                   | Result                                                                                                                               |
| ---------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-08-31 | First structural gate                 | 8/12 passed. Failures were preset 7 (current), 10 (hue and activity), 12 (hue) and 14 (brightness histogram and spatial variation).  |
| 2026-08-31 | Calibrated gate                       | 8/12 passed. Failures were preset 7 (current), 10 (hue and activity), 11 (peak) and 14 (brightness histogram and spatial variation). |
| 2026-09-01 | Hole topology fix, firmware `5b2e901` | 11/12 passed in the sweep. Preset 11 had a 2.593 s target stream gap and passed on a separate measurement.                           |
| 2026-09-01 | Final firmware `7eb5f31`              | 12/12 passed in one sweep, with 120 cells per lamp and no capture retries.                                                           |

## Final sweep

Preset file SHA-256: `5dde8cb917179b40c96d042e6294f2e6d8da5226b5d5eedf95b0d6dbd82b3531`.

Current is the ABL estimate in mA (reference/target). Ratio columns use target/reference.
The brightness histogram and hue columns are distances. Saturation is an absolute difference.
RGB sum is reported for comparison and does not gate a preset.

| Preset | Current (mA) | Current ratio | V hist | Hue  | Spatial ratio | Activity ratio | Peak ratio | Lit ratio | Saturation | Mean V ratio | RGB sum ratio |
| ------ | ------------ | ------------- | ------ | ---- | ------------- | -------------- | ---------- | --------- | ---------- | ------------ | ------------- |
| 1      | 1122/1106    | 0.985         | 0.06   | 0.06 | 1.07          | 1.15           | 1.00       | 1.00      | 0.000      | 0.97         | 0.96          |
| 2      | 1275/1310    | 1.028         | 0.02   | 0.34 | 0.96          | 0.98           | 1.00       | 1.00      | 0.001      | 1.00         | 1.01          |
| 3      | 914/934      | 1.022         | 0.04   | 0.04 | 0.99          | 0.97           | 0.99       | 1.00      | 0.001      | 1.00         | 1.00          |
| 4      | 1012/1038    | 1.025         | 0.00   | 0.04 | 1.00          | 1.02           | 1.00       | 1.00      | 0.002      | 1.00         | 1.00          |
| 5      | 961/977      | 1.017         | 0.01   | 0.05 | 0.99          | 1.00           | 1.00       | 1.00      | 0.000      | 0.99         | 0.99          |
| 7      | 372/386      | 1.037         | 0.01   | 0.02 | 0.99          | 1.00           | 0.99       | 0.99      | 0.000      | 0.98         | 1.00          |
| 9      | 431/454      | 1.054         | 0.01   | 0.01 | 0.99          | 0.99           | 0.99       | 1.00      | 0.000      | 0.99         | 0.99          |
| 10     | 447/464      | 1.039         | 0.00   | 0.02 | 0.99          | 1.00           | 1.00       | 1.00      | 0.001      | 0.99         | 1.00          |
| 11     | 324/342      | 1.054         | 0.01   | 0.00 | 0.99          | 1.01           | 1.00       | 0.98      | 0.000      | 0.98         | 1.00          |
| 12     | 1430/1440    | 1.008         | 0.01   | 0.03 | 1.00          | 1.01           | 1.00       | 0.99      | 0.001      | 0.99         | 1.00          |
| 13     | 1489/1507    | 1.012         | 0.02   | 0.07 | 1.00          | 1.02           | 1.00       | 0.99      | 0.000      | 0.98         | 1.00          |
| 14     | 1205/1156    | 0.959         | 0.05   | 0.04 | 0.99          | 1.01           | 0.93       | 0.98      | 0.001      | 0.94         | 0.93          |
