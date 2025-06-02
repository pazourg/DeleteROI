#!/bin/bash

set -e 

VERSION=`awk -F\" '/^VERSION/ { print $2 }' ./Lib/DeleteROIPkg/__init__.py`

if [[ -z "$VERSION" ]]; then
  echo "Error: VERSION is not set."
  exit 1
fi

echo "Compiling Version: ${VERSION}"

# Resolve absolute path to the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Cleanup any 
rm -f ${SCRIPT_DIR}/Downloads/"DeleteRoi-${VERSION}.jar"
rm -f ${SCRIPT_DIR}/Lib/DeleteROIPkg/*.class

# Use a subshell to isolate directory changes
(
  cd "$SCRIPT_DIR/Lib" || exit 1

  echo "Creating JAR: DeleteROI-${VERSION}.jar"
  jar -cf "$SCRIPT_DIR/Downloads/DeleteROI-${VERSION}.jar" $(find DeleteROIPkg -name '*.py')
  echo "JAR created successfully at Downloads/DeleteROI-${VERSION}.jar"
)