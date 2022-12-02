import os

from pyrevit import forms, script

script_config = script.get_config(section='pyRevitBoost.General.YankParameters')
if hasattr(script_config, 'config_file'):
    os.startfile(script_config.config_file)
else:
    forms.alert(
        title='Error: No config found',
        msg='No configuration file found. Have you assigned one?',
        ok=False,
        cancel=True,
        exitscript=True
    )
