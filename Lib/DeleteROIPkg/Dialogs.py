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

import fnmatch
import re
import os
import shutil
import traceback

# Java Imports
from java.awt               import BorderLayout, Button, Checkbox, Choice, Color, Dialog, Dimension, FlowLayout, Font, Frame, GridBagConstraints, GridBagLayout, Insets, Label, Panel, TextField
from java.awt.event         import ActionListener, KeyEvent, KeyListener, ItemListener, InputEvent, MouseAdapter, WindowEvent
from javax.swing            import JLabel, JPanel, JTable, JScrollPane
from javax.swing.table      import DefaultTableCellRenderer, DefaultTableModel

# GUI Imports
from ij.gui                 import Roi, TextRoi, Overlay, Line
from ij.gui                 import GenericDialog, DialogListener, NonBlockingGenericDialog
from ij.util                import FontUtil

# Our package imports
from DeleteROIPkg.Help      import HELP
from DeleteROIPkg.Utilities import close_all, convertToFloat, trace, OPTIONS

# Global fonts to use
FONT_LABEL     = FontUtil.getFont("Tahoma",      Font.PLAIN,  6)
FONT_MONO      = FontUtil.getFont("Courier New", Font.PLAIN, 12)
FONT_MONO_BOLD = FontUtil.getFont("Courier New", Font.BOLD,  12)
COLOR_LABEL    = Color.WHITE

#
# Main dialog to prompt for location of files and show the resulting matches.
#
# Current limitations:
#   - It cannot handle large numbers of files, the resulting UI is broken
#   - You cannot press update more than once, the resulting UI is broken
#
class SelectFilesDialog(GenericDialog):
    #
    # class level variables
    file_sep = os.path.sep
    
    # Constants used for UI
    LABEL_ADJUST_TYPE  = "Adjust Type"
    LABEL_BUFFER_PCT   = "Buffer Percent"
    LABEL_C1_SAT       = "C1 Sat"
    LABEL_C2_SAT       = "C2 Sat"
    LABEL_C3_SAT       = "C3 Sat"
    LABEL_CONT_BUFFER  = "Contrast Buffer %"
    LABEL_SRC_FOLDER   = "Source Folder:"
    LABEL_SET_MIN_MAN  = "SET Min/Max"
    LABEL_UPDATE       = "Update"

    def __init__(self, title, session_mgr, bundle_mgr, slide_mgr):
        #
        # Initialize our parent class
        super(GenericDialog, self).__init__(title)
        
        # Yukky, wasCanceled is both a method and variable which is a challenge for jython.  Provide 
        # our own means detecting cancel
        self.user_canceled = False
        
        # Save the bundle mgr for use during execution
        self.bundle_mgr    = bundle_mgr
        self.session_mgr   = session_mgr
        self.slide_mgr     = slide_mgr
        self.restored      = False
        self.src_path      = None
        
        # Defined Java.awt.Fields used for advanced UI (show/hide, etc.)
        self.choice_adjust = None
        self.choice_scale  = None
        self.bc_button     = None
        self.buffer_pct    = None
        self.bc_panel      = None
        self.buffer_label  = None
        self.sat_values    = []
        self.sat_labels    = []
        self.ok_button     = None
        self.update_button = None
        
        # Initialize all of the fields with appropriate controls
        self.addMessage("Please select a directory containing a set of TIF (CQ_RP.tif) and CiliaQ output files (CQ.txt) that start with the\n"+
                        "same filename root.  Once you have selected the folder, press UPDATE to select the files in the folder.  You will\n"+
                        "then be presented with the discovered images and number of ROI found.\n"+
                        " \n"+
                        "Choose the method for adjusting the montage presentation (Adjust Type).\n"+
                        " \n"+
                        "Once you are ready - select Next\n \n")

        # Be careful changing the labels, must match process_status() or we will fail to get the value
        self.addDirectoryField(self.LABEL_SRC_FOLDER, OPTIONS.src_folder, 40);
        
        # The main option values
        self.addButton(self.LABEL_UPDATE, SelectFilesDialog.UpdateListener(self))
        self.update_button = self.findButton(self.LABEL_UPDATE)
        self.addToSameRow()
        
        # The adjust type order MUST match the OPTIONS.TYPE_ADJUST_* index numbers
        self.addChoice(self.LABEL_ADJUST_TYPE, ["Min/Max", "Saturation", "Manual"], "Min/Max")
        self.addToSameRow()
        
        # Button when Min/Max is shown
        self.setupOptionsPanel()
        self.addToSameRow()
        
        self.addNumericField(self.LABEL_BUFFER_PCT, OPTIONS.buffer_percent, 1)
        self.buffer_label = self.getLabel()
        self.addToSameRow()
        self.addNumericField(self.LABEL_C1_SAT, OPTIONS.c1_sat, 1)
        self.sat_labels.append(self.getLabel())
        self.addToSameRow()
        self.addNumericField(self.LABEL_C2_SAT, OPTIONS.c2_sat, 1)
        self.sat_labels.append(self.getLabel())
        self.addToSameRow()
        self.addNumericField(self.LABEL_C3_SAT, OPTIONS.c3_sat, 1)
        self.sat_labels.append(self.getLabel())
        
        # Add a scrolling table that will house the results table.  We will initially hide this until needed.
        # Note the order of the columns MUST match what processDataTable() expects!
        columns         = [ 'Image #', '# ROI', 'Filename' ]
        column_width    = [ 100, 150 ]
        
        # Hack - we don't have control of the gridy constraint so add a dummy message to increment it
        self.addMessage("")
        self.getMessage().setVisible(False)
        
        self.data_table = ScrollableTablePanel(columns, column_width, visible_rows=8)
        self.data_table.set_column_alignment(0, JLabel.CENTER)
        self.data_table.set_column_alignment(1, JLabel.CENTER)
        self.data_table.setVisible(False)
        self.addPanelRemainder(self.data_table)
        
        # Setup the OK/Next button.  It starts as hidden
        self.setOKLabel("Next")
        self.ok_button = self.getButtons()[0]
        self.ok_button.setEnabled(False)
        
        # Enable help for this screen
        self.addHelp(HELP.getHelp(HELP.KEY_SFD))
        
        # Add the listener
        self.saveDialogFields()
        
        return

    # Method to create a panel for the SET Min/Max Button
    def setupOptionsPanel(self):
        #
        #gc.addButton("SET Min/Max", SelectFilesDialog.SetOptionsButtonListener(self))
        self.bc_button = Button(self.LABEL_SET_MIN_MAN)
        self.bc_button.addActionListener(SelectFilesDialog.SetOptionsButtonListener(self))
        
        # Create a spacer
        spacer = Panel()
        spacer.setPreferredSize(Dimension(18, 1))  # 20px horizontal spacer
        
        # Create a custom panel to align the Choice, Spacer, and Button
        self.bc_panel = Panel(FlowLayout(FlowLayout.LEFT))
        self.bc_panel.add(spacer)
        self.bc_panel.add(self.bc_button)
        
        # Add the panel to the dialog
        self.addPanel(self.bc_panel)
    
    # Walk the components looking for the specified button
    def findButton(self, label):
        #
        button = None
        
        for comp in self.getComponents():
            if isinstance(comp, Button) and comp.getLabel() == label:
                button = comp
                break
        
        return button
        
    # Called during dialog creation - depends upon the exact order/values items are created
    def saveDialogFields(self):
        #
        fields = GenericDialog.getDeclaredFields()
        
        # Save the currently defined choices and then add a listener to the Adjust Type.  The expected
        # order of the returned choices MUST match the defined order in the constructor.
        choices = self.getChoices()
        if len(choices) != 1:
            raise ValueError("Number of expected choice fields ({}) does not match actual: {}".format(len(choices), 1))
            
        self.adjust_choice = choices[0]
        self.adjust_choice.addItemListener(SelectFilesDialog.AdjustTypeListener(self))
        
        # Now walk the numeric fields looking for the items controlled by the AdjustTypeListener.  We
        # need to do this via it's position - this must match the order of creation!
        fields = self.getNumericFields()
        if len(fields) != 4:
            raise ValueError("Number of expected numberic fields ({}) does not match actual: {}".format(len(fields), 4))
        
        # First field is contrast percent
        self.buffer_pct = fields[0]
        
        # Next 3 are the saturation options in order
        for i in range(1, len(fields)):
            self.sat_values.append(fields[i])

        trace("SDA: processed sat_values: "+str(self.sat_values))
        
        # Now find any buttons we need to preserve
        buttons        = self.getButtons()
        self.bc_button = buttons[1]   # [0] is UPDATE which we don't need
        
        # Now setup the visibility of the controls based upon the drop down current value
        self.handleUiVisibility()
            
        # We are done

    # Change the visbility of controls based upon the selected adjust type
    def handleUiVisibility(self):
        #
        choice = self.adjust_choice.getSelectedIndex() + 1
        OPTIONS.setAdjustType(choice)
        #
        if choice == OPTIONS.TYPE_ADJUST_MIN_MAX:
            self.buffer_pct.setVisible(False)
            self.buffer_label.setVisible(False)
            self.bc_panel.setVisible(True)
            for value in self.sat_values:
                value.setVisible(False)
            for label in self.sat_labels:
                label.setVisible(False)
        elif choice == OPTIONS.TYPE_ADJUST_SATURATION:
            self.buffer_pct.setVisible(False)
            self.buffer_label.setVisible(False)
            self.bc_panel.setVisible(False)
            for value in self.sat_values:
                value.setVisible(True)
            for label in self.sat_labels:
                label.setVisible(True)
        elif choice == OPTIONS.TYPE_ADJUST_AUTO:
            self.buffer_pct.setVisible(True)
            self.buffer_label.setVisible(True)
            self.bc_panel.setVisible(False)
            for value in self.sat_values:
                value.setVisible(False)
            for label in self.sat_labels:
                label.setVisible(False)
        else:  # Default to MANUAL
            self.buffer_pct.setVisible(False)
            self.buffer_label.setVisible(False)
            self.bc_panel.setVisible(False)
            for value in self.sat_values:
                value.setVisible(False)
            for label in self.sat_labels:
                label.setVisible(False)
        
    # Execute the dialog returning once all information is collected.  If we did not successfully complete return false
    # otherwise we are all good and thus return true.
    def execute(self):
        #
        # Now show the actual dialog and wait for the user
        self.showDialog()
        
        # If the user cancelled abort all processing
        if self.userCanceled():
            raise UserWarning("Cancel")
        
        # Process all values from the UI
        self.processValues()
        self.processDataTable()
        
        # All done!
        return True, self.restored
        
    # Indicate if the user pressed cancel
    def userCanceled(self):
        return self.wasCanceled() or self.user_canceled
    
    def setUserCanceled(self):
        self.user_canceled = True
    
    # Retrieve the source path from the dialog box
    def getSourcePath(self):
        global OPTIONS
        #
        OPTIONS.setSrcFolder(self.getNextString())
        
        return OPTIONS.src_folder
    
    # Callback when Update button is pressed
    def updateFiles(self):
        #
        trace("Updating files")
        #
        # Find the source path in the dialog box (this is so clunky)
        src_path = self.getSourcePath()
        if len(src_path) == 0:
            #
            show_error("Missing source dir", "No source directory was selected!")
            return
        
        # Build a list of checkmark -> files -> ROI Info
        missing        = []
        scenes         = []
        img_pattern    = r'(_CQ_(?:\d+_\d+_)?RP\.tif)' #"_CQ_RP.tif"
        roi_pattern    = r'(_CQ(?:_\d+_\d+)?\.txt)'    #"_CQ.txt"
        #active_pattern = "-active.txt"                 # convert *.txt to *-active.txt
        matches        = self.fnmatch_regex(src_path, img_pattern)
        
        trace("+--> found: {}".format(len(matches)))
        
        if len(matches) > 0:
            #
            # Check to see if there are existing sessions
            self.session_mgr.set_src_path(src_path)
            if self.session_mgr.load_existing_state():
                #
                use_existing = False
                
                if not self.session_mgr.all_sessions_complete() and \
                   self.session_mgr.get_session_count() > 0:
                   # 
                   # We have existing sessions, ask if we should use them
                   if self.checkUseSessionData():
                       use_existing = True
                else:
                    # All of the sessions are complete, determine if we should continue or cancel
                    self.checkStartNewSession()
                
                # Existing sessions exists, and we are told to use it.  Close the existing
                # dialog and continue
                if use_existing:
                    self.restored = True
                    self.dispose()
                    return
                elif self.session_mgr.get_session_count() > 0:
                    self.session_mgr.reset()
        
            for filename in sorted(matches):
                #
                # Find the root of the name
                ciliaqfile = "*none*"
                root_name  = ""
                was_found  = False
                cq_match   = re.match(r'(^.*?)'+img_pattern, filename).groups()
                
                if len(cq_match) > 0 and len(cq_match[0]) > 0:
                    root_name = cq_match[0]
                    ciliaq = self.fnmatch_regex(src_path, re.escape(root_name) + roi_pattern, False)
                    if len(ciliaq) == 1:
                        ciliaqfile = ciliaq.pop()
                        was_found  = True
                        #
                        # Now add the files to the bundle manager
                        image_path  = self.create_fqn(src_path, filename)
                        roi_path    = self.create_fqn(src_path, ciliaqfile)
                        active_path = self.replace_ending(roi_path,  '.txt', '-active.txt')
                        
                        trace("image_path={}, roi_path={}, active_path={}".format(image_path, roi_path, active_path))
                        
                        # If the active path does not exist AND the roi path does, copy the ROI to create the ACTIVE.
                        # Starting with V0.5 (2/23/2025) we now make a copy of the ROI file and use that.  This ensures
                        # we never corrupt the original file.
                        if os.path.isfile(roi_path) and not os.path.exists(active_path):
                            trace("****>>>> copying to active")
                            shutil.copyfile(roi_path, active_path)
                        
                        # Now create the bundle using the active path
                        bundle = self.bundle_mgr.create_bundle(image_path, active_path)

                        # Now save the root image name for later slide name detection
                        scenes.append(bundle.get_image_filename())

                    else:
                        print("*** Found too many CQ.txt files! --> "+str(ciliaq))
                else:
                    missing.append(filename)

                trace("root={}, ciliaqfile={}, wasFound={}, matches={}".format(root_name, ciliaqfile, was_found, matches))
                
            # Take all detected scenes and attach them as slides.  Originally we tried to detect slides being used for multiple
            # scenes (i.e., ROI sets).  However this proved to be more complicated and ultimately determined to not be super
            # valuable.  So we now treat a scene as a slide which means we don't really need slides and scenes.  However I'm keeping
            # it for now just in case we change our minds.
            for bundle in self.bundle_mgr:
                slide = self.slide_mgr.find_slide(bundle.get_image_filename())
                
                if slide is None:
                    slide = self.slide_mgr.add_slide_root(bundle.get_image_filename())

                bundle.attach_slide(slide)
                slide.add_bundle(bundle)
                        
            # Build the output datasets
            files   = []
            columns = 1 if len(self.slide_mgr) <= 15 else 2
            
            # Add the output datasets to the data table and make it visible
            self.data_table.clear_table()
            for bundle in self.bundle_mgr:
                self.data_table.add_row([ bundle.get_id(), bundle.get_roi_length(), bundle.get_image_filename() ])
            self.data_table.setVisible(True)

            # Initially the table has not been dimensioned correctly because we didn't know the width
            self.data_table.set_table_width(self.getSize().width)

            # Show the changes
            self.showDialog()
            
            # Indicate that update has been called - current limitation we can only do this once
            self.ok_button.setEnabled(True)
            self.update_button.setEnabled(False)
            
    # Process all of the bundle detecting and creating the slides representing the common root filenames
    def detect_slides(self, scenes):
        #
        if scenes is None or len(scenes) == 0:
            return []
        
        try:
            # Take the list and sort.  We then attempt to detect the root of the name and when the root changes
            slides    = []
            scenes    = sorted(scenes)
            current   = None
            starting  = None
            match_pos = -1
            min_len   = 4        # minimum len of difference before we say they are the same
            remaining = len(scenes)
            
            for filename in scenes:
                #
                if current is None:
                    current   = filename
                    
                    # If this is the first entry AND there are more entries to process start from here.
                    if remaining > 1:
                        continue
                
                trace("** Processing: "+filename)
                
                if (filename != current) or (remaining == 1):
                    #
                    # Compare the filename and determine if this is the same match
                    max_len = len(filename) if len(filename) < len(current) else len(current)
                    matched = True
                    
                    trace("detectSlides: compare current={}, filename={}".format(current, filename))
                    
                    if match_pos > 0 and len(current) <= match_pos:
                        if current == filename[0: match_pos]:
                            trace("detectSlides: found match_pos match - same file")
                            # They are the same, let's continue
                            continue
                    
                    # Okay so try and find a new match position
                    for pos in range(0, max_len - 1):
                        #
                        if current[pos] != filename[pos]:
                            if pos < min_len:
                                trace("detectSlides: min_len trigger: pos={}, max_len={}".format(pos, max_len))
                                
                                # Too short of a match, assume the filename is the group
                                matched = False
                                break
                            
                            # Mark the spot
                            if pos != match_pos:
                                match_pos = pos
                                matched   = False
                            
                            # We are done
                            break
                      
                    trace("detectSlides: matched={}, max_len={}, match_pos={}".format(matched, max_len, match_pos))
                    trace("  +-->  current={}, filename={}".format(current, filename))
                    
                    # If we did not match, process the transition
                    if not matched:
                        if match_pos > 0:
                            # We previously found a index where they differ, use it
                            filename = filename[0: match_pos]
                            
                        if len(slides) == 0:
                            current  = current[0: match_pos]
                            #
                            trace("detectSlides: added new group: "+str(current))
                            # We never handled the current
                            slides.append(current)
                        
                        # Save the group name
                        if current != filename:
                            slides.append(filename)
                        
                            trace("detectSlides: added new group: "+str(filename))

                        # Transition to the new filename
                        current   = filename
                    elif len(scenes) == 1:
                        # Edge case in which there is only 1 total scene
                        slides.append(current)
            
                # We are done processing this slide
                remaining -= 1

            # We should have a set of plausible slides, add them to the SlideMgr
            print("trace: got {} scenes, resulted in {} slides".format(len(scenes), len(slides)))
            for slide in slides:
                trace("   +--> "+str(slide))
                self.slide_mgr.add_slide_root(slide)
                
            # Now process each bundle trying to attach it to the appropriate Slide
            for bundle in self.bundle_mgr:
                #
                slide = self.slide_mgr.find_slide(bundle.get_image_filename())
                
                if not slide is None:
                    bundle.attach_slide(slide)
                    slide.add_bundle(bundle)
                else:
                    print("detectSlides: ERROR: unable to attach bundle to slide: "+str(bundle.get_image_filename()))
            
        except BaseException as e:
            print("*** detectSlides: got exception processing: "+str(e))
            print(traceback.format_exc(e))

        return slides

    # We found existing session data, should we use it?
    def checkUseSessionData(self):
        #
        cd = GenericDialog("Use existing session information?")
        
        # Summarize what will happen:
        cd.addMessage("Existing session information has been found:")
        
        message  = "     Session     Images     # Roi      Status\n"
        for session in self.session_mgr:
            #
            status = "Pending" if not session.is_complete() else "Complete"
            message += "{:10} {:10} {:11}  --  {}\n".format(session.get_id(), \
                session.get_num_bundles(), session.get_num_roi(), status)
        cd.addMessage(message)
        
        # Update the font we want to use (fixed width to ensure things line up)
        msg = cd.getMessage()
        msg.setFont(FONT_MONO_BOLD)
        
        cd.addMessage("Press YES to continue using the session, NO to erase the session data and restart")

        # Now switch to a yes/no situation
        cd.enableYesNoCancel()
        cd.hideCancelButton()
        cd.showDialog()
        
        if cd.wasOKed():
            return True
        
        # Reset all of the managers so that we start from scratch
        self.session_mgr.reset()
        
        return False
    
    # All existing session data complete, should we erase and start a new session?
    def checkStartNewSession(self):
        #
        cd = GenericDialog("Existing session completed")
        
        # Summarize what will happen:
        cd.addMessage("Existing session information has been found:")
        
        message  = "     Session     Images      # Roi      Status\n"
        for session in self.session_mgr:
            #
            status = "Pending" if not session.is_complete() else "Complete"
            message += "{:10} {:10} {:12}  --  {}\n".format(session.get_id(), \
                session.get_num_bundles(), session.get_num_roi(), status)
        cd.addMessage(message)
        
        # Update the font we want to use (fixed width to ensure things line up)
        msg = cd.getMessage()
        msg.setFont(FONT_MONO_BOLD)
        
        cd.addMessage("All existings sessions have been completed.  Press New Session to start a new session.  Press Cancel to exit")

        # Now switch to a yes/no situation
        cd.enableYesNoCancel("New Session", "Cancel")
        cd.hideCancelButton()
        cd.showDialog()
        
        if not cd.wasOKed():
            raise UserWarning("Cancel")

        return True

    # Process most values in the UI
    def processValues(self):
        #
        global OPTIONS
        
        # Process the supplied directory
        OPTIONS.setSrcFolder(self.getNextString())
        
        # Now process the numeric fields.  These also don't have labels and thus need to be processed
        # in the same order they appear in the UI.  This code must match this order.
        OPTIONS.setSaturation(convertToFloat(self.sat_values[0].getText(), OPTIONS.c1_sat),
                              convertToFloat(self.sat_values[1].getText(), OPTIONS.c2_sat),
                              convertToFloat(self.sat_values[2].getText(), OPTIONS.c3_sat))

        trace("choices set: {}".format(OPTIONS))
        
        return True

    # Process the data table.  If items are selected it means omit!  
    def processDataTable(self):
        #
        global OPTIONS
        
        filename_column = 2  # zero index = column #3
        
        trace("processDataTable:")
        
        # TODO: we don't currently process the table - everything is always added.  The column order
        #     is critical - it must match the data definition above.  In order to selectively add we 
        #     need to determine on a per row basis if the row was selected or not.  The issue is 
        #     selecting rows to add means we need to have the user (or automatically) select all rows
        #     which visually is ugly.  The other option is to select those rows you don't want added.
        #     This would be counter intuitive.  Lastly we could add a column that is a check toggle such
        #     that selecting a row flips the state but does not keep the row highlighted.   TODO!
        for row in self.data_table:
            #
            filename = row[filename_column]
            
            trace("  +--> {}".format(filename))
            
            slide = self.slide_mgr.find_slide(filename)
            if slide is not None:
                slide.set_enabled(True)
            else:
                trace("ERROR matching slide -> root name={} cannot be located".format(root_name))
    
    # Given various parts of a filename construct a fully qualified filename
    def create_fqn(self, src_path, file_name, suffix=""):
        #
        return "{}{}{}{}".format(src_path, self.file_sep, file_name, suffix)
        
    # Search for matching filenames using the provides path and regex name expression
    def fnmatch_regex(self, src_path, file_name_regex, prefix_wildcard=True):
        #
        if (prefix_wildcard):
            pattern = r'.*?' + file_name_regex
        else:
            pattern = file_name_regex
        
        trace("fnmatch_regex: regex={}".format(pattern))
        
        # Now compile the expression
        re_pattern = re.compile(pattern)
        matches    = []
        
        # Now iterate over the file list pulling out matches
        for file in os.listdir(src_path):
            if re_pattern.match(file):
                matches.append(file)
                
        return matches

    # Simple replacement of end text in string
    def replace_ending(self, text, old_ending, new_ending):
        if text.endswith(old_ending):
            return text[:-len(old_ending)] + new_ending
        return text

    # Add a panel overriding how constraints are performed
    def addPanelRemainder(self, panel):
        #
        c = GridBagConstraints()
        c.gridwidth = GridBagConstraints.REMAINDER
        c.gridx     = 0
        #c.gridy    += c.gridy
        c.anchor    = GridBagConstraints.WEST
        c.insets    = Insets(5,0,0,0)
        
        self.add(panel, c)
    
    # Listener that allows us to detect when the UPDATE button is pressed
    class UpdateListener(ActionListener):
        #
        def __init__(self, dialog):
            #
            self.dialog = dialog
        #
        def actionPerformed(self, event):
            #
            try:
                trace("actionPerformed="+str(event))
                #
                self.dialog.updateFiles()
                
            except UserWarning as e:
                # If this is a cancel, indicate so
                print("User cancelled")
                self.dialog.setUserCanceled()
                self.dialog.dispose()
            except BaseException as e:
                print("actionPerformed -> exception: "+str(e))
                print(" --> "+traceback.format_exc(e))

    # Listener that allows us to detect when the Set Min/Max button is pressed
    class SetOptionsButtonListener(ActionListener):
        #
        def __init__(self, dialog):
            #
            self.dialog = dialog
        #
        def actionPerformed(self, event):
            #
            try:
                trace("actionPerformed="+str(event))
                
                # This dialog is self contained.  Once it returns it is dismissed.
                SetMinMaxOptionsDialog()
                
            except BaseException as e:
                print("actionPerformed -> exception: "+str(e))
                print(" --> "+traceback.format_exc(e))
        
    # Used to handle changes to the adjust type choice in the UI
    class AdjustTypeListener(ItemListener):
        #
        def __init__(self, dialog):
            #
            self.dialog = dialog
        #
        def itemStateChanged(self, event):
            #
            try:
                trace("AdjustTypeListener.itemStateChanged="+str(event))
                #
                self.dialog.handleUiVisibility()
                self.dialog.showDialog()
                #
            except BaseException as e:
                trace("AdjustTypeListener -> exception: "+str(e))

    # Code showing you how to tweak the font of items in the UI
    def setDialogCheckboxFont(self, font):
        try:
            # Get all declared fields in GenericDialog class
            fields = GenericDialog.getDeclaredFields()
            
            for field in fields:
                field.setAccessible(True)
                field_value = field.get(self)
    
                if field_value is None:
                    continue
                
                #print("font: checking field: "+str(field_value.__class__.__name__))
    
                # Check if the field is a list of components (messages, input fields, etc.)
                if "java.awt.Checkbox" in str(field_value):
                    trace("+---> "+str(field_value))
                    for component in field_value:
                        if hasattr(component, "setFont"):
                            component.setFont(font)
    
        except BaseException as e:
            print("Error setting font:" + str(e))
            print("   "+traceback.format_exc(e))

#
# Secondary dialog to prompt for the options to use while processing the results.
#
class ProcessFilesDialog(NonBlockingGenericDialog):
    #
    #LABEL_KEEP_UNUSED    = "Keep non-results"
    #LABEL_KEEP_HEADING   = "Keep result headers"
    #LABEL_USE_TAB_DEL    = "Use Tab delimiter"
    #LABEL_REM_BLANK_COLS = "Remove blank columns"
    #LABEL_ADD_SRC_NAME   = "Add source filename"
    #LABEL_ADD_SRC_COLUMN = "Add source filename to column number:"
    LABEL_ADVANCED_OPT   = "Advanced Options"
    
    # class level variables
    file_sep = os.path.sep

    def __init__(self, title, session_mgr):
        #
        # Initialize our parent class
        super(GenericDialog, self).__init__(title)
        
        # Save the session mgr for use during execution
        self.session_mgr = session_mgr
        
        # Initialize all of the fields with appropriate controls
        self.addMessage("We are about to process the montages.  They are grouped into sessions\n"+
                        "allowing continuation if you are interrupted.\n"+
                        " \n"+
                        "Once you are ready - press Continue")
        
        # Add the button to modify advanced options
        self.addButton(self.LABEL_ADVANCED_OPT, ProcessFilesDialog.AdvancedOptionsListener(self))
        # Summarize what will happen:  TODO - put this in a panel
        message  = "The following sessions will be processed:\n"
        message += "     Session     Images     # Roi      Status\n"
        
        for session in self.session_mgr:
            #
            status = "Pending" if not session.is_complete() else "Complete"
            message += "{:10} {:10} {:11}  --  {}\n".format(session.get_id(), \
                session.get_num_bundles(), session.get_num_roi(), status)
        self.addMessage(message)
        
        # Update the font we want to use (fixed width to ensure things line up)
        msg = self.getMessage()
        msg.setFont(FONT_MONO_BOLD)
        
        # Enable help for this screen
        self.addHelp(HELP.getHelp(HELP.KEY_PROCRSLT))
        
        # All set - show the dialog
        self.setOKLabel("Continue")
        self.showDialog()
        
        # Handle a cancel path
        if self.wasCanceled():
            raise UserWarning("Cancel")

        # Process the results
        self.processResults()
        
    # Take the resulting values and save them
    def processResults(self):
        #
        # The order of these operations on the array MUST match the order the checkboxes are added to the dialog
        #boxes = self.getCheckboxes()
        #OPTIONS.setKeepUnused(boxes[0].getState())
        #OPTIONS.setKeepHeading(boxes[1].getState())
        #OPTIONS.setUseTabDelimiter(boxes[2].getState())
        #OPTIONS.setRemBlankCols(boxes[3].getState())
        #OPTIONS.setAddSrcName(boxes[3].getState())
        
        # Now process the column number to use
        #numbers = self.getNumericFields()
        #OPTIONS.setAddSrcColumn(numbers[0].getText())
        pass
    
    # Listener that allows us to detect when the Advanced Options button is pressed
    class AdvancedOptionsListener(ActionListener):
        #
        def __init__(self, dialog):
            #
            self.dialog = dialog
        #
        def actionPerformed(self, event):
            #
            try:
                trace("actionPerformed="+str(event))
                
                # This dialog is self contained.  Once it returns it is dismissed.
                SetAdvancedOptions()
                
            except BaseException as e:
                print("actionPerformed -> exception: "+str(e))
                print(" --> "+traceback.format_exc(e))
        
# Dialog to set the 3-channel min/max values in OPTIONS
class SetMinMaxOptionsDialog(GenericDialog):
    #
    # Constants used for UI
    LABEL_MIN = "   Minimum"
    LABEL_MAX = "   Maximum"

    # Constructor
    def __init__(self):
        #
        # Initialize our parent class
        super(GenericDialog, self).__init__("Set MIN/MAX channel values")
        
        self.bc_values     = []
        self.bc_labels     = []

        self.addMessage("Please set the Min/Max values for each of the 3 channels\n")
        
        self.addMessage("------------ Channel 1 ------------")
        self.addNumericField(self.LABEL_MIN, OPTIONS.getBcMin(1), 0)
        self.addToSameRow()
        self.addNumericField(self.LABEL_MAX, OPTIONS.getBcMax(1), 0)

        self.addMessage("------------ Channel 2 ------------")
        self.addNumericField(self.LABEL_MIN, OPTIONS.getBcMin(2), 0)
        self.addToSameRow()
        self.addNumericField(self.LABEL_MAX, OPTIONS.getBcMax(2), 0)
        
        self.addMessage("------------ Channel 3 ------------")
        self.addNumericField(self.LABEL_MIN, OPTIONS.getBcMin(3), 0)
        self.addToSameRow()
        self.addNumericField(self.LABEL_MAX, OPTIONS.getBcMax(3), 0)
        
        # Enable help for this screen
        self.addHelp(HELP.getHelp(HELP.KEY_MMOPTIONS))
        
        self.showDialog()
        
        # Handle the min/max values fields
        if self.wasOKed():
            self.update_options()

    # Take the supplied values, ensure they are okay and set the options with them
    def update_options(self):
        #
        # Retrieve the values from the fields
        numbers = self.getNumericFields()
        if len(numbers) != 6:
            raise ValueError("SetMinMaxOptions: Number of expected numberic fields ({}) does not match actual: {}".format(len(numbers), 6))

        ch_1_min = convertToFloat(numbers[0].getText(), OPTIONS.getBcMin(1))
        ch_1_max = convertToFloat(numbers[1].getText(), OPTIONS.getBcMax(1))
        ch_2_min = convertToFloat(numbers[2].getText(), OPTIONS.getBcMin(2))
        ch_2_max = convertToFloat(numbers[3].getText(), OPTIONS.getBcMax(2))
        ch_3_min = convertToFloat(numbers[4].getText(), OPTIONS.getBcMin(3))
        ch_3_max = convertToFloat(numbers[5].getText(), OPTIONS.getBcMax(3))
        
        OPTIONS.setBcMinMax(1, ch_1_min, ch_1_max)
        OPTIONS.setBcMinMax(2, ch_2_min, ch_2_max)
        OPTIONS.setBcMinMax(3, ch_3_min, ch_3_max)
        
    # Takes the Min/Max values in Options and splits them apart
    def split_min_max(self, value, def_min, def_max):
        #
        try:
            return value.split(',')
        except BaseException as e:
            print("Error splitting min/max value {}: {}".format(str(value), str(e)))
            print("   "+traceback.format_exc(e))
            
        return def_min, def_max

# Dialog to set advanced OPTIONS
class SetAdvancedOptions(GenericDialog):
    #
    # Constants used for UI
    LABEL_ADD_SRC_NAME = "Column #"
    LABEL_DEBUG        = "Debug"
    LABEL_ROI_SIZE     = "ROI Size"
    LABEL_SCALE        = "Scale"
    
    # Constructor
    def __init__(self):
        #
        # Initialize our parent class
        super(GenericDialog, self).__init__("Set Advanced Options")
        
        self.addMessage("The options are as follows:\n"+
                        "  - Scale    - when creating the montage, scale the image by this amount\n"+
                        "  - ROI Size - length of edge when creating ROI square around target\n"+
                        "  - Debug    - turn on debug which adds labels to the montage for reference\n"+
                        "  - Column # - column number to add source filename to in CQ-stripped.txt file")

        print("SAO: starting up")

        # Create a custom panel to align the Choice, Spacer, and Button
        constraints = GridBagConstraints()
        gridbag     = GridBagLayout()
        self.panel  = Panel(gridbag)
        self.addPanel(self.panel)
    
        # Define overall settings
        constraints.ipadx = 8
        constraints.ipady = 8
        
        # Use column zero as a spacer in both X & Y dimensions
        spacer = Label("    ")
        self.setGridConstraints(gridbag, constraints, spacer, 0, 0, GridBagConstraints.EAST)
        self.panel.add(spacer)
        
        # Define the labels in column 1
        label_scale = Label(self.LABEL_SCALE)
        self.setGridConstraints(gridbag, constraints, label_scale, 1, 1, GridBagConstraints.EAST)
        self.panel.add(label_scale)

        label_roi_size = Label(self.LABEL_ROI_SIZE)
        self.setGridConstraints(gridbag, constraints, label_roi_size, 1, 2, GridBagConstraints.EAST)
        self.panel.add(label_roi_size)
        
        label_debug = Label(self.LABEL_DEBUG)
        self.setGridConstraints(gridbag, constraints, label_debug, 1, 3, GridBagConstraints.EAST)
        self.panel.add(label_debug)
        
        label_src_col = Label(self.LABEL_ADD_SRC_NAME)
        self.setGridConstraints(gridbag, constraints, label_src_col, 1, 4, GridBagConstraints.EAST)
        self.panel.add(label_src_col)

        # Define the controls in column 2
        constraints.gridy = 0
        constraints.anchor = GridBagConstraints.WEST

        self.choice_scale = Choice()
        for s in OPTIONS.SCALES:
            self.choice_scale.add(str(s))
        self.choice_scale.select(OPTIONS.SCALES[OPTIONS.scale - 1])

        self.setGridConstraints(gridbag, constraints, self.choice_scale, 2, 1, GridBagConstraints.WEST)
        self.panel.add(self.choice_scale)

        self.choice_roi_size = Choice()
        for r in OPTIONS.ROI_SIZE:
            self.choice_roi_size.add(str(r))
        self.choice_roi_size.select(OPTIONS.getRoiSizeIndexByValue())

        self.setGridConstraints(gridbag, constraints, self.choice_roi_size, 2, 2, GridBagConstraints.WEST)
        self.panel.add(self.choice_roi_size)

        self.chkbox_debug = Checkbox("", OPTIONS.debug)
        self.setGridConstraints(gridbag, constraints, self.chkbox_debug, 2, 3, GridBagConstraints.WEST)
        self.panel.add(self.chkbox_debug)

        self.src_column = TextField(str(OPTIONS.add_src_column), 3)
        self.setGridConstraints(gridbag, constraints, self.src_column, 2, 4, GridBagConstraints.WEST)
        self.panel.add(self.src_column)

        # Set any listeners needed
        self.src_column.addKeyListener(self);

        # Enable help for this screen
        self.addHelp(HELP.getHelp(HELP.KEY_AOPTIONS))

        # Now display 
        self.showDialog()
        
        # If not cancelled, process the results
        if self.wasOKed():
            self.processResults()

    # Helper to set grid bag constraints uniformly
    def setGridConstraints(self, gridbag, constraints, comp, row, column, anchor):
        #
        constraints.anchor = anchor
        constraints.gridx  = row
        constraints.gridy  = column
        gridbag.setConstraints(comp, constraints)
    
    # Take the resulting values and save them
    def processResults(self):
        #
        choice_val   = self.choice_scale.getSelectedItem()
        roi_size_val = self.choice_roi_size.getSelectedItem()
        scale        = OPTIONS.scale
        
        if choice_val == "1x":
            scale = 1
        elif choice_val == "2x":
            scale = 2
        elif choice_val == "3x":
            scale = 3
        else:
            trace("Unknown scale entered: {} - keeping default".format(scale))

        OPTIONS.setScale(scale)
        OPTIONS.setRoiSize(roi_size_val)
        OPTIONS.setDebug(self.chkbox_debug.getState())
    
    # Listener to validate src_column values (only permit numbers).  If we had more than one field
    # we would need to do this as seperate class or inline
    def keyTyped(self, ke):
        #
        #trace("keyTyped: {}".format(ke))
        
        keyChar = ke.getKeyChar()
        
        if len(keyChar) > 0 and not "{}".format(keyChar).isdigit():
            #trace("  +--> consuming!")
            ke.consume()

# Class used to display a table within a GenericDialog
class ScrollableTablePanel(Panel):
    def __init__(self, column_names, column_width, data=None, visible_rows=5):
        #
        Panel.__init__(self)
        self.setLayout(FlowLayout())
        
        # Remember the number of visible rows for later
        self.visible_rows = visible_rows

        # Define the table model with column names and empty data
        self.table_model = DefaultTableModel(data if data else [], column_names)

        # Create JTable with the model
        self.table = JTable(self.table_model)

        # Set the preferred viewport size to control visible rows
        row_height = self.table.getRowHeight()
        self.table.setPreferredScrollableViewportSize(Dimension(600, row_height * visible_rows))
        
        # Set the preferred column widths
        index = 0
        for width in column_width:
            self.table.getColumnModel().getColumn(index).setMaxWidth(width)
            index += 1

        # Wrap the table inside a JScrollPane to allow scrolling
        self.scroll_pane = JScrollPane(self.table)

        # Create a JPanel to hold the scroll pane
        swing_panel = JPanel(BorderLayout())
        swing_panel.add(self.scroll_pane, BorderLayout.CENTER)
        
        # Add the Swing panel to this AWT Panel
        self.add(swing_panel)

    def add_row(self, row_data):
        """Adds a row of data to the table."""
        self.table_model.addRow(row_data)
    
    def clear_table(self):
        """Removes all rows from the table."""
        self.table_model.setRowCount(0)
        
    def set_table_width(self, visible_width):
        #
        # Determine dialog width dynamically if available
        self.table_width = visible_width - 40  # Adjust for padding
        
        # Set the preferred viewport size to control visible rows
        row_height = self.table.getRowHeight()
        self.table.setPreferredScrollableViewportSize(Dimension(self.table_width, row_height * self.visible_rows))
        
    def set_column_alignment(self, column_num, alignment=JLabel.CENTER):
        #
        renderer = DefaultTableCellRenderer()
        renderer.setHorizontalAlignment( alignment )
        
        self.table.getColumnModel().getColumn(column_num).setCellRenderer(renderer)

    # Support the iterator to iterate over the data.  We return an array of columns per row
    def __iter__(self):
        # Iterator to iterate over data in the table
        if self.table_model.getRowCount() == 0:
            return None
            
        self._index = 0
        return self
        
    def __next__(self):
        # Next method for iterator (python3)
        if self._index < self.table_model.getRowCount():
            num_columns  = self.table_model.getColumnCount()
            vector       = self.table_model.getDataVector()
            row          = vector.get(self._index)
            result       = [r for r in row]
            self._index += 1
            return result
        else:
            raise StopIteration
            
    def next(self):
        # Next method for iterator (python2)
        return self.__next__()
        
# Create an error popup
def show_error(short_msg, message):
    #
    error_dialog = GenericDialog(short_msg)
    error_dialog.addMessage(message)
    error_dialog.hideCancelButton()
    error_dialog.showDialog()
