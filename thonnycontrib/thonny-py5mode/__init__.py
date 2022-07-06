'''thonny-py5mode frontend
   interacts with py5mode backend (backend > py5_imported_mode_backend.py)
'''

import builtins
import keyword
import os
import pathlib
import py5_tools
import shutil
import site
import tkinter as tk
import webbrowser
from .about_plugin import add_about_py5mode_command, open_about_plugin
from .install_jdk import install_jdk
from distutils.sysconfig import get_python_lib
from importlib import util
from thonny import editors, get_workbench, running, token_utils
from thonny.common import BackendEvent
from thonny.languages import tr
from thonny.running import Runner
from thonny.shell import BaseShellText
from tkinter import colorchooser
from tkinter.messagebox import showinfo
try:  # thonny 4 package layout
    from thonny import get_sys_path_directory_containg_plugins
except ImportError:  # thonny 3 package layout
    pass


_PY5_IMPORTED_MODE = 'run.py5_imported_mode'


def apply_recommended_py5_config() -> None:
    '''apply some recommended settings for thonny py5 work'''
    get_workbench().set_option('view.ui_theme', 'Kyanite UI')
    get_workbench().set_option('view.syntax_theme', 'Kyanite Syntax')
    get_workbench().set_option('view.highlight_current_line', 'True')
    get_workbench().set_option('view.locals_highlighting', 'True')
    get_workbench().set_option('assistance.open_assistant_on_errors', 'False')
    get_workbench().set_option('view.assistantview', False)
    get_workbench().hide_view('AssistantView')
    get_workbench().reload_themes()


def execute_imported_mode() -> None:
    '''run imported mode script using py5_tools run_sketch'''
    current_editor = get_workbench().get_editor_notebook().get_current_editor()
    current_file = current_editor.get_filename()

    if current_file is None:
        # thonny must 'save as' any new files, before it can run them
        editors.Editor.save_file(current_editor)
        current_file = current_editor.get_filename()

    if current_file and current_file.split('.')[-1] in ('py', 'py5', 'pyde'):
        # save and run py5 imported mode
        current_editor.save_file()
        user_packages = str(site.getusersitepackages())
        site_packages = str(site.getsitepackages()[0])
        plug_packages = util.find_spec('py5_tools').submodule_search_locations
        run_sketch_locations = [
          pathlib.Path(user_packages + '/py5_tools/tools/run_sketch.py'),
          pathlib.Path(site_packages + '/py5_tools/tools/run_sketch.py'),
          pathlib.Path(plug_packages[0] + '/tools/run_sketch.py'),
          pathlib.Path(get_python_lib() + '/py5_tools/tools/run_sketch.py')
        ]

        for location in run_sketch_locations:
            # if location matches py5_tools path, use it
            if location.is_file():
                run_sketch = location
                break

        # if display window location unspecified, set it to (50, 50)
        if get_workbench().get_option('run.py5_location') is None:
            get_workbench().set_option('run.py5_location', '50,50')
        # retrieve last display window location
        py5_loc = get_workbench().get_option('run.py5_location')
        py5_loc = ','.join(map(str, py5_loc))
        py5_switches = '--py5_options external location=' + py5_loc

        # run command to execute sketch
        working_directory = os.path.dirname(current_file)
        cd_cmd_line = running.construct_cd_command(working_directory) + '\n'
        exe_cmd_line = ['%Run', str(run_sketch), current_file, py5_switches]
        exe_cmd_line = ' '.join(exe_cmd_line) + '\n'
        running.get_shell().submit_magic_command(cd_cmd_line + exe_cmd_line)


def patched_execute_current(self: Runner, command_name: str) -> None:
    '''override run button behavior for py5 imported mode'''
    execute_imported_mode()


def patch_token_coloring() -> None:
    '''add py5 keywords to syntax highlighting'''
    py5_dir_str = py5_tools.reference.PY5_DIR_STR
    patched_builtinlist = token_utils._builtinlist + py5_dir_str
    matches = token_utils.matches_any('builtin', patched_builtinlist)
    patched_BUILTIN = r'([^.\'"\\#]\b|^)' + (matches + r'\b')
    token_utils.BUILTIN = patched_BUILTIN


def set_py5_imported_mode() -> None:
    '''set imported mode variable in thonny configuration.ini file'''
    if get_workbench().in_simple_mode():
        os.environ['PY5_IMPORTED_MODE'] = 'auto'
    else:
        p_i_m = str(get_workbench().get_option(_PY5_IMPORTED_MODE))
        os.environ['PY5_IMPORTED_MODE'] = p_i_m

        # switch on/off py5 run button behavior
        if get_workbench().get_option(_PY5_IMPORTED_MODE):
            Runner._original_execute_current = Runner.execute_current
            Runner.execute_current = patched_execute_current
        else:
            try:
                Runner.execute_current = Runner._original_execute_current
            except Exception:
                pass


def toggle_py5_imported_mode() -> None:
    '''toggle py5 imported mode settings'''
    var = get_workbench().get_variable(_PY5_IMPORTED_MODE)
    var.set(not var.get())
    install_jdk()
    set_py5_imported_mode()


def color_selector():
    '''open tkinter color selector'''
    colors = colorchooser.askcolor(title='Color Selector')
    print(colors[1])


def convert_code(translator) -> None:
    '''function to handle different py5_tools conversions'''
    workbench = get_workbench()
    current_editor = workbench.get_editor_notebook().get_current_editor()
    current_file = current_editor.get_filename()

    if current_file is None:
        # save unsaved file before attempting to convert it
        editors.Editor.save_file(current_editor)
        current_file = current_editor.get_filename()

    if current_file and current_file.split('.')[-1] in ('py', 'py5', 'pyde'):
        # save and run perform conversion
        current_editor.save_file()
        translator.translate_file(current_file, current_file)
        current_editor._load_file(current_file, keep_undo=True)
        showinfo('py5 Conversion', 'Conversion complete', master=workbench)


def patched_handle_program_output(self, msg: BackendEvent) -> None:
    '''catch display window movements and write coords to the config file'''
    if msg.__getitem__('data')[:8] == '__MOVE__':
        py5_loc = msg.__getitem__('data')[9:-1].split(' ')
        # write display window location to config file
        if len(py5_loc) == 2:
            py5_loc = py5_loc[0] + ',' + py5_loc[1]
            get_workbench().set_option('run.py5_location', py5_loc)
        # skip the rest of the function so the shell won't display coords
        return

    # print the rest of the shell output as usual
    BaseShellText._original_handle_program_output(self, msg)


conversion_tools_menu = tk.Menu(tearoff=0)
# items for the menu: py5 > Conversion tools
conversion_tools_menu.add_command(
  label='Processing.py → py5 imported mode',
  command=lambda: convert_code(py5_tools.translators.processingpy2imported))
conversion_tools_menu.add_command(
  label='py5 module mode → imported mode',
  command=lambda: convert_code(py5_tools.translators.imported2module))
conversion_tools_menu.add_command(
  label='py5 imported mode → module mode',
  command=lambda: convert_code(py5_tools.translators.module2imported))


def load_plugin() -> None:
    get_workbench().set_default(_PY5_IMPORTED_MODE, False)
    get_workbench().add_command(
      'toggle_py5_imported_mode',
      'py5',
      tr('Imported mode for py5'),
      toggle_py5_imported_mode,
      flag_name=_PY5_IMPORTED_MODE,
      group=10,
    )
    get_workbench().add_command(
      'apply_recommended_py5_config',
      'py5',
      tr('Apply recommended py5 settings'),
      apply_recommended_py5_config,
      group=20,
    )
    get_workbench().add_command(
      'py5_color_selector',
      'py5',
      tr('Color selector'),
      color_selector,
      group=30,
    )
    get_workbench().add_command(
      'py5_reference',
      'py5',
      tr('py5 reference'),
      lambda: webbrowser.open('https://py5.ixora.io/reference/sketch.html'),
      group=30,
    )
    git_raw_user = 'https://raw.githubusercontent.com/tabreturn/'
    git_asset_path = 'processing.py-cheat-sheet/master/py5/py5_cc.pdf'
    get_workbench().add_command(
      'py5_cheatsheet',
      'py5',
      tr('py5 cheatsheet'),
      lambda: webbrowser.open(git_raw_user + git_asset_path),
      group=30,
    )
    get_workbench().add_command(
      'conversion_tools',
      'py5',
      tr('Conversion helpers'),
      submenu=conversion_tools_menu,
      group=40,
    )
    add_about_py5mode_command(40)
    patch_token_coloring()
    set_py5_imported_mode()

    # note that _handle_program_output is not a public api
    # may need to treat different thonny versions differently
    h_p_o = BaseShellText._handle_program_output
    BaseShellText._original_handle_program_output = h_p_o
    BaseShellText._handle_program_output = patched_handle_program_output
