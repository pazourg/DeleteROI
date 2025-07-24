#!/bin/bash 

#
# Yes, we could use Maven, etc.  However this started as a trivial build script
# that has crept in functionality.  The use of Maven or other build systems will
# bring other complexity so I've resisted until it's proven we need it.
#

VERSION=`awk -F\" '/^VERSION/ { print $2 }' ./Lib/DeleteROIPkg/__init__.py`
JAVAC=`which javac`
CACHED_JARS=~/.delete_roi_cache

# Helper methods
find_fiji_jars() {
	#
    CHECK_DIR=$1
    if [[ -z "${CHECK_DIR})" ]]; then
    	echo "Missing argument to find_fiji_jars"
    	return 1
    fi
    
	# Check the system /Applications directory
	FIJI_DIR=`find ${CHECK_DIR} -name "Fiji.app" 2> /dev/null`

	if [[ -z "${FIJI_DIR}" ]]; then
		return 2
	fi
	
	# We found 1 or more paths, try and find the jar files
	for d in ${FIJI_DIR};
	do
		FOUND=`realpath ${d}/../jars`
		if [ -d "${FOUND}" ]; then
			export FIJI_JARS=${FOUND}/*
			break
		fi
	done
	
	if [[ -z "${FIJI_JARS}" ]]; then
		return 3
	fi
	
	return 0
}

setup_fiji_jars() {
	# Determine if there is a cached set of jar files for the javac compiler
	if [[ -f "${CACHED_JARS}" ]]; then
		# Ensure that the contents are not older than 8 hours (in minutes)
		if [[ ! -z "`find ${CACHED_JARS} -mmin -480`" ]]; then
			# We have contents!  Load it
			FIJI_JARS=`cat ${CACHED_JARS}`
			
			echo "  --> Using cached content"
		else
			# These are too old - purge
			rm ${CACHED_JARS}
		fi
	fi
	
	if [[ -z "${FIJI_JARS}" ]]; then
		find_fiji_jars /Applications
		if [ $? -ne 0 ]; then
			find_fiji_jars ~
		fi
		
		# Save to the cache file
		echo "${FIJI_JARS}" > ${CACHED_JARS}
	fi
		
	if [[ -z "${FIJI_JARS}" ]]; then
		echo "Error: Unable to find Fiji jar files"
		exit 4
	fi
}

if [[ -z "$VERSION" ]]; then
  echo "Error: VERSION is not set."
  exit 1
fi

# Ensure we have a javac command we need to compile the Plugin command
if [[ -z "${JAVAC}" ]]; then
   echo "Error: Unable to find javac compiler."
   exit 2
fi

echo "Compiling Version: ${VERSION}"

# Now locate the Fiji jar files... this is Mac specific.  This can take a while so
# allow for caching it via a dot file in the home directory.  If this file is too
# old we will recalculate it.
echo "Searching for Fiji jar files"
setup_fiji_jars
if [[ -z "${FIJI_JARS}" ]]; then
	echo "Error: Unable to find Fiji jar files"
	exit 3
fi

echo "  --> Using Fiji Jars files: ${FIJI_JARS}"

# Resolve absolute path to the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Define the target jar file and ensure Releases exists
mkdir -p Releases/
JAR_FILENAME="DeleteROI_-${VERSION}.jar"
JAR_FILE_DL="Releases/${JAR_FILENAME}"

# Cleanup any left over files
rm -f "${SCRIPT_DIR}/${JAR_FILE_DL}"
rm -f "${SCRIPT_DIR}"/Lib/DeleteROIPkg/*.class

# Use a subshell to isolate directory changes
(
  cd "$SCRIPT_DIR/Lib" || exit 1
  
  # Build the Plugin java file
  echo "Compiling DeleteROI_Plugin.java"
  javac -cp "${FIJI_JARS}" --release 8 -Xlint:-options DeleteROI_Plugin.java

  echo "Creating JAR: ${JAR_FILENAME}"
  jar -cf "${SCRIPT_DIR}/${JAR_FILE_DL}" $(find . -name '*.py' -o -name '*.class' -o -name 'plugins.config')
  echo "JAR created successfully at: ${JAR_FILE_DL}"
)