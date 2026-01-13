# Jan 4th 2026

## Changes
* Rewrote communications code, now fully functional and just require a visual interface
* Default configurations can be found in the config folder

## Notes
* Refer to page #26 of the ESA manual for testing noise floor and small signals.
    * Importantly, sweep time refers to the integrated signal over that time.
    * For SA, ONLY GET NEW VALUES, is currently fetching old ones
    * The SA works by taking (sweep_time/n_points) seconds at each frequency and either measuring max amplitude, or average amplitude. Thus the integration time is proportional to the N_points/span.