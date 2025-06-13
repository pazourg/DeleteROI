''' ===============================================================================
 * DeleteRoi, a plugin for imagej/Fiji
 * 
 * Copyright (C) 2025 Gregory Pazour
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation (http://www.gnu.org/licenses/gpl.txt )
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public
 * License along with this program.  If not, see
 * <http://www.gnu.org/licenses/gpl-3.0.html>.
 *    
 * For any questions please feel free to contact (Gregory.Pazour@umassmed.edu)
 * ===============================================================================
'''

# Standard Python imports
import imp, os, sys

# GUI Imports
from ij.plugin.frame        import RoiManager

# Our package imports
from DeleteROIPkg.Bundles   import BundleManager
from DeleteROIPkg.Dialogs   import SelectFilesDialog, ProcessFilesDialog, show_error
from DeleteROIPkg.Session   import SessionManager
from DeleteROIPkg.Slides    import SlideManager
from DeleteROIPkg.Utilities import close_all, trace
from DeleteROIPkg.Utilities import parm_columns, parm_max_rows
from DeleteROIPkg.Utilities import OPTIONS

# Constants 
VERSION = "1.0.2"

# https://imagej.net/scripting/jython/

# Main function to run the process
def main():
    #
    # Ensure all images are closed
    close_all()
    
    print("DeleteRoi: version {} loaded and started".format(VERSION))
    
    # Just in case, setup the ROI Manager now
    roi_manager = RoiManager.getInstance()
    if roi_manager is None:
        roi_manager = RoiManager()
        
    # Create the BundleManager to manage the bundles created by the Dialog
    bundle_mgr  = BundleManager()
    slide_mgr   = SlideManager()
    session_mgr = SessionManager(bundle_mgr, slide_mgr)

    # results message
    result      = ""
    
    try:
    	# Define the title of the SelectFilesDialog to include the version number
    	title = "DeleteROI File Selector   - DeleteROI v{}".format(VERSION)
    	
        # Prompt the user for the bundles to the processed.
        select_files = SelectFilesDialog(title, session_mgr, bundle_mgr, slide_mgr)
        status, restored = select_files.execute()
        
        # Save any preferences
        OPTIONS.savePrefs()
        
        # Create the sessions we will need
        if not restored:
            session_mgr.create_sessions(roi_per_session=500)
        
        # Present the dialog box that allows the user to process the results
        group_num = session_mgr.get_group_num()
        results = ProcessFilesDialog("Processing results - Group #{}".format(group_num), session_mgr)
        
        # Save any preferences
        OPTIONS.savePrefs()

        # Now iterate through the sessions, processing each as a montage.  At the
        # end of each session being process state is saved to enable restart.
        for session in session_mgr:
            #
            if session.is_complete():
                print("Skipping session due to being complete: "+str(session))
                continue
            
            session.process(parm_columns, OPTIONS.roi_size, parm_max_rows)
            #
            print("Session completed: "+str(session))
            #
            session_mgr.save_session_state()
            
        # Indicate final result
        num_sessions  = session_mgr.get_session_count()
        num_completed = session_mgr.get_completed_session_count() 
        result = "{} out of {} sessions have been completed for Group #{}.".format(num_completed, num_sessions, group_num)
                            
    except UserWarning as e:
        num_sessions  = session_mgr.get_session_count()
        num_completed = session_mgr.get_completed_session_count() 
        result = "Processing cancelled, {} out of {} sessions were completed and have been saved".format(num_completed, num_sessions)
        print("*** Exception: "+str(e))
    
    # Close everything before we display complete message
    close_all()
    
    # Give a status message indicating that we are complete
    show_error("All processing complete", result)

    print("All Processing Complete")
    
    # Just in case
    close_all()

    # Save any preferences - just in case
    OPTIONS.savePrefs()
