# pylint: disable=import-error
import rpw

__doc__ = '''\
Adds the electrical systems of currently selected elements to the selection.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)

    electrical_systems = []
    for el in elements:
        if hasattr(el, 'MEPModel'):
            electrical_systems.extend(el.MEPModel.GetElectricalSystems())

    selection.add(electrical_systems)


if __name__ == '__main__':
    main()
