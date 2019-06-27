import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

# helper class for cleaner multi-operation blocks on a single node.
class It():
  def __init__(self, node): self.node = node
  def __enter__(self): return self.node
  def __exit__(self, type, value, traceback): return False

#
# Dcm2niixGUI
#

class Dcm2niixGUI(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Diffusion-weighted DICOM Import (DCM2niixGUI)"
    self.parent.categories = ["Diffusion.Import and Export"]
    self.parent.dependencies = []
    self.parent.contributors = ["Isaiah Norton, Lauren O'Donnell (Brigham & Women's Hospital)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
Scripted wrapper GUI to run dcm2niix.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
Isaiah Norton and Lauren O'Donnell funded by NIH ITCR TODO.

Scripted module template originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

#
# Dcm2niixGUIWidget
#

class Dcm2niixGUIWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...

    #
    # Parameters Area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # input directory selector
    #
    with It(ctk.ctkPathLineEdit()) as w:
      self.inputDirectorySelector = w
      # make a directory-only, save dialog
      w.filters = ctk.ctkPathLineEdit.Dirs | ctk.ctkPathLineEdit.Writable
      parametersFormLayout.addRow("Input Directory: ", w)

    #
    # Apply Button
    #
    with It( qt.QPushButton("Apply") ) as w:
      self.applyButton = w
      w.toolTip = "Run the algorithm."
      w.enabled = False
      parametersFormLayout.addRow(w)

    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputDirectorySelector.connect('currentPathChanged(const QString&)', self.reset)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onSelect()

  def reset(self, _foo):
    enabled = os.path.isdir(self.inputDirectorySelector.currentPath)
    self.applyButton.enabled = enabled

  def cleanup(self):
    pass

  def onSelect(self):
    self.applyButton.enabled = self.inputDirectorySelector.currentPath

  def onApplyButton(self):
    logic = Dcm2niixGUILogic()
    self.applyButton.text = "Running..."
    result,error = logic.run(self.inputDirectorySelector.currentPath)
    self.applyButton.text = "Apply"
    if result is False:
      slicer.util.errorDisplay(error)


#
# Dcm2niixGUILogic
#

import tempfile
import subprocess

class Dcm2niixGUILogic(ScriptedLoadableModuleLogic):
  def run(self, inputDirectory):
    """
    Run the actual algorithm
    """

    tmp_dir = slicer.util.tempDirectory()
    tmp_out = tempfile.NamedTemporaryFile(dir=tmp_dir)
    # suffix=".nrrd"

    cmdPath = os.path.join(os.path.dirname(slicer.modules.dcm2niixgui.path), "Resources", "bin", "dcm2niix")
    args = list(( cmdPath,
                  "-1",
                  "-d", "0",
                  "-f", str(os.path.basename(tmp_out.name)),
                  "-o", str(tmp_dir),
                  "-e", "y", # this flag tells dcm2nii to directly create a .nrrd
                  "-z", "y",
                  str(inputDirectory)
                  ))
    print("running: ", args)
    try:
      call_output = subprocess.check_output(args)
    except Exception as err:
      print(err)
      return False, err

    print('dcm2nii arguments:')
    print(args)
    print('')
    print('dcm2nii results:')
    print(call_output)

    outputFileName = os.path.join(tmp_dir, tmp_out.name+'.nhdr')

    res = slicer.util.loadVolume( outputFileName, properties={"name": os.path.basename(str(inputDirectory))} )

    return res, "Check log for error"


class Dcm2niixGUITest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_Dcm2niixGUI1()

  def test_Dcm2niixGUI1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = Dcm2niixGUILogic()
    #self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
