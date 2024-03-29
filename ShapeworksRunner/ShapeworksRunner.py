from __future__ import print_function
import os
import unittest
import vtk, qt, ctk, slicer
from vtk import vtkStructuredPointsReader
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import logging
import json

#
# ShapeworksRunner
#

class ShapeworksRunner(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Shapeworks Runner"
    self.parent.categories = ["Shape Analysis"]
    self.parent.dependencies = []
    self.parent.contributors = ["Dan White (SCI Institute - University of Utah)"]
    self.parent.helpText = """First version of Shapeworks runner extension
"""
    self.parent.acknowledgementText = """
Insert acknowledgment here.
"""

#
# ShapeworksRunnerWidget
#

class ShapeworksRunnerWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    self.logic = ShapeworksRunnerLogic()
    self.logic.logCallback = self.addLog
    self.modelGenerationInProgress = False

    uiWidget = slicer.util.loadUI(self.resourcePath('UI/ShapeworksRunner.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    uiWidget.setPalette(slicer.util.mainWindow().style().standardPalette())

    # Finish UI setup ...
    #self.ui.parameterNodeSelector.addAttribute( "vtkMRMLScriptedModuleNode", "ModuleName", "ShapeworksRunner" )
    #self.ui.parameterNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.ui.inputSegmentationSelector.setMRMLScene( slicer.mrmlScene )
    #self.ui.inputModelSelector.setMRMLScene( slicer.mrmlScene )
    #self.ui.outputModelSelector.setMRMLScene( slicer.mrmlScene )

    customShapeworksPath = self.logic.getCustomShapeworksPath()
    self.ui.customShapeworksPathSelector.setCurrentPath(customShapeworksPath)
    self.ui.customShapeworksPathSelector.nameFilters = [self.logic.shapeworksFilename]

    #clipNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLClipModelsNode")
    #self.ui.clipNodeWidget.setMRMLClipNode(clipNode)

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # connections
    #self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.showTemporaryFilesFolderButton.connect('clicked(bool)', self.onShowTemporaryFilesFolder)
    #self.ui.inputSegmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateMRMLFromGUI)
    self.ui.inputSegmentationSelector.connect("checkedNodesChanged()", self.updateMRMLFromGUI)
    #self.ui.inputModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateMRMLFromGUI)
    #self.ui.outputModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateMRMLFromGUI)
    # Immediately update deleteTemporaryFiles in the logic to make it possible to decide to
    # keep the temporary file while the model generation is running
    self.ui.keepTemporaryFilesCheckBox.connect("toggled(bool)", self.onKeepTemporaryFilesToggled)

    # Shapeworks steps
    self.ui.launchShapeWorksPushButton_.connect("clicked(bool)", self.launchShapeWorksClicked)
    self.ui.generateProjectPushButton_.connect("clicked(bool)", self.generateProjectClicked)
    self.ui.groomPushButton_.connect("clicked(bool)", self.groomClicked)
    self.ui.optimizePushButton_.connect("clicked(bool)", self.optimizeClicked)
    self.ui.loadResultsPushButton_.connect("clicked(bool)", self.loadResultsClicked)
    # ShapeWorks file handling
    self.ui.setWorkingDirectoryPushButton_.connect("clicked(bool)", self.setWorkingDirectoryClicked)
    self.ui.loadProjectPushButton_.connect("clicked(bool)", self.loadProjectClicked)
    self.ui.saveProjectPushButton_.connect("clicked(bool)", self.saveProjectClicked)
    self.ui.saveGroomedPushButton_.connect("clicked(bool)", self.saveGroomClicked)
    self.ui.saveOptimizePushButton_.connect("clicked(bool)", self.saveOptimizeClicked)
    self.ui.saveResultsPushButton_.connect("clicked(bool)", self.saveResultsClicked)

    self.ui.loadDocsButton_.connect("clicked(bool)", self.loadDocsClicked)

    #Parameter node connections
    self.ui.inputSegmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    #self.ui.inputModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    #self.ui.outputModelSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    self.ui.showDetailedLogDuringExecutionCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.keepTemporaryFilesCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)

    self.ui.customShapeworksPathSelector.connect("currentPathChanged(const QString&)", self.updateParameterNodeFromGUI)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()
    #self.ui.parameterNodeSelector.setCurrentNode(self._parameterNode)
    #self.ui.parameterNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)",  self.setParameterNode)

    # Refresh Apply button state
    self.updateMRMLFromGUI()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Make sure parameter node exists and observed
    self.initializeParameterNode()
    self.updateMRMLFromGUI()

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    if self.parent.isEntered:
      self.initializeParameterNode()


  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

    # Select default input nodes if nothing is selected yet to save a few clicks for the user
    if not self._parameterNode.GetNodeReference("InputSegmentation"):
      firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
      if firstVolumeNode:
        self._parameterNode.SetNodeReferenceID("InputSegmentation", firstVolumeNode.GetID())

    # Select default input nodes if nothing is selected yet to save a few clicks for the user
    if not self._parameterNode.GetNodeReference("InputSurface"):
      firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLModelNode")
      if firstVolumeNode:
        self._parameterNode.SetNodeReferenceID("InputSurface", firstVolumeNode.GetID())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    self.ui.inputSegmentationSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputSegmentation"))
    #self.ui.inputModelSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputSurface"))
    #self.ui.outputModelSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputModel"))

    self.ui.showDetailedLogDuringExecutionCheckBox.checked = (self._parameterNode.GetParameter("showDetailedLogDuringExecution") == "true")
    self.ui.keepTemporaryFilesCheckBox.checked = (self._parameterNode.GetParameter("keepTemporaryFiles") == "true")

    self.ui.customShapeworksPathSelector.setCurrentPath(self._parameterNode.GetParameter("customShapeworksPath"))

    # Update buttons states and tooltips
    self.updateMRMLFromGUI()

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

    #Inputs/Outputs
    self._parameterNode.SetNodeReferenceID("InputSegmentation", self.ui.inputSegmentationSelector.currentNodeID)
    #self._parameterNode.SetNodeReferenceID("InputSurface", self.ui.inputModelSelector.currentNodeID)
    #self._parameterNode.SetNodeReferenceID("OutputModel", self.ui.outputModelSelector.currentNodeID)

    #General parameters
    self._parameterNode.SetParameter("showDetailedLogDuringExecution", "true" if self.ui.showDetailedLogDuringExecutionCheckBox.checked else "false")
    self._parameterNode.SetParameter("keepTemporaryFiles", "true" if self.ui.keepTemporaryFilesCheckBox.checked else "false")

    self._parameterNode.SetParameter("customShapeworksPath", self.ui.customShapeworksPathSelector.currentPath)

    self._parameterNode.EndModify(wasModified)

  def updateMRMLFromGUI(self):
    #Enable correct input selections
    inputIsModel = False
    self.ui.inputSegmentationLabel.visible = not inputIsModel
    self.ui.inputSegmentationSelector.visible = not inputIsModel
    self.ui.segmentSelectorLabel.visible = not inputIsModel
    self.ui.segmentSelectorCombBox.visible = not inputIsModel
    #self.ui.inputModelLabel.visible = inputIsModel
    #self.ui.inputModelSelector.visible = inputIsModel
    self.ui.segmentSelectorCombBox.enabled = self.ui.inputSegmentationSelector.currentNode() is not None

    self.ui.segmentSelectorCombBox.clear()

    #populate segments
    for inputSeg in self.ui.inputSegmentationSelector.checkedNodes():
      #print(inputSeg.GetName())

      if inputSeg is not None:
        segmentIDs = vtk.vtkStringArray()
        inputSeg.GetSegmentation().GetSegmentIDs(segmentIDs)
        #print(segmentIDs.GetNumberOfValues())
        for index in range(0, segmentIDs.GetNumberOfValues()):
          #print(segmentIDs.GetValue(index))
          self.ui.segmentSelectorCombBox.addItem("{0}: {1}".format(inputSeg.GetName(), segmentIDs.GetValue(index)))

    self.updateParameterNodeFromGUI()

  def onShowTemporaryFilesFolder(self):
    qt.QDesktopServices().openUrl(qt.QUrl("file:///" + self.logic.getTempDirectoryBase(), qt.QUrl.TolerantMode));

  def onKeepTemporaryFilesToggled(self, toggle):
    self.logic.deleteTemporaryFiles = toggle

  def generateProjectClicked(self):
    self.logic.generateShapeworksProjectJson(lambda s : s in [n.GetName() for n in self.ui.inputSegmentationSelector.checkedNodes()])

  def groomClicked(self):
    self.logic.groomShapeworksProject()

  def optimizeClicked(self):
    self.logic.optimizeShapeworksProject()

  def loadResultsClicked(self):
    self.logic.loadResultsOfShapeworksProject()

  def setWorkingDirectoryClicked(self):
    print("setWorkingDirectoryClicked")

  def launchShapeWorksClicked(self):
    inputParams = ["--name={0}".format(self.logic.projectFileName)]
    from sys import platform
    os.unsetenv("QT_PLUGIN_PATH")
    if platform == "win32":
      import subprocess
      subprocess.run(r"C:\Program Files\ShapeWorks\bin\ShapeWorksStudio.exe")
    else:
      os.system("open /Applications/ShapeWorksStudio.app")

  def loadProjectClicked(self):
    print("loadProjectClicked")
    #self.logic.loadResultsOfShapeworksProject()

  def saveProjectClicked(self):
    self.logic.saveProject()

  def saveGroomClicked(self):
    self.logic.saveGroomedFiles()

  def saveOptimizeClicked(self):
    self.logic.saveOptimizedFiles()

  def saveResultsClicked(self):
    print("saveResultsClicked")
    #self.logic.loadResultsOfShapeworksProject()

  def loadDocsClicked(self):
    print("loadDocsClicked")
    import webbrowser
    webbrowser.open("http://sciinstitute.github.io/ShapeWorks/latest/")
    #self.logic.loadResultsOfShapeworksProject()

  def addLog(self, text):
    """Append text to log window
    """
    self.ui.statusLabel.appendPlainText(text)
    slicer.app.processEvents()  # force update

#
# ShapeworksRunnerLogic
#

class ShapeworksRunnerLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)
    self.logCallback = None
    self.abortRequested = False
    self.deleteTemporaryFiles = True
    self.logStandardOutput = False
    self.customShapeworksPathSettingsKey = 'ShapeworksRunner/CustomShapeworksPath'
    import os
    self.scriptPath = os.path.dirname(os.path.abspath(__file__))
    self.shapeworksPath = self.shapeworksExecutablePath()
    self.projectFileName = ""
    self.shapeworksTempDir = self.createTempDirectory()

    import platform
    executableExt = '.exe' if platform.system() == 'Windows' else ''
    self.shapeworksFilename = 'shapeworks' + executableExt

    self.binDirCandidates = [
      # install tree
      os.path.join(self.scriptPath, '..'),
      os.path.join(self.scriptPath, '../../../bin'),
      # build tree
      os.path.join(self.scriptPath, '../../../../bin'),
      os.path.join(self.scriptPath, '../../../../bin/Release'),
      os.path.join(self.scriptPath, '../../../../bin/Debug'),
      os.path.join(self.scriptPath, '../../../../bin/RelWithDebInfo'),
      os.path.join(self.scriptPath, '../../../../bin/MinSizeRel') ]

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    self.setParameterIfNotDefined(parameterNode, "showDetailedLogDuringExecution", "false")
    self.setParameterIfNotDefined(parameterNode, "keepTemporaryFiles", "false")

    self.setParameterIfNotDefined(parameterNode, "customShapeworksPath", "")

  def setParameterIfNotDefined(self, parameterNode, key, value):
    if not parameterNode.GetParameter(key):
      parameterNode.SetParameter(key, value)

  def addLog(self, text):
    logging.info(text)
    if self.logCallback:
      self.logCallback(text)
      
  def shapeworksExecutablePath(self):
    from sys import platform
    if platform == "win32":
      return r"C:\Program Files\ShapeWorks\bin\shapeworks.exe"
    else:
      return "/Applications/ShapeWorks/bin/shapeworks"

  def getShapeworksPath(self):
    if self.shapeworksPath:
      return self.shapeworksPath

    self.shapeworksPath = self.getCustomShapeworksPath()
    if self.shapeworksPath:
      return self.shapeworksPath

    for binDirCandidate in self.binDirCandidates:
      shapeworksPath = os.path.abspath(os.path.join(binDirCandidate, self.shapeworksFilename))
      logging.debug("Attempt to find executable at: "+shapeworksPath)
      if os.path.isfile(shapeworksPath):
        # found
        self.shapeworksPath = shapeworksPath
        return self.shapeworksPath

    raise ValueError('Shapeworks not found')

  def getCustomShapeworksPath(self):
    settings = qt.QSettings()
    if settings.contains(self.customShapeworksPathSettingsKey):
      #self.addLog("getCustomShapeworksPath: " + settings.value(self.customShapeworksPathSettingsKey))
      return settings.value(self.customShapeworksPathSettingsKey)
    return ''

  def setCustomShapeworksPath(self, customPath):
    # don't save it if already saved
    settings = qt.QSettings()
    if settings.contains(self.customShapeworksPathSettingsKey):
      if customPath == settings.value(self.customShapeworksPathSettingsKey):
        return
    settings.setValue(self.customShapeworksPathSettingsKey, customPath)
    self.shapeworksPath = None
    self.getShapeworksPath()

  def buildProjectJsonInputData(self, inputFiles):
    return [{  "name": name, "shape_file": filename} for name,filename in inputFiles]

  def buildProjectJson(self, inputFiles):
    jsonProject = {
        "data": self.buildProjectJsonInputData(inputFiles),
        "groom": {
            "": {},
            "file": {}
        },
        "optimize": {
          "verbosity": "1",
          "particle_format": "vtk"
        }
      }
    return jsonProject

  def generateShapeworksProjectJson(self, selected):
    inputFiles = []
    for k,v in slicer.util.getNodes().items():
      if v.GetTypeDisplayName() == "Segmentation" or v.GetTypeDisplayName() == "Model": # TODO: need input widget for these first.
        if (selected(k)):
          segFile = os.path.join(self.shapeworksTempDir, k + ".nrrd")
          inputFiles.append((k, segFile))
          slicer.util.saveNode(v, segFile, {"useCompression": False})
    self.saveJsonProject(json.dumps(self.buildProjectJson(inputFiles)))

  def saveJsonProject(self, jProj):
    self.projectFileName = os.path.join(self.shapeworksTempDir, "shapeworksProject.swproj")
    with open(self.projectFileName, "w") as outfile:
      outfile.write(jProj)
    print("Wrote: ", self.projectFileName)

  def saveProject(self):
    file_name = qt.QFileDialog.getSaveFileName(None, "Save ShapeWorks Project File","","All Files (*);;Json Files(*.json)")
    print("Filename to save:", file_name)
    import shutil
    shutil.copyfile(self.projectFileName, file_name)
    
  def saveGroomedFiles(self):
    dir = qt.QFileDialog.getExistingDirectory(None, "Open Directory", self.shapeworksTempDir, qt.QFileDialog.ShowDirsOnly | qt.QFileDialog.DontResolveSymlinks)
    with open(self.projectFileName) as projFile:
      data = json.load(projFile)
      for d in data["data"]:
        _, filename = os.path.split(d["groomed_file"])
        fileToCopy = os.path.join(self.shapeworksTempDir, d["groomed_file"])
        import shutil
        shutil.copyfile(fileToCopy, os.path.join(dir, filename))
        
  def saveOptimizedFiles(self):
    dir = qt.QFileDialog.getExistingDirectory(None, "Open Directory", self.shapeworksTempDir, qt.QFileDialog.ShowDirsOnly | qt.QFileDialog.DontResolveSymlinks)
    with open(self.projectFileName) as projFile:
      data = json.load(projFile)
      for d in data["data"]:
        _, filename = os.path.split(d["world_particles_file"])
        fileToCopy = os.path.join(self.shapeworksTempDir, d["world_particles_file"])
        import shutil
        shutil.copyfile(fileToCopy, os.path.join(dir, filename))

  def runShapeworksCommand(self, inputParams, name):
    swCmd = "{0}: {1} {2}".format(name, self.shapeworksPath, ' '.join(inputParams))
    print(swCmd)
    os.unsetenv("QT_PLUGIN_PATH")
    ep = self.runShapeworks(inputParams, self.getShapeworksPath())
    self.logProcessOutput(ep, self.shapeworksFilename)

  def groomShapeworksProject(self):
    inputParams = ["groom", "--name={0}".format(self.projectFileName), "--progress"]
    self.runShapeworksCommand(inputParams, inputParams[0])
    self.addLog("Groomed files:")
    self.addLog(os.listdir(os.path.join(self.shapeworksTempDir, "groomed")))

  def optimizeShapeworksProject(self):
    inputParams = ["optimize", "--name={0}".format(self.projectFileName)]
    self.runShapeworksCommand(inputParams, inputParams[0])
    self.addLog("Optimized files:")
    self.addLog(os.listdir(os.path.join(self.shapeworksTempDir, "shapeworksProject_particles")))

  def loadResultsOfShapeworksProject(self):
    print("This requires Shapeworks 6.5+")
    dir = os.path.join(self.shapeworksTempDir, "shapeworksProject_particles")
    filesToRead = [file for file in os.listdir(dir) if file.endswith("_local.vtk")] # local or world? transform?
    print("Loading these vtk point files:\n" + repr(filesToRead))
    for vtkPointFile in filesToRead:
      reader = vtk.vtkPolyDataReader()
      reader.SetFileName(os.path.join(dir, vtkPointFile))
      reader.ReadAllVectorsOn()
      reader.ReadAllScalarsOn()
      reader.Update()
      data = reader.GetOutput()
      # Create the vtkSphereSource object.
      sphere = vtk.vtkSphereSource()
      sphere.SetRadius(2.0)
      # Create the vtkGlyph3D object.
      glyph = vtk.vtkGlyph3D()
      glyph.SetInputData(data)
      glyph.SetSourceConnection(sphere.GetOutputPort())
      pointCloudModelNode = slicer.modules.models.logic().AddModel(glyph.GetOutputPort())
      pointCloudModelNode.SetName(vtkPointFile)

  def runShapeworks(self, cmdLineArguments, executableFilePath):
    self.addLog("Running Shapeworks...")
    import subprocess

    # Hide console window on Windows
    from sys import platform
    if platform == "win32":
      info = subprocess.STARTUPINFO()
      info.dwFlags = 1
      info.wShowWindow = 0
    else:
      info = None

    self.addLog("Running Shapeworks using: "+executableFilePath+": "+repr(cmdLineArguments))
    return subprocess.Popen([executableFilePath] + cmdLineArguments,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, startupinfo=info)

  def logProcessOutput(self, process, processName):
    # save process output (if not logged) so that it can be displayed in case of an error
    processOutput = ''
    import subprocess
    for stdout_line in iter(process.stdout.readline, ""):
      if self.logStandardOutput:
        self.addLog(stdout_line.rstrip())
      else:
        processOutput += stdout_line.rstrip() + '\n'
      slicer.app.processEvents()  # give a chance to click Cancel button
      if self.abortRequested:
        process.kill()
    process.stdout.close()
    return_code = process.wait()
    if return_code:
      if self.abortRequested:
        raise ValueError("User requested cancel.")
      else:
        if processOutput:
          self.addLog(processOutput)
        raise subprocess.CalledProcessError(return_code, processName)

  def getTempDirectoryBase(self):
    tempDir = qt.QDir(slicer.app.temporaryPath)
    fileInfo = qt.QFileInfo(qt.QDir(tempDir), "ShapeworksRunner")
    dirPath = qt.QDir.toNativeSeparators(fileInfo.absoluteFilePath())
    qt.QDir().mkpath(dirPath)
    return dirPath

  def createTempDirectory(self):
    import qt, slicer
    tempDir = qt.QDir(self.getTempDirectoryBase())
    tempDirName = qt.QDateTime().currentDateTime().toString("yyyyMMdd_hhmmss_zzz")
    fileInfo = qt.QFileInfo(qt.QDir(tempDir), tempDirName)
    dirPath = qt.QDir.toNativeSeparators(fileInfo.absoluteFilePath())
    print(f"dirPath: {dirPath}")
    qt.QDir().mkpath(dirPath)
    return dirPath

  def runImpl(self, segments = []):

    self.abortRequested = False

    self.addLog('Shapeworks is started in working directory: ' + shapeworksTempDir)

    ep = self.runShapeworks(inputParams, self.getShapeworksPath())
    self.logProcessOutput(ep, self.shapeworksFilename)

    # Clean up
    if self.deleteTemporaryFiles:
      import shutil
      shutil.rmtree(tempDir)

    self.addLog("Shapeworks processing is complete.")

class ShapeworksRunnerTest(ScriptedLoadableModuleTest):
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
    self.test_TODO()

  def test_TODO(self):
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

    logic = ShapeworksRunnerLogic()

    jsonTest = logic.buildProjectJson([])
    self.assertEqual(jsonTest, "{'data': [], 'groom': {'': {}, 'file': {}}, 'optimize': {'verbosity': '1'}}")
    #logic.generateShapeworksProjectJson(lambda s : True)


    #self.assertTrue(False)

    self.delayDisplay('Test passed!')
