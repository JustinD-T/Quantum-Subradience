### Noise Floor Quantification
 
## Procedure
* Have everything in the RF setup on, except with the output side fully attenuated/off
* Have the y-scale set to linear (W)
* Read data from the spectrum analyzer continously for a long time 
* Plot the variance of each index, calculated from a rolling mean from the first index verus time
    * eg. (x_n, y_n) = (n*SWEEP_TIME, (SUM(data_n) / n) )

## Notes
* BackgroundTest1 -> 1000 points, 2.5s sweep, full setup w noise.
* BackgroundTest2 -> Same as Run 1, except w 500 pts