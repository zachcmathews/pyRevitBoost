import sys

import rpw
from Autodesk.Revit.DB import (
    ElementTransformUtils,
    Line,
    XYZ
)
from Autodesk.Revit.Exceptions import (
    InvalidOperationException,
    OperationCanceledException
)
from pyrevit import forms

__doc__ = "Rotate multiple elements about their origins."
__author__ = "Zachary Mathews"
__context__ = "Selection"

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc


def main():
    elements = [doc.GetElement(_id) for _id in uidoc.Selection.GetElementIds()]
    if elements:
        try:
            center = uidoc.Selection.PickPoint("Pick center of rotation")
            start = uidoc.Selection.PickPoint("Pick starting point")
            end = uidoc.Selection.PickPoint("Pick end point")
        except (InvalidOperationException, OperationCanceledException):
            sys.exit()

    v0 = (start - center).Normalize()
    v1 = (end - center).Normalize()
    angle = v0.AngleTo(v1)
    angle = angle * -1 if v0.CrossProduct(v1).Z < 0 else angle
    with rpw.db.Transaction("Rotate multiple elements", doc=doc):
        cnt = 0
        num_elements = len(elements)
        with forms.ProgressBar(title='{value} of {max_value}') as pb:
            for element in elements:
                origin = element.Location.Point
                a = XYZ(origin.X, origin.Y, 0)
                b = XYZ(origin.X, origin.Y, 10)
                axis = Line.CreateBound(a, b)

                ElementTransformUtils.RotateElement(
                    doc,
                    element.Id,
                    axis,
                    angle
                )
                cnt += 1
                pb.update_progress(cnt, num_elements)


if __name__ == '__main__':
    main()
