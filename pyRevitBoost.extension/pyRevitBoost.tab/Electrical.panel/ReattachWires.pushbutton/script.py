# pylint: disable=import-error
import sys
from itertools import chain
from System.Collections.Generic import List

from Autodesk.Revit.DB import (ElementId, FamilyInstance,
                               FilteredElementCollector)
from Autodesk.Revit.DB.Electrical import Wire
from Autodesk.Revit.Exceptions import (ArgumentException,
                                       InvalidOperationException)

from pyrevit import forms
import rpw

from boostutils import get_electrical_connectors, is_inside_view, to_XY

__doc__ = '''\
Reattach wires that may have become disconnected due to rotation, \
copying, etc.
'''
__title__ = 'Reattach\nWires'
__author__ = 'Zachary Mathews'
__context__ = 'Wires'

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc
view = uidoc.ActiveView

# Get selected wires
if uidoc.Selection.GetElementIds():
    _wires = FilteredElementCollector(doc, uidoc.Selection.GetElementIds()) \
        .OfClass(Wire) \
        .ToElements()

# Filter wires that extend outside of view if cropped
wires = []
if view.CropBoxActive:
    for wire in _wires:
        if (
            is_inside_view(wire.GetVertex(0), view, include_z=False)
            and is_inside_view(wire.GetVertex(wire.NumberOfVertices-1), view, include_z=False)
        ):
            wires.append(wire)
else:
    wires = _wires

if not wires:
    forms.alert(
        msg='You must first select wires in the current view.',
        title='Error'
    )
    sys.exit()

# Get all connectors excluding wire connectors
all_wires = FilteredElementCollector(doc, uidoc.ActiveView.Id) \
    .OfClass(Wire) \
    .ToElementIds()
elements = FilteredElementCollector(doc, uidoc.ActiveView.Id) \
    .OfClass(FamilyInstance) \
    .Excluding(all_wires) \
    .ToElements()

connectors = []
for element in elements:
    connectors.extend(get_electrical_connectors(element))

cnt = 0
max = len(wires)
failed = []
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.Transaction('Reattach wires'):
        for wire in wires:
            start = to_XY(wire.GetVertex(0))
            end = to_XY(wire.GetVertex(wire.NumberOfVertices-1))

            closest_to_start = min(
                connectors,
                key=lambda c: c.Owner.Location.Point.DistanceTo(start)
            )
            closest_to_end = min(
                connectors,
                key=lambda c: c.Owner.Location.Point.DistanceTo(end)
            )
            try:
                wire.ConnectTo(closest_to_start, closest_to_end)
            except (ArgumentException, InvalidOperationException):
                failed.append(wire)

            cnt += 1
            pb.update_progress(cnt, max)

if failed:
    uidoc.Selection.SetElementIds(
        List[ElementId]([wire.Id for wire in failed])
    )
    forms.alert(
        title='Error',
        msg='Failed to connect {} wire{}.\n{} left selected.'
            .format(
                len(failed),
                's' if len(failed) > 1 else '',
                'They were' if len(failed) > 1 else 'It was',
            )
    )
