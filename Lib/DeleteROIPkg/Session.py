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
import json
import os
import random
import re
import shutil
import traceback

from   datetime             import datetime

# GUI Imports
from ij.gui                 import NonBlockingGenericDialog

# Our package imports
from DeleteROIPkg.Dialogs   import show_error
from DeleteROIPkg.Montage   import MontageManager
from DeleteROIPkg.Utilities import addItemToList, trace, OPTIONS

# Constants
DATE_FORMAT  = "%Y-%m-%d %H:%M:%S"
GROUP_DIR    = "Group_" 
STATE_FILE   = '.session_state.json'

# Manager to handle the sessions.  Each session is potentially a subset of of the 
# overall items to processed.  Logistically, if the set of items to be examined is really
# large there is risk that failure along the way could result in loss of all of your
# work.  As such a session breaks the work into manageable chunks that can be continued
# over time.  As long as a session is complete you can move on to the next session.
#
# Starting with V0.5 (02/23/2025) we now store all changes within a subdirectory ("GROUP_xx")
# where xx is the group number (starting with 01) comprising a new set of sessions.  Each group
# is a new set of sessions and thus a delta from the prior group.
#
class SessionManager:
    #
    def __init__(self, bundle_mgr, slide_mgr):
        #
        self.bundle_mgr       = bundle_mgr
        self.slide_mgr        = slide_mgr
        
        # State used by the session manager
        self.sessions         = []
        self.path             = None    # Path to directory where image/txt files are stored
        self.session_filename = None
        
        # State used to track the subdirectory used to store all group results
        self.group_path      = None
        self.group_num       = 0
    
    # Determine if all sessions are complete
    def all_sessions_complete(self):
        #
        for sess in self.sessions:
            if not sess.is_complete():
                return False
        
        return True
        
    # Returns the number of sessions currently known
    def get_session_count(self):
        return len(self.sessions)
        
    # Returns the number of completed sessions
    def get_completed_session_count(self):
        #
        completed = 0
        for sess in self.sessions:
            if sess.is_complete():
                completed += 1
                
        return completed
        
    # Store the current path we are using
    def set_src_path(self, path):
        #
        self.path, tail = os.path.split(path)
        
    # Retun the current group number
    def get_group_num(self):
        return self.group_num
        
    # Return the current group path
    def get_group_path(self):
        #
        if self.group_num == 0 or self.group_path is None or len(self.group_path.strip()) == 0:
            raise AssertError("Attemp to fetch group_path when it has not been setup")
            
        return self.group_path
        
    # Determine the group path to store all results
    def setup_group_path(self):
        #
        # We need to determine the output directory
        if self.path is None or len(self.path) == 0:
            raise AssertionError("Source path not yet set, unable to determine result path") 
                
        # Scan the root directory for the group looking for any existing group output.   Each
        # of those directories will be numbered starting with one (1).  Find the last one and
        # calculate the number number to use.  This directory will be created as needed.
        matches = fnmatch.filter(os.listdir(self.path), GROUP_DIR+"[0-9]*")
        
        trace("get_group_path: {}".format(matches))
        
        if len(matches) > 0:
            #
            group_pattern = GROUP_DIR + r'([0-9]+)$'
            #
            for dirname in sorted(matches):
                group_num = re.match(group_pattern, dirname).groups()
                
                if len(group_num) > 0 and len(group_num[0]) > 0:
                    # 
                    curr_group_num = int(group_num[0])
                    if curr_group_num > self.group_num:
                        self.group_num = curr_group_num
            
            # We have the last known group directory, check to see how many files within.  If none
            # we will resuse, if any we move to the next
            target_dir = os.path.join(self.path, GROUP_DIR+"{}".format(self.group_num))
            if len(os.listdir(target_dir)) > 0:
                self.group_num += 1
            
            trace("  +--> calculated group_num is: {}".format(self.group_num))
        else:
            self.group_num = 1
            
        # Now calculate the actual path we need
        self.group_path = os.path.join(self.path, GROUP_DIR+"{}".format(self.group_num))
            
        # Ensure the group output directory actually exists
        if not os.path.exists(self.group_path):
            os.makedirs(self.group_path)
            
        return self.group_path
                    
    # Open the existing session state replacing all current sessions with the 
    # stored session information
    def load_existing_state(self):
        #
        trace("load_existing_state: path="+str(self.path))

        # True if we succesfully restored the state
        restored = False

        # Calculate the path to the state file
        self.session_filename = self.path + os.path.sep + STATE_FILE
        self.session_filename = self.session_filename.replace(os.path.sep + os.path.sep, os.path.sep)

        try:
            if not os.path.exists(self.session_filename):
                # No existing state
                print("Session: no existing sessions found, continuing...")
                return False
            
            # Load the existing information, if a session loads with no bundles discard it
            with open(self.session_filename, "r") as in_file:
                info = json.load(in_file)
                in_file.close
            
            # Storage for the sessions, we swap it on success
            restored_sessions = []
            
            # Restore the sessions
            headers      = info['headers']
            path         =     headers['path']
            num_sessions = int(headers['num_sessions'])
            num_slides   = int(headers['num_slides'])
            version      =     headers['version']
            
            # The original V1.0 is not entirely compatible
            if version != '1.2':
                session_backup = "{}.invalid".format(self.session_filename)
                shutil.copyfile(self.session_filename, session_backup)
                os.remove(self.session_filename)
                
                raise AssertionError("Session state encoded with unsupported version: {} - ignoring prior session state".format(version))
            
            # Add V1.2 changes
            if 'group' in info:
                group = info['group']
            
                # Restore  the results information
                self.group_path = group['path']
                self.group_num  = int(group['num'])
                
            if 'options' in info:
                options = info['options']
                
                # Restore the options previously saved
                OPTIONS.setAdjustType(options['adjust_type'])
                OPTIONS.setBufferPercent(options['buffer_percent'])
                OPTIONS.setRoiSize(options['roi_size'])
                OPTIONS.setScale(options['scale'])
                OPTIONS.setAddSrcColumn(options['src_column'])

                # No access method at the moment
                OPTIONS.bc_channel_1 = options['bc_channel_1']
                OPTIONS.bc_channel_2 = options['bc_channel_2']
                OPTIONS.bc_channel_3 = options['bc_channel_3']
                
                # Saturation
                OPTIONS.setSaturation(options['c1_sat'], options['c2_sat'], options['c3_sat'])
                
            # Load the slide information
            if not self.slide_mgr.load_from_session(info['slides']):
                raise AssertionError('Failed to load slides from session')
            
            # Load the session information, order is important
            for session_info in info['sessions']:
                session = SessionManager.Session(self, 0, self.slide_mgr, self.bundle_mgr)
                session.load_session_info(session_info)
                
                restored_sessions.append(session)
                
            if len(restored_sessions) != num_sessions:
                raise AssertionError("Expected sessions ({}) does not match actual ({})".format(num_sessions, len(restored_sessions)))
            
            # check to see if there are actually sessions
            if len(restored_sessions) == 0:
                return False
            
            # We have successfully loaded the session information
            self.sessions = restored_sessions
            restored      = True
        
        except BaseException as e:
            print("Unable to load existing session state: "+str(e))
            print(traceback.print_exc(e))
            
            show_error("Failed to load session state", "Failed to restore session information: {} -> {}".format(e.__class__.__name__, str(e)))

        return restored

    # Create or update the saved session state information
    def save_session_state(self):
        #
        if self.path is None or len(self.path) == 0:
            raise ValueError("Path not properly specified")

        self.session_filename = self.path + os.path.sep + STATE_FILE
        self.session_filename = self.session_filename.replace(os.path.sep + os.path.sep, os.path.sep)

        print("Session save: "+str(len(self.sessions)))
        
        try:
            # Write the header
            header_info = {}
            header_info['path']         = str(self.session_filename)
            header_info['num_sessions'] = len(self.sessions)
            header_info['num_slides']   = len(self.slide_mgr)
            header_info['version']      = '1.2'
            
            # Write each slide information
            slide_info = []
            for slide in self.slide_mgr:
                info = slide.save_session_info()
                slide_info.append(info)
            
            # Now write each session object, it's important that we save them in order
            session_info = []
            for session in self.sessions:
                #
                info = session.save_session_info()
                session_info.append(info)
                
            # Save the result information
            group_info = {
                'path' : self.group_path,
                'num'  : self.group_num
            }
            
            # Options information
            option_info = {
                'adjust_type'    : OPTIONS.adjust_type,
                'buffer_percent' : OPTIONS.buffer_percent,
                'roi_size'       : OPTIONS.roi_size,
                'scale'          : OPTIONS.scale,
                'src_column'     : OPTIONS.add_src_column,
                'bc_channel_1'   : OPTIONS.bc_channel_1,
                'bc_channel_2'   : OPTIONS.bc_channel_2,
                'bc_channel_3'   : OPTIONS.bc_channel_3,
                'c1_sat'         : OPTIONS.c1_sat,
                'c2_sat'         : OPTIONS.c2_sat,
                'c3_sat'         : OPTIONS.c3_sat
            }
            
            # Create the output information
            out_info = {
                'headers' : header_info,
                'sessions': session_info,
                'slides'  : slide_info,
                'group'   : group_info,
                'options' : option_info,
            }
            
            # Now write the output file
            with open(self.session_filename, "w") as out_file:
                #
                out_file.write(json.dumps(out_info, indent=4, sort_keys=True))
                out_file.close()
        
        except BaseException as e:
            print("ERROR: Failure saving existing session state: "+str(e))
            print(traceback.print_exc(e))
            
            show_error("Failed to save session state", "Failed to save session information: {} -> {}".format(e.__class__.__name__, str(e)))
            
            return False
            
        return True
    
    # Reset all session information including the underlying managers.  If we are told not to re-use the 
    # session information we need to make it go away.
    def reset(self):
        #
        trace("session.reset: calling reset")
        
        self.sessions   = []
        self.group_num  = 0
        self.group_path = None
        
        self.slide_mgr.reset()
        self.bundle_mgr.reset()
    
    # Taking the supplied parameters create sessions to process the bundles.  The goal is
    # to take at least one bundle from each slide for each session.  However since that will
    # probably result in too few bundles per session we loop through slides until we have
    # at least bundles_per_session.
    #
    # Effective 03-17-25, there is only 1 bundle per "slide".  This is due to the fact that
    #    we no longer attempt to recognize slides that span multiple bundles.   As such we
    #    need to randomize the bundles and pick bundles for each session.
    #
    # Parameters:
    #   - int - target number of per session, if zero put all bundles in one session
    #
    def create_sessions(self, roi_per_session):
        #
        session = None
        
        # Determine the group path that should be used
        self.setup_group_path()
        
        # Buld an array of bundles and then randomize them
        random_bundles = [bundle for bundle in self.bundle_mgr ]
        random.shuffle(random_bundles) 
        
        # Now loop through each bundle and adding it to the session
        trace("createSessions: processing bundles")
        
        for bundle in random_bundles:
            
            if not bundle.is_enabled():
                trace("  +--> bundle is not enabled, skipping: "+str(bundle))
                continue
            if bundle.get_roi_length() == 0:
                trace("  +--> zero length ROI, skipping: "+str(bundle))
                continue
           
            # Ensure we have allocated the session
            if session is None:
                session = SessionManager.Session(self, len(self.sessions) + 1, self.slide_mgr, self.bundle_mgr)
                self.sessions.append(session)
            
            # We have an item to add
            session.add_bundle(bundle)
            
            if session.get_num_roi() >= roi_per_session:
                session = None
                
        # Now save all of the just created session information
        self.save_session_state()
        
        return True
    
    # Find sesssion by ID
    def find_session_by_id(self, session_id):
        #
        if session_id > len(self.sessions):
            return None
            
        return self.sessions[session_id]
    
    # Helper class representing a session
    class Session:
        #
        # Constructor
        def __init__(self, session_mgr, session_id, slide_mgr, bundle_mgr):
            #
            # Remember managers for later
            self.session_mgr     = session_mgr
            self.session_id      = session_id
            self.slide_mgr       = slide_mgr
            self.bundle_mgr      = bundle_mgr
            
            # List of bundles being processed
            self.bundles         = []
            self.slides          = []
            self.status_complete = False

        # Retrieve the session ID
        def get_id(self):
            #
            return self.session_id
       
        # Return the number of bundles associated with this session
        def get_num_bundles(self):
            return len(self.bundles)
        
        # Return the number of slides associated with this session
        def get_num_slides(self):
            return len(self.slides)
        
        # Return the number of ROI associated with this session
        def get_num_roi(self):
            #
            num_roi = 0
            for bundle in self.bundles:
                num_roi += bundle.get_roi_info().get_roi_count()
                
            return num_roi
            
        # Return the number of deletions (culled) associated with this session
        def get_culled_count(self):
            return 0
        
        # Returns true if the session has been completed
        def is_complete(self):
            return self.status_complete
            
        def set_complete(self, status):
            self.status_complete = status
            
        # Add a bundle to be processed
        def add_bundle(self, bundle):
            #
            trace("session.addBundle: "+str(bundle))
            
            if bundle not in self.bundles:
                self.bundles.append(bundle)
            else:
                trace("  +--> bundle already added, ignoring")
                
            if bundle.slide and bundle.slide not in self.slides:
                self.slides.append(bundle.slide)
            else:
                trace("  +--> add to slide skipped: "+str(bundle.slide))
                
        # Process the session using the MontageManager to create montages
        def process(self, columns, roi_size, max_rows):
            #
            if len(self.bundles) == 0:
                trace("Session.process: no bundles to process")
                return
            
            # Save the time we are starting the run
            start_time = datetime.now()
            
            # Additional montage creation and other functions can follow here...
            mm = MontageManager(self.session_id, columns, max_rows, roi_size)
            
            # Preserve the Slides so we can intelligently group the Montages and handle restarts
            for bundle in self.bundles:
                mm.add_bundle(bundle)
                
                if bundle.slide and bundle.slide not in self.slides:
                    self.slides.append(bundle.slide)
            
            # Now lock the bundles and create the montage, we get an array of montages
            mm.lock_bundles(OPTIONS.debug)
            montages = mm.create_montage(max_rows)
        
            # Now iterate over the montages displaying them
            for montage in mm:
                montage.process_montage(OPTIONS.scale)
                
            # Write out all changes
            completed, changes, no_changes = self.save_changes(dry_run=True)

            # Show the overall results
            results = NonBlockingGenericDialog("Results of processing session #"+str(self.session_id))
            
            mod_messages  = "The following ROI files will be modified:\n    "
            if len(changes) > 0:
                mod_messages += "\n    ".join(changes)
            else:
                mod_messages += "    -- None --"
            results.addMessage(mod_messages)
            
            not_messages  = "The following ROI files were NOT modified:\n    "
            if len(no_changes) > 0:
                not_messages += "\n    ".join(no_changes)
            else:
                not_messages += "    -- None --"
            results.addMessage(not_messages)
            
            results.addMessage("Pressing Ok will complete this session and write the ROI changes to disk")
            results.showDialog()
            
            if results.wasCanceled():
                raise UserWarning("Cancel")
            
            # Save the ROI information
            self.save_changes()
            
            # Update the session state to indicate we have completed this session
            self.set_complete(True)
            
            # Update the readme file containing the summary information
            self.update_readme(start_time, completed, "{}\n\n{}".format(mod_messages, not_messages))
            
        # Save the changes that have occured in the bundles
        def save_changes(self, dry_run=False):
            #
            completed  = True
            success    = []
            failed     = []
            group_path = self.session_mgr.get_group_path()
            
            # Ensure the directory exists
            if not os.path.exists(group_path):
                os.mkdir(group_path)
            
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

        # Update the saved session state information to show this session has completed
        def load_session_info(self, info):
            #
            self.session_id = int(info['session_id'])
            
            # Validation values
            num_bundles =  int(info['num_bundles'])
            bundles     =      info['bundles']
            is_complete = bool(info['is_complete'])
            
            # Process each bundle
            if len(bundles) != num_bundles:
                raise AssertionError("Number of expected bundles ({}) does not match actual ({})".format(num_bundles, len(bundles)))
            
            # Now process the bundles, it's important that the order be maintained 
            for entry in bundles:
                bundle_id  =  int(entry['bid'])
                image_path =      entry['image_path']
                roi_path   =      entry['roi_path']
                roi_size   =  int(entry['roi_size'])
                is_enabled = bool(entry['is_enabled'])
                slide_root =      entry['slide_root']
                
                # Create the bundle
                bundle = self.bundle_mgr.create_bundle(image_path, roi_path, bundle_id)
                bundle.set_enabled(is_enabled)

                if bundle.get_roi_length() != roi_size:
                    raise AssertionError("ROI Size expected ({}) does not match bundle size ({}) for bundle: {}".format(roi_size, bundle.get_roi_length(), str(bundle)))
                    
                # Add the bundle to the session
                self.add_bundle(bundle)

                # Ensure it is attached to the slide (if appropriate).  These are created earlier by the mgr
                slide = self.slide_mgr.find_slide(slide_root)
                if slide is not None:
                    bundle.attach_slide(slide)
                    slide.add_bundle(bundle)
                    
                    if slide not in self.slides:
                        self.slides.append(slide)

            # Now save the is_complete status
            self.set_complete(is_complete)
       
        # Create information about the session to write to storage
        def save_session_info(self):
            #
            num_bundles = len(self.bundles)
            
            info = {}
            info['session_id']     = self.get_id()
            info['num_bundles']    = num_bundles
            info['num_slides']     = self.get_num_slides()
            info['is_complete']    = self.is_complete()
            
            bundle_info = []
            for index in range(0, num_bundles):
                bundle = self.bundles[index]
                #
                entry = {}
                entry['index']      = index
                entry['bid']        = bundle.get_id()
                entry['image_path'] = bundle.get_image_path()
                entry['roi_path']   = bundle.get_roi_path()
                entry['roi_size']   = bundle.get_roi_length()
                entry['is_enabled'] = bundle.is_enabled()
                entry['slide_root'] = bundle.get_slide_root()
                
                bundle_info.append(entry)
                
            info['bundles'] = bundle_info
        
            return info
            
        # Write the README.txt file in the group directory
        def update_readme(self, start_time, completed, messages):
            #
            session_mgr = self.session_mgr
            readme_path = os.path.join(session_mgr.get_group_path(), "README.txt")
            
            # Determine if the path exist, if not we need to create it and then append the results
            try:
                if not os.path.isfile(readme_path):
                    #
                    readme_file = open(readme_path, 'w')
                    
                    readme_file.write("Group {} Summary Information\n\n".format(session_mgr.group_num))
                    readme_file.write("   Processed directory: {}\n".format(session_mgr.path))
                    readme_file.write("\n")
                    readme_file.write("Options Parameters\n");
                    readme_file.write("------------------\n");
                    
                    if OPTIONS.adjust_type == OPTIONS.TYPE_ADJUST_MIN_MAX:
                        readme_file.write("  Adjust Type: Min/Max\n")
                        readme_file.write("    Channel 1:  Min={}  Max={}\n".format(OPTIONS.getBcMin(1), OPTIONS.getBcMax(1)))
                        readme_file.write("    Channel 2:  Min={}  Max={}\n".format(OPTIONS.getBcMin(2), OPTIONS.getBcMax(2)))
                        readme_file.write("    Channel 3:  Min={}  Max={}\n".format(OPTIONS.getBcMin(3), OPTIONS.getBcMax(3)))
                    elif OPTIONS.adjust_type == OPTIONS.TYPE_ADJUST_SATURATION:
                        readme_file.write("  Adjust Type: Saturation\n")
                        readme_file.write("    Channel 1:  {}\n".format(OPTIONS.c1_sat))
                        readme_file.write("    Channel 2:  {}\n".format(OPTIONS.c2_sat))
                        readme_file.write("    Channel 3:  {}\n".format(OPTIONS.c3_sat))
                    elif OPTIONS.adjust_type == OPTIONS.TYPE_ADJUST_MANUAL:
                        readme_file.write("  Adjust Type: Manual\n")
                    
                    readme_file.write("  ROI Size: {}\n".format(OPTIONS.roi_size))
                    readme_file.write("  Scale   : {}\n".format(OPTIONS.scale))
                    readme_file.write("  Column #: {}\n".format(OPTIONS.add_src_column))
                    readme_file.write("\n")
                    readme_file.write("SESSION PROCESSING INFORMATION:\n")
                    readme_file.write("-------------------------------\n")
                else:
                    readme_file = open(readme_path, 'a')
                    
                # Now add the current session information
                readme_file.write("  Session #{} - Processing Information\n".format(self.get_id()))
                readme_file.write("     Start Time: {}\n".format(start_time.strftime(DATE_FORMAT)))
                readme_file.write("     End Time  : {}\n".format(datetime.now().strftime(DATE_FORMAT)))
                readme_file.write("\n")
                readme_file.write("     ----- Messages -----\n")
                
                msg_re = re.compile('.*?slide=([0-9]+),.?bundle=([0-9]+),[ ]*(.*)')
                for m in messages.split('\n'):
                    trace(">>> {}".format(m))
                    result = msg_re.match(m)
                    if result:
                        slide_id, bundle_id, msg = result.groups()
                        bundle = self.bundle_mgr.find_bundle_by_id(bundle_id)
                        # A bit of a hack, we want to reference the roi_file in the Group directory
                        roi_fn = bundle.get_roi_filename().replace("-active","") if bundle else "Bundle ID: {}".format(bundle_id)
                        readme_file.write("        file={}, {}\n".format(roi_fn, msg))
                    else:
                        readme_file.write("     {}\n".format(m))
                readme_file.write("\n")
                
                # All done, close the file
                readme_file.close()
                    
            except BaseException as e:
                trace("Unable to write README.txt file: {}".format(str(e)))
                trace("{}".format(traceback.format_exc())) 
                
                if readme_file:
                    readme_file.close()
            
    # Iterator to access available sessions
    def __iter__(self):
        # Iterator to iterate over entry indices
        if self.sessions is None or len(self.sessions) == 0:
            return None
        
        self._index = 0
        return self

    def __next__(self):
        # Next method for iterator (python3)
        if self._index < len(self.sessions):
            result = self.sessions[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration
            
    def next(self):
        # Next method for iterator (python2)
        return self.__next__()
        