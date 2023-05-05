# pylint: disable=import-error
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector
from Autodesk.Revit.DB.Electrical import ElectricalSystem

import rpw

__doc__ = '''\
Select all electrical systems.
'''
__author__ = 'Zachary Mathews'


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection(uidoc=uidoc)

    electrical_systems = \
        FilteredElementCollector(doc)\
        .OfCategory(BuiltInCategory.OST_ElectricalCircuit)\
        .OfClass(ElectricalSystem)\
        .ToElements()

    selection.add(electrical_systems)


if __name__ == '__main__':
    main()
