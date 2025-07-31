This is the python script for data processing for the data from CamTrapNZ tool. The key steps include:

##### Summarise Camera Dates
Scans an Excel sheet to extract photo date information per camera label. It summarizes the **earliest** and **latest** photo dates for each label and calculates the number of days between them.

##### Identify Independent Detections
Identifies independent wildlife detections per camera and species. A detection is considered independent if it occurs **at least 30 minutes** after the previous detection of the same species at the same camera

##### Calculate Camera Trap Rates with 95% CI
Calculates detection rate (per 100 camera days) per species and uses the **Wilson score interval** to generate 95% confidence intervals.

##### Plot Trap Rates Graph
Creates a clustered column chart showing camera trap rates per species, with error bars.
