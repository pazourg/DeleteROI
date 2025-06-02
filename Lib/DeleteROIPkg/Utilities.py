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
import traceback

# Java Imports
from java.awt        import Color, Font

# ImageJ Imports
from ij              import IJ, Prefs
from ij.util         import FontUtil

# Define constants
parm_border_width  = 4
parm_columns       = 8            # Montage - number of columns wide
parm_delimiter     = "\t"         # CiliaQ output file delimiter
parm_max_rows      = 10           # Montage - max number of rows
parm_screen_height = 0            # Total Screen height
parm_screen_width  = 0            # Total Screen width

# Helper classes

# Holder of all global options (usually modifiable by UI)
class Options:
    #
    PREFS_PREFIX = "DeleteROI."

    PREF_KEY_ADJUST_TYPE    = "{}{}".format(PREFS_PREFIX, "adjust_type")
    PREF_KEY_BUFFER_PERCENT = "{}{}".format(PREFS_PREFIX, "buffer_percent")
    PREF_KEY_BC_CHANNEL_1   = "{}{}".format(PREFS_PREFIX, "bc_channel_1")
    PREF_KEY_BC_CHANNEL_2   = "{}{}".format(PREFS_PREFIX, "bc_channel_2")
    PREF_KEY_BC_CHANNEL_3   = "{}{}".format(PREFS_PREFIX, "bc_channel_3")
    PREF_KEY_C1_SAT         = "{}{}".format(PREFS_PREFIX, "c1_sat")
    PREF_KEY_C2_SAT         = "{}{}".format(PREFS_PREFIX, "c2_sat")
    PREF_KEY_C3_SAT         = "{}{}".format(PREFS_PREFIX, "c3_sat")
    PREF_KEY_DEBUG          = "{}{}".format(PREFS_PREFIX, "debug")
    PREF_KEY_ROI_SIZE       = "{}{}".format(PREFS_PREFIX, "roi_size")
    PREF_KEY_SCALE          = "{}{}".format(PREFS_PREFIX, "scale")
    PREF_KEY_SRC_FOLDER     = "{}{}".format(PREFS_PREFIX, "src_folder")
    
    PREF_KEY_ADD_SRC_COLUMN = "{}{}".format(PREFS_PREFIX, "add_src_column")
    PREF_KEY_ADD_SRC_NAME   = "{}{}".format(PREFS_PREFIX, "add_src_name")
    PREF_KEY_KEEP_HEADING   = "{}{}".format(PREFS_PREFIX, "keep_heading")
    PREF_KEY_KEEP_UNUSED    = "{}{}".format(PREFS_PREFIX, "keep_unused")
    PREF_KEY_REM_BLANK_COLS = "{}{}".format(PREFS_PREFIX, "rem_blank_cols")
    PREF_KEY_USE_TAB_DEL    = "{}{}".format(PREFS_PREFIX, "use_tab_del")
    
    # Values read from UI - initialize to default values.  We expect direct access to these values
    TYPE_ADJUST_MIN_MAX     = 1
    TYPE_ADJUST_SATURATION  = 2
    TYPE_ADJUST_MANUAL      = 3
    TYPE_ADJUST_AUTO        = 4
    
    # Mapping from OPTIONS to Text
    ROI_SIZE    = [ 32, 64, 128, 256 ]
    SCALES      = [ "1x", "2x", "3x" ]
    
    # Constructor
    def __init__(self):
        #
        self.adjust_type    = Options.TYPE_ADJUST_SATURATION
        self.buffer_percent = 0.25         # The % of extra buffer when changing contrast
        self.bc_channel_1   = "0,600"      # Decimal value for min/max brightness/contrast - channel 1
        self.bc_channel_2   = "5000,30000" # Decimal value for min/max brightness/contrast - channel 2
        self.bc_channel_3   = "5000,30000" # Decimal value for min/max brightness/contrast - channel 3
        self.c1_sat         = 0.2
        self.c2_sat         = 0.2
        self.c3_sat         = 0.3
        self.debug          = False
        self.roi_size       = 64           # Size of ROI edge (square), adjust for different resolutions
        self.scale          = 2            # The scale multiplier for montage images (i.e., if size is 64 display xScale)
        self.src_folder     = ""
        self.trace          = False
        
        # Output options
        self.add_src_column = 1            # If adding src image name, column number to place it
        
        # Obsolete
        self.add_src_name   = True         # Add the src image name to specified column
        self.keep_heading   = True         # Should the results header be kept?
        self.keep_unused    = True         # Should we keep the non-results sections?
        self.rem_blank_cols = False        # Remove blank columns from results
        self.use_tab_del    = False        # Use a tab for the delimiter, otherwise a comma (CSV)
        
        # Load the prefererences
        self.loadPrefs()
    
    # Setter methods
    def setAdjustType(self, adjust_type):
        print("OPTIONS: setting adjust_type (%) to: {}".format(adjust_type))
        self.adjust_type = int(adjust_type)
        
    def setBufferPercent(self, buffer_percent):
        print("OPTIONS: setting buffer_percent (%) to: {}".format(buffer_percent))
        self.buffer_percent = float(buffer_percent)
    
    # Sets the current ROI_SIZE to the specified value after validating 
    def setRoiSize(self, size):
        print("OPTIONS: setting roi_size to: {}".format(size))
        
        # Ensure it is an int value
        size = int(size)
        
        # Validate it is a valid value
        valid = False
        for r in self.ROI_SIZE:
            if r == size:
                valid = True
                break
                
        if not valid:
            raise AssertionError("Attempt to set roi_size to invalid value: {}".format(size))
            
        self.roi_size = int(size)

    # Returns the ROI_SIZE value corresponding to the specified index.  If no index supplied, return current value
    def getRoiSizeValueByIndex(self, index=None):
    
        # If no index supplied, use the current index
        if index == None:
            return self.ROI_SIZE[self.roi_index]
        
        if index > len(self.ROI_SIZE) - 1:
            raise ValueError("Index {} too large: {}".format(index, len(self.ROI_SIZE) - 1))
        
        return self.ROI_SIZE[index]

    # Takes the supplied value and finds the index in the ROI_SIZE array
    def getRoiSizeIndexByValue(self, value=None):
    
        # If no value supplied, use the current index
        if value is None:
            value = self.roi_size
        
        index = -1
        for r in range(0, len(self.ROI_SIZE)):
            if value == self.ROI_SIZE[r]:
                index = r
                break
                        
        return index
    
    # TODO: store the string value not the index like we do for roi_size
    def setScale(self, scale):
        # Ensure we don't have a float, etc.
        scale = int(scale)
        print("OPTIONS: setting scale to: {}".format(scale))
        self.scale = scale
    
    # Retrieve the Brightness/Contrast min value for the specified channel
    def getBcMin(self, channel):
        #
        return int(self.getChannel(channel).split(',')[0])
        
    # Retrieve the Brightness/Contrast max value for the specified channel
    def getBcMax(self, channel):
        #
        return int(self.getChannel(channel).split(',')[1])
    
    def getChannel(self, channel):
        #
        if channel == 1:
            return self.bc_channel_1
        elif channel == 2:
            return self.bc_channel_2
        elif channel == 3:
            return self.bc_channel_3
        
        raise AssertError("ERROR setBcMinMax: invalid channel number: "+str(channel))
    
    # Set the min & max Brightness/Constrast values for the specified channel
    def setBcMinMax(self, channel, bc_min, bc_max):
        #
        value = "{},{}".format(int(bc_min), int(bc_max))

        print("OPTIONS: setting Min/Max for channel {} to: {}".format(channel, value))

        if channel == 1:
            self.bc_channel_1 = value
        elif channel == 2:
            self.bc_channel_2 = value
        elif channel == 3:
            self.bc_channel_3 = value
        else:
            print("ERROR setBcMinMax: invalid channel number: "+str(channel))
            
    def setSaturation(self, c1, c2, c3):
        print("OPTIONS: setting saturation to: {}, {}, {}".format(c1, c2, c3))
        self.c1_sat = float(c1)
        self.c2_sat = float(c2)
        self.c3_sat = float(c3)
        
    def setDebug(self, debug):
        print("OPTIONS: setting debug to: {}".format(debug))
        self.debug  = bool(debug)
        
    def setSrcFolder(self, src_folder):
        print("OPTIONS: setting src_folder to: {}".format(src_folder))
        self.src_folder = src_folder
    
    def setTrace(self, setting=False):
        print("OPTIONS: setting trace to: {}".format(setting))
        self.trace = bool(setting)
    
    def setAddSrcColumn(self, column_num=1):
        print("OPTIONS: setting add_src_column to: {}".format(column_num))
        self.add_src_column = int(column_num)
        
    def setAddSrcName(self, add_src_name=False):
        print("OPTIONS: setting add_src_name to: {}".format(add_src_name))
        self.add_src_name = bool(add_src_name)
        
    def setKeepHeading(self, keep=True):
        print("OPTIONS: setting keep_heading to: {}".format(keep))
        self.keep_heading = bool(keep)
        
    def setKeepUnused(self, keep_unused=True):
        print("OPTIONS: setting keep_unused to: {}".format(keep_unused))
        self.keep_unused = bool(keep_unused)
        
    def setRemBlankCols(self, rem_blank_cols=False):
        print("OPTIONS: setting add_src_column to: {}".format(rem_blank_cols))
        self.rem_blank_cols = bool(rem_blank_cols)
        
    def setUseTabDelimiter(self, tab_delimiter=False):
        print("OPTIONS: setting use_tab_del to: {}".format(tab_delimiter))
        self.use_tab_del = bool(tab_delimiter)
    
    # Helper method to validate min/max formatting is correct.  This is essentially a kludge
    # to minimize the number of fields.
    def validate_min_max(self, channel_value):
        #
        return channel_value
        
    # Method to save and load values from preferences file
    def loadPrefs(self):
        #
        try:
            prefs = Prefs()
            error = prefs.load(IJ, None)
            if error is None:
                self.adjust_type    = int(self.loadSinglePref(prefs,   Options.PREF_KEY_ADJUST_TYPE,    self.adjust_type))
                self.buffer_percent = int(self.loadSinglePref(prefs,   Options.PREF_KEY_BUFFER_PERCENT, self.buffer_percent))
                self.bc_channel_1   = self.loadSinglePref(prefs,       Options.PREF_KEY_BC_CHANNEL_1,   self.bc_channel_1)
                self.bc_channel_2   = self.loadSinglePref(prefs,       Options.PREF_KEY_BC_CHANNEL_2,   self.bc_channel_2)
                self.bc_channel_3   = self.loadSinglePref(prefs,       Options.PREF_KEY_BC_CHANNEL_3,   self.bc_channel_3)
                self.c1_sat         = float(self.loadSinglePref(prefs, Options.PREF_KEY_C1_SAT,         self.c1_sat))
                self.c2_sat         = float(self.loadSinglePref(prefs, Options.PREF_KEY_C2_SAT,         self.c2_sat))
                self.c3_sat         = float(self.loadSinglePref(prefs, Options.PREF_KEY_C3_SAT,         self.c3_sat))
                self.debug          = bool(self.loadSinglePref(prefs,  Options.PREF_KEY_DEBUG,          self.debug))
                self.roi_size       = int(self.loadSinglePref(prefs,   Options.PREF_KEY_ROI_SIZE,       self.roi_size))
                self.scale          = int(self.loadSinglePref(prefs,   Options.PREF_KEY_SCALE,          self.scale))
                self.src_folder     = self.loadSinglePref(prefs,       Options.PREF_KEY_SRC_FOLDER,     self.src_folder)
                
                self.add_src_column = int(self.loadSinglePref(prefs,   Options.PREF_KEY_ADD_SRC_COLUMN, self.add_src_column))
                self.add_src_name   = bool(self.loadSinglePref(prefs,  Options.PREF_KEY_ADD_SRC_NAME,   self.add_src_name))
                self.keep_heading   = bool(self.loadSinglePref(prefs,  Options.PREF_KEY_KEEP_HEADING,   self.keep_heading))
                self.keep_unused    = bool(self.loadSinglePref(prefs,  Options.PREF_KEY_KEEP_UNUSED,    self.keep_unused))
                self.rem_blank_cols = bool(self.loadSinglePref(prefs,  Options.PREF_KEY_REM_BLANK_COLS, self.rem_blank_cols))
                self.use_tab_del    = bool(self.loadSinglePref(prefs,  Options.PREF_KEY_USE_TAB_DEL,    self.use_tab_del))
            else:
                print("ERROR: Unable to load preferences: "+str(error))
                
            print("Loaded-> "+str(self))
        except BaseException as e:
            print("OPTIONS: ERROR - unable to load preferences: "+str(e))
            print(traceback.format_exc())
        
    def savePrefs(self):
        #
        try:
            prefs = Prefs()
            
            self.saveSinglePref(prefs, Options.PREF_KEY_ADJUST_TYPE,     self.adjust_type)
            self.saveSinglePref(prefs, Options.PREF_KEY_BUFFER_PERCENT,  self.buffer_percent)
            self.saveSinglePref(prefs, Options.PREF_KEY_BC_CHANNEL_1,    self.bc_channel_1)
            self.saveSinglePref(prefs, Options.PREF_KEY_BC_CHANNEL_2,    self.bc_channel_2)
            self.saveSinglePref(prefs, Options.PREF_KEY_BC_CHANNEL_3,    self.bc_channel_3)
            self.saveSinglePref(prefs, Options.PREF_KEY_C1_SAT,          self.c1_sat)
            self.saveSinglePref(prefs, Options.PREF_KEY_C2_SAT,          self.c2_sat)
            self.saveSinglePref(prefs, Options.PREF_KEY_C3_SAT,          self.c3_sat)
            self.saveSinglePref(prefs, Options.PREF_KEY_DEBUG,           self.debug)
            self.saveSinglePref(prefs, Options.PREF_KEY_ROI_SIZE,        self.roi_size)
            self.saveSinglePref(prefs, Options.PREF_KEY_SCALE,           self.scale)
            self.saveSinglePref(prefs, Options.PREF_KEY_SRC_FOLDER,      self.src_folder)
            
            self.saveSinglePref(prefs, Options.PREF_KEY_ADD_SRC_COLUMN,  self.add_src_column)
            self.saveSinglePref(prefs, Options.PREF_KEY_ADD_SRC_NAME,    self.add_src_name)
            self.saveSinglePref(prefs, Options.PREF_KEY_KEEP_HEADING,    self.keep_heading)
            self.saveSinglePref(prefs, Options.PREF_KEY_KEEP_UNUSED,     self.keep_unused)
            self.saveSinglePref(prefs, Options.PREF_KEY_REM_BLANK_COLS,  self.rem_blank_cols)
            self.saveSinglePref(prefs, Options.PREF_KEY_USE_TAB_DEL,     self.use_tab_del)
            
            prefs.savePreferences()
        except BaseException as e:
            print("OPTIONS: ERROR - unable to save preferences: "+str(e))
        
    def loadSinglePref(self, prefs, key, default):
        #
        try:
            return prefs.get(key, default)
        except BaseException as e:
            print("Prefs: Exception load pref ({}) using default {}".format(key, default))
            #print(traceback.format_exc())
            
        return default

    def saveSinglePref(self, prefs, key, value):
        #
        try:
            prefs.set(key, value)
        except BaseException as e:
            print("Prefs: Exception saving pref ({}) = {}: {}".format(key, value))
    
    # Debugging information
    def __str__(self):
        return "OPTIONS: adjust_type={}, buffer_percent={}, scale={}, bc_c1={}, bc_c2={}, bc_c2={}, c1={}, c2={}, c3={}, roi_size={}, debug={}, src_folder={}".format(self.adjust_type, \
                self.buffer_percent, self.scale, self.bc_channel_1, self.bc_channel_2, self.bc_channel_3, self.c1_sat, self.c2_sat, self.c3_sat, self.roi_size, self.debug, self.src_folder)

# Add item to list at specified index number
def addItemToList(target, index, item):
    #
    if target is None:
        raise AssertionError('Specified target is null!')
    
    # Indexes are zero offset so len must always be one more than index
    if index >= len(target):
        # Array is not large enough, enlarge it
        target.append([0] * (len(target) - index))
   
    target[index] = item

# Helper method to convert a string to a float 
def convertToFloat(value, default):
    #
    try:
        return float(value)
    except ValueError:
        trace("conversion of '{}' to float failed, using default value: {}".format(value, default))
        return default

# Helper method for debug printout
def trace(message):
    #
    if OPTIONS.trace:
        print("DBG: "+str(message))

# Function to close all images and ROIs
def close_all():
    #
    # Garbage cleanup
    #
    IJ.run("Close All")

#
# Global setting for Options - usually set via the UI and defined in Utilities.py
#
OPTIONS = Options()
OPTIONS.trace = True
