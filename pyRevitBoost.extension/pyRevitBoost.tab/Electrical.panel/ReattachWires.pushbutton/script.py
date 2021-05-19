# pylint: disable=import-error
from Autodesk.Revit.DB.Electrical import Wire
from Autodesk.Revit.Exceptions import (ArgumentException,
                                       InvalidOperationException)

from pyrevit import forms
import rpw

from boostutils import to_XY

__doc__ = '''\
Reattach wires that may have become disconnected due to rotation, \
copying, etc.
'''
__title__ = 'Reattach\nWires'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def has_electrical_connectors(element):
    return (
        hasattr(element, 'MEPModel')
        and element.MEPModel.ConnectorManager
        and not element.MEPModel.ConnectorManager.Connectors.IsEmpty
    )


def get_electrical_connectors(element):
    from Autodesk.Revit.DB import Domain
    return [
        c for c in element.MEPModel.ConnectorManager.Connectors
        if c.Domain == Domain.DomainElectrical
    ]


def is_inside_view(wire, view):
    from boostutils import is_inside_viewplan
    return (
        is_inside_viewplan(point=wire.GetVertex(0), view=view)
        and is_inside_viewplan(point=wire.GetVertex(1), view=view)
    )


if __name__ == '__main__':
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    view = uidoc.ActiveView
    selection = rpw.ui.Selection()

    # Filter wires that extend outside of view if cropped
    wires = set(
        el for el in selection.get_elements(wrapped=False)
        if type(el) == Wire
    )
    failed = []
    if view.CropBoxActive:
        for wire in wires.copy():
            if not is_inside_view(wire, view):
                wires.remove(wire)
                failed.append(wire)

    # Get all elements with connectors excluding wires
    elements = rpw.db.Collector(
        view=view,
        where=lambda e: type(e) != Wire and has_electrical_connectors(e)
    ).get_elements(wrapped=False)

    # Get all connectors
    connectors = []
    for element in elements:
        connectors.extend(get_electrical_connectors(element))

    cnt = 0
    max = len(wires)
    with forms.ProgressBar(title='{value} of {max_value}') as pb:
        with rpw.db.Transaction('Reattach wires'):
            for wire in wires:
                start = to_XY(wire.GetVertex(0))
                end = to_XY(wire.GetVertex(wire.NumberOfVertices-1))

                closest_to_start = min(
                    connectors,
                    key=lambda c: to_XY(c.Origin).DistanceTo(start)
                )
                closest_to_end = min(
                    connectors,
                    key=lambda c: to_XY(c.Origin).DistanceTo(end)
                )

                try:
                    wire.ConnectTo(closest_to_start, closest_to_end)
                except (ArgumentException, InvalidOperationException):
                    failed.append(wire)

                cnt += 1
                pb.update_progress(cnt, max)

    if failed:
        selection.clear()
        selection.add(failed)
        selection.update()
        forms.alert(
            title='Error',
            msg='Failed to connect {} wire{}.\n{} left selected.'
                .format(
                    len(failed),
                    's' if len(failed) > 1 else '',
                    'They were' if len(failed) > 1 else 'It was',
                )
        )
