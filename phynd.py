#!/usr/bin/python3
"""Modal find windows that matches by parts of the path."""
import configparser
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from typing import Any, List, Tuple

import pandas as pd
from system_hotkey import SystemHotkey

MIN_NB_CHARS = 3
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


def _parse_str_tuple(input_str: str) -> Tuple[str]:
    return tuple(k.strip('\'\" ') for k in input_str[1:-1].split(","))

def _parse_str_list(input_str: str) -> List[str]:
    return [k.strip('\'\" ') for k in input_str[1:-1].split(",")]

class Configuration:
    """Object that can initialise, change and inform about App configuration."""

    def __init__(self: object) -> None:
        """Set the path of the appdata and ini file."""
        config_path = Path(
            os.environ.get("APPDATA")
            or os.environ.get("XDG_CONFIG_HOME")
            or Path(os.environ["HOME"]) / ".config"
        ) / "phynd"

        self.ini_path = Path(config_path, "phynd.ini")

        # dict to store all settings
        self.configuration_dict = {}
        self.set("cmdlinearguments", sys.argv[1:])
        self.set("csvdir", config_path)
        self.set("csvname", "phynd.csv.xz")
        self._set_default_configuration()
        self._read_configuration()

    def _set_default_configuration(self: object) -> None:
        """Set default configuration parameters."""
        self.set("topdir", Path("~").expanduser())
        self.set("savesettings", value=True)
        self.set("hotkey", ("control", "shift", "h"))
        self.set("exclude", [])

    def _read_configuration(self: object) -> None:
        """Get configurable parameters from Phynd.ini."""
        config = configparser.ConfigParser(
            converters={"stringtuple": _parse_str_tuple, "stringlist": _parse_str_list})
        if config.read(self.ini_path):
            default = config["phynd"]
            topdir = default.get("topdir", self.get("topdir"))
            hotkey = default.getstringtuple("hotkey", self.get("hotkey"))
            exclude = default.getstringlist("exclude", self.get("exclude"))
            # store read values in configuration_dict
            self.set("topdir", topdir)
            self.set("hotkey", hotkey)
            self.set("exclude", exclude)

    def write_configuration(self: object) -> None:
        """Save configuration info."""
        # save settings disabled
        if not self.get("savesettings"):
            return

        config = configparser.ConfigParser()
        config["phynd"] = {
            "topdir":self.get("topdir"),
            "hotkey":self.get("hotkey"),
            "exclude":self.get("exclude"),
        }
        with Path.open(self.ini_path, "w") as configfile:
            config.write(configfile)

    def get(self: object, parameter: str) -> Any:
        """Return one value of the configuration."""
        if parameter in self.configuration_dict:
            return self.configuration_dict[parameter]
        return None

    def set(self: object, param: str, value: Any) -> None:
        """Add/Change a configuration parameter."""
        self.configuration_dict[param] = value

class InputDialog(tk.Toplevel):
    """Modal input window."""

    def __init__(self: object, parent: object, dirlist: pd.DataFrame) -> None:
        """Set defaults for class."""
        super().__init__()

        self.parent = parent
        self.dirlist = dirlist
        self.matching_dirs = []
        self.result = None

        self.title("Phynd")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        # we want the popup window to be comfortably large
        # and a bit near the top of the screen
        window_width  = screen_width * 0.5
        window_height = screen_height * 0.3
        self.geometry("%dx%d+%d+%d" % (
            window_width,
            window_height,
            screen_width * 0.5 - window_width/2,
            screen_height * 0.3 - window_height/2,
        ))

        myfont = tkfont.Font(family="Helvetica", size=12)
        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(
            self,
            font=myfont,
            textvariable=self.input_var,
        )
        self.input_var.trace_add("write", self._input_changed)
        self.input_entry.pack(fill="x", padx=10, pady=10)

        self.results_lb = tk.Listbox(
            self,
            font=myfont,
            height=round(window_height*0.8),
            selectmode=tk.SINGLE,
        )
        self.results_lb.pack(fill="x", padx=10, pady=10)
        self.results_lb.bind("<Double-Button-1>", self._on_result_selected)
        self.results_lb.bind("<Return>", self._on_result_selected)
        self.bind("<Control-q>", self._quit)
        self.bind("<Escape>", self._abort)

        self.attributes("-topmost", True)
        self.focus_force()
        self.input_entry.focus_set()
        self.wait_window(self)

    def _input_changed(self: object, *_: List) -> None:
        self._filter_by_input()
        self._show_output()

    def _filter_by_input(self: object) -> None:
        # only start searching after a few letters have been entered
        if len(self.input_var.get()) < MIN_NB_CHARS:
            return
        dirl = self.dirlist
        for wrd in self.input_var.get().split():
            if wrd.islower():
                idx = dirl["Name"].str.lower().str.find(wrd) != -1
            else:
                idx = dirl["Name"].str.find(wrd) != -1
            dirl = dirl[idx]
        self.matching_dirs = list(dirl["Name"])

    def _show_output(self: object) -> None:
        self.results_lb.delete(0, tk.END)
        for item in self.matching_dirs:
            self.results_lb.insert(tk.END, item)

    def _on_result_selected(self: object, *_: List) -> None:
        self.result = self.matching_dirs[self.results_lb.curselection()[0]]
        self._return_to_parent()

    def _quit(self: object, *_: List) -> None:
        self.result = "###I###WANT###YOU###TO###GO###KILL###YOURSELF###"
        self._return_to_parent()

    def _abort(self: object, *_: List) -> None:
        self.result = ""
        self._return_to_parent()

    def _return_to_parent(self: object) -> None:
        self.withdraw()
        self.update_idletasks()
        self.destroy()

class Phynd(tk.Tk):
    """The main application class of phynd."""

    def __init__(self: object) -> None:
        """Set the defaults for phynd."""
        super().__init__()

        self.cfg = Configuration()

        self.attributes("-type", "dock")
        self.geometry("0x0+0+0")

        self.hk = SystemHotkey()
        self.hk.register(self.cfg.get("hotkey"), callback=self._show_hide)
        self.doing_input = False
        self.all_dirs = None

        self._read_all_dirs_from_file()

        dir_find_thread = threading.Thread(target=self._update_all_dirs)
        dir_find_thread.daemon = True
        dir_find_thread.start()

    def _exit_program(self: object, *_: List) -> None:
        self.cfg.write_configuration()
        self.quit()

    def _show_hide(self: object, *_: List) -> None:
        if self.all_dirs is None:
            return
        if not self.doing_input:
            self.update_idletasks()
            self.doing_input = True
            self.hk.unregister(self.cfg.get("hotkey"))
            input_result = InputDialog(self, self.all_dirs).result
            self.hk.register(self.cfg.get("hotkey"), callback=self._show_hide)
            self.doing_input = False
        if not input_result:
            return
        if input_result == "###I###WANT###YOU###TO###GO###KILL###YOURSELF###":
            self._exit_program()
            return
        subprocess.run("/usr/bin/konsole &", shell=True, cwd=input_result)

    def _write_all_dirs_to_file(self: object) -> None:
        if not Path.is_dir(self.cfg.get("csvdir")):
            Path.mkdir(self.cfg.get("csvdir"))
        self.all_dirs.to_csv(
            Path(self.cfg.get("csvdir")) / self.cfg.get("csvname"),
            columns=["Name"],
        )

    def _read_all_dirs_from_file(self: object) -> None:
        csvfile = Path(self.cfg.get("csvdir")) / self.cfg.get("csvname")
        if Path.is_file(csvfile):
            self.all_dirs = pd.read_csv(csvfile)

    def _update_all_dirs(self: object) -> None:
        dirl = []
        excludes = self.cfg.get("exclude")
        for root, dirs, _ in os.walk(self.cfg.get("topdir")):
            dirs[:] = [
                d
                for d in dirs
                if not (d.startswith(".") or Path(root) / d in excludes)
            ]
            dirl.extend([
                Path(root) / directory for directory in dirs
            ])
        self.all_dirs = pd.DataFrame(columns=["Name"], data=dirl)
        self._write_all_dirs_to_file()

def main() -> None:
    """Start the application and wait for user input."""
    phynd = Phynd()
    phynd.mainloop()

if __name__ == "__main__":
    main()
