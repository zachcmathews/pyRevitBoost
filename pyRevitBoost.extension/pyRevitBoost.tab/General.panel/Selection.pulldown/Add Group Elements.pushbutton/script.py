# pylint: disable=import-error
from Autodesk.Revit.DB import Group

import rpw

__doc__ = '''\
Adds the elements of currently selected groups to the selection.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)

    groups = [e for e in elements if type(e) is Group]
    group_elements = []
    for g in groups:
        group_elements.extend(g.GetMemberIds())

    selection.add(group_elements)


if __name__ == '__main__':
    main()
