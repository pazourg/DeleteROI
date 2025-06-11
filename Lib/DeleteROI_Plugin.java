/* ===============================================================================
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
 */

import ij.IJ;
import ij.plugin.PlugIn;
import org.python.util.PythonInterpreter;
import org.python.core.*;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;


public class DeleteROI_Plugin implements PlugIn {
    @Override
    public void run(String arg) {
        
        try {
            PythonInterpreter interpreter = new PythonInterpreter();
            
            InputStream scriptStream = DeleteROI_Plugin.class.getResourceAsStream("/DeleteROIPkg/DeleteROILauncher.py"); // Replace with your script path inside the jar
            if (scriptStream != null) {
                interpreter.execfile(scriptStream);
            } else {
                System.err.println("Script not found in jar");
            }
            
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
