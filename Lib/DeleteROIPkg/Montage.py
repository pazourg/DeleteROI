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
import math
import random
import re
import threading

from java.awt               import BorderLayout, Color, FlowLayout, Font, GridBagLayout, GridBagConstraints
from java.awt.event         import ActionListener, MouseAdapter, InputEvent, WindowAdapter
from javax.swing            import JButton, JFrame, JPanel, JTextArea

from ij                     import IJ
from ij.gui                 import ImageCanvas
from ij.plugin.frame        import RoiManager
from ij.plugin              import MontageMaker, Zoom


# GUI Imports
from ij.gui                 import Roi, TextRoi, Overlay, Line, NonBlockingGenericDialog

# Our package imports
from DeleteROIPkg.Bundles   import RoiInfo
from DeleteROIPkg.Dialogs   import COLOR_LABEL, FONT_MONO
from DeleteROIPkg.Utilities import close_all, parm_screen_width, trace, OPTIONS

class MontageManager:
    #
    # Creates and manages the montage to be processed
    #
    def __init__(self, session_id, columns=5, rows=10, roi_size=64, border_width=4):
        #
        self.session_id   = session_id
        
        # Originally the ROI bounding box could have different width/height (i.e., not be a square). 
        self.cell_height  = roi_size
        self.cell_width   = roi_size
        self.border_width = border_width
        #
        self.bundles      = []            # All defined bundles with internal ROi data
        self.montages     = []            # The set of currently defined Montage objects
        self.random_roi   = []            # All ROI objects in random order
        self.locked       = False         # True when manager locked and randomization performed
        
        # Now we need to determine practical maximums
        self.screen_height, self.screen_width, self.m_columns, self.max_rows = \
            self.determine_screen_size(self.cell_height, self.cell_width, columns, rows, border_width)
    
    # Add a bundle to be processed
    def add_bundle(self, bundle):
        #
        if (bundle is None):
            raise Error("Bundle not specified")
            
        self.bundles.append(bundle)
        
    # Lock the bundles, this causes the creation of the random order used in showing the
    # montages to the user.
    def lock_bundles(self, debug=OPTIONS.debug):
        #
        if (self.locked):
            # We are already locked!
            raise Error("Attempt to lock bundles when already locked!")
        if len(self.bundles) == 0:
            raise ValueError("No bundles exist")
            
        # Lock the bundles and randomize everything
        self.locked = True
        
        # Ensure the bundles have been processed and then randomized
        for bundle in self.bundles:
            bundle.process(debug)
        
        # Now create the random_b structure containing the random items across the bundles
        total_entries = 0
        for bundle in self.bundles:
            if bundle.is_enabled():
                total_entries += bundle.get_roi_length()
        
        # Save up all ROI entries into an array so that we can populate the montage(s)
        roi_entries = []
        for bundle in self.bundles:
            for entry in bundle:
                roi_entries.append(entry)
       
        # Now randomize this list for processing
        for i in range(len(roi_entries)):
            random.shuffle(roi_entries)
        self.random_roi = roi_entries
        
    # Process the montage.  We have a set of bundles each representating an image and the associated ROI.
    # The montage will be a set of random ROI selected from the set of bundles.  This will allow us to 
    # present the ROI blind to the user.
    
    # This method processes all of the bundles resulting in an array of Montage objects that we will use
    # to display to the user.  This class implements Iterator enabling you to iterate over the Montage
    # objects displaying and collecting feedback from the user.  
    #
    # You must call create_montage before calling the iterator since this populates the underlying structures.
    #
    def create_montage(self, max_rows):
        #
        # Construct the Montage objects that will drive everything else.   They are constrainted to contain
        # a maximum of max_rows per montage.  Note that we might adjust max_rows based upon the calculated
        # maximum for the screen.
        if max_rows > self.max_rows:
            max_rows = self.max_rows
        #
        curr_montage       = None
        images_per_montage = self.m_columns * max_rows
        num_roi_proc       = 0
        montage_id         = 0
        
        # Process the random_roi
        for entry in self.random_roi:
            #
            if entry.isCulled():
                continue
            
            if curr_montage is None:
                montage_id += 1
                curr_montage = MontageManager.Montage(self, montage_id, self.session_id, self.m_columns, self.cell_height, self.cell_width, self.border_width)
                self.montages.append(curr_montage)
            
            trace("create_montage: images_per_montage={}, entry={}, num_roi_proc={}".format(images_per_montage, entry, num_roi_proc))
            
            # Add the entry to the montage.  They are already randomized so this is straight forward
            curr_montage.add_entry(entry)
            num_roi_proc += 1
            
            # Ensure we don't add more ROI then permitted
            if num_roi_proc >= images_per_montage:
                trace("Current montage full: {}".format(curr_montage.get_num_entries()))
                num_roi_proc = 0
                curr_montage = None

        return
    
    # Retrieve the current screen size and calculate the max size we will permit the montage
    def determine_screen_size(self, cell_height, cell_width, max_columns, max_rows, border_width):
        #
        trace("ScreenSize({}, {}, {}, {}, {})".format(cell_height, cell_width, max_columns, max_rows, border_width))

        dimension     = IJ.getScreenSize()
        screen_height = dimension.height
        screen_width  = dimension.width
        
        # Determine how many rows we can accomodate given the screen height & width
        cols = int((screen_width  - 100) / ((cell_width  * OPTIONS.scale) + border_width))
        rows = int((screen_height - 200) / ((cell_height * OPTIONS.scale) + border_width))
        
        if cols < max_columns:
            max_columns = cols
        if rows < max_rows:
            max_rows = rows

        trace("ScreenSize: screen_height={}, screen_width={}, max_columns={}, max_rows={}".format(screen_height, screen_width, max_columns, max_rows))

        return screen_height, screen_width, max_columns, max_rows
        
    # Returns the number of montages that exists
    def get_num_montages(self):
        #
        return len(self.montages)

    # Iterator to access available montages
    def __iter__(self):
        # Iterator to iterate over entry indices
        if self.montages is None or len(self.montages) == 0:
            raise KeyError("Failed to call create_montage - no montages available")
        
        self._index = 0
        return self

    def __next__(self):
        # Next method for iterator (python3)
        if self._index < len(self.montages):
            result = self.montages[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration
            
    def next(self):
        # Next method for iterator (python2)
        return self.__next__()
    
    #
    # Helper class to manage an instance of a montage
    class Montage:
        #
        # Static variables
        num_montages  = 0
        montage_maker = MontageMaker()
        leftButton    = 16;     # Bitmask from Java AWT
        rightButton   = 4;      # same
        
        # Constructor
        def __init__(self, montage_mgr, montage_id, session_id, columns=5, cell_height=64, cell_width=64, border_width=4):
            #
            self.montage_mgr  = montage_mgr
            self.montage_id   = montage_id
            self.session_id   = session_id
            self.border_width = int(border_width)
            self.cell_height  = int(cell_height)
            self.cell_width   = int(cell_width)
            self.m_columns    = int(columns)
            #
            # To be computed
            self.m_rows       = -1
            self.m__height    = -1
            self.m__width     = -1

            # The montage will display in the order added to the list
            self.roi_entries  = []    # RoiEntry being processed
            self.marked_cells = []    # row,col of montage cells to be omitted
            self.lbl_rois     = []    # roi's for labels on the montage
            
            # Now save a pointer to the generated image & dialog
            self.m_image      = None
            self.dialog       = None
            self.cancelled    = False

        # Add an entry to the montage
        def add_entry(self, roi_entry):
            #
            if not isinstance(roi_entry, RoiInfo.RoiEntry):
                raise ValueError("Attempt to insert non RoiEntry: "+str(roi_entry))
            
            # Save the roi_entry
            self.roi_entries.append(roi_entry)
        
            # Compute the montage dimensions.
            self.m_rows = int(math.ceil(float(len(self.roi_entries)) / float(self.m_columns)))
            
            trace("add_entry({}, {}, {})".format(len(self.roi_entries), self.m_columns, self.m_rows))

        # Returns the number of ROI entries currently defined
        def get_num_entries(self):
            return len(self.roi_entries)
        
        # Process all of the added entries creating a montage
        def process_montage(self, scale=1.0):
            #
            self.isCancelled(False)
            
            # ---- Block Execution Until Window is Closed ----
            self.condition  = threading.Condition()  # Create a condition variable for blocking
            self.txt_font   = Font("Calibri", Font.PLAIN, 16)

            self.m_image    = self.create_montage(scale)
            self.m_image.setOverlay(Overlay())

            self.m_canvas   = ImageCanvas(self.m_image)
            self.m_listener = MontageManager.Montage.DetectClicksListener(self)
            
            # We need to ensure that the image is at 100% at the moment otherwise the X,Y values don't line up
            self.m_canvas.setSize(self.m_width, self.m_height)
            
            image_panel = JPanel(FlowLayout(FlowLayout.CENTER))  # Center the image
            image_panel.add(self.m_canvas)
            
            # Set the listener to handle selection/deselection of images
            self.m_canvas.addMouseListener(self.m_listener)
            self.draw_grid()
            
            # Now embed the image into the dialog
            self.frame = JFrame("Montage #{} of {} for Session #{}".format(self.montage_id, self.montage_mgr.get_num_montages(), self.session_id))
            self.frame.setLayout(BorderLayout())
            self.frame.setResizable(False);
            self.frame.setSize(self.m_image.getWidth() + 50, self.m_image.getHeight() + 80)  # Adjust the window size

            # Create a panel for the help text
            text_area = JTextArea(2, 60)  # Text box (rows=5, columns=20)
            text_area.setFont(self.txt_font)
            text_area.setText("Please determine which images are to be excluded - clicking on an image\n"+
                              "to exclude/include.  Once you are finished please press \"Completed\"")
            text_area.setEditable(False)  # Make text read-only
            
            text_panel = JPanel(BorderLayout())
            text_panel.add(text_area, BorderLayout.WEST)
            
            # Create a panel for buttons
            cancel_button = JButton("Cancel")
            cancel_button.setFont(self.txt_font);
            cancel_button.addActionListener(MontageManager.Montage.CancelPressedListener(self))
            next_button   = JButton("Completed")
            next_button.setFont(self.txt_font);
            next_button.addActionListener(MontageManager.Montage.CompletedPressedListener(self))

            button_panel  = JPanel(FlowLayout(FlowLayout.RIGHT))
            button_panel.add(cancel_button)
            button_panel.add(next_button)

            # We need to add the text and buttons to a panel that will be placed at the bottom
            footer_panel = JPanel(GridBagLayout())             # Vertical Alignment
            constraints = GridBagConstraints()
            constraints.fill = GridBagConstraints.BOTH
            constraints.weighty = 1  # Allows the components to expand vertically
            constraints.anchor = GridBagConstraints.CENTER  # Centers vertically
            constraints.gridx = 0  # First column
            constraints.gridy = 0

            footer_panel.add(text_panel,   constraints)    # Text on left
            
            constraints.gridx = 1  # Second column
            footer_panel.add(button_panel, constraints)    # Buttons on right

            # Add components to the JFrame
            self.frame.add(image_panel,   BorderLayout.CENTER)  # Image on top
            self.frame.add(footer_panel,  BorderLayout.SOUTH)   # Footer panel at bottom-left
            
            # Finalize and display the window
            self.frame.setVisible(True)
            self.frame.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE)
            self.frame.addWindowListener(MontageManager.Montage.WindowCloseListener(self))

            # Block execution until window closes
            with self.condition:
                self.condition.wait()
            
            # We are done with the montage, hide it
            self.m_image.close()
            self.frame.dispose()
            
            # Determine if the user cancelled
            if self.wasCancelled():
                raise UserWarning("Cancel")
            
            # The culled list is a set of Row/Column values that we need to convert into the RoIEntry
            # values that we will then use to omit from the output file.
            for item in self.marked_cells:
                row, column = item.split(",")
                index       = ((int(row) - 1) * self.m_columns) + int(column)
                entry       = self.roi_entries[index - 1]
                
                trace(">>>> {}, {} = Index ({}) : {}".format(row, column, index, str(entry)))
                
                # Mark the entry as culled
                entry.setCulled(True)
                entry.markCulled(True)
                
            trace("Montage processing completed.  {} entries culled".format(len(self.marked_cells)))
            
            # If the user cancelled, raise it now
            if self.wasCancelled():
                raise UserWarning("Cancel")
            
        # Create the montage for this entry
        def create_montage(self, scale=1.0):
            #
            # The roi_entries structure is used to display the montage in order provided.
            roiManager = RoiManager.getInstance()
            if roiManager is None:
                raise ValueError("RoiManager was not setup")
            roiManager.reset()
            
            # local variables
            num_roi_entries   = len(self.roi_entries)
            roi_index         = 0
            stack_title       = "ROIs Stack_" + str(self.montage_id)
            slice_index       = 0
            
            # Computed variables
            self.mcell_height = int(self.cell_height * scale)
            self.mcell_width  = int(self.cell_width * scale)
            self.m_height     = int((self.mcell_height + self.border_width) * self.m_rows)
            self.m_width      = int((self.mcell_width  + self.border_width) * self.m_columns)
            
            # Create an empty stack for the montage
            IJ.newImage(stack_title, "RGB", self.mcell_width, self.mcell_height, num_roi_entries + 1);  # Create a stack to hold all the ROIs
            stack = IJ.getImage();
            stack.hide()
            
            trace(" roi_entries="+str(self.roi_entries))

            # Process the ROI info creating ROI entries as appropriate
            for entry in self.roi_entries:
            
                # Retrieve the current value
                bundle        = entry.get_roi_info().get_bundle()
                calibration   = entry.get_roi_info().calibration
                item_id       = entry.item_id
                item_x_center = int(entry.x_value * calibration) - int(self.cell_width/2)
                item_y_center = int(entry.y_value * calibration) - int(self.cell_height/2)
                roi_name      = "{}-{}".format(bundle.bundle_id, item_id)
                
                trace("image_id: {}, BID: {}, ID: {}, x={}, y={}".format(bundle.image.getID(), bundle.bundle_id, item_id, item_x_center, item_y_center))
        
                # Indicate which slice we are working on
                slice_index += 1

                # Set the ROI to the defined rectangle (centered at x, y) and add it to the RoiManager
                image = bundle.image
                trace("create_montage(title={})".format(image.getTitle()))
                if OPTIONS.debug:
                    image.show()
                else:
                    image.hide()
                image.setRoi(item_x_center, item_y_center, self.cell_width, self.cell_height);
                roiManager.add(image, image.getRoi(), -1)
                roiManager.rename(roi_index, roi_name)
            
                # Create a new image to hold the ROI extraction
                img_dup = image.duplicate()
                img_dup.hide()
                img_dup.setRoi(item_x_center, item_y_center, self.cell_width, self.cell_height);
                roi = image.getRoi()
                roi.setName(roi_name)
                img_dup.setTitle("title=ROIExtracted_" + item_id)
            
                # Resize the cropped image to requested pixels
                img_resize = img_dup.resize(self.mcell_width, self.mcell_height, "bilinear")
                img_resize.copy()
                
                # Paste the extracted image into the stack
                stack.setSlice(slice_index)    # Set the current slice to the i-th position
                stack.paste()
            
                # Close the extracted ROI image to keep things clean
                img_dup.close()
                img_resize.close()
                
                # The next roi slot to use
                roi_index += 1

            # There is an issue in which the last image pasted does not show up unless the montage is visible.  I suspect
            # it's around the image being updated on the screen.  As a workaround change the slice to finish the paste.  There is
            # likely a better way of forcing the window to update but this does work.
            stack.setSlice(slice_index+1)    # Set the current slice to the i-th position
            
            # At this point we have a stack of images ready to be used for the montage
            IJ.setBackgroundColor(0, 0, 0)  # Set the background color to black
            IJ.setForegroundColor(255,255,255)
            img_montage  = self.montage_maker.makeMontage2(stack, self.m_columns, self.m_rows, 1.0, 1, num_roi_entries, 1, self.border_width, False)
            img_montage.setTitle("Montage_{}".format(self.montage_id))

            # Now hide the montage until needed
            img_montage.hide()
            
            # Clean up some more
            stack.close()

            return img_montage
            
        # Draw grid function
        def draw_grid(self):
            #
            # using the overlay for the montage, draw a grid.  We always start with a new Overlay
            overlay = self.get_image_overlay(self.m_canvas, True)
            #
            num_cells      = len(self.roi_entries)
            
            trace("draw grid: rows={}, num_cells={}".format(self.m_rows, num_cells))
            #
            for i in range(1, self.m_columns):
                x = i * (self.mcell_width + self.border_width)
                trace("draw_grid({}, {}, {})".format(i, ((self.m_rows - 1) * self.m_columns) + i, num_cells))
                if ((self.m_rows - 1) * self.m_columns) + i > num_cells:
                    line = Line(x, 0, x, self.m_height - self.mcell_height)
                else:                    
                    line = Line(x, 0, x, self.m_height)
                overlay.add(line)
            for j in range(1, self.m_rows):
                y = j * (self.mcell_height + self.border_width)
                line = Line(0, y, self.m_width, y)
                overlay.add(line)
            #
            # Now draw any labels we are supposed to have
            self.draw_labels()
            
            return overlay
        
        # Draw the labels - mostly used to debug/validate data
        def draw_labels(self):
            #
            # using the overlay for the montage, draw a grid.  We always start with a new Overlay
            overlay = self.get_image_overlay(self.m_canvas)
            #
            if not OPTIONS.debug:
                trace("Skipping labels due to DEBUG: "+str(OPTIONS.debug))
                return overlay
            #
            num_cells = len(self.roi_entries)
            
            trace("draw labels: existing={}, rows={}, num_cells={}".format(len(self.lbl_rois), self.m_rows, num_cells))
            #
            for index in range(0, num_cells):
                #
                if len(self.lbl_rois) > index:
                    # We have an existing label, use it
                    label_roi = self.lbl_rois[index]
                else:
                    # Need to create the label
                    entry     = self.roi_entries[index]
                    label     = "{}-{}".format(entry.roi_info.bundle.bundle_id, entry.item_id)
                    #
                    row       = int(index / self.m_columns)
                    column    = int((index % self.m_columns))
                    x_value   = (self.mcell_height + self.border_width) * column
                    y_value   = (self.mcell_height + self.border_width) * row
                    label_roi = TextRoi(x_value, y_value, label, FONT_MONO)
                    label_roi.setColor(COLOR_LABEL)
            
                    trace("draw_labels: row={}, column={}, x={}, y={}, label={}".format(row, column, x_value, y_value, label))
                    
                    # Now save the roi we created, we append growing the array, matching the index number
                    self.lbl_rois.append(label_roi)
                    
                    if len(self.lbl_rois) != (index + 1):
                        raise ValueError("Index mismatch creating labels: array size={}, index={}".format(len(self.lbl_rois), index+1))
                    
                # Take the supplied label and add it to the image
                overlay.add(label_roi)
            #
            return overlay            
        
        # Function to toggle "X" overlay on cell click
        def toggle_x(self, row, column):
            #
            cell_key = "{},{}".format(row, column)
            
            trace("toggling X: "+cell_key)
            #
            if cell_key in self.marked_cells:
                self.remove_x(row, column)
                self.marked_cells.remove(cell_key)
            else:
                self.add_x(row, column)
                self.marked_cells.append(cell_key)
        
        # Draw "X" overlay for specific cell
        def add_x(self, row, column):
            #
            overlay     = self.get_image_overlay(self.m_canvas)
            cell_height = self.mcell_height + self.border_width
            cell_width  = self.mcell_width  + self.border_width
            #
            x1, y1 = (column - 1) * cell_height, (row - 1) * cell_height
            x2, y2 = x1 + cell_width, y1 + cell_width
            overlay.add(Line(x1, y1, x2, y2))   # Diagonal from top-left to bottom-right
            overlay.add(Line(x1, y2, x2, y1))   # Diagonal from bottom-left to top-right
        
        # Remove "X" overlay for specific cell
        def remove_x(self, row, column):
            # Workaround since Overlay.get() is unsupported; clear and redraw without the specific "X"
            # by replacing the Overlay.
            overlay = self.draw_grid()
            #
            match = "{},{}".format(row, column)
            #
            for item in self.marked_cells:
                if item != match:
                    r, c = map(int, item.split(","))
                    self.add_x(r, c)  # Re-add other "X" overlays
        
        # Helper function to create an overlay and set the default properties/attributes
        def get_image_overlay(self, image, recreate=False):
            #
            overlay = image.getOverlay()
            if overlay is None or recreate:
                #
                overlay = Overlay()
                image.setOverlay(overlay)
                #
                overlay.setLabelColor(Color.WHITE)
                overlay.drawLabels(False)

            return overlay
        
        # Handle cancellation
        def wasCancelled(self):
            return self.cancelled
            
        def isCancelled(self, cancelled=True):
            self.cancelled = cancelled
            #
            if cancelled:
                with self.condition:
                    self.condition.notify_all()
            
        # Overload the str() function to print something useful
        def __repr__(self):
            #
            return "montage({}, {})".format(self.montage_id, len(self.roi_entries))

        # Helper class to handle button pressess for Montage display
        class CancelPressedListener(ActionListener):
            def __init__(self, montage):
                self.montage = montage
            #
            def actionPerformed(self, event):
                self.montage.isCancelled()   
                #IJ.log("Cancel Clicked!")  # Replace with your logic to load next image

        class CompletedPressedListener(ActionListener):
            def __init__(self, montage):
                self.montage = montage
            #
            def actionPerformed(self, event):
                with self.montage.condition:
                    self.montage.condition.notify_all()  # Wake up the main thread
                #IJ.log("Completed Clicked!")  # Replace with your logic to load next image
                
        class WindowCloseListener(WindowAdapter):
            #
            def __init__(self, montage):
                self.montage = montage
            #
            def windowClosing(self, event):
                """Unblock execution when the window is closed."""
                #IJ.log("Window closed.")
                self.montage.frame.dispose()       # Dispose window properly
                with self.montage.condition:
                    self.montage.condition.notify_all()  # Wake up the main thread
            
        # Helper class to handle mount clicks
        class DetectClicksListener(MouseAdapter):
            #
            def __init__(self, montage):
                #
                self.montage      = montage
                self.mcell_height = montage.mcell_height + montage.border_width
                self.mcell_width  = montage.mcell_width  + montage.border_width
                
            # Respond to the mouse being pressed
            def mousePressed(self, event):
                #
                trace("got mouse event: "+str(event))
                trace(" +--> {} : {}".format(event.getModifiers(), InputEvent.BUTTON1_MASK))
                
                # If left mouse button pressed, let the montage know about it
                if (event.getModifiers() & InputEvent.BUTTON1_MASK):
                    #
                    clickedRow    = int(event.getY() // self.mcell_height) + 1
                    clickedColumn = int(event.getX() // self.mcell_width)  + 1
                    #
                    trace("Mouse button pressed: {}-{}".format(clickedRow, clickedColumn))
                    #
                    try:
                        self.montage.toggle_x(clickedRow, clickedColumn)
                        
                        self.montage.m_canvas.repaint()
                        
                    except BaseException as e:
                        print("Error handling mouse click:", e)
