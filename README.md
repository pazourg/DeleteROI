# DeleteROI

The ImageJ plugin CiliaQ developed by Hansen and colleagues (Hansen et al., 2021) provides for sophisticated analysis 
of ciliary parameters in three-dimensional space. However, midbodies and other non-ciliary structures can contaminate 
the output and require significant effort to remove. Furthermore, the manual removal of contamination risks subjective 
bias as the data is not blinded to the investigator. 

To address these problems, we developed an ImageJ plugin that presents images of the cilia region-of-interests (ROIs) 
identified by CiliaQ in a clickable grid that allows for marking and automated removal of non-ciliary contaminants. 
To reduce subjective bias, our plugin works on a dataset of multiple images and presents the cilia randomly. If the 
dataset contains both control and experimental conditions, the cilia are randomly interspersed with no visible 
information about their experimental group, thus reducing subjective bias. After removal of contamination, the 
cleaned data is output using the CiliaQ file formats.

# Installation

DeleteROI is dependent on installations of FIJI (Schindelin et al., 2012) and the output from CiliaQ (Hansen et al., 2021). 
You will need to install [FIJI version 2024-09-25](https://imagej.net/software/fiji/downloads) or later noting the location
of the installation.  Once the installation is complete, you will need to move the following files as indicated:
  - place DeleteROI_.py in the \<FIJI-install-dir>/scripts/Plugins folder  
  - place DeleteROI-1.0.1.jar (or latest version number) in the \<FIJI-install-dir>/jars/Lib (you may need to create the Lib directory).  Please note that when updating to a new version ensure that only one (1) jar file is present, delete all other versions.  Failure to ensure that will result in indeterminate behavior.
     
Restart FIJI and run the software via Plugins -> DeleteROI.  When installing new versions of DeleteROI you must restart
FIJI to ensure the updated jar file is being used.

# Examples

To assist in learning how to use DeleteROI, an example dataset is available at [Cilia.pro/DeleteROI](https://cilia.pro/DeleteROI/ExampleData/) 
to be downloaded and used to try out the overall functionality.  In addition, the full paper in PDF format can be 
directly [downloaded here](/Documentation/DeleteROI_05_30_2025.pdf) 
which provides additional usage information.

Once you have started DeleteROI and selected the directory containing the example dataset a randomized Montage will be
generated that allows you to select (X out) images that are not relevant.  This will cause the corresponding ROI entries
to be commented out of the _CQ.txt files.  

![An example montage is:](/Documentation/Montage_example.jpg)

# Building a new version

First create a directory locally to hold all of the source code, we will assume 'DeleteROI' as the directory name.  Next
download all of the code from GitHub either by cloning the repository or downloading it as a zip file/unpacking.

A build is triggered via the make_jar.sh script.  This is currently written as a bash script for Linux/Mac systems.  While a Windows 
script is not currently provided it should be trivial to manually perform the operations.

To execute make_jar.sh from the command line, ensure you are in the directory containing the make_jar.sh script (cd DeleteROI) and execute as follows:
```
> cd DeleteROI
> ./make_jar.sh
Compiling Version: 1.0.1
Creating JAR: DeleteROI-1.0.1.jar
JAR created successfully at Downloads/DeleteROI-1.0.1.jar
>
```
Note that the version number is stored in the __init__.py file located in Lib/DeleteROIPkg.

# License

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License V3
as published by the Free Software Foundation (http://www.gnu.org/licenses/gpl.txt )
