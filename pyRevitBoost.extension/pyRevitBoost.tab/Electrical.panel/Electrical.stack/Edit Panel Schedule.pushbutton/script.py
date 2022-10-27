# pylint: disable=import-error
import sys

from Autodesk.Revit.DB import IndependentTag
from Autodesk.Revit.DB.Electrical import (
    ElectricalSystem,
    PanelScheduleView,
    Wire
)

from pyrevit import forms
import rpw

__doc__ = '''\
Edit panel schedule of selected circuits.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)

    panel_schedules = \
        rpw.db.Collector(
            of_class=PanelScheduleView)\
        .get_elements(wrapped=False)

    panel_schedule_lookup = dict((ps.GetPanel(), ps) for ps in panel_schedules)
    panels = set()
    for el in elements:
        if type(el) is ElectricalSystem:
            panels.add(el.BaseEquipment)
            continue

        if type(el) is IndependentTag:
            el = el.GetTaggedLocalElement()

        if type(el) is Wire:
            electrical_systems = [
                doc.GetElement(_id) for _id in el.GetMEPSystems()
            ]
            panels.update([es.BaseEquipment for es in electrical_systems])
            continue

        if not hasattr(el, 'MEPModel'):
            continue

        mep_model = el.MEPModel
        electrical_systems = mep_model.GetElectricalSystems()
        panels.update([es.BaseEquipment for es in electrical_systems])

    if not panels:
        sys.exit()

    for panel in sorted(panels, key=lambda p: p.Name):
        panel_schedule = panel_schedule_lookup.get(panel.Id)

        if not panel_schedule:
            forms.alert(
                'Could not open panel schedule for {}. '
                'Has it been created?'.format(panel.Name))
            continue

        uidoc.ActiveView = panel_schedule


if __name__ == '__main__':
    main()
