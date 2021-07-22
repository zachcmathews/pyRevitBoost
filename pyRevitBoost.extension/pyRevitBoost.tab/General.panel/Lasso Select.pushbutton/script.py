# pylint: disable=import-error
import clr
clr.AddReference('PresentationCore')

import sys
import math

from System.Windows.Media import PointCollection, PolyBezierSegment
from System.Windows.Input import MouseButtonState

from Autodesk.Revit.DB import (BoundingBoxIntersectsFilter,
                               ElementId,
                               FilteredElementCollector,
                               IndependentTag,
                               LocationCurve,
                               LocationPoint,
                               Outline,
                               TextNote,
                               XYZ)
from Autodesk.Revit.UI import SelectionUIOptions

import rpw 
from pyrevit import forms, script

__doc__ = 'Lasso select elements'
__title__ = 'Lasso Select'
__author__ = 'Zachary Mathews'


class Form(forms.WPFWindow):
    """
    Draws the window and curve and keeps track of the user's movement through\
    a series of window coordinates to be returned to the caller.
    """
    def __init__(self, top, left, bottom, right):
        forms.WPFWindow.__init__(self, 'form.xaml')
        self.Top = top
        self.Left = left
        self.Height = bottom - top
        self.Width = right - left

        self._canvas = self.FindName('canvas')
        self._pathFigure = self.FindName('pathFigure')
        self._pathSegmentsCollection = self.FindName('pathSegments')
        self._polyBezierSegment = None

        self._mouseDown = False
        self._pathPts = []

    def _drawPath(self):
        if len(self._pathPts) >= 4:
            if self._polyBezierSegment is None:
                self._polyBezierSegment = PolyBezierSegment()
                self._pathSegmentsCollection.Add(self._polyBezierSegment)

            # We need the number of points to be evenly divisible by 3
            pts = PointCollection()
            lastIndex = ((len(self._pathPts) - 1) // 3) * 3
            for pt in self._pathPts[1:lastIndex + 1]:
                pts.Add(pt)

            # End with the start point
            pts.Add(self._pathPts[0])
            pts.Add(self._pathPts[0])
            pts.Add(self._pathPts[0])

            self._polyBezierSegment.Points = pts

    def onMouseDown(self, sender, e):
        self._mouseDown = True
        pt = e.GetPosition(self)
        self._pathFigure.StartPoint = pt
        self._pathPts.append(pt)

    def onMouseMove(self, sender, e):
        if self._mouseDown:
            self._pathPts.append(e.GetPosition(self))
            self._drawPath()

            # The MouseUp handler won't work if the user
            # releases when they're not above our window
            if (e.LeftButton != MouseButtonState.Pressed):
                self.Close()

    def onMouseUp(self, sender, e):
        self.Close()

    def show(self):
        self.ShowDialog()

        if self._pathPts:
            self._pathPts.append(self._pathPts[0])

        return self._pathPts


def windowCoordsToModelCoords(pt, windowRect, viewCorners, viewRight, viewUp):
    """
    Convert the given window coordinates into model coordinates.

    Arguments:
        pt (`System.Windows.Point`) : The window coordinates to convert to\
            model coordinates.
        windowRect (`Autodesk.Revit.DB.Rectangle`) : The Rectangle containing\
            the coordinates of the view's drawing area in screen coordinates.
        viewCorners (`IList<Autodesk.Revit.DB.XYZ>`) : Two corners of the\
            view's rectangle in model coordinates.
        viewRight (`Autodesk.Revit.DB.XYZ`) : The unit vector towards the\
            right side of the screen in model space.
        viewUp (`Autodesk.Revit.DB.XYZ`) : The unit vector towards the top of\
            the screen in model space.

    Returns:
        modelPt (`Autodesk.Revit.DB.XYZ`) : The model coordinates\
            corresponding to the given window coordinates.
    """
    windowWidth = windowRect.Right - windowRect.Left
    windowHeight = windowRect.Bottom - windowRect.Top

    viewWidth = abs((viewCorners[1] - viewCorners[0]).DotProduct(viewRight))
    viewHeight = abs((viewCorners[1] - viewCorners[0]).DotProduct(viewUp))

    fracLeft = pt.X / windowWidth
    fracTop = pt.Y / windowHeight

    vectFromLeft = fracLeft * viewWidth * viewRight
    vectFromTop = fracTop * viewHeight * -viewUp

    # Get the view's edges since I'm not sure if the corners will always be
    # bottom left and top right
    viewLeft = min(
        viewCorners[0].DotProduct(viewRight),
        viewCorners[1].DotProduct(viewRight)
    ) * viewRight
    viewTop = max(
        viewCorners[0].DotProduct(viewUp),
        viewCorners[1].DotProduct(viewUp)
    ) * viewUp

    return (viewLeft + vectFromLeft) + (viewTop + vectFromTop)


def isPointInCurve(pt, curvePts, viewRight, viewUp, minRotations=0.50):
    """
    Determine if a model point is inside of a curve.

    Arguments:
        pt (`Autodesk.Revit.DB.XYZ`) : The model coordinates to test.
        curvePts (`list<Autodesk.Revit.DB.XYZ>`) : The model coordinates of\
            points defining the curve.
        minRotations (`Number`) : The minimum number of revolutions the curve\
            must make around the point to pass.

    Returns:
        isPointInCurve (`Boolean`) : True if the curve performs at least\
            minRotations around the point. Otherwise, False.

    Notes:
        Uses the curve's winding number around a point to determine if it\
            is enclosed.
    """
    dThetas = []
    prevX = (curvePts[0] - pt).DotProduct(viewRight)
    prevY = (curvePts[0] - pt).DotProduct(viewUp)
    for cPt in curvePts[1:]:
        # Project the vector from the pt to the curve onto the viewing plane
        v = cPt - pt
        x = v.DotProduct(viewRight)
        y = v.DotProduct(viewUp)

        dx = x - prevX
        dy = y - prevY
        dThetas.append(
            ((x * dy) - (y * dx)) / (x**2 + y**2)
        )

        prevX = x
        prevY = y

    winding_num = sum(dThetas) / (2 * math.pi)
    return abs(winding_num) > minRotations


if __name__ == '__main__':
    doc = rpw.revit.doc
    uiapp = rpw.revit.uiapp
    uidoc = rpw.revit.uidoc

    # Require acknowledgement that lasso select does not work in activated
    # viewports on sheets
    config = script.get_config()
    acknowledged = config.get_option('ack', False)
    if not acknowledged:
        op = forms.alert('Lasso select does not work in activated viewports '
                         'on sheets.',
                         warn_icon=True,
                         options=["Acknowledge", "Cancel"])

        if op == 'Acknowledge':
            config.ack = True
            script.save_config()
        else:
            sys.exit()

    # Get active UIView
    activeView = rpw.revit.active_view
    openUIViews = uidoc.GetOpenUIViews()
    try:
        [activeUIView] = [
            uiView for uiView
            in openUIViews
            if uiView.ViewId == activeView.Id
        ]
    except ValueError:
        forms.alert('Lasso select does not work when a view is active in both '
                    'a viewport on a sheet and its own view. Please '
                    'deactivate the viewport on the sheet and try again!',
                    exitscript=True)

    # Clear selection
    selection = rpw.ui.Selection(uidoc=uidoc)
    selection.clear()

    # Draw lasso
    windowRect = activeUIView.GetWindowRectangle()
    screenPts = Form(windowRect.Top,
                     windowRect.Left,
                     windowRect.Bottom,
                     windowRect.Right).show()
    if not screenPts:
        sys.exit()

    # Convert screen coordinates to model coordinates
    viewDir = activeView.ViewDirection
    viewRight = activeView.RightDirection
    viewUp = activeView.UpDirection
    viewCorners = activeUIView.GetZoomCorners()

    modelPts = [
        windowCoordsToModelCoords(
            pt, windowRect,
            viewCorners, viewRight, viewUp
        ) for pt in screenPts
    ]

    # Construct bounding box for preliminary filtering
    outline = Outline(modelPts[0], modelPts[0])
    for pt in modelPts[1:]:
        outline.AddPoint(pt)

    # Grow bounding box to ~ +/-infinity in view direction
    if viewDir.DotProduct(XYZ(1, 1, 1)) < 0:
        outline.MinimumPoint += 1e10 * viewDir
        outline.MaximumPoint += -1e10 * viewDir
    else:
        outline.MinimumPoint += -1e10 * viewDir
        outline.MaximumPoint += 1e10 * viewDir

    # Get all model elements within the bounding box for further testing
    isInsideFilter = BoundingBoxIntersectsFilter(outline)
    modelElements = \
        FilteredElementCollector(doc, activeView.Id)\
        .WherePasses(isInsideFilter)\
        .ToElements()

    # Get all annotation elements within the view for further testing
    # Annotation elements are owned by the parent of dependent views
    parentId = activeView.GetPrimaryViewId()
    if parentId != ElementId.InvalidElementId:
        annotationElements = \
            FilteredElementCollector(doc, activeView.Id)\
            .OwnedByView(parentId)\
            .ToElements()
    else:
        annotationElements = \
            FilteredElementCollector(doc, activeView.Id)\
            .OwnedByView(activeView.Id)\
            .ToElements()

    # Exclude pinned elements if select pinned elements is off
    elements = list(modelElements)
    elements.extend(annotationElements)
    if not SelectionUIOptions.GetSelectionUIOptions().SelectPinned:
        elements = [
            el for el in elements
            if not SelectionUIOptions.ElementSelectsAsPinned(doc, el)
        ]

    # We have to check two points for curve based elements,
    # so we separate them from the point based elements.
    curveBasedElements = [
        el for el in elements
        if type(el.Location) == LocationCurve
        and el.Location.Curve.IsBound
    ]
    pointBasedElements = [
        el for el in elements
        if type(el.Location) == LocationPoint
    ]

    # IndependentTag (tags, keynotes, etc) and TextNotes store
    # their location in a different property
    independentTagElements = [
        el for el in elements
        if type(el) == IndependentTag
    ]
    textNoteElements = [
        el for el in elements
        if type(el) == TextNote
    ]

    # Now check if inside of curve using winding number algorithm
    curveBasedElements = [
        el for el in curveBasedElements
        if isPointInCurve(pt=el.Location.Curve.GetEndPoint(0),
                          viewRight=viewRight,
                          viewUp=viewUp,
                          curvePts=modelPts)
        and isPointInCurve(pt=el.Location.Curve.GetEndPoint(1),
                           viewRight=viewRight,
                           viewUp=viewUp,
                           curvePts=modelPts)
    ]
    pointBasedElements = [
        el for el in pointBasedElements
        if isPointInCurve(pt=el.Location.Point,
                          viewRight=viewRight,
                          viewUp=viewUp,
                          curvePts=modelPts)
    ]
    independentTagElements = [
        el for el in independentTagElements
        if isPointInCurve(pt=el.TagHeadPosition,
                          viewRight=viewRight,
                          viewUp=viewUp,
                          curvePts=modelPts)
    ]
    textNoteElements = [
        el for el in textNoteElements
        if isPointInCurve(pt=el.Coord,
                          viewRight=viewRight,
                          viewUp=viewUp,
                          curvePts=modelPts)
    ]

    selection.add(curveBasedElements)
    selection.add(pointBasedElements)
    selection.add(independentTagElements)
    selection.add(textNoteElements)
    selection.update()
