# Running ShapeWorks in Slicer


template use case for the WIP Shapeworks Slicer extention
<https://github.com/dcwhite/SlicerSegmentMesher/tree/shapeworks-runner>

This version is for segmented images, but can be extended to other datatypes


## Data

This usecase will use the ellipsoid dataset, found within the [github repo](https://github.com/SCIInstitute/ShapeWorks/tree/master/Examples/Studio/Ellipsoid).  An explaination of the equivalent workflow is found [here](http://sciinstitute.github.io/ShapeWorks/latest/use-cases/segmentation-based/ellipsoid.html).  

## Envisioned workflow


### Load data into Slicer

Open Slicer and in the welcome module (default window) choose the AddData option.  Using the dialogue window, select the 9 ellipsoid segmentations from the [ShapeWorks usecases](https://github.com/SCIInstitute/ShapeWorks/tree/master/Examples/Studio/Ellipsoid).  before importing the volumes, switch the data type from Volume to Segmentation for each of the files.  


segmentations can be edited in slicer before sending to ShapeWorks using the Segment Editor module

### Running ShapeWorks in the Extension

Open the ShapeWorks Extension.  Select from the list of Segmentations the ones to include in the shape model (all 9 ellipsoid segmentations).  

Choose a project file path and name, if the file exists, it will populate the parameters of the UI from the project file, but it will be overwritten when shapeworks is run.  the file path is where the data will be saved

choose the parameters to use for each of phases: groom,  and optimize

click "groom"

This should save the data to the project path and create or modify the project file, which should look like [the one provided with the example](https://github.com/SCIInstitute/ShapeWorks/blob/master/Examples/Studio/Ellipsoid/ellipsoid.xlsx).  The Extention should then launch Shapeworks, essentially with the system command:
```
shapeworks groom --name="project_file --progress"
```
Hopefully, it should be easy enough to track the progress, or we can include the printouts like in the Cleaver Extension.  

The extension will catch when Shapeworks finishes the groom stage, which will allow the optimize step to be run

The groomed files found in the groom folder should be send back to Slicer.  -- maybe?

Modify the optimize parameters as appropriate.  

click "optimize"

This should  modify the project file as approptiat, run the system command
```
shapeworks optimize --name="project_file --progress"
```

more info about the command line tools in ShapeWorks are found [here](
http://sciinstitute.github.io/ShapeWorks/latest/tools/ShapeWorksCommands.html)


The extention should then show the specificity, generalization, and compactness plots and send the particles back to slicer 

This can be done manually with <https://discourse.slicer.org/t/how-to-replace-markups-with-np-array-in-application-markupstomodel/25000/8>







