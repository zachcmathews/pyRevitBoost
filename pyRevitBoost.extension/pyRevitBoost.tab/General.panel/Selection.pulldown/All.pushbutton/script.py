# pylint: disable=import-error
from Autodesk.Revit.DB import FilteredElementCollector

import rpw

__title__ = 'Select All'
__doc__ = 'Select all view-independent elements in project'
__author__ = 'Zachary Mathews'
    

def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc

    elements = FilteredElementCollector(doc).WhereElementIsViewIndependent().ToElements()
    selection = rpw.ui.Selection(uidoc=uidoc)
    selection.clear()
    selection.add(elements)


if __name__ == '__main__':
    main()
