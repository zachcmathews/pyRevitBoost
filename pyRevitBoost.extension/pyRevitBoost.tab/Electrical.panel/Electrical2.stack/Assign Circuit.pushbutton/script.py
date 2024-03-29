# pylint: disable=import-error
import re

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    ElementOnPhaseStatus,
    ElementSet,
    FamilyInstance,
    FilteredElementCollector,
    IndependentTag,
    Transaction,
    TransactionGroup,
)
from Autodesk.Revit.DB.Electrical import (
    ElectricalSystem,
    ElectricalSystemType,
    PanelScheduleView,
    Wire,
)

from pyrevit import forms
import rpw

__title__ = 'Assign\nCircuit'
__doc__ = '''\
Assign circuit to panel and breaker number.
Breaker number optional.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def main():
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    view = rpw.revit.active_view.unwrap()
    phase = \
        view.get_Parameter(BuiltInParameter.VIEW_PHASE).AsElementId()
    elements = rpw.ui.Selection(uidoc=uidoc).get_elements(wrapped=False)

    retry = True
    tg = None
    while retry:
        tg = TransactionGroup(doc)
        tg.Start('Assign circuit')

        # Check user selection
        # Circuit was selected
        if len(elements) == 1 and type(elements[0]) == ElectricalSystem:
            circuit = elements[0]
        # Tag was selected, grab its associated circuit
        elif len(elements) == 1 and type(elements[0]) == IndependentTag:
            wire = doc.GetElement(elements[0].TaggedLocalElementId)
            if not type(wire) == Wire:
                tg.RollBack()
                forms.alert(
                    title='Invalid tag',
                    msg='Selected tag is not associated with an '
                        'electrical system.',
                    cancel=True,
                    ok=False,
                    exitscript=True
                )
            circuits = wire.GetMEPSystems()
            if not circuits:
                tg.RollBack()
                forms.alert(
                    title='Invalid tag',
                    msg='Selected tag is not associated with an '
                        'electrical system.',
                    cancel=True,
                    ok=False,
                    exitscript=True
                )
            circuit = doc.GetElement(circuits[0])
            if not type(circuit) == ElectricalSystem:
                tg.RollBack()
                forms.alert(
                    title='Invalid tag',
                    msg='Selected tag is not associated with an '
                        'electrical system.',
                    cancel=True,
                    ok=False,
                    exitscript=True
                )
        # Wire was selected, grab its associated circuit
        elif len(elements) == 1 and type(elements[0]) == Wire:
            circuit = elements[0].MEPSystem
            if not circuit:
                forms.alert(
                    title='No connected electrical system',
                    msg='Wire has no electrical system attached.',
                    cancel=True,
                    ok=False,
                    exitscript=True
                )
        # Other elements were selected, we'll create an electrical system
        # and connect them all later
        else:
            # Remove wires from selection
            elements = [
                el for el in elements
                if hasattr(el, 'MEPModel') and el.MEPModel
            ]
            circuit = None
            for el in elements:
                if not el.MEPModel:
                    continue

                circuits = el.MEPModel.GetElectricalSystems()
                if not circuits:
                    continue

                for _circuit in circuits:
                    with rpw.db.Transaction(
                        'Assign circuit: remove element from existing circuit',
                        doc=doc
                    ):
                        elSet = ElementSet()
                        elSet.Insert(el)
                        _circuit.RemoveFromCircuit(elSet)

        # Get the user input
        desired_circuit = forms.ask_for_string(
            title='Assign Circuit',
            default='XX-1,3,5',
            prompt='Enter circuit or panel:'
        )
        if not desired_circuit:
            tg.RollBack()
            break

        # Check the user input
        match = \
            re.match(
                pattern='^(?P<panel_name>\w+)(-(?P<circuit_number>((\d+),?\ ?){1,3})?)?$',
                string=desired_circuit
            )
        if not match:
            tg.RollBack()
            retry = forms.alert(
                title='Invalid circuit format',
                msg='Input circuit format is invalid.',
                retry=True,
                cancel=True,
                ok=False,
                exitscript=True
            )
            continue

        panel_name = match.group('panel_name')
        desired_circuit_number = match.group('circuit_number')

        # Find the panel
        panels = [
            panel for panel in
            FilteredElementCollector(doc)
            .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
            .OfClass(FamilyInstance)
            .ToElements()
            if panel.Name == panel_name
            and (
                panel.GetPhaseStatus(phase) == ElementOnPhaseStatus.Existing
                or panel.GetPhaseStatus(phase) == ElementOnPhaseStatus.New
            )
        ]
        if not panels:
            panels = [
                panel for panel in
                FilteredElementCollector(doc)
                .OfCategory(BuiltInCategory.OST_ElectricalEquipment)
                .OfClass(FamilyInstance)
                .ToElements()
                if str(panel.Name).upper() == str(panel_name).upper()
            ]
        if not panels:
            tg.RollBack()
            retry = forms.alert(
                title='Panel does not exist',
                msg='Panel {} does not exist.'.format(panel_name),
                retry=True,
                cancel=True,
                ok=False,
                exitscript=True
            )
            continue
        if len(panels) > 1:
            tg.RollBack()
            forms.alert(
                title='Multiple panels with same name',
                msg='Multiple panels with name {} exist. '
                    'Unable to resolve.'.format(panel_name),
                cancel=True,
                ok=False,
                exitscript=True
            )
        panel = panels[0]

        # Find the panel schedule view
        try:
            [panel_schedule] = [
                schedule for schedule in
                FilteredElementCollector(doc)
                .OfClass(PanelScheduleView)
                .ToElements()
                if schedule.GetPanel() == panel.Id
            ]
        except ValueError:
            tg.RollBack()
            retry = forms.alert(
                title='Panel schedule does not exist',
                msg='You must create the panel schedule for panel {} '
                    'before running this command.'.format(panel_name),
                ok=False,
                cancel=True,
                exitscript=True
            )

        # Prepare the panel schedule slots to assign the circuit to
        if desired_circuit_number:
            desired_circuit_slots = \
                [int(n) for n in desired_circuit_number.split(',')]

            max_slots = (
                panel.get_Parameter(
                    BuiltInParameter.RBS_ELEC_NUMBER_OF_CIRCUITS)
                or panel.get_Parameter(
                    BuiltInParameter.RBS_ELEC_MAX_POLE_BREAKERS)
            ).AsInteger()

            if any(slot > max_slots for slot in desired_circuit_slots):
                tg.RollBack()
                retry = forms.alert(
                    title='Panel capacity exceeded',
                    msg='Desired circuit number {} exceeds number of '
                        'panelboard poles.'.format(desired_circuit_number),
                    retry=True,
                    cancel=True,
                    ok=False,
                    exitscript=True
                )
                continue

            for slot in desired_circuit_slots:
                rows, cols = panel_schedule.GetCellsBySlotNumber(slot)
                for row in rows:
                    for col in cols:
                        # Remove blocking circuit
                        blocking_circuit = \
                            panel_schedule.GetCircuitByCell(row, col)
                        if blocking_circuit:
                            with rpw.db.Transaction(
                                'Assign circuit: remove blocking circuit',
                                doc=doc
                            ):
                                blocking_circuit.DisconnectPanel()
                        # Remove blocking space
                        elif panel_schedule.IsSpace(row, col):
                            with rpw.db.Transaction(
                                'Assign circuit: remove blocking space',
                                doc=doc
                            ):
                                panel_schedule.RemoveSpace(row, col)
                        # Remove blocking spare
                        elif panel_schedule.IsSpare(row, col):
                            with rpw.db.Transaction(
                                'Assign circuit: remove blocking spare',
                                doc=doc
                            ):
                                panel_schedule.RemoveSpare(row, col)

        # Create the circuit if needed
        if not circuit:
            t = Transaction(doc)
            t.Start('Assign circuit: create circuit')
            try:
                circuit = ElectricalSystem.Create(
                    doc,
                    [el.Id for el in elements],
                    ElectricalSystemType.PowerCircuit
                )
                t.Commit()
            except:     # noqa: E722
                t.RollBack()
                tg.RollBack()
                forms.alert(
                    title='Error creating circuit',
                    msg='There was an error creating the circuit '
                        'automatically.\n\n'
                        'Try doing so manually, and then select the circuit '
                        'before running this command to assign the panel and '
                        'breaker #.',
                    cancel=False,
                    ok=False,
                    exitscript=True
                )

        # Assign the panel if needed
        if circuit.BaseEquipment != panel:
            t = Transaction(doc)
            t.Start('Assign circuit: select panel')
            try:
                circuit.SelectPanel(panel)
                t.Commit()
            except:     # noqa: E722
                t.RollBack()
                tg.RollBack()
                forms.alert(
                    title='Error connecting circuit to panel',
                    msg='There was an error connecting the circuit to the '
                        'selected panel.\n\n'
                        'If any of the selected elements\' connector '
                        'voltages or # of poles are set by an instance '
                        'parameter, the electrical system must be created '
                        'using the standard Revit method. Afterwards, you '
                        'can assign the panel and breaker # using this '
                        'command.',
                    cancel=False,
                    ok=False,
                    exitscript=True
                )

        # Move to the correct slots if needed
        if not desired_circuit_number:
            tg.Assimilate()
            break

        if circuit.StartSlot == desired_circuit_slots[0]:
            tg.Assimilate()
            break

        start_rows, start_cols = \
            panel_schedule.GetCellsBySlotNumber(circuit.StartSlot)
        end_rows, end_cols = \
            panel_schedule\
            .GetCellsBySlotNumber(desired_circuit_slots[0])

        if circuit.BaseEquipment != panel:
            t = Transaction(doc)
            t.Start('Assign circuit: move to correct slot')
            try:
                panel_schedule.MoveSlotTo(
                    start_rows[0],
                    start_cols[0],
                    end_rows[0],
                    end_cols[0]
                )
                t.Commit()
            except:     # noqa: E722
                t.RollBack()
                tg.RollBack()
                forms.alert(
                    title='Error moving circuit',
                    msg='There was an error moving the circuit to the correct '
                        'breaker number.\n\n'
                        'Perhaps the selected breaker is locked. Check the '
                        'panel schedule to see if you can move the circuit to '
                        'the desired breaker manually.',
                    cancel=False,
                    ok=False,
                    exitscript=True
                )

        tg.Assimilate()
        break


if __name__ == '__main__':
    main()
