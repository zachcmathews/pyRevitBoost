# pylint: disable=import-error
import rpw
from Autodesk.Revit.DB import ExternalResourceLoadStatus, KeynoteTable 

from pyrevit import forms

__doc__ = 'Reload keynotes for the current document.'
__title__ = 'Reload Keynotes'
__author__ = 'Zachary Mathews'

if __name__ == '__main__':
    doc = rpw.revit.doc
    keynote_table = KeynoteTable.GetKeynoteTable(doc)

    with rpw.db.Transaction('Reload keynotes') as t:
        result = keynote_table.Reload(None)
        if not (
            ExternalResourceLoadStatus.Success == result
            or ExternalResourceLoadStatus.ResourceAlreadyCurrent == result
        ):
            forms.alert("Couldn't reload keynotes.")
