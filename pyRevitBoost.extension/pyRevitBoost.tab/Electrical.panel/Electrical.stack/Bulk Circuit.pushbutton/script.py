# pylint: disable=import-error
import sys
from Autodesk.Revit.DB import (
    BuiltInParameter,
    Domain,
    Transaction,
    TransactionStatus
)
from Autodesk.Revit.DB.Electrical import ElectricalSystem

from pyrevit import forms
import rpw

__doc__ = '''\
Bulk circuit selected elements.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)
    equipments = \
        rpw.db.Collector(
            of_category='OST_ElectricalEquipment',
            of_class='FamilyInstance')\
        .get_elements(wrapped=False)

    existing_electrical_systems = set()
    connectors = set()
    for el in elements:
        if not hasattr(el, 'MEPModel'):
            continue

        mep_model = el.MEPModel
        if not mep_model.ConnectorManager:
            continue

        existing_electrical_systems.update(mep_model.GetElectricalSystems())
        connectors.update([
            c for c in mep_model.ConnectorManager.Connectors
            if c.Domain == Domain.DomainElectrical])

    if not connectors:
        sys.exit()

    system_types = \
        sorted(list(set(c.ElectricalSystemType for c in connectors)))
    if len(system_types) == 1:
        system_type = system_types.pop()
    else:
        system_type = \
            forms.SelectFromList.show(system_types, 'Select system type')

    if not system_type:
        sys.exit()

    connectors = [
        c for c in connectors
        if c.ElectricalSystemType == system_type
    ]

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
                compatible_equipment.append(EquipmentOption(e))
                break

    equipment = \
        forms.SelectFromList.show(
            sorted(compatible_equipment, key=lambda e: e.name),
            title='Select equipment')

    if not equipment:
        sys.exit()

    def _alert_and_exit():
        forms.alert('Could not circuit selected elements', exitscript=True)

    new_electrical_systems = []
    t = Transaction(doc)
    if t.Start('Bulk circuit') != TransactionStatus.Started:
        _alert_and_exit()

    for es in existing_electrical_systems:
        if es.SystemType == system_type:
            doc.Delete(es.Id)

    for c in connectors:
        new_electrical_systems.append(
            ElectricalSystem.Create(c, c.ElectricalSystemType))

    for es in new_electrical_systems:
        if es.BaseEquipment != equipment.equipment:
            es.SelectPanel(equipment.equipment)

    if t.Commit() != TransactionStatus.Committed:
        _alert_and_exit()


if __name__ == '__main__':
    main()
