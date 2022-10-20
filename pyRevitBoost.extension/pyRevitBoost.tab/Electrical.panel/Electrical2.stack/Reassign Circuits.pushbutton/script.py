# pylint: disable=import-error
import sys
from Autodesk.Revit.DB import (
    BuiltInParameter,
    Domain,
    Transaction,
    TransactionStatus
)

from pyrevit import forms
import rpw

__doc__ = '''\
Reassign circuits to other panel.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    equipments = \
        rpw.db.Collector(
            of_category='OST_ElectricalEquipment',
            of_class='FamilyInstance')\
        .get_elements(wrapped=False)

    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)
    electrical_systems = \
        rpw.db.Collector(
            elements=elements,
            of_category='OST_ElectricalCircuit')\
        .get_elements(wrapped=False)

    if not electrical_systems:
        forms.alert('No electrical systems selected.', exitscript=True)

    system_types = list(set([es.SystemType for es in electrical_systems]))
    if len(system_types) > 1:
        forms.alert(
            'You have selected more than one electrical system type',
            exitscript=True)

    system_type = system_types[0]

    class EquipmentOption():
        def __init__(self, equipment):
            self._equipment = equipment
            self._name = \
                equipment\
                .get_Parameter(
                    getattr(BuiltInParameter, 'RBS_ELEC_PANEL_NAME'))\
                .AsString()

        @property
        def name(self):
            return self._name

        @property
        def equipment(self):
            return self._equipment

    compatible_equipment = []
    for e in equipments:
        cm = e.MEPModel.ConnectorManager
        if cm is None:
            continue

        for c in e.MEPModel.ConnectorManager.Connectors:
            if (
                c.Domain == Domain.DomainElectrical
                and c.ElectricalSystemType == system_type
            ):
                eo = EquipmentOption(e)
                if eo.name:
                    compatible_equipment.append(eo)
                break

    equipment = \
        forms.SelectFromList.show(
            sorted(compatible_equipment, key=lambda e: e.name),
            title='Select equipment')

    if not equipment:
        sys.exit()

    def _alert_and_exit():
        forms.alert('Could not reassign selected circuits', exitscript=True)

    t = Transaction(doc)
    if t.Start('Reassign circuits') != TransactionStatus.Started:
        _alert_and_exit()

    failed = []
    for es in electrical_systems:
        try:
            if es.BaseEquipment != equipment.equipment:
                es.SelectPanel(equipment.equipment)
        except:
            failed.append(es)

    if t.Commit() != TransactionStatus.Committed:
        _alert_and_exit()

    if failed:
        selection.clear()
        selection.add(failed)
        _alert_and_exit()


if __name__ == '__main__':
    main()
