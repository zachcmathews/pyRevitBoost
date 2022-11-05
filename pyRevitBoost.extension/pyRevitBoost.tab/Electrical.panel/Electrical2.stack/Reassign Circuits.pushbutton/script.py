# pylint: disable=import-error
import sys
from itertools import chain

from Autodesk.Revit.DB import (
    BuiltInParameter,
    DisplayUnitType,
    Domain,
    Transaction,
    TransactionGroup,
    TransactionStatus,
    UnitUtils,
)
from Autodesk.Revit.DB.Electrical import (
    ElectricalSystemType,
    PanelConfiguration,
    PanelScheduleView,
)

from pyrevit import forms
import rpw

__doc__ = '''\
Reassign circuits to other panel.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def is_distribution_system_compatible(system, v_lg, v_ll):
    compatible = True
    sys_v_lg = system.VoltageLineToGround
    sys_v_ll = system.VoltageLineToLine

    if v_lg:
        if not sys_v_lg:
            compatible = False
        elif v_lg < sys_v_lg.MinValue:
            compatible = False
        elif v_lg > sys_v_lg.MaxValue:
            compatible = False

    if v_ll:
        if not sys_v_ll:
            compatible = False
        elif v_ll < sys_v_ll.MinValue:
            compatible = False
        elif v_ll > sys_v_ll.MaxValue:
            compatible = False

    return compatible


def get_first_cell(schedule, slot):
    rows, cols = schedule.GetCellsBySlotNumber(slot)
    row = rows[0]
    col = cols[0]
    return row, col


def get_panel_info(schedule):
    data = schedule.GetTableData()
    num_slots = data.NumberOfSlots

    circuit_slots = []
    spare_slots = []
    space_slots = []
    empty_slots = []
    for slot in range(1, num_slots + 1):
        row, col = get_first_cell(schedule, slot)
        circuit = schedule.GetCircuitByCell(row, col)
        if schedule.IsSpare(row, col):
            spare_slots.append(slot)
        elif schedule.IsSpace(row, col):
            space_slots.append(slot)
        elif circuit:
            circuit_slots.append(slot)
        else:
            empty_slots.append(slot)

    def _consecutive(slots):
        groups = []
        group = []
        last_slot = None
        for slot in slots:
            if last_slot is None:
                group = [slot]
                last_slot = slot
            elif slot > last_slot + 2:
                groups.append(group)
                group = [slot]
                last_slot = slot
            else:
                group.append(slot)
                last_slot = slot

        if group:
            groups.append(group)

        return groups

    # Group empty slots according to configuration
    # such that consecutive poles are next to each other
    # (i.e. 1,3,5... then 9,11,13... for two columns, circuits across)
    configuration = data.PanelConfiguration
    if configuration == PanelConfiguration.TwoColumnsCircuitsAcross:
        odd = [i for i in empty_slots if i % 2]
        even = [i for i in empty_slots if i % 2 == 0]
        empty_slots = list(chain(_consecutive(odd), _consecutive(even)))
    # Group empty slots according to configuration
    # such that consecutive poles are next to each other
    # (i.e. 1..10 then 10..20 for two columns, circuits down)
    elif configuration == PanelConfiguration.TwoColumnsCircuitsDown:
        first_column = \
            [i for i in empty_slots if i <= data.GetNumberOfCircuitRows]
        second_column = \
            [i for i in empty_slots if i > data.GetNumberOfCircuitRows]
        empty_slots = \
            list(chain(_consecutive(first_column),
                       _consecutive(second_column)))

    return {
        'circuit_slots': circuit_slots,
        'spare_slots': spare_slots,
        'space_slots': space_slots,
        'empty_slots': sorted(empty_slots, key=len, reverse=True),
    }


def get_circuit_groups(schedule, circuits):
    groups = dict()
    for circuit in circuits:
        (rows, cols) = schedule.GetCellsBySlotNumber(circuit.StartSlot)
        nRow = rows[0]
        nCol = cols[0]

        group = schedule.IsSlotGrouped(nRow, nCol)
        if group not in groups:
            groups[group] = []

        groups[group].append(circuit)

    return groups.values()


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    distribution_systems = doc.Settings.ElectricalSetting.DistributionSysTypes
    equipments = \
        rpw.db.Collector(
            of_category='OST_ElectricalEquipment',
            of_class='FamilyInstance')\
        .get_elements(wrapped=False)

    schedule_lookup = dict(
        (psv.GetPanel(), psv)
        for psv in
        rpw.db.Collector(
            of_class=PanelScheduleView).get_elements(wrapped=False))

    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)
    circuits = \
        rpw.db.Collector(
            elements=elements,
            of_category='OST_ElectricalCircuit')\
        .get_elements(wrapped=False)

    if not circuits:
        forms.alert('No electrical systems selected.', exitscript=True)

    system_types = set([c.SystemType for c in circuits])
    if len(system_types) > 1:
        forms.alert(
            'You have selected more than one electrical system type',
            exitscript=True)
    system_type = system_types.pop()

    if system_type == ElectricalSystemType.PowerCircuit:
        v_lg = set(
            UnitUtils.ConvertFromInternalUnits(
                c.Voltage, DisplayUnitType.DUT_VOLTS)
            for c in circuits if c.PolesNumber == 1)
        v_ll = set(
            UnitUtils.ConvertFromInternalUnits(
                c.Voltage, DisplayUnitType.DUT_VOLTS)
            for c in circuits if c.PolesNumber > 1)
        if len(v_lg) > 1 or len(v_ll) > 1:
            forms.alert(
                'No distribution systems are compatible with all selected '
                'circuits.',
                exitscript=True)

        if v_lg:
            v_lg = v_lg.pop()
        if v_ll:
            v_ll = v_ll.pop()

        compatible_distribution_systems = [
            ds.Id for ds in distribution_systems
            if is_distribution_system_compatible(ds, v_lg, v_ll)]
        if not compatible_distribution_systems:
            forms.alert(
                'No distribution systems are compatible with all selected '
                'circuits.',
                exitscript=True
            )

    class EquipmentOption():
        def __init__(self, name, equipment):
            self._name = name
            self._equipment = equipment

        @property
        def name(self):
            return self._name

        @property
        def equipment(self):
            return self._equipment

    compatible_equipment = []
    for e in equipments:
        if system_type == ElectricalSystemType.PowerCircuit:
            distribution_system_param = \
                e.get_Parameter(
                    getattr(
                        BuiltInParameter,
                        'RBS_FAMILY_CONTENT_DISTRIBUTION_SYSTEM'))

            if not distribution_system_param:
                continue

            distribution_system = distribution_system_param.AsElementId()
            if distribution_system not in compatible_distribution_systems:
                continue

        cm = e.MEPModel.ConnectorManager
        if cm is None:
            continue

        for c in e.MEPModel.ConnectorManager.Connectors:
            if (
                c.Domain == Domain.DomainElectrical
                and c.ElectricalSystemType == system_type
            ):
                schedule = schedule_lookup.get(e.Id)

                if schedule:
                    name = schedule.Name
                else:
                    name = \
                        e.get_Parameter(
                            getattr(
                                BuiltInParameter,
                                'RBS_ELEC_PANEL_NAME'))\
                        .AsString()

                if not name:
                    continue

                eo = EquipmentOption(name, e)
                compatible_equipment.append(eo)
                break

    if not compatible_equipment:
        forms.alert('No equipment is compatible with all selected circuits.',
                    exitscript=True)

    selected = \
        forms.SelectFromList.show(
            sorted(compatible_equipment, key=lambda e: e.name),
            title='Select equipment')

    if not selected:
        sys.exit()

    equipment = selected.equipment
    if equipment.Id not in schedule_lookup:
        forms.alert('Must create panel schedule before running this command.',
                    exitscript=True)

    schedule = schedule_lookup[equipment.Id]
    equipment_info = get_panel_info(schedule)

    circuits_by_equipment = dict()
    for c in circuits:
        _equipment = c.BaseEquipment
        equipment_id = _equipment.Id if _equipment else None
        if equipment_id not in circuits_by_equipment:
            circuits_by_equipment[equipment_id] = []

        circuits_by_equipment[equipment_id].append(c)

    circuit_groups = []
    for equipment_id, circuits in circuits_by_equipment.items():
        groups = get_circuit_groups(schedule_lookup[equipment_id], circuits)
        circuit_groups.extend(groups)
    circuit_groups.sort(key=len, reverse=True)

    def _alert_and_exit():
        forms.alert('Could not reassign selected circuits', exitscript=True)

    tg = TransactionGroup(doc)
    if tg.Start('Reassign circuits') != TransactionStatus.Started:
        _alert_and_exit()

    failed = []
    empty_slots = equipment_info['empty_slots']
    for group in circuit_groups:
        num_slots = sum(len(c.SlotIndex.split(',')) for c in group)
        if (num_slots > len(empty_slots[0])):
            failed.extend(group)
            continue

        group.sort(key=lambda c: c.StartSlot)

        t = Transaction(doc)
        if t.Start('Reassign circuits') != TransactionStatus.Started:
            _alert_and_exit()

        for circuit in sorted(group):
            if circuit.BaseEquipment != equipment:
                circuit.SelectPanel(equipment)

        if t.Commit() != TransactionStatus.Committed:
            tg.Rollback()
            _alert_and_exit()

        t = Transaction(doc)
        if t.Start('Move circuits') != TransactionStatus.Started:
            _alert_and_exit()

        for circuit in group:
            if circuit in failed:
                continue

            from_row, from_col = get_first_cell(schedule, circuit.StartSlot)
            to_row, to_col = \
                get_first_cell(schedule, empty_slots[0][0])

            if not (to_row == from_row and to_col == from_col):
                schedule.MoveSlotTo(from_row, from_col, to_row, to_col)

            empty_slots[0].pop(0)
            if not empty_slots[0]:
                empty_slots.pop(0)

        if t.Commit() != TransactionStatus.Committed:
            tg.Rollback()
            _alert_and_exit()

        # Resort the empty slots list after using up slots
        empty_slots.sort(key=len, reverse=True)

    if tg.Assimilate() != TransactionStatus.Committed:
        _alert_and_exit()

    if failed:
        selection.clear()
        selection.add(failed)
        _alert_and_exit()


if __name__ == '__main__':
    main()
