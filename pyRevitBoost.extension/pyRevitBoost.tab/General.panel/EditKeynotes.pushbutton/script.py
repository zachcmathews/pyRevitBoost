# pylint: disable=import-error
import sys
import os.path
import webbrowser

import rpw
from Autodesk.Revit.DB import KeynoteTable, ModelPathUtils

from pyrevit import forms

__doc__ = '''Collaborate on keynotes in real-time using the Atom text editor.
Requires teletype-revit-linker package.'''
__title__ = 'Edit\nKeynotes'
__author__ = 'Zachary Mathews'

doc = rpw.revit.doc

keynote_table = KeynoteTable.GetKeynoteTable(doc)
keynotes_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(
    keynote_table.GetExternalFileReference().GetAbsolutePath()
)

if not os.path.isfile(keynotes_path):
    forms.alert(
        title='Error',
        msg='Could not find keynotes file for the current model.\n\n\
Please be sure you have specified the appropriate file in \
\'Keynoting Settings\' under Annotate > Keynote.'
    )
    sys.exit()

lock_file = keynotes_path + '.lock'
uri = open(lock_file).read() \
    if os.path.isfile(lock_file) \
    else 'atom://teletype-revit-linker/new?file={}'.format(keynotes_path)

webbrowser.open(uri, autoraise=True)
