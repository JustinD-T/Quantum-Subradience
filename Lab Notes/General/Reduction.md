# Reduction Pipeline

## Baseline Determination
- Define a range outside hte expected signal to fit a 1st or 2nd order polynomial

## Data Smoothing
- box-car averaging (bin mean, intensity sum)

## Pipeline
1. Define baseline, subtract across n measurements
2. Bin data

## Noise Determination
1. Remove baseline
2. Compute variance/STD (mean should be zero), always within the same bandwidth  
    - STD of amplitudes in a single bin, over measurements averaged
    - Should have no signal
    - MEAN OF POWER IN A GIVEN CHANNEL, STD COMPUTED OVER AMPLITUDES IN A GIVEN MEASUREMENT
        -NEXT MEASUREMENT, AVERAGE AND TAKE STD

## Visualization Improvements:
- Add a plot for noise vs time
- add a plot for reduced integrated signal
