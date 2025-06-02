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

import os
import re
import shutil
import traceback

from java.awt               import Color
from datetime               import datetime

from ij                     import CompositeImage, IJ, WindowManager
from ij.gui                 import NonBlockingGenericDialog
from ij.plugin              import ZProjector
from ij.process             import LUT

# Our package imports
from DeleteROIPkg.Utilities import close_all, trace, OPTIONS

     
# Manager to handle all defined bundles    
class BundleManager:
    #
    next_bundle_id = 0
    
    #
    # Creates and manages the bundles to be processed
    #
    def __init__(self):
        #
        self.bundles = []            # All defined bundles with internal ROi data
    
    # Create a bundle to be processed
    def create_bundle(self, image_path, roi_data_path, bundle_id=-1):
        #
        if (image_path is None):
            raise ValueError("Image path not specified")
        if (roi_data_path is None):
            raise ValueError("ROI data path not specified")
        
        # Determine if the image_path/roi_data_path is already present
        bundle = self.find_bundle(image_path, roi_data_path)
        
        # Construct the bundle
        if (bundle is None):
            if bundle_id == -1:
                BundleManager.next_bundle_id += 1
                bundle_id = BundleManager.next_bundle_id
            elif bundle_id > BundleManager.next_bundle_id:
                BundleManager.next_bundle_id = bundle_id
                
            bundle = CiliaQBundle(bundle_id, image_path, roi_data_path)
        
            # Add it to the save array
            self.bundles.append(bundle)
        
        return bundle
    
    # Save the changes that have occured in the bundles
    def save_changes(self, group_path, dry_run=False):
        #
        completed = True
        success   = []
        failed    = []
        
        for bundle in self.bundles:
        
            if not bundle.is_enabled():
                continue
             
            # Save the changes and result the results
            result, errors, msgs = bundle.save_changes(group_path, dry_run)
            
            # If the result failed we will return an overall False
            if not result:
                completed = False

            success  += msgs
            failed   += errors
        
        # Return out values
        return completed, success, failed
    
    # Find any existing bundle
    def find_bundle(self, image_path, roi_data_path):
        #
        if image_path is None or roi_data_path is None:
            return None

        found_bundle = None
        for bundle in self.bundles:
            if image_path == bundle.get_image_path() and roi_data_path == bundle.get_roi_path():
                found_bundle = bundle
                break
                
        return found_bundle
    
    # Find bundle matching image filename (not full path)
    def find_bundle_by_image_filename(self, filename):
        #
        found_bundle = None
        
        # The filename may contain spaces which should be interpreted as single character wildcards
        pattern = re.escape(filename).replace(r'\ ', r'.*')
        matcher = re.compile(pattern)
        #
        for bundle in self.bundles:
            match = matcher.match(bundle.get_image_filename())
            #
            #trace("checking bundle: match={}, {}, {}".format(match is not None, bundle.get_image_filename(), filename))
            if match:
                found_bundle = bundle
                break
                
        return found_bundle
        
    # Find the bundle by ID
    def find_bundle_by_id(self, bundle_id):
        #
        found_bundle = None
        bundle_id    = int(bundle_id)
        
        for bundle in self.bundles:
            if bundle.get_id() == bundle_id:
                found_bundle = bundle
                break
                
        return found_bundle

    # Reset the manager to the initial state
    def reset(self):
        #
        BundleManager.next_bundle_id = 0
        self.bundles = []

    # Return the number of bundles currently registered
    def get_length(self):
        return len(self.bundles)

    # Iterator to access available montages
    def __iter__(self):
        # Iterator to iterate over entry indices
        if self.bundles is None or len(self.bundles) == 0:
            return None
        
        self._index = 0
        return self

    def __next__(self):
        # Next method for iterator (python3)
        if self._index < len(self.bundles):
            result = self.bundles[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration
            
    def next(self):
        # Next method for iterator (python2)
        return self.__next__()
    
class CiliaQBundle:
    #
    # This class is used to process an image/CiliaQ txt file generating the appropriate ROI information 
    #
    def __init__(self, bid, image_path, roi_data_path):
        # 
        if not os.path.isfile(image_path):
            raise ValueError("Supplied image_path is not a file: "+str(image_path))
        if not os.path.isfile(roi_data_path):
            raise ValueError("Supplied roi_data_path is not a file: "+str(roi_data_path))
        
        # Now save the path information
        self.bundle_id     = bid
        self.image_path    = image_path
        self.roi_data_path = roi_data_path

        # Pointer to slide we are associated with
        self.slide         = None
        
        # Pointer to active images
        self.image         = None
        
        # Indicates if this bundle is enabled or not
        self.enabled       = True
        
        # Process the ROI data at this point.  This is lightweight
        self.roi_info      = self.process_roi(roi_data_path)

    # Return the Bundle ID
    def get_id(self):
        return self.bundle_id
    
    # Return the number of roi entries
    def get_roi_length(self):
        if self.roi_info is not None:
            return self.roi_info.get_data_len()
        else:
            return 0
    
    # Handle the enabled/disabled status
    def is_enabled(self):
        # Originally we controlled it, but now we delegate to the slide if it exists
        if self.slide:
            return self.slide.is_enabled()
        else:
            return self.enabled
        
    def set_enabled(self, status=True):
        self.enabled = status

    # Attach the bundle to the provided slide
    def attach_slide(self, slide):
        #
        self.slide = slide
    
    # Returns the defined fully qualified image_path 
    def get_image_path(self):
        return self.image_path
        
    # Return just the filename contained in the image_path
    def get_image_filename(self):
        return os.path.basename(self.image_path)
    
    # Returns the defined roi_data_path 
    def get_roi_path(self):
        return self.roi_data_path

    # Return just the filename contained in the image_path
    def get_roi_filename(self):
        return os.path.basename(self.roi_data_path)

    # Return the underlying RoiInfo containing the ROI for this bundle
    def get_roi_info(self):
        return self.roi_info
        
    # Returns the root for the slide we are assocated with, None if no slide
    def get_slide_root(self):
        #
        if self.slide is not None:
            return self.slide.get_root_filename()
        
        return None
    
    # Process the image and generate the ROI data
    def process(self, debug=OPTIONS.debug):
        #
        # Process the image, saving the resulting image for use by montage
        if self.image is None:
            self.image = self.process_image(self.image_path, debug)
        
        # Now process the ROI information - should already be done
        if self.roi_info is None:
            self.roi_info = self.process_roi(self.roi_data_path)
        
        # Final validation
        result = self.roi_info.validateRoiInfo()
        if result is not None:
            IJ.showMessage("Error processing TXT File", "Error while processing image: {} --> {}".format(self.get_image_filename(), result))
            return

    # If there are changes to the ROI file, save them now
    def save_changes(self, group_path, dry_run=False):
        if dry_run:
            return self.roi_info.determine_changes(group_path)
        else:
            return self.roi_info.save_changes(group_path)

    # Iterator to access available ROI entries
    def __iter__(self):
        if self.roi_info is not None:
            return self.roi_info.__iter__()
        
        return self

    def __next__(self):
        raise StopIteration
            
    def next(self):
        return self.__next__()
    
    # Private methods - not meant to be called external to class
    
    # Function to open and process the image
    def process_image(self, image_path, show=False):
        #
        # Open the primary image
        image = IJ.openImage(image_path)
        image.hide()
        #
        # TODO: Edit LUT to change channel one 255 to Blue (0,0,255)
        img_lut = self.modify_color_mask(image)
        img_lut.hide()
        
        # Perform any required filters, etc.
        #
        img_zp = ZProjector.run(img_lut, "max")
        img_zp.hide()
        
        # After the ZProjector the min/max values are zero.  Reset them and continue
        img_zp.setC(1)
        ip1 = img_zp.getChannelProcessor()
        ip1.resetMinAndMax()
        img_zp.setC(2)
        ip1 = img_zp.getChannelProcessor()
        ip1.resetMinAndMax()
        img_zp.setC(3)
        ip1 = img_zp.getChannelProcessor()
        ip1.resetMinAndMax()
        img_zp.updateAndRepaintWindow()

        # Auto adjust the constrast on the zprojector image
        if OPTIONS.adjust_type == OPTIONS.TYPE_ADJUST_MIN_MAX:
            self.adjust_image_bc_min_max(img_zp)
        elif OPTIONS.adjust_type == OPTIONS.TYPE_ADJUST_SATURATION:
            self.adjust_image_sauration(img_zp, OPTIONS.c1_sat, OPTIONS.c2_sat, OPTIONS.c3_sat)
        elif OPTIONS.adjust_type == OPTIONS.TYPE_ADJUST_AUTO:
            self.adjust_image_auto(img_zp, OPTIONS.buffer_percent)
        else:  # must be manual or unknown
            # Since the user is going to manually adjust, ensure the image is being shown and then cause
            # the Brightness & Contrast control to be shown
            img_zp.show()
            IJ.run("Brightness/Contrast...")
            
            # We explicitly use non-blocking dialog to allow the user to do other things (like adjust)
            manual = NonBlockingGenericDialog("Waiting for manual adjustment")
            manual.addMessage("The image is being displayed in a seperate window.  Please manually adjust the image\n"+
                              "to be processing.  Once completed please select OK")
            manual.showDialog()
            # Did the user cancel?
            if manual.wasCanceled():
                raise UserWarning("Cancel")

        # Convert to RGB, doing it programatically did not work and I can't figure out why
        img_zp.show()         # Just in case the image was manually closed by the user
        IJ.run("RGB Color")   # The currently showing image is converted
        
        # Retrieve the RGB Color image
        img_rgb = WindowManager.getCurrentImage()
        
        # Show it to the user if requested
        if not show:
            img_rgb.hide()
        
        # Lastly, update the name to make debugging easier
        name = img_rgb.getTitle()
        img_rgb.setTitle(name + " (ID: {})".format(self.bundle_id))
        
        # Now cleanup
        image.close()
        img_lut.close()
        img_zp.close()
        
        # All done, we have an image fully processed - return it
        return img_rgb

    #
    # Modify the channel containing the mask by changing the max intensity (WHITE) to be BLUE.  This
    # method does NOT create a new image, it only modifies the image provided.
    #
    def modify_color_mask(self, image, newImage=True, c1_name="Blue", c2_name="Green", c3_name="Red"):
        #
        if not isinstance(image, CompositeImage):
           raise ValueError("Image must be a composite image to modify channel LUTs.")
    
        #trace("modifyMaskColor - channel={}, title={}".format(channel, image.getTitle()))
        
        # Now process the channel changing the LUT
        if newImage:
            updated = image.duplicate()
        else:
            updated = image
        updated.setTitle("{} (COLORS)".format(image.getTitle()))
        updated.hide()

        updated.setMode(CompositeImage.COMPOSITE)

        # Change the mask channel - preserve the min/max values
        updated.setChannelLut(LUT.createLutFromColor(Color.BLUE),  1)
        updated.setChannelLut(LUT.createLutFromColor(Color.GREEN), 2)
        updated.setChannelLut(LUT.createLutFromColor(Color.RED),   3)
        
        # Ensure channel 1 (Mask) has the correct min/max values - we really should validate
        # that channel 1 is the actual mask channel otherwise this is likely the wrong thing
        # to do.
        updated.setC(1)
        ip1 = updated.getChannelProcessor()
        ip1.setMinAndMax(0, 255)

        updated.setC(1)
        updated.updateAndRepaintWindow()
        
        trace("modifyMaskColor = window="+str(updated.getWindow()))

        return updated

    # Method to determine the min/max pixel values to be used to "automatically" adjust contrast.
    # The results is a pair: min max
    #
    # Parameters:
    #   buffer_percent = the % to enlarge the window to include more stuff to ensure we don't clip the image
    #
    def adjust_image_auto(self, image, buffer_percent=0.50):
        #
        # Ensure we have an image
        if image is None:
            return None
        
        trace("adjust_image_auto(buffer_percent={})".format(buffer_percent))
        
        # Ensure the image has multiple channels
        if image.getNChannels() < 2:
            IJ.showMessage("This script is for multi-channel images only.")
        else:
            # Calculate min and max for each channel
            num_channels = image.getNChannels()
            min_values   = []
            max_values   = []
            
            # Calculate min and max based on a percentage cutoff
            lower_percentile = 0.01   # Bottom 1%
            upper_percentile = 0.99   # Top 99%
            pixel_range      = 2 ** image.getBitDepth()     # Max value of a pixel
    
            # Iterate through each channel
            for channel in range(1, num_channels + 1):
                # Set the active channel
                image.setC(channel)
                
                # Calculate the min and max values for the current channel using the raw processor
                stack     = image.getStack()
                processor = stack.getProcessor(channel)
                stats     = processor.getStats()
                
                #trace("AIMAM: [{}]: stats={}".format(channel, str(stats)))
                
                # Calculate cumulative histogram to determine percentile cutoffs
                histogram       = stats.histogram()
                cumulative_hist = [sum(histogram[:i + 1]) for i in range(len(histogram))]
                total_pixels    = cumulative_hist[-1]
                bin_width       = pixel_range / len(histogram)  # Width of each histogram bin
                
                if channel == 1:
                    trace("AIMAM: [{}]: histogram={}".format(channel, histogram))
            
                # Calculate minimum intensity based on lower percentile
                #min_cutoff = next((i for i, count in enumerate(cumulative_hist) if count >= lower_percentile * total_pixels), stats.min)
                lower_target = lower_percentile * total_pixels
                min_bucket = next((i for i, count in enumerate(cumulative_hist) if count >= lower_target), 0)
            
                # Calculate maximum intensity based on upper percentile and buffer factor
                #max_cutoff = next((i for i, count in enumerate(cumulative_hist) if count >= upper_percentile * total_pixels), stats.max)
                upper_target = upper_percentile * total_pixels
                max_bucket = next((i for i, count in enumerate(cumulative_hist) if count >= upper_target), len(histogram) - 1)
                
                # Convert buckets to pixel intensity
                min_cutoff = int(min_bucket * bin_width)
                max_cutoff = int(max_bucket * bin_width)
        
                # Apply buffer to the cutoffs to broaden the amount
                buffer_min = int(buffer_percent * pixel_range)
                buffer_max = int(buffer_percent * pixel_range)
        
                # Extend the cutoffs based on the buffer
                min_cutoff = max(0, min_cutoff - buffer_min)  # Ensure it doesn't go below 0
                max_cutoff = min(pixel_range - 1, max_cutoff + buffer_max)  # Ensure it doesn't exceed the max value
        
                # If we went too far adjust back now
                if min_cutoff < stats.min:
                    min_cutoff = stats.min
                if max_cutoff > stats.max:
                    max_cutoff = stats.max
                
                trace(" +--> min_cut={}, max_cut={}, buffer_min={}, buffer_max={}".format(min_cutoff, max_cutoff, buffer_min, buffer_max))
                
                min_values.append(min_cutoff)
                max_values.append(max_cutoff)
                
            # Adjust contrast/brightness based on min and max values for each channel
            #trace("calculated values:")
            #for i in range(0, len(min_values)):
            #    trace("+--> [{}] = min={}, max={}".format(i, min_values[i], max_values[i]))

            for channel in range(1, num_channels + 1):
            
                image.setC(channel)
                ip1 = image.getChannelProcessor()
                ip1.setMinAndMax(min_values[channel - 1], max_values[channel - 1])  
                
                trace("adjust_image_auto - channel[{}] : min={}, max={}".format(channel-1, min_values[channel-1], max_values[channel-1]))
            
            # Update the display
            image.updateAndDraw()
        
        return image

    # Adjust the min/max values of each channgel
    def adjust_image_bc_min_max(self, image):
        #
        num_channels = image.getNChannels()
        
        trace("adjust_image_bc_min_max(title: {}, num_channels={})".format(image.getTitle(), num_channels))
        
        for channel in range(1, num_channels + 1):
            #
            bc_min = OPTIONS.getBcMin(channel)
            bc_max = OPTIONS.getBcMax(channel)
            
            trace("   --> channel: {}, min: {}, max: {}".format(channel, bc_min, bc_max))
            
            image.setC(channel)
            ip1 = image.getChannelProcessor()
            
            # Debug: Check existing min/max before changing
            #stats = ip1.getStatistics()
            #trace("Before update - Channel {}: mean={}, min={}, max={}".format(channel, stats.mean, stats.min, stats.max))

            ip1.resetMinAndMax()
            ip1.setMinAndMax(bc_min, bc_max)
            image.setDisplayRange(bc_min, bc_max)
            image.updateAndDraw()
            
        # We need to force the update to get all channels to be rendered correctly
        image.updateAndDraw()

    # Adjust the contrast of the provided image.  A new image is NOT created, just modified in place.
    def adjust_image_sauration(self, image, c1_sat, c2_sat, c3_sat):
        #
        trace("adjust_image_sauration({}, {}, {}) : title: {}".format(c1_sat, c2_sat, c3_sat, image.getTitle()))
        
        # TODO: determine what we want to do to channel 1 (Mask) including actually detecting it is the mask
        if c2_sat >= 0:
            image.setC(2)  # Set the current channel to 2
            processor = image.getChannelProcessor()  # Get the processor for the current channel
            processor.resetMinAndMax()  # Reset min and max values for contrast enhancement
            IJ.run(image, "Enhance Contrast", "saturated=" + str(c2_sat))  # Enhance contrast for channel 2

        if c3_sat >= 0:
            image.setC(3)  # Set the current channel to 3
            processor = image.getChannelProcessor()  # Get the processor for the current channel
            processor.resetMinAndMax()  # Reset min and max values for contrast enhancement
            IJ.run(image, "Enhance Contrast", "saturated=" + str(c3_sat))  # Enhance contrast for channel 3
        
        # The image was modified but it is the same image
        image.updateAndDraw()
        
    # Function to process the ROI information
    def process_roi(self, roi_data_path):
        #
        # roi_info structure will all of the important stuff
        roi_info = RoiInfo(self)
    
        #
        # Open the CiliaQ output file (likely a tab delimited CSV)
        #
        with open(roi_data_path, 'r') as file:
            #
            rows = file.read().splitlines()

            # Variables to store the metadata information
            roi_info        = RoiInfo(self)
            calibration     = 1.0
            history_region  = 0
            settings_region = 0
            results_region  = 0
            row_count       = len(rows)

            # We need to find the settings , History, and Results regions.  We use this to then find the calibration settings
            for index in range(row_count):
                if rows[index].startswith("Settings:"):
                    settings_region = index
                    break
        
            for index in range(settings_region + 1, row_count):
                if rows[index].startswith("History:"):
                    history_region = index
                    break
        
            for index in range(history_region + 1, row_count):
                if rows[index].startswith("Results:"):
                    results_region = index
                    break
        
            if history_region == 0:
                history_region = results_region
        
            trace("Regions:  settings={}, history={}, results={}".format(settings_region, history_region, results_region))
            
            # Now find the calibration setting
            start_column     = 1
            expected_columns = 3 + start_column
            
            for index in range(settings_region + 1, history_region - 1):
                # We normalize this to a CSV format by converting any tabs to ","
                columns = rows[index].replace("\t", ",").split(",")
                #
                if len(columns) < expected_columns:
                    trace("SKIPPING --> {} < {}".format(len(columns), expected_columns))
                    continue    # Insufficient columns - skip
                
                trace("[{}, {}]: [0]={},[1]={},[2]={}".format(index, len(columns), columns[0], columns[1], columns[2]))
                
                if columns[start_column].startswith("Calibration"):
                    calibration = 1 / float(columns[start_column + 1])
                    trace("calibration = {}".format(calibration))
                    break
        
            # Loop through each row, starting from the Results: marker + 2 (skip headers)
            start_column     = 2
            expected_columns = 3 + start_column
            processed_rows   = 0
            
            for index in range(results_region + 2, row_count):
                
                 # Determine if this row is culled, 
                is_culled = rows[index].startswith('#')
                
                # We normalize this to a CSV format by converting any tabs to ","
                columns = rows[index].replace("\t", ",").split(",")
                
                if len(columns) < expected_columns:
                    trace(" SKIPPING row[{}] --> ({})={}".format(index, len(columns), rows[index]))
                    continue
                
                #trace("Processing: "+rows[index])
                
                # Save the values
                item_id = columns[start_column]
                item_x  = columns[start_column + 1]
                item_y  = columns[start_column + 2]
                
                #trace("+--> {}, {}, {}".format(item_id, item_x, item_y));
                
                if len(item_id) > 0 and len(item_x) > 0 and len(item_y) > 0:
                    # Save to the RoiInfo object
                    roi_info.add_entry(item_id, float(item_x), float(item_y), is_culled)
                    
                    # We successfully stored a row
                    processed_rows += 1
        
            # Save the metadata information
            roi_info.set_metadata(row_count, history_region, results_region - history_region, processed_rows, calibration, roi_data_path)
            
            # DBG: Print results to confirm the arrays were populated correctly
            trace("processed_rows={}, roi_info Results: ".format(processed_rows))
            #for item in roi_info:
            #    trace("     +--> [{}]: {}".format(item, roi_info.get_entry(item)))
        
            return roi_info

    # Overload the str() function to print something useful
    def __repr__(self):
        #
        return "bundle({}, {}, {})".format(self.get_image_filename(), self.get_roi_filename(), self.enabled)

# Class to store the ROI information for a bundle
class RoiInfo:
    #
    # This class is used to track the ROI information for a specific TIF file/CiliaQ TXT output.
    def __init__(self, bundle):
        #
        # Store the bundle we are associate with
        self.bundle      = bundle
        
        # Initialize metadata as explicit attributes
        self.row_count   = 0
        self.header_len  = 0
        self.data_len    = 0
        self.calibration = 1.0
        self.file_name   = ""
        
        # Initialize the entries list
        self.entries = []  # To store entries with item_id, x_value, y_value

    # Save the metadata
    def set_metadata(self, row_count=None, header_len=None, history_len=None, data_len=None, calibration=None, file_name=None):
        #
        trace("set_metadata: bundle_id={}, row_count={}, header_len={}, history_len={}, data_len={}, calibration={}, file_name={}"
            .format(self.bundle.bundle_id, row_count, header_len, history_len, data_len, calibration, file_name))
        
        # Set individual metadata fields if provided, otherwise retain current values.
        if row_count is not None:
            self.set_row_count(row_count)
        if header_len is not None:
            self.set_header_len(header_len)
        if history_len is not None:
            self.set_history_len(history_len)
        if data_len is not None:
            self.set_data_len(data_len)
        if calibration is not None:
            self.set_calibration(calibration)
        if file_name is not None:
            self.set_file_name(file_name)

    # Metadata setters
    def set_row_count(self, value):
        self.row_count = value
        
    # The number of rows in the header
    def set_header_len(self, value):
        self.header_len = value

    # The number of rows in the history section
    def set_history_len(self, value):
        self.history_len = value

    # The number of rows in the data (should equal len(entries)
    def set_data_len(self, value):
        self.data_len = value

    # The computed calibration value
    def set_calibration(self, value):
        self.calibration = value

    # The file name the ROI information is from
    def set_file_name(self, value):
        self.file_name = value

    # Retrieve the bundle we are associated with
    def get_bundle(self):
        return self.bundle
    
    # Metadata getters
    def get_row_count(self):
        return self.row_count

    def get_header_len(self):
        return self.header_len

    def get_history_len(self):
        return self.history_len

    def get_data_len(self):
        return self.data_len

    def get_calibration(self):
        return self.calibration

    def get_file_name(self):
        return self.file_name

    # Method to add an entry
    def add_entry(self, item_id, x_value, y_value, is_culled=False):
        # Add a new entry with specified item_id, x_value, and y_value.
        self.entries.append(RoiInfo.RoiEntry(self, item_id, x_value, y_value, is_culled))
        
    # Getter method for values in an entry by index - really a private method, don't use
    def get_entry(self, index):
        # Retrieve entry at specified index.
        if 0 <= index < len(self.entries):
            return self.entries[index]
        else:
            raise IndexError("Entry index out of range")
            
    def get_item_id(self, index):
        # Retrieve the item_id at the specified index
        entry = get_entry(index)
        if (entry is not None):
            return entry.item_id
        else:
            raise KeyError("Key '{}' not found".format(index))

    def get_x_value(self, index):
        # Retrieve the item_id at the specified index
        entry = get_entry(index)
        if (entry is not None):
            return entry.x_value
        else:
            raise KeyError("Key '{}' not found".format(index))
            
    def get_y_value(self, index):
        # Retrieve the item_id at the specified index
        entry = get_entry(index)
        if (entry is not None):
            return entry.y_value
        else:
            raise KeyError("Key '{}' not found".format(index))

    # Method to delete an entry by index
    def delete_entry(self, index):
        # Delete entry at specified index.
        if 0 <= index < len(self.entries):
            del self.entries[index]
        else:
            raise IndexError("Entry index out of range")
    
    # Method to return the count of culled entries
    def get_culled_count(self):
        num_culled = 0
        for entry in self.entries:
            if entry.isCulled():
                num_culled += 1
                
        return num_culled
    
    # Method to return the number of roi entries
    def get_roi_count(self):
        return len(self.entries)

    # Iterator to access available indices
    def __iter__(self):
        # Iterator to iterate over entry indices.
        self._index = 0
        return self

    def __next__(self):
        # Next method for iterator.
        if self._index < len(self.entries):
            result = self.entries[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration
            
    def next(self):
        return self.__next__()
    
    # If there are culled entries, write an updated ROI file minus the culled entries.  The results is a tuple
    # indicating:
    #   boolean  - True/False indicating if the changed were saved
    #   string[] - array of messages to show the user
    #
    # Note that effective V0.5 (2/23/2025) we have a bifricated scheme for storing the output:
    #     - get_roi_path() returns the "active" roi file which is a copy of the original in the top level directory
    #       --> this file is updated to comment out "#' the entries being disabled
    #     - group_path is where we should store all of the ouput as follows:
    #       --> The previous version of the -active prior to modification is stored here
    #       --> A copy of the -active stripped of everything except the active ROI information
    #
    def save_changes(self, group_path):
        #
        bundle_id    = self.bundle.bundle_id
        image_name   = self.bundle.get_image_filename()
        result       = False
        skipped_ids   = [int(id.item_id) for id in self.entries if id.isMarkedCulled()]       
        slide_id     = self.bundle.slide.slide_id if self.bundle.slide else "-"
        errors       = []
        messages     = []
        
        trace("save_changes: bundle_id={}, cull_count={}, slide_id={}, roi_name={}".format(bundle_id, len(skipped_ids), slide_id, self.bundle.get_roi_filename()))
        
        # Calculate the names of the files we will be using
        roi_path         = self.bundle.get_roi_path()
        roi_filename     = self.bundle.get_roi_filename().replace("-active","")
        ext_index        = roi_filename.rfind(".")
        
        working_filename = self.bundle.get_roi_filename().replace("-active","-working")
        working_path     = os.path.join(group_path, working_filename)
        roiS_path        = os.path.join(group_path, "{}-stripped{}".format(roi_filename[:ext_index], roi_filename[ext_index:]))
        
        # Now make a working copy of the roi, replacing if it previously existed
        shutil.copyfile(roi_path, working_path)
        
        #messages.append("Bundle ID={}, to file={}".format(self.bundle.bundle_id, roi_path))

        # Now save the files:
        #    roi_path  - will only be modified by adding '#' to all entries that are being culled.
        #    roiS_path - will only contain the roi entries that are left, no other information
        #
        try:
            # Open the input and output files
            in_file       = open(working_path, 'r')
            out_roi_file  = open(roi_path,     'w')
            out_roiS_file = open(roiS_path,    'w')
            
            # Copy the entire header as it is
            for i in range(self.get_header_len()):
                out_roi_file.write(in_file.readline())

            # Copy/append the history section
            history_len   = self.get_history_len()
            curr_time     = datetime.now().strftime('%m/%d/%Y @ %H:%M')
            history_line  = "    {}: {} items culled - {}\n".format(curr_time, len(skipped_ids), skipped_ids)
            
            trace(" +--> Processing history: length={}".format(history_len))
            
            if history_len == 0:
                out_roi_file.write("History:\n")
                out_roi_file.write(history_line)
                out_roi_file.write("\n")
            else:
                for i in range(history_len):
                    line = in_file.readline()
                    
                    # Add the history before the first blank line
                    if len(history_line) > 0 and len(line.strip()) == 0:
                        out_roi_file.write(history_line)
                        history_line = ""
                        
                    out_roi_file.write(line)
            
            # Handle any blank lines and position ourselves on the Results line
            allowed_lines = 10
            line = in_file.readline()
            
            while line.strip() != "Results:":
                out_roi_file.write(line)
                line = in_file.readline()
                
                allowed_lines -= 1
                if allowed_lines < 1:
                    raise AssertionError("Unable to locate Results: - active file corrupted! --> {}".format(self.bundle.get_roi_filename()))
            out_roi_file.write(line)

            # We should be on the "ID" header line
            out_roi_file.write(in_file.readline())
            
            # We should now be at the Results:.  The roi_entries should match the in_file order.
            # However just to be careful we will validate the ID's match - if they don't we have a 
            # code issue.
            start_column     = 2
            expected_columns = 3 + start_column
            processed_rows   = 0

            for entry in self.entries:
                #
                line = in_file.readline()
                
                # We normalize this to a CSV format by converting any tabs to ","
                columns = line.replace("\t", ",").split(",")
                
                if len(columns) < expected_columns:
                    errors.append("{},{} +--> ERROR: column count unexpected! SKIPPING ID[{}] --> num_columns={},  lines is: {}".format(slide_id, bundle_id, entry.item_id, len(columns), line))
                    continue
                
                # Confirm this is the expected ID
                if entry.item_id == columns[start_column]:
                    #
                    # If the item is culled we will add a '#' to the beginning of the line
                    if entry.isCulled() and not columns[0].startswith('#'):
                        out_roi_file.write("# "+self.convertLineDelimiter(columns))
                    else:
                        out_roi_file.write(self.convertLineDelimiter(columns))  
                    
                    if not entry.isCulled():
                        # Add the name in specified column before outputing the line
                        columns[OPTIONS.add_src_column - 1] = roi_filename
                        out_roiS_file.write(self.convertLineDelimiter(columns))
                    
                    processed_rows += 1
                    
                else:
                    print(" --> "+line)
                    raise AssertionError("Item ID did not match - entry={}, file ID={}, processing bundle {}, file={}".format(entry.item_id, columns[start_column], bundle_id, roi_path))
                    
            if processed_rows > 0:
                messages.append("{},{},ROI={},REM={},IDs={}".format(slide_id, bundle_id, len(self.entries), len(skipped_ids), skipped_ids))
            
            # Now handle any addition rows that exist.  We do not treat this as column data
            for line in in_file:
                out_roi_file.write(line)
            
            # Close the files
            in_file.close()
            out_roi_file.close()
            out_roiS_file.close()
            
            # Now copy the -active file into the Session with the original name
            modified_roi_file = os.path.join(group_path, roi_filename)
            shutil.copyfile(roi_path, modified_roi_file)
            
            # Delete the working copy
            os.remove(working_path)
            
            result = True
                
        except BaseException as e:
            print("DBG: {}\n{}".format(str(e), traceback.format_exc()))
            errors.append("{},{} +--> Failed to save - error={}".format(slide_id, bundle_id, str(e)))
            
            if out_roi_file:
                out_roi_file.close()
            if out_roiS_file:
                out_roiS_file.close()
            
        # Successfully completed
        return result, errors, messages

    # 
    # This is effectively a dry-run of the save_changes code.  It is used to return to the 
    # UI a set of changes that will occur when save_changes is called.  This allows the UI to
    # ask for permission before making the changes.  Doing this in a seperate function dramatically
    # simplifies the code.
    #
    def determine_changes(self, group_path):
        #
        bundle_id    = self.bundle.bundle_id
        slide_id     = self.bundle.slide.slide_id if self.bundle.slide else "-"
        
        changes     = []
        no_changes  = []
        
        try:
            # Determine the id's that are being skipped for this session
            skipped_ids = [int(id.item_id) for id in self.entries if id.isMarkedCulled()]
            
            # If we have no elements to cull, do nothing.
            if len(skipped_ids) == 0:
                no_changes.append("slide={}, bundle={}, num ROI={}, deleted={}".format(slide_id, bundle_id, len(self.entries), 0))
                return False, no_changes, changes
       
            changes.append("slide={}, bundle={}, num ROI={}, deleted={}, IDs={}".format(slide_id, bundle_id, len(self.entries), len(skipped_ids), skipped_ids))
            
        except BaseException as e:
            print("DBG: {}\n{}".format(str(e), traceback.format_exc()))
            no_changes.append("{},{} +--> Failed to save - error={}".format(slide_id, bundle_id, str(e)))
            
        # Successfully completed
        return False, no_changes, changes
        
    # Debugging information
    def validateRoiInfo(self):
        #
        if (len(self.entries) == 0):
            return "RoiInfo is empty!";
        
        # If we got no data rows we have nothing to do.
        if (self.get_data_len() < 1):
            return "No data present in roiInfo";
        
        # Confirm the amount of data and the metadata match
        if (self.get_data_len() != (len(self.entries))): 
            return "Data length inconsistent with metadata";
    
        return None;

    # Take either an array of columns or a line and ensure that the delimiters match the OPTIONS setting
    def convertLineDelimiter(self, line):
        #
        if line is None:
            return None
        
        if isinstance(line, list):
            if OPTIONS.use_tab_del:
                results = u"\t".join(line)
            else:
                results = u",".join(line)
        else:
            if OPTIONS.use_tab_del:
                results = line.replace(",", "\t")
            else:
                results = line.replace("\t", ",")
            
        return results
    
    # Helper class
    class RoiEntry:
        #
        def __init__(self, info, item_id, x_value, y_value, is_culled=False):
            #
            self.roi_info      = info
            self.item_id       = item_id
            self.is_culled     = is_culled
            self.marked_culled = False;
            
            # Ensure we are storing floating point numbers
            if isinstance(x_value, float):
                self.x_value = x_value
            else:
                self.x_value = parseFloat(x_value)
                
            if isinstance(y_value, float):
                self.y_value = y_value
            else:
                self.y_value = parseFloat(y_value)

        # Overload the str() function to print something useful
        def __repr__(self):
            #
            return "RoiEntry({}: {}, {}, {})".format(self.roi_info.bundle.bundle_id, self.item_id, self.x_value, self.y_value)

        # Return the Roi info object we are associated with
        def get_roi_info(self):
            return self.roi_info
            
        #
        # This ROI is culled.  This means it was marked culled in the ROI file
        #
        def isCulled(self):
            return self.is_culled
            
        def setCulled(self, status=True):
            self.is_culled = status
            
        #
        # This ROI is being marked culled.  It was not previously culled - done via UI.  We need this differenciation
        # to allow proper history recording.
        #
        def isMarkedCulled(self):
            return self.marked_culled
            
        def markCulled(self, status=True):
            self.marked_culled = status