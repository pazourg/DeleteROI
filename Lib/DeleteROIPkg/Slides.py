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

import random
import re

# Our package imports
from DeleteROIPkg.Utilities import close_all, trace, OPTIONS

# Class representing a slides (i.e., coverslip).
class SlideManager:
    #
    next_slide_id = 0
        
    # Constructor
    def __init__(self):
        #
        self.slides = []
        
    # Add a root filename
    def add_slide_root(self, root):
        #
        slide = None
        
        if not root in self:
            SlideManager.next_slide_id += 1
            slide = SlideManager.Slide(SlideManager.next_slide_id, root)
            
            self.slides.append(slide)
        else:
            for entry in self.slides:
                if entry.root_filename == root:
                    slide = entry
                    break
            #
            trace("SlideMgr: attempt to add root multiple times: "+str(root))
            
        return slide
            
    # Try and find a Slide that matches the provided full filename
    def find_slide(self, filename):
        #
        if filename is None:
            return None
        
        # Now try and find a match
        match = None
        
        for slide in self.slides:
            if slide.is_covered(filename):
                match = slide
                break
        
        return match
        
    # Load the slides from session state
    def load_from_session(self, session_info):
        #
        saved_slides = self.slides
        
        try:
            for session in session_info:
                slide = SlideManager.Slide(0, "X")
                slide.load_session_info(session)
                self.slides.append(slide)
                
                # Ensure that any future slides have distinct ID's
                SlideManager.next_slide_id = len(self.slides)
        except BaseException as e:
            self.slides = saved_slides
            raise e
        
        return True

    # Reset the manager to the initial state
    def reset(self):
        #
        SlideManager.next_slide_id = 0
        self.slides = []

    # Implement IN logic such that "root in SlideMgr" works.
    def __contains__(self, item):
        #
        if item is None:
            return False
            
        matched = False
        
        for entry in self.slides:
            #
            if entry.root_filename == item:
                matched = True
                break
        
        return matched

    # Iterator to access available montages
    def __iter__(self):
        # Iterator to iterate over entry indices
        if self.slides is None or len(self.slides) == 0:
            return  None        
        
        self._index = 0
        return self

    def __next__(self):
        # Next method for iterator (python3)
        if self._index < len(self.slides):
            result = self.slides[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration
            
    def next(self):
        # Next method for iterator (python2)
        return self.__next__()

    # Implement len()
    def __len__(self):
        return len(self.slides)

    # Overload the str() function to print something useful
    def __repr__(self):
        #
        return "Slides: num={}, slides={}".format(len(self.slides), str(self.slides))

    # Class representing a single slide.  Since multiple scenes have been taken using the same slide
    # we don't have a concrete/single image representing the slide.  Instead we have the root portion
    # of the filename that is the same across the scenes.  This is what we are recording.
    class Slide:
        #
        # Constructors
        def __init__(self, slide_id, root):
            #
            self.slide_id       = slide_id
            self.root_filename  = root
            
            # Define the matcher we use to find the match
            self.pattern        = re.sub(r'_|\\ ', r'[_ ]', re.escape(root)).replace(r'\[', '[')
            self.matcher        = re.compile(self.pattern)

            # The set of bundles associated with this slide
            self.bundles        = []
            self.random_bundles = None
            self.status_enabled = False
            
        # Returns the root filename
        def get_root_filename(self):
            #
            return self.root_filename

        # Determine if the provided filename is covered by this slide
        def is_covered(self, filename):
            #
            match = self.matcher.match(filename)
            
            return match is not None
            
        # Handle the enabled status
        def set_enabled(self, status):
            #
            self.status_enabled = bool(status)
            
        def is_enabled(self):
            return self.status_enabled

        # The ID of this slide
        def get_id(self):
            return self.slide_id

        # Returns the number of bundles associated with this slide
        def get_num_bundles(self):
            #
            return len(self.bundles)
            
        # Returns the number of RoiInfo objects associated with the bundles we are associated with
        def get_num_roi(self):
            #
            num_roi = 0
            
            for bundle in self.bundles:
                #
                num_roi += bundle.get_roi_length()
            
            return num_roi
            
        #Returns the number of RoiInfo objects being culled
        def get_culled_count(self):
            #
            num_culled = 0
            
            for bundle in self.bundles:
                #
                num_culled += bundle.get_roi_info().get_culled_count()
            
            return num_culled            
            
        # Store the set of bundles associated with this slide
        def add_bundle(self, bundle):
            #
            if self.random_bundles is not None:
                raise ValueError("Bundles locked due to randomization/consumption")
            
            if not bundle in self.bundles:
                self.bundles.append(bundle)

        # Randomizing the bundles, consumes the next item in the list.  Once we have consumed all of
        # the entries, return None.  After None is returned subsequent calls will reset and start 
        # again.  This is essentially a self-starting iterator.
        def consume(self):
            #
            result = None
            
            if self.random_bundles is None:
                # Randomize the current list so that consumption of the bundles is random
                self.random_bundles = list(self.bundles)
                for i in range(0, len(self.bundles)):
                    random.shuffle(self.random_bundles)
                    
            # If we consumed all of the entries, clear the random list.
            if len(self.random_bundles) > 0:
                result = self.random_bundles.pop(0)
            else:
                self.random_bundles = None
                    
            return result

        # Update the saved session state information to show this session has completed
        def load_session_info(self, session_info):
            #
            slide_id      =  int(session_info['slide_id'])
            root_filename =  str(session_info['root_filename'])
            
            # Recall the constructor to setup
            self.__init__(slide_id, root_filename)
            
            # Now the remaining state
            self.status_enabled    = bool(session_info['is_enabled'])
            
        # Create information about the session to write to storage
        def save_session_info(self):
            #
            session_info = {}
            session_info['slide_id']      = self.slide_id
            session_info['root_filename'] = self.root_filename
            session_info['is_enabled']    = self.status_enabled
            
            return session_info

        # Iterator to access available bundles in the slide
        def __iter__(self):
            # Iterator to iterate over entry indices
            if self.bundles is None or len(self.bundles) == 0:
                return  None        
            
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

        # Implement len()
        def __len__(self):
            return len(self.bundles)
            
        # Overload the str() function to print something useful
        def __repr__(self):
            #
            return "Slide(ID={}, is_enabled={}, # bundles={}, root={})".format(self.slide_id, self.status_enabled, len(self.bundles), str(self.root_filename))
            