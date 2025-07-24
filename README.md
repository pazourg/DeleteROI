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

DeleteROI is dependent upon installations of FIJI (Schindelin et al., 2012) and the output from CiliaQ (Hansen et al., 2021). 
You will need to install [FIJI version 2024-09-25](https://imagej.net/software/fiji/downloads) or later noting the location
of the installation directory.  

The DeleteROI plugin is located in [releases](releases) on the right sidebar in GitHub or built locally as described 
in the [Building a new version](#building-a-new-version) section).  It is self contained in a <b>jar</b> file starting with 
the name "DeleteROI_" (the underscore is required by ImageJ/Fiji).  The latest version of DeleteROI is the following:

> [DeleteROI_-1.0.3-2.jar](https://github.com/pazourg/DeleteROI/releases/download/v1.0.3-2/DeleteROI_-1.0.3-2.jar) - Released July 24th, 2025

You can install the plugin by starting up Fiji and then selecting Plugin->Install... from the menu.  Please note that there
are two versions of the Install command in the Plugin menu.  Select the "Install..." option <b>not</b> the "Install Plugin" 
option.  This will present a file chooser where you will select the Delete_ROI jar file downloaded as describe above.  The 
next screen is confirming where to install the jar file - the plugin directory for Fiji.  Note the location, you might need this
when performing an upgrade.

The manual plugin installation method does not currently have the ability to manage version upgrades.  This means that the
installation of a newer version of DeleteROI (when the version number changes) will result in two versions being installed.
This is invalid and will result in DeleteROI showing up twice in the menu.  During "Plugin->Install..." execution, you should 
see a Plugin configuration error popup when installing a new version.   At the moment you will need to manually delete the 
older version described in the popup before restarting Fiji.  Using the file browser, navigate to the plugins directory you noted
during plugin installation (see above) and delete the older version of the plugin (ensure that only 1 DeleteROI_ jar file is
present).

Remember to restart Fiji and run the software via Plugins -> DeleteROI to activate the new version.

Windows users: please note that you might need to start Fiji in Administrator mode (right click on Fiji application
and select "Run as administrator") in order to install or upgrade the plugin.  Failure to do so may result in failures due 
to permission issues.  You will only need to do this while running the Plugin->Install... operation.  You should not run 
Fiji as Administrator during normal usage.

We are investigating adding DeleteROI to the Fiji/Imagej plugin repository to simplify installation.

# Examples

To assist in learning how to use DeleteROI, an example dataset is available at [Cilia.pro/DeleteROI](https://cilia.pro/DeleteROI/ExampleData/) 
to be downloaded and used to try out the overall functionality.  In addition, the full paper in PDF format can be 
directly [downloaded here](https://raw.github.com/pazourg/DeleteROI/main/Documentation/DeleteROI_05_30_2025.pdf) which provides 
additional usage information.

Once you have started DeleteROI and selected the directory containing the example dataset a randomized Montage will be
generated that allows you to select (X out) images that are not relevant.  This will cause the corresponding ROI entries
to be commented out of the _CQ.txt files.  

![An example montage is:](/Documentation/Montage_example.jpg)

# Building a new version

First create a directory locally to hold all of the source code, we will assume 'DeleteROI' as the directory name.  Next
download all of the code from GitHub either by cloning the repository or downloading it as a zip file/unpacking.

A build is triggered via the make_jar.sh script.  This is currently written as a bash script for Linux/Mac systems.  While a Windows 
script is not currently provided it should be feasible to manually perform the operations.

To execute make_jar.sh from the command line, ensure you are in the directory containing the make_jar.sh script (cd DeleteROI) and execute as follows:
```
> cd DeleteROI
> ./make_jar.sh
Compiling Version: 1.0.2
Searching for Fiji jar files
  -> Using Fiji Jars files: /Applications/Fiji.app/jars/*
Compiling DeleteROI_Plugin.java
Creating JAR: DeleteROI_-1.0.2.jar
JAR created successfully at: Releases/DeleteROI_-1.0.2.jar
>
```
Note that the version number is stored in the \_\_init\_\_.py file located in Lib/DeleteROIPkg.

# License

This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License V3
as published by the Free Software Foundation (http://www.gnu.org/licenses/gpl.txt )
