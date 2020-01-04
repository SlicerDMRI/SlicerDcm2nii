import os
import string
from __main__ import vtk, qt, ctk, slicer
import logging
import numpy
from DICOMLib import DICOMPlugin
from DICOMLib import DICOMLoadable

#
# This DICOM plugin uses dcm2niix to examine and load DICOM images.
#

class Dcm2niixPluginClass(DICOMPlugin):
  """ dcm2niix based DICOM reader plugin
  """

  def __init__(self):
    super(Dcm2niixPluginClass,self).__init__()
    self.loadType = "dcm2niix"
    self.tags['seriesUID'] = "0020,000E"

  def examine(self,fileLists):
    """ Returns a list of DICOMLoadable instances
    corresponding to ways of interpreting the
    fileLists parameter.
    """
    loadables = []
    for files in fileLists:
      loadables += self.examineFiles(files)

    return loadables

  def examineFiles(self,files):
    """ Returns a list of DICOMLoadable instances
    corresponding to ways of interpreting the
    files parameter.
    """
    loadables = []

    import tempfile
    from subprocess import Popen, PIPE, CalledProcessError
    with tempfile.TemporaryDirectory(dir=slicer.app.temporaryPath) as tempDir:

      # write DICOM file list to text file
      inputDicomFileListFilename = os.path.join(tempDir, "input-dicom-files.txt")
      with open(inputDicomFileListFilename, 'w') as fp:
        for filename in files:
          fp.write("{0}\n".format(filename))

      # examine using dcm2niix
      cmdPath = os.path.join(os.path.dirname(slicer.modules.dcm2niixgui.path), "Resources", "bin", "dcm2niix")
      command_line = [cmdPath,
                    "-n", "-1", # examine only, do not write output files
                    "-s", "y", # input is a single filelist
                    "-f", "%p_%t_%s", # output file name (difference compared to the default is that folder name is removed)
                    "-i", "y", # ignore derived, localizer and 2D images
                    "-o", str(tempDir), # set output folder
                    str(inputDicomFileListFilename)
                    ]
      logging.debug(repr(command_line))

      try:
        # launch dcm2niix
        proc = slicer.util.launchConsoleProcess(command_line)

        # process output
        loadableInitialized = False
        for line in proc.stdout:
          line = line.rstrip()
          if not loadableInitialized:
            # Default scalar volume reader has confidence of 0.5, so this value will not
            # make dcm2niix used by default but the user has to select it
            confidence = 0.45
            warningMessages = []
            infoMessages = []
            loadableInitialized = True
          logging.debug(line)
          #slicer.app.processEvents()  # give a chance the application to refresh GUI
          if (line.startswith("Compression will be faster with pigz")
            or line.startswith("Chris Rorden's dcm2niiX")
            or line.startswith("Conversion required")):
            # general information, ignore
            pass
          elif (line.startswith(" ")
            or line.startswith("dx=")
            or line.startswith("instance=")):
            # debug message, ignore
            pass
          elif (line.startswith("Warning:")
            or line.startswith("Unsupported transfer syntax")
            or line.startswith("Unable to determine")):
            if line not in warningMessages:
              warningMessages.append(line)
            # Reduce confidence if there was a warning.
            # This value is higher than scalar volume's confidence of 0.2 when no pixel data is found.
            confidence = 0.3
          elif line.startswith("\t"):
            # found a loadable file
            [dummy, seriesNumber, filepath] = line.split('\t')
            loadable = DICOMLoadable()
            loadable.files = files
            seriesUID = slicer.dicomDatabase.fileValue(files[0],self.tags['seriesUID'])
            seriesName = self.defaultSeriesNodeName(seriesUID) 
            loadable.name = seriesName
            loadable.warning = ('\n').join(warningMessages)
            dcm2niixGeneratedName = os.path.basename(filepath)
            loadable.tooltip = ('\n').join([dcm2niixGeneratedName]+infoMessages)
            loadable.selected = True
            loadable.confidence = confidence
            loadable.seriesNumber = seriesNumber
            loadables.append(loadable)
            loadableInitialized = False
          else:
            infoMessages.append(line)

        proc.wait()
        retcode=proc.returncode
        if retcode != 0:
          raise CalledProcessError(retcode, proc.args, output=proc.stdout, stderr=proc.stderr)
      except CalledProcessError as e:
        logging.debug("Failed to examine files using dcm2niix: {0}".format(e.message))

    return loadables

  def load(self,loadable):
    """Load the selection
    """
    loadedNode = None

    import tempfile
    import os
    from subprocess import Popen, PIPE, CalledProcessError
    from DICOMScalarVolumePlugin import DICOMScalarVolumePluginClass

    with tempfile.TemporaryDirectory(dir=slicer.app.temporaryPath) as tempDir:

      # write DICOM file list to text file
      inputDicomFileListFilename = os.path.join(tempDir, "input-dicom-files.txt")
      with open(inputDicomFileListFilename, 'w') as fp:
        for filename in loadable.files:
          fp.write("{0}\n".format(filename))

      # examine using dcm2niix
      cmdPath = os.path.join(os.path.dirname(slicer.modules.dcm2niixgui.path), "Resources", "bin", "dcm2niix")
      command_line = [cmdPath,
                    "-n", str(loadable.seriesNumber), # load only the selected series number
                    "-s", "y", # input is a single filelist
                    #"-f", "%s_%p_%d", # output file name is series number, protocol, and description
                    "-i", "y", # ignore derived, localizer and 2D images
                    "-o", str(tempDir), # set output folder
                    #"-e", "y", # create nrrd (it does not always work well)
                    str(inputDicomFileListFilename)
                    ]
      logging.debug(repr(command_line))

      try:
        # launch dcm2niix
        proc = slicer.util.launchConsoleProcess(command_line)

        # process output
        loadableInitialized = False
        for line in proc.stdout:
          logging.debug(line.rstrip())
          slicer.app.processEvents()  # give a chance the application to refresh GUI
        proc.wait()
        retcode=proc.returncode
        if retcode != 0:
          raise CalledProcessError(retcode, proc.args, output=proc.stdout, stderr=proc.stderr)
      except CalledProcessError as e:
        logging.debug("Failed to load series {0} using dcm2niix: {1}".format(loadable.seriesNumber, e.message))

      import os
      volumeFiles = [file for file in os.listdir(tempDir) if file.endswith(".nii")]
      for volumeFile in volumeFiles:
          loadedNode = slicer.util.loadVolume(os.path.join(tempDir, volumeFile), properties={'name': loadable.name})
          # Add the volume in subject hierarchy
          defaultScalarVolumePlugin = DICOMScalarVolumePluginClass()
          defaultScalarVolumePlugin.setVolumeNodeProperties(loadedNode,loadable)

    return loadedNode

#
# Dcm2niixPlugin
#

class Dcm2niixPlugin:
  """
  This class is the 'hook' for slicer to detect and recognize the plugin
  as a loadable scripted module
  """
  def __init__(self, parent):
    parent.title = "dcm2niix DICOM import plugin"
    parent.categories = ["Developer Tools.DICOM Plugins"]
    parent.contributors = ["Andras Lasso (PerkLab)"]
    parent.helpText = """
    Plugin to the DICOM Module to import DICOM files using dcm2niix.
    No module interface here, only in the DICOM module.
    """
    parent.acknowledgementText = """
    dcm2niix is developed by Chris Rorden.
    """

    # don't show this module - it only appears in the DICOM module
    parent.hidden = True

    # Add this extension to the DICOM module's list for discovery when the module
    # is created.  Since this module may be discovered before DICOM itself,
    # create the list if it doesn't already exist.
    try:
      slicer.modules.dicomPlugins
    except AttributeError:
      slicer.modules.dicomPlugins = {}
    slicer.modules.dicomPlugins['Dcm2niixPlugin'] = Dcm2niixPluginClass
