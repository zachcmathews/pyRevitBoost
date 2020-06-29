# pylint: disable=import-error
import math

from Autodesk.Revit.DB import (ElementTransformUtils, FamilyInstance, Line,
                               ViewPlan, XYZ)
from Autodesk.Revit.Exceptions import ArgumentException

import rpw
from pyrevit import forms

__doc__ = 'Align with view axes.'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'

if __name__ == '__main__':
    doc = rpw.doc
    uidoc = rpw.uidoc
    view = uidoc.ActiveView

    if not isinstance(view, ViewPlan):
        forms.alert(
            title='Error',
            msg='This command only works in plan views.',
            exitscript=True
        )

    selection = rpw.ui.Selection()
    elements = (
        e for e in selection.get_elements(wrapped=False)
        if isinstance(e, FamilyInstance)
    )

    failed = []
    with rpw.db.Transaction('Align with View'):
        for el in elements:
            rot_x = el.GetTotalTransform()\
                      .OfVector(XYZ.BasisX)\
                      .AngleOnPlaneTo(view.RightDirection, view.ViewDirection)
            rot_y = el.GetTotalTransform()\
                      .OfVector(XYZ.BasisX)\
                      .AngleOnPlaneTo(view.UpDirection, view.ViewDirection)
            rot_neg_x = el.GetTotalTransform()\
                          .OfVector(XYZ.BasisX)\
                          .AngleOnPlaneTo(
                              -view.RightDirection,
                              view.ViewDirection
                          )
            rot_neg_y = el.GetTotalTransform()\
                          .OfVector(XYZ.BasisX)\
                          .AngleOnPlaneTo(
                              -view.UpDirection,
                              view.ViewDirection
                          )

            while rot_x > math.pi:
                rot_x -= 2*math.pi
            while rot_y > math.pi:
                rot_y -= 2*math.pi
            while rot_neg_x > math.pi:
                rot_neg_x -= 2*math.pi
            while rot_neg_y > math.pi:
                rot_neg_y -= 2*math.pi

            rotation = min(
                [rot_x, rot_y, rot_neg_x, rot_neg_y],
                key=lambda r: abs(r)
            )
            z_axis = Line.CreateUnbound(el.Location.Point, view.ViewDirection)

            try:
                ElementTransformUtils.RotateElement(
                    doc,
                    el.Id,
                    z_axis,
                    rotation
                )
            except ArgumentException:
                failed.append(el.Id)

    if failed:
        selection.clear()
        selection.add(failed)
        selection.update()
        forms.alert(
            title='Failed to align with view',
            msg=('Failed to flip {} selected elements.'
                 .format(len(failed))),
            exitscript=True
        )
