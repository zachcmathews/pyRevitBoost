import sys

from Autodesk.Revit.DB import Document, ElementTransformUtils, Arc, Line, XYZ
from Autodesk.Revit.UI import TaskDialog
from Autodesk.Revit import Exceptions

from pyrevit import script, forms
import rpw

__doc__ = "Rotate multiple elements about their origins."
__title__ = "Rotate\nMultiple"
__author__ = "Zachary Mathews"
__context__ = "Selection"

uidoc = rpw.revit.uidoc
doc = rpw.revit.doc

# Get user input
elements = [doc.GetElement(id) for id in uidoc.Selection.GetElementIds()]
if elements:
	try:
		center = uidoc.Selection.PickPoint("Pick center of rotation")
		start = uidoc.Selection.PickPoint("Pick starting point")
		end = uidoc.Selection.PickPoint("Pick end point")
	except:
		sys.exit()

angle = (start-center).AngleTo(end-center)
with rpw.db.Transaction("Rotate multiple elements"):
	cnt = 0
	max = len(elements)
	with forms.ProgressBar(title='{value} of {max_value}') as pb:
		for element in elements:
			origin = element.Location.Point
			a = XYZ(origin.X, origin.Y, 0)
			b = XYZ(origin.X, origin.Y, 10)
			axis = Line.CreateBound(a,b)

			ElementTransformUtils.RotateElement(doc, element.Id, axis, angle)
			cnt += 1
			pb.update_progress(cnt, max)
