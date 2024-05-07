# pylint: disable=import-error
from System.Collections.Generic import List

from itertools import groupby
import math

from Autodesk.Revit.DB import (
    BuiltInParameter,
    CopyPasteOptions,
    ElementId,
    ElementTransformUtils,
    FamilyInstance,
    Group,
    Line,
    Options,
    Plane,
    SpatialElementBoundaryLocation,
    SpatialElementBoundaryOptions,
    Transform,
    XYZ,
)

import rpw
from pyrevit import forms
from boostutils import draw_circle

__doc__ = '''\
Copy selected element or group to similar spaces.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


class XyzSet():
    def __init__(self):
        self.points = []
        pass

    def __iter__(self):
        return self.points

    def __len__(self):
        return len(self.points)

    def __getitem__(self, idx):
        return self.points[idx]

    def add(self, new_point):
        for point in self.points:
            if new_point.IsAlmostEqualTo(point):
                break
        else:
            self.points.append(new_point)


def get_doors_in_boundary_segment_of_space(
    doc, phase, boundary_segment, space_number
):
    doors_in_boundary_segment_of_space = []

    # Find boundary-defining element in linked model or this model
    element_id = boundary_segment.ElementId
    link_element_id = boundary_segment.LinkElementId
    if link_element_id.IntegerValue != -1:
        link_instance = doc.GetElement(element_id)
        link_type = doc.GetElement(link_instance.GetTypeId())
        phase_map = link_type.GetPhaseMap()

        element_doc = link_instance.GetLinkDocument()
        element = element_doc.GetElement(link_element_id)
        element_phase = element_doc.GetElement(phase_map[phase.Id])
    else:
        element_doc = doc
        element = element_doc.GetElement(element_id)
        element_phase = phase

    # Add points for the doors
    wall_category = element_doc.Settings.Categories['Walls']
    if element and element.Category.Id == wall_category.Id:
        door_category = element_doc.Settings.Categories['Doors']
        doors = [
            element_doc.GetElement(eid)
            for eid in element.FindInserts(False, False, False, False)
            if (
                element_doc.GetElement(eid).Category.Id
                == door_category.Id
            )
        ]

        for d in doors:
            door_from_room = d.FromRoom[element_phase]
            if door_from_room:
                door_from_room_number = \
                    door_from_room.get_Parameter(
                        getattr(BuiltInParameter, 'ROOM_NUMBER')
                    ).AsString()
            else:
                door_from_room_number = None

            door_to_room = d.ToRoom[element_phase]
            if door_to_room:
                door_to_room_number = \
                    door_to_room.get_Parameter(
                        getattr(BuiltInParameter, 'ROOM_NUMBER')
                    ).AsString()
            else:
                door_to_room_number = None

            if (
                door_from_room_number == space_number
                or door_to_room_number == space_number
            ):
                doors_in_boundary_segment_of_space.append(d)

    return doors_in_boundary_segment_of_space


def get_space_descriptors(doc, phase, view, space):
    space_number = space.get_Parameter(
        getattr(BuiltInParameter, 'SPACE_ASSOC_ROOM_NUMBER')
    ).AsString()
    options = Options()
    options.View = view

    spatial_element_boundary_options = SpatialElementBoundaryOptions()
    spatial_element_boundary_options.SpatialElementBoundaryLocation = \
        SpatialElementBoundaryLocation.Finish
    boundary_segment_collections = \
        space.GetBoundarySegments(spatial_element_boundary_options)

    # We don't want to include the door points in the
    # calculation for centroid
    door_points = XyzSet()
    boundary_points = XyzSet()
    for collection in boundary_segment_collections:
        for boundary_segment in collection:
            curve = boundary_segment.GetCurve()
            p0 = curve.GetEndPoint(0)
            p1 = curve.GetEndPoint(1)

            # Add points on the perimeter
            boundary_points.add(p0)
            boundary_points.add(p1)

            # Add points for doors
            doors = \
                get_doors_in_boundary_segment_of_space(
                    doc, phase, boundary_segment, space_number)
            for d in doors:
                width = d.Symbol.get_Parameter(
                    getattr(BuiltInParameter, 'DOOR_WIDTH')).AsDouble()
                location = d.Location.Point
                tangent = d.GetTotalTransform().OfVector(XYZ(1, 0, 0))

                p0 = location + (width / 2) * tangent
                p1 = location - (width / 2) * tangent
                door_points.add(XYZ(p0.X, p0.Y, 0))
                door_points.add(XYZ(p1.X, p1.Y, 0))

    sum_A, sum_Cx, sum_Cy = 0, 0, 0
    last_iteration = len(boundary_points) - 1
    for i in range(len(boundary_points)):
        if i != last_iteration:
            shoelace = \
                boundary_points[i].X * boundary_points[i + 1].Y \
                - boundary_points[i + 1].X * boundary_points[i].Y

            sum_A += shoelace

            sum_Cx += (
                boundary_points[i].X + boundary_points[i + 1].X
            ) * shoelace

            sum_Cy += (
                boundary_points[i].Y + boundary_points[i + 1].Y
            ) * shoelace
        else:
            # N-1 case (last iteration): substitute i+1 -> 0
            shoelace = \
                boundary_points[i].X * boundary_points[0].Y \
                - boundary_points[0].X * boundary_points[i].Y

            sum_A += shoelace

            sum_Cx += (
                boundary_points[i].X + boundary_points[0].X
            ) * shoelace

            sum_Cy += (
                boundary_points[i].Y + boundary_points[0].Y
            ) * shoelace
    
    A = 0.5 * sum_A
    if A == 0:
        return None
    factor = 1 / (6.0 * A)

    Cx = factor * sum_Cx
    Cy = factor * sum_Cy
    centroid = XYZ(Cx, Cy, space.Level.Elevation)

    points = XyzSet()
    for point in door_points:
        points.add(point)
    for point in boundary_points:
        points.add(point)

    vectors = XyzSet()
    for point in points:
        vector = point - centroid
        vectors.add(vector)

    # Discard all the vectors that are within a foot of each
    # other, they're not distinct enough
    unique_vectors = []
    for length, vectors in groupby(
        vectors, key=lambda v: round(v.GetLength())
    ):
        vectors = list(vectors)
        if len(vectors) == 1:
            unique_vectors.append(vectors[0])

    return centroid, unique_vectors


def draw_space_descriptors(centroid, unique_vectors, view, doc):
    draw_circle(centroid, 0.25, view, doc)

    for vector in unique_vectors:
        line = Line.CreateBound(centroid, centroid + vector)
        doc.Create.NewDetailCurve(view, line)


def get_transforms_between_spaces(
    centroid_1, unique_vectors_1,
    centroid_2, unique_vectors_2,
    draw_descriptors=False
):
    uv1_iter = iter(unique_vectors_1)
    v1_0 = next(uv1_iter, None)
    v2_0 = None
    while v1_0 and not v2_0:
        v2_0 = [
            v for v in unique_vectors_2
            if abs(v.GetLength() - v1_0.GetLength()) < 5e-1
        ]
        if v2_0:
            break
        else:
            v1_0 = next(uv1_iter, None)
    else:
        return None

    v1_1 = next(uv1_iter, None)
    v2_1 = None
    while v1_1 and not v2_1:
        v2_1 = [
            v for v in unique_vectors_2
            if abs(v.GetLength() - v1_1.GetLength()) < 5e-1
        ]
        if v2_1:
            break
        else:
            v1_1 = next(uv1_iter, None)
    else:
        return None

    if not v1_0 or not v1_1 or not v2_0 or not v2_1:
        return None

    v2_0 = v2_0[0]
    v2_1 = v2_1[0]
    # if draw_descriptors:
    #     with rpw.db.Transaction("Debugging"):
    #         doc = rpw.revit.doc
    #         view = rpw.revit.uidoc.ActiveView
    #         draw_space_descriptors(centroid_2, [v2_0, v2_1], view, doc)

    # Determine rotation transformation
    v11_v10 = (v1_1 - v1_0).Normalize()
    v21_v20 = (v2_1 - v2_0).Normalize()
    multiplier = 1.0 if v11_v10.CrossProduct(v21_v20).Z > 0 else -1.0

    # Determine reflection transformation
    # If cross products are inverse, we need to reflect
    xp1 = v1_0.CrossProduct(v1_1).Normalize()
    xp2 = v2_0.CrossProduct(v2_1).Normalize()
    if xp1.IsAlmostEqualTo(-xp2):
        angle = (v11_v10).AngleTo(-v21_v20)
        rotation = Transform.CreateRotationAtPoint(
            XYZ.BasisZ,
            multiplier * angle,
            centroid_1
        )
        normal = v1_0 - rotation.OfVector(v2_0)
        plane = Plane.CreateByNormalAndOrigin(
            normal,
            centroid_1
        )
        reflection = Transform.CreateReflection(plane)
        rotation = Transform.CreateRotationAtPoint(
            XYZ.BasisZ,
            multiplier * -angle,
            centroid_1
        )
    else:
        angle = (v11_v10).AngleTo(v21_v20)
        rotation = Transform.CreateRotationAtPoint(
            XYZ.BasisZ,
            multiplier * angle,
            centroid_1
        )
        reflection = Transform.Identity

    translation = Transform.CreateTranslation(centroid_2 - centroid_1)
    return translation * rotation * reflection


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    view = uidoc.ActiveView
    phase = doc.GetElement(
        view
        .get_Parameter(getattr(BuiltInParameter, 'VIEW_PHASE'))
        .AsElementId()
    )

    spaces = rpw.db.Collector(of_category='OST_MEPSpaces')\
                .get_elements(wrapped=False)

    # Remove deleted spaces from the list
    spaces = [
        s for s in spaces
        if s.Area > 1e-9
    ]

    if not spaces:
        forms.alert('No spaces in model.', exitscript=True)

    selection = rpw.ui.Selection(uidoc=uidoc)
    elements = selection.get_elements(wrapped=False)
    el = elements[0]

    if type(el) is Group:
        location = el.Location.Point
        src_space = \
            next(
                space
                for space in spaces
                if space.IsPointInSpace(location)
            )
    elif type(el) is FamilyInstance:
        src_space = el.Space[phase]
    else:
        forms.alert('Cannot copy selected element.', exitscript=True)

    if not src_space:
        forms.alert(
            'Selected element is not enclosed in a space.',
            exitscript=True)

    # Remove src space from dst_spaces
    spaces = [
        s for s in spaces
        if s.Id != src_space.Id
    ]

    class SpaceMapping():
        def __init__(self, space, transform):
            self._name = (
                space.get_Parameter(
                    getattr(BuiltInParameter, 'ROOM_NAME')).AsString()
                + " "
                + space.get_Parameter(
                    getattr(BuiltInParameter, 'ROOM_NUMBER')).AsString()
            )
            self._space = space
            self._transform = transform

        @property
        def name(self):
            return self._name

        @property
        def space(self):
            return self._space

        @property
        def transform(self):
            return self._transform

    similar_spaces = []

    try:
        centroid, unique_vectors = \
            get_space_descriptors(doc, phase, view, src_space)
    except:
        forms.alert(
            'Space is not asymmetric enough to create a descriptive'
            'set of vectors for calculating transforms.',
            exitscript=True
        )

    for space in spaces:
        try:
            dst_centroid, dst_unique_vectors = \
                get_space_descriptors(doc, phase, view, space)
        except:
            continue
        transform = \
            get_transforms_between_spaces(
                centroid, unique_vectors,
                dst_centroid, dst_unique_vectors,
            )
        if transform:
            similar_spaces.append(SpaceMapping(space, transform))

    dst_spaces = forms.SelectFromList.show(
        sorted(similar_spaces, key=lambda s: s.name),
        title="Select spaces",
        multiselect=True
    )
    if not dst_spaces:
        return

    # Debugging
    # for space_mapping in dst_spaces:
    #     centroid_2, unique_vectors_2 = get_space_descriptors(doc, phase, view, space_mapping.space)
    #     get_transforms_between_spaces(
    #         centroid, unique_vectors,
    #         centroid_2, unique_vectors_2,
    #         draw_descriptors=True
    #     )

    copies = []
    with rpw.db.Transaction("Copy to similar spaces", doc=doc):
        # Copied elements must be in .NET collection
        elements = List[ElementId]()
        elements.Add(el.Id)

        options = CopyPasteOptions()
        for space_mapping in dst_spaces:
            copies.extend(ElementTransformUtils.CopyElements(
                doc,
                elements,
                doc,
                space_mapping.transform,
                options
            ))
    
    if copies:
        selection = rpw.ui.Selection(uidoc=uidoc)
        selection.clear()
        selection.add(copies)
            

if __name__ == '__main__':
    main()
