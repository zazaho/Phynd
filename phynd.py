#!/usr/bin/python3
import sys
import os
from os.path import expanduser
import glob
import subprocess
import configparser
import threading
import tkinter as tk
from tkinter import font as tkfont
import pandas as pd
from system_hotkey import SystemHotkey

# logic:
# create a window
# hide it
# register a hot key that will show the window
# register esc to hide i
# register Crtl-qesc to quit

# have a list (in a panda DataFrame of all directories below home:
# upon start up read it from a file
# start a thread to find the current dirs
# when the thread finishes update the list and overwrite the file


class Configuration():
    ' Object that can initialise, change and inform about App configuration'
    def __init__(self):
        # The path of the appdata and ini file
        ConfigPath = os.path.join(
            os.environ.get('APPDATA') or
            os.environ.get('XDG_CONFIG_HOME') or
            os.path.join(os.environ['HOME'], '.config'),
            "phynd"
        )
        self.IniPath = os.path.join(ConfigPath, 'phynd.ini')

        # dict to store all settings
        self.ConfigurationDict = {}
        self.set('cmdlinearguments',sys.argv[1:])
        self.set('csvdir',ConfigPath)
        self.set('csvname','phynd.csv.xz')
        self._setDefaultConfiguration()
        self._readConfiguration()

    def _setDefaultConfiguration(self):
        'Default configuration parameters'
        self.set('topdir',expanduser("~"))
        self.set('hotket',('control', 'shift', 'h'))

    def _readConfiguration(self):
        '''Function to get configurable parameters from Phynd.ini.'''
        config = configparser.ConfigParser()
        if config.read(self.IniPath):
            default = config['phynd']
            topdir = default.get('topdir', expanduser("~"))
            hotkey = default.get('hotkey', ('control', 'shift', 'h'))
            # store read values in ConfigurationDict
            self.set('topdir',topdir)
            self.set('hotkey',hotkey)

    def writeConfiguration(self):
        'save configuration info'

        # save settings disabled
        if not self.ConfigurationDict['savesettings']:
            return

        config = configparser.ConfigParser()
        config['phynd'] = {
            'topdir':self.get('topdir'),
            'hotkey':self.get('hotkey'),
        }
        with open(self.IniPath, 'w') as configfile:
            config.write(configfile)

    def get(self, parameter):
        'Return one value of the configuration'
        if parameter in self.ConfigurationDict:
            return self.ConfigurationDict[parameter]

    def set(self, param, value):
        'Add/Change a configuration parameter'
        self.ConfigurationDict[param] = value

class inputDialog(tk.Toplevel):
    def __init__(self, parent, dirlist):
        super().__init__()

        self.parent = parent
        self.dirlist = dirlist
        self.matchingDirs = None

        self.title("Phynd")
        self.attributes("-topmost", True)
        self.attributes('-type', 'dock')
        self.result = None

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        # we want the popup window to be comfortably large
        # and a bit near the top of the screen
        window_width  = screen_width * 0.5
        window_height = screen_height * 0.3

        self.geometry('%dx%d+%d+%d' % (
            window_width,
            window_height,
            screen_width * 0.5 - window_width/2,
            screen_height * 0.3 - window_height/2
        ))
        self.update_idletasks()

        myfont = tkfont.Font(family='Helvetica', size=12)

        self.inputVar = tk.StringVar()
        self.inputEntry = tk.Entry(
            self,
            font=myfont,
            textvariable=self.inputVar,
        )
        self.inputVar.trace_add("write", self._inputChanged)
        self.inputEntry.pack(fill='x', padx=10, pady=10)

        self.ResultsLB = tk.Listbox(
            self,
            font=myfont,
            height=round(window_height*0.8),
            selectmode=tk.SINGLE,
        )
        self.ResultsLB.pack(fill='x', padx=10, pady=10)
        self.ResultsLB.bind('<Double-Button-1>', self._onResultSelected)
        self.ResultsLB.bind('<Return>', self._onResultSelected)
        self.bind("<Control-q>", self._quit)
        self.bind("<Escape>", self._abort)

        self.focus_force()
        self.inputEntry.focus_set()
        self.wait_window(self)
        
    def _inputChanged(self, *args):
        filteredDirs = self._filterByInput()
        self._showOutput()
        
    def _filterByInput(self):
        dirl = self.dirlist
        for wrd in self.inputVar.get().split():
            orgNames = dirl['Name']
            lowNames = dirl['Name'].str.lower()
            if wrd.islower():
                Idx = lowNames.str.find(wrd) != -1
            else:
                Idx = orgNames.str.find(wrd) != -1
            dirl = dirl[Idx]
        self.matchingDirs = dirl['Name'].values

    def _showOutput(self):
        self.ResultsLB.delete(0, tk.END)
        for item in self.matchingDirs:
            self.ResultsLB.insert(tk.END, item)

    def _onResultSelected(self, *args):
        self.result = self.matchingDirs[self.ResultsLB.curselection()]
        self._returntoparent()

    def _quit(self, *args):
        self.result = "###I###WANT###YOU###TO###GO###KILL###YOURSELF###"
        self._returntoparent()
        
    def _abort(self, *args):
        self.result = ""
        self._returntoparent()
        
    def _returntoparent(self):
        self.withdraw()
        self.update_idletasks()
        self.destroy()
        
class myapp(tk.Tk):
    def __init__(self, ScriptPath=None):
        super().__init__()

        self.Cfg = Configuration()

        self.attributes('-type', 'dock')
        self.geometry("0x0+0+0")

        self.hk = SystemHotkey()
        self.hk.register(('control', 'shift', 'h'), callback=self.showhide)
        self.doingInput = False
        self.allDirs = None

        self.readAllDirsFromFile()

        dirFindThread = threading.Thread(target=self.updateAllDirs)
        dirFindThread.daemon = True
        dirFindThread.start()

    def exitProgram(self, *args):
        self.quit()

    def showhide(self, *args):
        if self.allDirs is None:
            return
        if not self.doingInput:
            self.update_idletasks()
            self.doingInput = True
            self.hk.unregister(('control', 'shift', 'h'))
            inputResult = inputDialog(self, self.allDirs).result
            self.hk.register(('control', 'shift', 'h'), callback=self.showhide)
            self.doingInput = False
        if not inputResult:
            return
        if inputResult == "###I###WANT###YOU###TO###GO###KILL###YOURSELF###":
            self.exitProgram()
            return
        #subprocess.run("/usr/bin/konsole &", shell=True, cwd=inputResult)
        subprocess.run('xdg-open "%s" &' % (inputResult), shell=True)
         
    def writeAllDirsToFile(self):
        if not os.path.isdir(self.Cfg.get('csvdir')):
            os.mkdir(self.Cfg.get('csvdir'))
        self.allDirs.to_csv(
            os.path.join(self.Cfg.get('csvdir'), self.Cfg.get('csvname')),
            columns=['Name'],
        )
        
    def readAllDirsFromFile(self):
        csvfile = os.path.join(self.Cfg.get('csvdir'), self.Cfg.get('csvname'))
        if os.path.isfile(csvfile):
            self.allDirs = pd.read_csv(csvfile)
        
    def updateAllDirs(self):
        dirl = []
        for root, dirs, files in os.walk(self.Cfg.get('topdir')):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            dirl.extend([os.path.join(root, dir) for dir in dirs])
        #dirl = [x for x, _, _ in os.walk()]
        self.allDirs = pd.DataFrame(columns=['Name'], data=dirl)
        self.writeAllDirsToFile()
        
def main():
    app = myapp()
    app.mainloop()

if __name__ == "__main__":
    main()
