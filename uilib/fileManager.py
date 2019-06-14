from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal

import motorlib

from .fileIO import saveFile, loadFile, fileTypes


class FileManager(QObject):

    fileNameChanged = pyqtSignal(str, bool)

    def __init__(self, app):
        super().__init__()
        self.app = app

        self.fileHistory = []
        self.currentVersion = 0
        self.savedVersion = 0

        self.fileName = None

        self.newFile()

    # Check if current motor is unsaved and start over from default motor. Called when the menu item is triggered.
    def newFile(self):
        if self.unsavedCheck():
            newMotor = motorlib.motor.Motor()
            motorConfig = self.app.preferencesManager.preferences.general.getProperties()
            newMotor.config.setProperties(motorConfig) # Copy over user's preferences
            self.startFromMotor(newMotor)

    # Reset to empty motor history and set current motor to what is passed in
    def startFromMotor(self, motor, filename=None):
        motor = self.checkPropellant(motor)
        self.fileHistory = [motor.getDict()]
        self.currentVersion = 0
        self.savedVersion = 0
        self.fileName = filename
        self.sendTitleUpdate()

    # Asks the user for a filename if they haven't provided one. Otherwise, dump the motor to a file and show any resulting errors in a popup. Called when the menu item is triggered.
    def save(self):
        if self.fileName is None:
            self.saveAs() # Though this function calls save again, the above condition will be false on the second time around and the file will save
        else:
            try:
                saveFile(self.fileName, self.fileHistory[self.currentVersion], fileTypes.MOTOR)
                self.savedVersion = self.currentVersion
                self.sendTitleUpdate()
            except Exception as exc:
                self.app.outputException(exc, "An error occurred while saving the file: ")

    # Asks for a new file name and saves the motor
    def saveAs(self):
        fileName = self.showSaveDialog()
        if fileName is not None:
            self.fileName = fileName
            self.save()

    # Checks for unsaved changes, asks for a filename, and loads the file
    def load(self, path=None):
        if self.unsavedCheck():
            if path is None:
                path = QFileDialog.getOpenFileName(None, 'Load motor', '', 'Motor Files (*.ric)')[0]
            if path != '': # If they cancel the dialog, path will be an empty string
                try:
                    res = loadFile(path, fileTypes.MOTOR)
                    if res is not None:
                        motor = motorlib.motor.Motor()
                        motor.applyDict(res)
                        self.startFromMotor(motor, path)
                        return True
                except Exception as exc:
                    self.app.outputException(exc, "An error occurred while loading the file: ")

        return False # If no file is loaded, return false

    # Return the recent end of the motor history
    def getCurrentMotor(self):
        newMotor = motorlib.motor.Motor()
        newMotor.applyDict(self.fileHistory[self.currentVersion])
        return newMotor

    # Add a new entry to motor history
    def addNewMotorHistory(self, motor): # Add a new version of the motor to the motor history. Should be used for all user interactions.
        if motor.getDict() != self.fileHistory[self.currentVersion]:
            if self.canRedo():
                del self.fileHistory[self.currentVersion + 1:]
            self.fileHistory.append(motor.getDict())
            self.currentVersion += 1
            self.sendTitleUpdate()

    # Changes the current motor without adding undo history. Should not be used after user interaction.
    def overrideCurrentMotor(self, motor):
        self.fileHistory[-1] = motor.getDict()

    # Returns true if there is history before the current motor
    def canUndo(self):
        return self.currentVersion > 0

    # Rolls back the current motor to point at the motor before it in the history
    def undo(self):
        if self.canUndo():
            self.currentVersion -= 1
            self.sendTitleUpdate()

    # Returns true if there is history ahead of the current motor
    def canRedo(self):
        return self.currentVersion < len(self.fileHistory) - 1

    # Changes current motor to be the next motor in history
    def redo(self):
        if self.canRedo():
            self.currentVersion += 1
            self.sendTitleUpdate()

    # If there is unsaved history, ask the user if they want to save it. Returns true if it is safe to start a new motor (save, discard) or false if not (cancel)
    def unsavedCheck(self):
        if self.savedVersion != self.currentVersion:
            msg = QMessageBox()

            msg.setText("The current file has unsaved changes. Close without saving?")
            msg.setWindowTitle("Close without saving?")
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

            res = msg.exec_()
            if res == QMessageBox.Save:
                self.save()
                return True
            if res == QMessageBox.Discard:
                return True
            return False

        return True

    # Outputs the filename component of the title
    def sendTitleUpdate(self):
        self.fileNameChanged.emit(self.fileName, self.savedVersion == self.currentVersion)

    # Pops up a save file dialog and returns the path, or None if it is canceled
    def showSaveDialog(self):
        path = QFileDialog.getSaveFileName(None, 'Save motor', '', 'Motor Files (*.ric)')[0]
        if path == '' or path is None:
            return None
        if path[-4:] != '.ric':
            path += '.ric'
        return path

    # Checks if a motor's propellant is in the library, adds it if it isn't, and also looks for conflicts
    def checkPropellant(self, motor):
        if motor.propellant is not None:
            if motor.propellant.getProperty('name') not in self.app.propellantManager.getNames():
                self.app.outputMessage('The propellant from the loaded motor was not in the library, so it was added as "' + motor.propellant.getProperty('name') + '"',
                        'New propellant added')
                self.app.propellantManager.propellants.append(motor.propellant)
                self.app.propellantManager.savePropellants()
            else:
                if motor.propellant.getProperties() != self.app.propellantManager.getPropellantByName(motor.propellant.getProperty('name')).getProperties():
                    addedNumber = 1
                    while motor.propellant.getProperty('name') + ' (' + str(addedNumber) + ')' in self.app.propellantManager.getNames():
                        addedNumber += 1
                    motor.propellant.setProperty('name', motor.propellant.getProperty('name') + ' (' + str(addedNumber) + ')')
                    self.app.propellantManager.propellants.append(motor.propellant)
                    self.app.propellantManager.savePropellants()
                    self.app.outputMessage('The propellant from the loaded motor matches an existing item in the library, but they have different properties. The propellant from the motor has been added to the library as "' + motor.propellant.getProperty('name') + '"',
                        'New propellant added')
        return motor
